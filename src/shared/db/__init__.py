"""
Shared Database Module

Provides database connection pooling and repository base classes.
"""

from .connection import get_db, get_db_session, init_db, close_db, AsyncSessionLocal, engine
from .repository import BaseRepository
from .models import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin

__all__ = [
    "get_db",
    "get_db_session",
    "init_db",
    "close_db",
    "BaseRepository",
    "AsyncSessionLocal",
    "engine",
    "Base",
    "UUIDMixin",
    "TimestampMixin",
    "SoftDeleteMixin",
]
