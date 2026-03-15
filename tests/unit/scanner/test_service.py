"""
Unit tests for ScanService.

@spec FEAT-001 - Service tests
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.scanner.service import ScanService, ScanError
from src.scanner.repository import ScanModel, LinkModel
from src.scanner.crawler import CrawlResult


class TestScanService:
    """Tests for ScanService."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_session):
        """Create service instance."""
        return ScanService(mock_session)

    @pytest.mark.asyncio
    async def test_create_scan_valid_url(self, service, mock_session):
        """@spec FEAT-001/AC-001 - Start scan with URL input."""
        mock_scan = ScanModel(
            id=uuid4(),
            url="https://example.com",
            depth=3,
            status="pending",
        )

        with patch.object(service.scan_repo, "create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_scan

            scan = await service.create_scan(url="https://example.com", depth=3)

        assert scan.url == "https://example.com"
        assert scan.depth == 3
        assert scan.status == "pending"

    @pytest.mark.asyncio
    async def test_create_scan_invalid_url(self, service):
        """@spec FEAT-001/EC-006 - Validate URL format."""
        with pytest.raises(ScanError) as exc:
            await service.create_scan(url="not-a-url")

        assert exc.value.error_code == "invalid_url"

    @pytest.mark.asyncio
    async def test_create_scan_clamp_depth(self, service, mock_session):
        """@spec FEAT-001/EC-008 - Clamp depth to 1-10 range."""
        mock_scan = ScanModel(
            id=uuid4(),
            url="https://example.com",
            depth=10,
            status="pending",
        )

        with patch.object(service.scan_repo, "create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_scan

            # Test depth > 10
            scan = await service.create_scan(url="https://example.com", depth=15)
            # Depth should be clamped to 10
            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs["depth"] == 10

    @pytest.mark.asyncio
    async def test_create_scan_clamp_depth_minimum(self, service, mock_session):
        """@spec FEAT-001/EC-008 - Clamp depth to minimum 1."""
        mock_scan = ScanModel(
            id=uuid4(),
            url="https://example.com",
            depth=1,
            status="pending",
        )

        with patch.object(service.scan_repo, "create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_scan

            # Test depth < 1
            scan = await service.create_scan(url="https://example.com", depth=0)
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs["depth"] == 1

    @pytest.mark.asyncio
    async def test_stop_scan(self, service, mock_session):
        """@spec FEAT-001/AC-007 - Stop in-progress scan."""
        scan_id = uuid4()
        mock_scan = ScanModel(
            id=scan_id,
            url="https://example.com",
            depth=3,
            status="running",
        )

        with patch.object(service.scan_repo, "find_by_id", new_callable=AsyncMock) as mock_find:
            with patch.object(service.scan_repo, "update_status", new_callable=AsyncMock) as mock_update:
                mock_find.return_value = mock_scan

                result = await service.stop_scan(scan_id)

        mock_update.assert_called_once_with(scan_id, "stopped")

    @pytest.mark.asyncio
    async def test_stop_scan_not_found(self, service):
        """Stop scan returns error if not found."""
        with patch.object(service.scan_repo, "find_by_id", new_callable=AsyncMock) as mock_find:
            mock_find.return_value = None

            with pytest.raises(ScanError) as exc:
                await service.stop_scan(uuid4())

        assert exc.value.error_code == "not_found"

    @pytest.mark.asyncio
    async def test_get_links_pagination(self, service, mock_session):
        """@spec FEAT-001/EC-002 - Pagination."""
        scan_id = uuid4()
        mock_scan = ScanModel(
            id=scan_id,
            url="https://example.com",
            depth=3,
            status="completed",
        )
        mock_links = [
            LinkModel(
                id=uuid4(),
                scan_id=scan_id,
                url=f"https://example.com/page{i}",
                status="ok",
                depth=1,
            )
            for i in range(5)
        ]

        with patch.object(service.scan_repo, "find_by_id", new_callable=AsyncMock) as mock_find:
            with patch.object(service.link_repo, "find_by_scan", new_callable=AsyncMock) as mock_find_links:
                mock_find.return_value = mock_scan
                mock_find_links.return_value = (mock_links, 100)

                result = await service.get_links(scan_id=scan_id, page=2, per_page=5)

        assert len(result["links"]) == 5
        assert result["pagination"]["page"] == 2
        assert result["pagination"]["total"] == 100

    @pytest.mark.asyncio
    async def test_get_links_max_per_page(self, service, mock_session):
        """@spec FEAT-001/EC-002 - Max 100 per page."""
        scan_id = uuid4()
        mock_scan = ScanModel(
            id=scan_id,
            url="https://example.com",
            depth=3,
            status="completed",
        )

        with patch.object(service.scan_repo, "find_by_id", new_callable=AsyncMock) as mock_find:
            with patch.object(service.link_repo, "find_by_scan", new_callable=AsyncMock) as mock_find_links:
                mock_find.return_value = mock_scan
                mock_find_links.return_value = ([], 0)

                await service.get_links(scan_id=scan_id, page=1, per_page=200)

                # Should clamp to 100
                call_kwargs = mock_find_links.call_args[1]
                assert call_kwargs["per_page"] == 100

    @pytest.mark.asyncio
    async def test_export_scan_json(self, service, mock_session):
        """@spec FEAT-001/AC-006 - Export scan results as JSON."""
        scan_id = uuid4()
        mock_scan = ScanModel(
            id=scan_id,
            url="https://example.com",
            depth=3,
            status="completed",
            total_links=10,
            checked_links=10,
            broken_links=2,
            created_at=datetime.now(timezone.utc),
        )
        mock_links = [
            LinkModel(
                id=uuid4(),
                scan_id=scan_id,
                url="https://example.com/404",
                status="broken",
                status_code=404,
                depth=1,
                checked_at=datetime.now(timezone.utc),
            )
        ]

        with patch.object(service.scan_repo, "find_by_id", new_callable=AsyncMock) as mock_find:
            with patch.object(service.link_repo, "get_all_for_export", new_callable=AsyncMock) as mock_export:
                mock_find.return_value = mock_scan
                mock_export.return_value = mock_links

                content_type, content = await service.export_scan(scan_id, "json")

        assert content_type == "application/json"
        assert b"https://example.com" in content

    @pytest.mark.asyncio
    async def test_export_scan_csv(self, service, mock_session):
        """@spec FEAT-001/AC-006 - Export scan results as CSV."""
        scan_id = uuid4()
        mock_scan = ScanModel(
            id=scan_id,
            url="https://example.com",
            depth=3,
            status="completed",
            created_at=datetime.now(timezone.utc),
        )
        mock_links = [
            LinkModel(
                id=uuid4(),
                scan_id=scan_id,
                url="https://example.com/page",
                status="ok",
                status_code=200,
                depth=1,
                checked_at=datetime.now(timezone.utc),
            )
        ]

        with patch.object(service.scan_repo, "find_by_id", new_callable=AsyncMock) as mock_find:
            with patch.object(service.link_repo, "get_all_for_export", new_callable=AsyncMock) as mock_export:
                mock_find.return_value = mock_scan
                mock_export.return_value = mock_links

                content_type, content = await service.export_scan(scan_id, "csv")

        assert content_type == "text/csv"
        assert b"url,status" in content  # Header

    @pytest.mark.asyncio
    async def test_export_scan_invalid_format(self, service):
        """Export with invalid format raises error."""
        with pytest.raises(ScanError) as exc:
            await service.export_scan(uuid4(), "xml")

        assert exc.value.error_code == "invalid_format"


class TestScanError:
    """Tests for ScanError."""

    def test_error_creation(self):
        """Test error attributes."""
        error = ScanError("test_error", "Test error message")
        assert error.error_code == "test_error"
        assert error.message == "Test error message"
        assert str(error) == "Test error message"
