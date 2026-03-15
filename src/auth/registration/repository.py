"""
User Repository Module

@spec FEAT-001/DM-001 (User)
@spec FEAT-001/DM-002 (EmailVerificationToken)

Provides data access for User and EmailVerificationToken entities.
"""

import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, MappedAsDataclass, mapped_column

from src.shared.db.models import Base, UUIDMixin, TimestampMixin
from src.shared.db.repository import BaseRepository


# ============================================================================
# SQLAlchemy Models
# ============================================================================

class UserModel(Base, UUIDMixin, TimestampMixin):
    """
    User database model.

    @spec FEAT-001/DM-001
    """
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(nullable=False, index=True, unique=True)
    password_hash: Mapped[str] = mapped_column(nullable=False)
    email_verified: Mapped[bool] = mapped_column(nullable=False, default=False)


class EmailVerificationTokenModel(Base, UUIDMixin, TimestampMixin):
    """
    Email verification token database model.

    @spec FEAT-001/DM-002
    """
    __tablename__ = "email_verification_tokens"

    user_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    token: Mapped[str] = mapped_column(nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)


# ============================================================================
# Repositories
# ============================================================================

class UserRepository(BaseRepository[UserModel]):
    """
    Repository for User entity.

    @spec FEAT-001/DM-001
    """

    def __init__(self, session: AsyncSession):
        super().__init__(UserModel, session)

    async def find_by_email(self, email: str) -> Optional[UserModel]:
        """
        Find user by email address.

        @spec FEAT-001/AC-002 - Check for duplicate email
        """
        # Normalize email to lowercase
        normalized_email = email.strip().lower()

        result = await self.session.execute(
            select(UserModel).where(UserModel.email == normalized_email)
        )
        return result.scalar_one_or_none()

    async def set_email_verified(self, user_id: UUID) -> None:
        """
        Mark user's email as verified.

        @spec FEAT-001/AC-004
        """
        user = await self.find_by_id(user_id)
        if user:
            user.email_verified = True
            await self.session.flush()


class EmailVerificationTokenRepository(BaseRepository[EmailVerificationTokenModel]):
    """
    Repository for EmailVerificationToken entity.

    @spec FEAT-001/DM-002
    """

    def __init__(self, session: AsyncSession):
        super().__init__(EmailVerificationTokenModel, session)

    async def create_token(
        self, user_id: UUID, expires_in_hours: int = 24
    ) -> EmailVerificationTokenModel:
        """
        Create a new verification token.

        @spec FEAT-001/C-004 - Token expires in 24 hours
        """
        # Generate cryptographically secure token (32 bytes, hex encoded = 64 chars)
        token = secrets.token_hex(32)

        expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_in_hours)

        return await self.create(
            user_id=user_id,
            token=token,
            expires_at=expires_at,
        )

    async def find_valid_token(self, token: str) -> Optional[EmailVerificationTokenModel]:
        """
        Find a valid (not expired, not used) token.

        @spec FEAT-001/API-002
        """
        now = datetime.now(timezone.utc)

        result = await self.session.execute(
            select(EmailVerificationTokenModel).where(
                and_(
                    EmailVerificationTokenModel.token == token,
                    EmailVerificationTokenModel.expires_at > now,
                    EmailVerificationTokenModel.used_at.is_(None),
                )
            )
        )
        return result.scalar_one_or_none()

    async def mark_used(self, token: str) -> None:
        """
        Mark token as used.

        @spec FEAT-001/DM-002
        """
        token_record = await self.find_valid_token(token)
        if token_record:
            token_record.used_at = datetime.now(timezone.utc)
            await self.session.flush()
