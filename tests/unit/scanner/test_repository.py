"""
Unit tests for Scanner Repositories.

@spec FEAT-001 - Repository tests
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import select

from src.scanner.repository import ScanModel, LinkModel, ScanRepository, LinkRepository


class TestScanModel:
    """Tests for ScanModel."""

    def test_model_attributes(self):
        """Test model has required attributes."""
        scan = ScanModel(
            url="https://example.com",
            depth=3,
            status="pending",
            respect_robots=True,  # Explicit for test since defaults need DB
        )
        assert scan.url == "https://example.com"
        assert scan.depth == 3
        assert scan.status == "pending"
        assert scan.respect_robots is True


class TestLinkModel:
    """Tests for LinkModel."""

    def test_model_attributes(self):
        """Test model has required attributes."""
        link = LinkModel(
            scan_id=uuid4(),
            url="https://example.com/page",
            status="ok",
            depth=1,
        )
        assert link.status == "ok"
        assert link.depth == 1
        assert link.status_code is None


class TestScanRepository:
    """Tests for ScanRepository."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def repo(self, mock_session):
        """Create repository instance."""
        return ScanRepository(mock_session)

    @pytest.mark.asyncio
    async def test_update_status_running(self, repo, mock_session):
        """@spec FEAT-001/API-002 - Update status to running."""
        scan_id = uuid4()
        mock_scan = ScanModel(
            id=scan_id,
            url="https://example.com",
            depth=3,
            status="pending",
        )

        with patch.object(repo, "find_by_id", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_scan

            await repo.update_status(scan_id, "running")

        assert mock_scan.status == "running"
        assert mock_scan.started_at is not None
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_status_completed(self, repo, mock_session):
        """Update status to completed sets completed_at."""
        scan_id = uuid4()
        mock_scan = ScanModel(
            id=scan_id,
            url="https://example.com",
            depth=3,
            status="running",
            started_at=datetime.now(timezone.utc),
        )

        with patch.object(repo, "find_by_id", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_scan

            await repo.update_status(scan_id, "completed")

        assert mock_scan.status == "completed"
        assert mock_scan.completed_at is not None

    @pytest.mark.asyncio
    async def test_increment_checked(self, repo, mock_session):
        """@spec FEAT-001/AC-002 - Increment checked links counter."""
        scan_id = uuid4()
        mock_scan = ScanModel(
            id=scan_id,
            url="https://example.com",
            depth=3,
            status="running",
            checked_links=5,
        )

        with patch.object(repo, "find_by_id", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_scan

            await repo.increment_checked(scan_id)

        assert mock_scan.checked_links == 6

    @pytest.mark.asyncio
    async def test_increment_broken(self, repo, mock_session):
        """@spec FEAT-001/AC-002 - Increment broken links counter."""
        scan_id = uuid4()
        mock_scan = ScanModel(
            id=scan_id,
            url="https://example.com",
            depth=3,
            status="running",
            broken_links=2,
        )

        with patch.object(repo, "find_by_id", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_scan

            await repo.increment_broken(scan_id)

        assert mock_scan.broken_links == 3

    @pytest.mark.asyncio
    async def test_set_error(self, repo, mock_session):
        """@spec FEAT-001/DM-001 - Set error message and mark as failed."""
        scan_id = uuid4()
        mock_scan = ScanModel(
            id=scan_id,
            url="https://example.com",
            depth=3,
            status="running",
        )

        with patch.object(repo, "find_by_id", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_scan

            await repo.set_error(scan_id, "Connection failed")

        assert mock_scan.error_message == "Connection failed"
        assert mock_scan.status == "failed"
        assert mock_scan.completed_at is not None


class TestLinkRepository:
    """Tests for LinkRepository."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def repo(self, mock_session):
        """Create repository instance."""
        return LinkRepository(mock_session)

    @pytest.mark.asyncio
    async def test_find_by_scan(self, repo, mock_session):
        """@spec FEAT-001/API-003 - Find links by scan with pagination."""
        scan_id = uuid4()

        # Mock scalar for count
        mock_session.scalar = AsyncMock(return_value=50)

        # Mock execute for results
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        links, total = await repo.find_by_scan(scan_id, page=2, per_page=10)

        assert total == 50
        assert links == []

    @pytest.mark.asyncio
    async def test_find_by_scan_with_status_filter(self, repo, mock_session):
        """@spec FEAT-001/API-003 - Filter by status."""
        scan_id = uuid4()

        mock_session.scalar = AsyncMock(return_value=5)
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        links, total = await repo.find_by_scan(scan_id, status="broken", page=1, per_page=10)

        assert total == 5

    @pytest.mark.asyncio
    async def test_find_by_url(self, repo, mock_session):
        """@spec FEAT-001/EC-004 - Find link by URL for deduplication."""
        scan_id = uuid4()
        link_id = uuid4()
        mock_link = LinkModel(
            id=link_id,
            scan_id=scan_id,
            url="https://example.com/page",
            status="ok",
            depth=1,
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_link
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await repo.find_by_url(scan_id, "https://example.com/page")

        assert result == mock_link

    @pytest.mark.asyncio
    async def test_count_by_scan(self, repo, mock_session):
        """Count links by scan."""
        scan_id = uuid4()
        mock_session.scalar = AsyncMock(return_value=25)

        count = await repo.count_by_scan(scan_id)

        assert count == 25

    @pytest.mark.asyncio
    async def test_count_by_scan_with_status(self, repo, mock_session):
        """Count links by scan and status."""
        scan_id = uuid4()
        mock_session.scalar = AsyncMock(return_value=10)

        count = await repo.count_by_scan(scan_id, status="broken")

        assert count == 10

    @pytest.mark.asyncio
    async def test_get_all_for_export(self, repo, mock_session):
        """@spec FEAT-001/API-005 - Get all links for export."""
        scan_id = uuid4()

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_result)

        links = await repo.get_all_for_export(scan_id)

        assert links == []
