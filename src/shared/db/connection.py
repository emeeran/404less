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
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)

# Database URL from environment. Default to local SQLite for zero-config dev.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./sdd.db")
DB_REQUIRED = os.getenv("DB_REQUIRED", "false").lower() == "true"

# Engine configuration
engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    poolclass=NullPool,  # For serverless/async contexts
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

    # Validate connection at startup. In local/dev environments, allow
    # startup without a database unless explicitly required.
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:
        if DB_REQUIRED:
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
