"""
Scan Service Module

@spec FEAT-001 - Scan orchestration service

Coordinates crawler execution, database persistence, and SSE broadcasting.
"""

import asyncio
import csv
import io
import json
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.db.connection import AsyncSessionLocal

from .crawler import AsyncCrawler, CrawlResult, CrawlerConfig
from .repository import ScanRepository, LinkRepository, ScanModel
from .robots import RobotsChecker
from .sse import sse_manager


class ScanError(Exception):
    """Base exception for scan errors."""

    def __init__(self, error_code: str, message: str):
        self.error_code = error_code
        self.message = message
        super().__init__(message)


class ScanService:
    """
    Orchestrates scan lifecycle and crawler coordination.

    @spec FEAT-001
    """

    # Track running crawlers for stop functionality
    _running_crawlers: dict[UUID, AsyncCrawler] = {}

    def __init__(self, session: AsyncSession):
        """
        Initialize scan service.

        Args:
            session: Database session
        """
        self.session = session
        self.scan_repo = ScanRepository(session)
        self.link_repo = LinkRepository(session)

    async def create_scan(
        self,
        url: str,
        depth: int = 3,
        respect_robots: bool = True,
        user_agent: Optional[str] = None,
    ) -> ScanModel:
        """
        Create a new scan.

        @spec FEAT-001/API-001 - Create new scan
        @spec FEAT-001/AC-001 - Start scan with URL input
        @spec FEAT-001/EC-006 - Validate URL format
        @spec FEAT-001/EC-008 - Clamp depth to 1-10 range
        @spec FEAT-001/C-005 - Max depth 10
        """
        # Validate URL
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            raise ScanError("invalid_url", "URL must be a valid http or https URL")

        # @spec FEAT-001/EC-008 - Clamp depth
        depth = max(1, min(depth, 10))

        # Build user agent
        final_user_agent = user_agent or "404less/0.1.0 (+https://github.com/user/404less)"

        # Create scan record
        scan = await self.scan_repo.create(
            url=url,
            depth=depth,
            respect_robots=respect_robots,
            user_agent=final_user_agent,
            status="pending",
        )

        return scan

    async def start_scan(self, scan_id: UUID) -> None:
        """
        Start the scan in the background.

        @spec FEAT-001/AC-001
        """
        scan = await self.scan_repo.find_by_id(scan_id)
        if not scan:
            raise ScanError("not_found", "Scan not found")

        # Update status to running
        await self.scan_repo.update_status(scan_id, "running")
        await self.session.commit()

        # Start crawler in background
        asyncio.create_task(self._run_crawler(scan.id))

    async def _run_crawler(self, scan_id: UUID) -> None:
        """
        Execute the crawler for a scan.

        Internal method - runs in background.
        """
        try:
            async with AsyncSessionLocal() as session:
                scan = await ScanRepository(session).find_by_id(scan_id)

            if not scan:
                return

            # Setup crawler
            robots_checker = RobotsChecker() if scan.respect_robots else None
            config = CrawlerConfig(user_agent=scan.user_agent or "404less/0.1.0")

            crawler = AsyncCrawler(
                scan_id=scan.id,
                config=config,
                robots_checker=robots_checker,
                on_link_checked=lambda r: self._on_link_checked(scan.id, r),
                on_progress=lambda p: self._on_progress(scan.id, p),
            )

            # Track running crawler
            self._running_crawlers[scan.id] = crawler

            # Run crawler
            await crawler.crawl(
                start_url=scan.url,
                max_depth=scan.depth,
                respect_robots=scan.respect_robots,
            )

            # Update final status
            if crawler.is_stopped:
                async with AsyncSessionLocal() as session:
                    scan_repo = ScanRepository(session)
                    await scan_repo.update_status(scan.id, "stopped")
                    await session.commit()
                await sse_manager.broadcast_stopped(scan.id)
            else:
                async with AsyncSessionLocal() as session:
                    scan_repo = ScanRepository(session)
                    await scan_repo.update_status(scan.id, "completed")
                    await session.commit()
                await sse_manager.broadcast_completed(
                    scan.id,
                    crawler.total_links,
                    crawler.broken_links,
                )

        except Exception as e:
            async with AsyncSessionLocal() as session:
                scan_repo = ScanRepository(session)
                await scan_repo.set_error(scan_id, str(e))
                await session.commit()
            await sse_manager.broadcast_error(scan_id, str(e))

        finally:
            # Cleanup
            if scan_id in self._running_crawlers:
                del self._running_crawlers[scan_id]

    async def _on_link_checked(self, scan_id: UUID, result: CrawlResult) -> None:
        """
        Callback when a link is checked.

        Stores result in database and broadcasts SSE event.
        """
        async with AsyncSessionLocal() as session:
            link_repo = LinkRepository(session)
            scan_repo = ScanRepository(session)

            # Store link in database
            await link_repo.create(
                scan_id=scan_id,
                url=result.url,
                status=result.status,
                status_code=result.status_code,
                error=result.error,
                depth=result.depth,
                parent_url=result.parent_url,
                checked_at=datetime.now(timezone.utc),
            )

            # Update scan counters
            await scan_repo.increment_checked(scan_id)
            if result.status == "broken":
                await scan_repo.increment_broken(scan_id)

            await session.commit()

        # Broadcast SSE event
        await sse_manager.broadcast_link_checked(
            scan_id=scan_id,
            url=result.url,
            status=result.status,
            status_code=result.status_code,
            depth=result.depth,
        )

    async def _on_progress(self, scan_id: UUID, progress: dict) -> None:
        """
        Callback for progress updates.

        Broadcasts progress via SSE.
        """
        await sse_manager.broadcast_progress(
            scan_id=scan_id,
            checked_links=progress["checked_links"],
            total_links=progress["total_links"],
            broken_links=progress["broken_links"],
            current_url=progress["current_url"],
        )

    async def get_scan(self, scan_id: UUID) -> Optional[ScanModel]:
        """
        Get scan by ID.

        @spec FEAT-001/API-002
        """
        return await self.scan_repo.find_by_id(scan_id)

    async def stop_scan(self, scan_id: UUID) -> ScanModel:
        """
        Stop an in-progress scan.

        @spec FEAT-001/API-004
        @spec FEAT-001/AC-007 - Preserve partial results
        """
        scan = await self.scan_repo.find_by_id(scan_id)
        if not scan:
            raise ScanError("not_found", "Scan not found")

        # Stop crawler if running
        if scan_id in self._running_crawlers:
            self._running_crawlers[scan_id].stop()

        # Update status
        await self.scan_repo.update_status(scan_id, "stopped")

        return await self.scan_repo.find_by_id(scan_id) or scan

    async def get_links(
        self,
        scan_id: UUID,
        status_filter: Optional[str] = None,
        page: int = 1,
        per_page: int = 50,
    ) -> dict:
        """
        Get paginated links for a scan.

        @spec FEAT-001/API-003
        @spec FEAT-001/EC-002 - Pagination
        """
        # Validate scan exists
        scan = await self.scan_repo.find_by_id(scan_id)
        if not scan:
            raise ScanError("not_found", "Scan not found")

        # @spec FEAT-001/EC-002 - Max 100 per page
        per_page = min(per_page, 100)

        links, total = await self.link_repo.find_by_scan(
            scan_id=scan_id,
            status=status_filter,
            page=page,
            per_page=per_page,
        )

        return {
            "links": [
                {
                    "url": link.url,
                    "status": link.status,
                    "status_code": link.status_code,
                    "error": link.error,
                    "depth": link.depth,
                    "parent_url": link.parent_url,
                    "checked_at": link.checked_at.isoformat() if link.checked_at else None,
                }
                for link in links
            ],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": (total + per_page - 1) // per_page,
            },
        }

    async def export_scan(self, scan_id: UUID, format: str) -> tuple[str, bytes]:
        """
        Export scan results.

        @spec FEAT-001/API-005
        @spec FEAT-001/AC-006
        """
        # Validate format
        if format not in ("json", "csv"):
            raise ScanError("invalid_format", "Format must be 'json' or 'csv'")

        # Validate scan exists
        scan = await self.scan_repo.find_by_id(scan_id)
        if not scan:
            raise ScanError("not_found", "Scan not found")

        # Get all links
        links = await self.link_repo.get_all_for_export(scan_id)

        if format == "json":
            data = {
                "scan": {
                    "id": str(scan.id),
                    "url": scan.url,
                    "depth": scan.depth,
                    "status": scan.status,
                    "total_links": scan.total_links,
                    "checked_links": scan.checked_links,
                    "broken_links": scan.broken_links,
                    "created_at": scan.created_at.isoformat() if scan.created_at else None,
                    "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
                },
                "links": [
                    {
                        "url": link.url,
                        "status": link.status,
                        "status_code": link.status_code,
                        "error": link.error,
                        "depth": link.depth,
                        "parent_url": link.parent_url,
                        "checked_at": link.checked_at.isoformat() if link.checked_at else None,
                    }
                    for link in links
                ],
            }
            return "application/json", json.dumps(data, indent=2).encode("utf-8")

        else:  # csv
            output = io.StringIO()
            writer = csv.writer(output)

            # Header
            writer.writerow([
                "url", "status", "status_code", "error",
                "depth", "parent_url", "checked_at"
            ])

            # Data
            for link in links:
                writer.writerow([
                    link.url,
                    link.status,
                    link.status_code or "",
                    link.error or "",
                    link.depth,
                    link.parent_url or "",
                    link.checked_at.isoformat() if link.checked_at else "",
                ])

            return "text/csv", output.getvalue().encode("utf-8")
