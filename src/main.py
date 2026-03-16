"""
404less - Broken Link Scanner

Main application entry point.

@spec FEAT-001, FEAT-002, FEAT-003
"""

from contextlib import asynccontextmanager
import logging
import time
from typing import Optional

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.exc import SQLAlchemyError

from src.shared.config import validate_config, ENVIRONMENT
from src.shared.logging_config import setup_logging
from src.shared.db.connection import init_db, close_db, check_db_health
from src.scanner.routes import router as scanner_router
from src.auth.registration.routes import router as registration_router
from src.auth.login.routes import router as login_router
from src.auth.password_reset.routes import router as password_reset_router


logger = logging.getLogger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Application start time for uptime tracking
_app_start_time: float = time.time()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Add request ID to all requests for tracing.

    @spec Observability - Request tracing
    """

    async def dispatch(self, request: Request, call_next):
        import uuid

        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses.

    @spec Security hardening - HTTP security headers
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # XSS protection (legacy browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Content Security Policy
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "  # unsafe-inline for SPA
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "frame-ancestors 'none';"
        )

        # Permissions Policy (formerly Feature Policy)
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=()"
        )

        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    setup_logging()
    validate_config()
    await init_db()
    yield
    # Shutdown
    await close_db()


# Create application
app = FastAPI(
    title="404less",
    description="Broken Link Scanner - Find broken links before your users do",
    version="0.1.0",
    lifespan=lifespan,
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add middleware (order matters - last added is first executed)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(_: Request, __: SQLAlchemyError) -> JSONResponse:
    """Return JSON when database operations fail."""
    return JSONResponse(
        status_code=503,
        content={
            "detail": {
                "error": "database_unavailable",
                "message": "Database is unavailable. Start the database and retry.",
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Ensure unexpected failures still return JSON payloads."""
    logger.exception("Unhandled exception for %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "error": "internal_error",
                "message": "Internal server error",
            }
        },
    )


# Include routers
app.include_router(scanner_router)
app.include_router(registration_router)
app.include_router(login_router)
app.include_router(password_reset_router)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    """
    Serve the main SPA page.

    @spec FEAT-001/AC-008 - Minimalist UI renders quickly
    """
    return FileResponse("static/index.html")


@app.get("/health")
async def health():
    """
    Basic health check endpoint.

    Returns overall application health status.
    """
    db_health = await check_db_health()
    db_connected = db_health.get("connected", False)

    return {
        "status": "ok" if db_connected else "degraded",
        "environment": ENVIRONMENT,
        "database": "connected" if db_connected else "disconnected",
    }


@app.get("/health/ready")
async def health_ready():
    """
    Readiness probe for Kubernetes.

    Returns 200 only when the application is ready to accept traffic.
    Returns 503 if critical dependencies are unavailable.
    """
    db_health = await check_db_health()

    if not db_health.get("connected", False):
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "reason": "database_unavailable",
            },
        )

    return {"status": "ready"}


@app.get("/health/live")
async def health_live():
    """
    Liveness probe for Kubernetes.

    Returns 200 as long as the application process is running.
    Use this to detect deadlocks or hung processes.
    """
    return {"status": "alive", "uptime_seconds": int(time.time() - _app_start_time)}


@app.get("/health/db")
async def health_db():
    """
    Database health check endpoint.

    Returns detailed database connectivity and pool status.
    """
    db_health = await check_db_health()

    if not db_health.get("connected", False):
        return JSONResponse(
            status_code=503,
            content=db_health,
        )

    return db_health


@app.get("/metrics")
async def metrics():
    """
    Prometheus-compatible metrics endpoint.

    Returns metrics in Prometheus text format.
    """
    db_health = await check_db_health()
    uptime = int(time.time() - _app_start_time)

    lines = [
        "# HELP app_uptime_seconds Application uptime in seconds",
        "# TYPE app_uptime_seconds counter",
        f"app_uptime_seconds {uptime}",
        "",
        "# HELP app_info Application information",
        "# TYPE app_info gauge",
        f'app_info{{environment="{ENVIRONMENT}"}} 1',
        "",
        "# HELP db_connected Database connection status (1=connected, 0=disconnected)",
        "# TYPE db_connected gauge",
        f"db_connected {1 if db_health.get('connected') else 0}",
        "",
    ]

    # Add pool metrics if available
    if db_health.get("type") == "QueuePool":
        lines.extend([
            "# HELP db_pool_size Total connection pool size",
            "# TYPE db_pool_size gauge",
            f"db_pool_size {db_health.get('size', 0)}",
            "",
            "# HELP db_pool_checked_in Connections available in pool",
            "# TYPE db_pool_checked_in gauge",
            f"db_pool_checked_in {db_health.get('checked_in', 0)}",
            "",
            "# HELP db_pool_checked_out Connections currently in use",
            "# TYPE db_pool_checked_out gauge",
            f"db_pool_checked_out {db_health.get('checked_out', 0)}",
            "",
            "# HELP db_pool_overflow Current overflow count",
            "# TYPE db_pool_overflow gauge",
            f"db_pool_overflow {db_health.get('overflow', 0)}",
            "",
        ])

    return PlainTextResponse(
        content="\n".join(lines),
        media_type="text/plain; charset=utf-8",
    )
