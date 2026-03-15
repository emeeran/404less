"""
Base Repository Module

@spec Shared infrastructure - repository pattern for data access

Provides a base repository class with common CRUD operations.
"""

from typing import TypeVar, Generic, Type, Any, Optional, List
from uuid import UUID

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    """
    Base repository with common CRUD operations.

    Usage:
        class UserRepository(BaseRepository[User]):
            async def find_by_email(self, email: str) -> Optional[User]:
                ...
    """

    def __init__(self, model: Type[ModelType], session: AsyncSession):
        """
        Initialize repository.

        Args:
            model: SQLAlchemy model class
            session: Async database session
        """
        self.model = model
        self.session = session

    async def create(self, **kwargs: Any) -> ModelType:
        """Create a new record."""
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def find_by_id(self, id: UUID) -> Optional[ModelType]:
        """Find a record by ID."""
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def find_all(self, limit: int = 100, offset: int = 0) -> List[ModelType]:
        """Find all records with pagination."""
        result = await self.session.execute(
            select(self.model).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def update(self, id: UUID, **kwargs: Any) -> Optional[ModelType]:
        """Update a record by ID."""
        await self.session.execute(
            update(self.model).where(self.model.id == id).values(**kwargs)
        )
        return await self.find_by_id(id)

    async def delete(self, id: UUID) -> bool:
        """Delete a record by ID. Returns True if deleted."""
        result = await self.session.execute(
            delete(self.model).where(self.model.id == id)
        )
        return result.rowcount > 0
