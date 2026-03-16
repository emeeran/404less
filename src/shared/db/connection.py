"""
Database Connection Module

@spec Shared infrastructure - database connection pooling

Provides async database connection management using SQLAlchemy async engine.
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.pool import NullPool, QueuePool

logger = logging.getLogger(__name__)

# Database URL from environment. Default to local SQLite for zero-config dev.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./sdd.db")
DB_REQUIRED = os.getenv("DB_REQUIRED", "false").lower() == "true"


def _is_production() -> bool:
    """Check if running in production environment."""
    return os.getenv("ENVIRONMENT", "development").lower() == "production"


def _get_pool_config() -> dict:
    """Get connection pool configuration based on environment."""
    if DATABASE_URL.startswith("sqlite"):
        # SQLite doesn't support connection pooling
        return {"poolclass": NullPool}

    if _is_production():
        # Production PostgreSQL: use QueuePool with configurable settings
        return {
            "poolclass": QueuePool,
            "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
            "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "30")),
            "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "3600")),
            "pool_pre_ping": True,  # Verify connections before use
        }
    else:
        # Development: simple pooling for PostgreSQL
        return {
            "poolclass": QueuePool,
            "pool_size": 5,
            "max_overflow": 10,
            "pool_pre_ping": True,
        }


# Engine configuration
engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    **_get_pool_config(),
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db() -> None:
    """
    Initialize database connection pool and ensure schema exists.

    Call this at application startup.
    """
    from src.shared.db.models import Base

    pool_config = _get_pool_config()
    pool_type = pool_config.get("poolclass", NullPool).__name__
    logger.info("Initializing database connection (pool type: %s)", pool_type)

    # Validate connection at startup. In local/dev environments, allow
    # startup without a database unless explicitly required.
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database connection established successfully")
    except Exception as exc:
        if DB_REQUIRED:
            logger.error("Database connection failed: %s", exc)
            raise
        logger.warning(
            "Database is unavailable at startup; continuing in degraded mode. "
            "Set DB_REQUIRED=true to fail fast. Error: %s",
            exc,
        )


async def close_db() -> None:
    """
    Close database connection pool.

    Call this at application shutdown.
    """
    await engine.dispose()


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database sessions.

    Usage:
        async with get_db_session() as session:
            result = await session.execute(query)
    """
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database sessions.

    Usage:
        @router.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with get_db_session() as session:
        yield session


@asynccontextmanager
async def get_background_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for background task database sessions.

    Provides isolated session management for background tasks like
    crawler callbacks. Each call creates a new session that is
    properly committed or rolled back.

    This is preferred over raw AsyncSessionLocal() usage because it
    ensures proper cleanup and error handling.

    Usage:
        async with get_background_session() as session:
            repo = ScanRepository(session)
            await repo.update_status(scan_id, "completed")
            # Auto-commits on success, rolls back on exception

    @spec FEAT-001 - Background session management
    """
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


def get_pool_status() -> dict:
    """
    Get current connection pool status.

    Returns pool statistics for monitoring and health checks.
    """
    pool = engine.pool

    if isinstance(pool, NullPool):
        return {
            "type": "NullPool",
            "connected": False,
            "message": "Connection pooling not enabled (SQLite or NullPool)",
        }

    return {
        "type": "QueuePool",
        "size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "invalid": pool.invalidatedcount() if hasattr(pool, "invalidatedcount") else 0,
    }


async def check_db_health() -> dict:
    """
    Check database connectivity and return health status.

    Used by health check endpoints to verify database is responsive.
    """
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            result.fetchone()

        pool_status = get_pool_status()
        pool_status["connected"] = True
        pool_status["latency_ms"] = None  # Could add timing if needed

        return pool_status
    except Exception as e:
        logger.error("Database health check failed: %s", e)
        return {
            "connected": False,
            "error": str(e),
            "type": "error",
        }
