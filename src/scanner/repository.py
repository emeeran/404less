"""
Scanner Repository Module

@spec FEAT-001/DM-001 (Scan)
@spec FEAT-001/DM-002 (Link)

Provides data access for Scan and Link entities.
"""

from datetime import datetime, timezone
from typing import Optional, List, Tuple
from uuid import UUID

from sqlalchemy import select, func, and_, Index, String, Integer, Boolean, Text, Uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.db.models import Base, UUIDMixin, TimestampMixin
from src.shared.db.repository import BaseRepository


# ============================================================================
# SQLAlchemy Models
# ============================================================================

class ScanModel(Base, UUIDMixin, TimestampMixin):
    """
    Scan database model.

    @spec FEAT-001/DM-001
    """
    __tablename__ = "scans"

    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    depth: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", index=True
    )
    respect_robots: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    total_links: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    checked_links: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    broken_links: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class LinkModel(Base, UUIDMixin, TimestampMixin):
    """
    Link database model.

    @spec FEAT-001/DM-002
    """
    __tablename__ = "links"

    scan_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    depth: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    checked_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    __table_args__ = (
        Index("idx_links_scan_status", "scan_id", "status"),
        Index("idx_links_scan_depth", "scan_id", "depth"),
    )


# ============================================================================
# Repositories
# ============================================================================

class ScanRepository(BaseRepository[ScanModel]):
    """
    Repository for Scan entity.

    @spec FEAT-001/DM-001
    """

    def __init__(self, session: AsyncSession):
        super().__init__(ScanModel, session)

    async def update_status(self, scan_id: UUID, status: str) -> None:
        """
        Update scan status.

        @spec FEAT-001/API-002
        """
        scan = await self.find_by_id(scan_id)
        if scan:
            scan.status = status
            if status == "running" and not scan.started_at:
                scan.started_at = datetime.now(timezone.utc)
            elif status in ("completed", "stopped", "failed"):
                scan.completed_at = datetime.now(timezone.utc)
            await self.session.flush()

    async def increment_checked(self, scan_id: UUID) -> None:
        """
        Increment checked links counter.

        @spec FEAT-001/AC-002
        """
        scan = await self.find_by_id(scan_id)
        if scan:
            scan.checked_links += 1
            await self.session.flush()

    async def increment_broken(self, scan_id: UUID) -> None:
        """
        Increment broken links counter.

        @spec FEAT-001/AC-002
        """
        scan = await self.find_by_id(scan_id)
        if scan:
            scan.broken_links += 1
            await self.session.flush()

    async def set_total_links(self, scan_id: UUID, total: int) -> None:
        """
        Set total links count.

        @spec FEAT-001/AC-002
        """
        scan = await self.find_by_id(scan_id)
        if scan:
            scan.total_links = total
            await self.session.flush()

    async def set_error(self, scan_id: UUID, error_message: str) -> None:
        """
        Set error message and mark as failed.

        @spec FEAT-001/DM-001
        """
        scan = await self.find_by_id(scan_id)
        if scan:
            scan.error_message = error_message
            scan.status = "failed"
            scan.completed_at = datetime.now(timezone.utc)
            await self.session.flush()


class LinkRepository(BaseRepository[LinkModel]):
    """
    Repository for Link entity.

    @spec FEAT-001/DM-002
    """

    def __init__(self, session: AsyncSession):
        super().__init__(LinkModel, session)

    async def find_by_scan(
        self,
        scan_id: UUID,
        status: Optional[str] = None,
        page: int = 1,
        per_page: int = 50,
    ) -> Tuple[List[LinkModel], int]:
        """
        Find links by scan with optional filtering and pagination.

        @spec FEAT-001/API-003
        @spec FEAT-001/EC-002 - Pagination for thousands of links
        """
        base_query = select(LinkModel).where(LinkModel.scan_id == scan_id)

        if status:
            base_query = base_query.where(LinkModel.status == status)

        # Get total count
        count_query = select(func.count()).select_from(base_query.subquery())
        total = await self.session.scalar(count_query) or 0

        # Get paginated results
        offset = (page - 1) * per_page
        result = await self.session.execute(
            base_query.order_by(LinkModel.created_at).offset(offset).limit(per_page)
        )
        links = list(result.scalars().all())

        return links, total

    async def find_by_url(self, scan_id: UUID, url: str) -> Optional[LinkModel]:
        """
        Find a link by URL within a scan.

        @spec FEAT-001/EC-004 - For deduplication check
        """
        result = await self.session.execute(
            select(LinkModel).where(
                and_(LinkModel.scan_id == scan_id, LinkModel.url == url)
            )
        )
        return result.scalar_one_or_none()

    async def count_by_scan(self, scan_id: UUID, status: Optional[str] = None) -> int:
        """
        Count links by scan.

        @spec FEAT-001/DM-002
        """
        query = select(func.count()).where(LinkModel.scan_id == scan_id)
        if status:
            query = query.where(LinkModel.status == status)
        return await self.session.scalar(query) or 0

    async def get_all_for_export(self, scan_id: UUID) -> List[LinkModel]:
        """
        Get all links for a scan (for export).

        @spec FEAT-001/API-005
        @spec FEAT-001/AC-006
        """
        result = await self.session.execute(
            select(LinkModel)
            .where(LinkModel.scan_id == scan_id)
            .order_by(LinkModel.created_at)
        )
        return list(result.scalars().all())
