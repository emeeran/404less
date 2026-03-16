"""
404less - Broken Link Scanner

Main application entry point.

@spec FEAT-001, FEAT-002, FEAT-003
"""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.exc import SQLAlchemyError

from src.shared.db.connection import init_db, close_db
from src.scanner.routes import router as scanner_router
from src.auth.registration.routes import router as registration_router
from src.auth.login.routes import router as login_router
from src.auth.password_reset.routes import router as password_reset_router


logger = logging.getLogger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


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

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)


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
    """Health check endpoint."""
    return {"status": "ok"}
