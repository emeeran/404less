"""
Integration tests for Scanner API endpoints.

@spec FEAT-001 - API endpoint tests
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from src.main import app
from src.scanner.repository import ScanModel, LinkModel
from src.scanner.service import ScanService, ScanError


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_db():
    """Create mock database session."""
    return AsyncMock()


class TestCreateScanEndpoint:
    """Tests for POST /api/scans."""

    @patch("src.scanner.routes.get_db")
    @patch("src.scanner.routes.ScanService")
    def test_create_scan_success(self, mock_service_class, mock_get_db, client):
        """@spec FEAT-001/API-001 - Create new scan."""
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db

        mock_scan = ScanModel(
            id=uuid4(),
            url="https://example.com",
            depth=3,
            status="pending",
        )

        mock_service = MagicMock()
        mock_service.create_scan = AsyncMock(return_value=mock_scan)
        mock_service.start_scan = AsyncMock()
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/scans",
            json={"url": "https://example.com", "depth": 3},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["url"] == "https://example.com"
        assert data["depth"] == 3
        assert data["status"] == "pending"

    def test_create_scan_invalid_url(self, client):
        """@spec FEAT-001/EC-006 - Invalid URL format."""
        response = client.post(
            "/api/scans",
            json={"url": "not-a-url", "depth": 3},
        )

        assert response.status_code == 422  # Validation error

    def test_create_scan_invalid_depth(self, client):
        """@spec FEAT-001/C-005 - Depth must be 1-10."""
        response = client.post(
            "/api/scans",
            json={"url": "https://example.com", "depth": 15},
        )

        assert response.status_code == 422  # Validation error


class TestGetScanEndpoint:
    """Tests for GET /api/scans/{scan_id}."""

    @patch("src.scanner.routes.get_db")
    @patch("src.scanner.routes.ScanService")
    def test_get_scan_success(self, mock_service_class, mock_get_db, client):
        """@spec FEAT-001/API-002 - Get scan status."""
        scan_id = uuid4()
        mock_scan = ScanModel(
            id=scan_id,
            url="https://example.com",
            depth=3,
            status="running",
            total_links=100,
            checked_links=50,
            broken_links=5,
        )

        mock_service = MagicMock()
        mock_service.get_scan = AsyncMock(return_value=mock_scan)
        mock_service_class.return_value = mock_service

        response = client.get(f"/api/scans/{scan_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert data["total_links"] == 100
        assert data["checked_links"] == 50
        assert data["broken_links"] == 5

    @patch("src.scanner.routes.get_db")
    @patch("src.scanner.routes.ScanService")
    def test_get_scan_not_found(self, mock_service_class, mock_get_db, client):
        """@spec FEAT-001/API-002 - Scan not found."""
        mock_service = MagicMock()
        mock_service.get_scan = AsyncMock(return_value=None)
        mock_service_class.return_value = mock_service

        response = client.get(f"/api/scans/{uuid4()}")

        assert response.status_code == 404


class TestGetLinksEndpoint:
    """Tests for GET /api/scans/{scan_id}/links."""

    @patch("src.scanner.routes.get_db")
    @patch("src.scanner.routes.ScanService")
    def test_get_links_success(self, mock_service_class, mock_get_db, client):
        """@spec FEAT-001/API-003 - Get paginated links."""
        scan_id = uuid4()

        mock_service = MagicMock()
        mock_service.get_links = AsyncMock(return_value={
            "links": [
                {
                    "url": "https://example.com/page1",
                    "status": "ok",
                    "status_code": 200,
                    "depth": 1,
                },
                {
                    "url": "https://example.com/page2",
                    "status": "broken",
                    "status_code": 404,
                    "depth": 1,
                },
            ],
            "pagination": {
                "page": 1,
                "per_page": 50,
                "total": 2,
                "total_pages": 1,
            },
        })
        mock_service_class.return_value = mock_service

        response = client.get(f"/api/scans/{scan_id}/links")

        assert response.status_code == 200
        data = response.json()
        assert len(data["links"]) == 2
        assert data["pagination"]["total"] == 2

    @patch("src.scanner.routes.get_db")
    @patch("src.scanner.routes.ScanService")
    def test_get_links_with_status_filter(self, mock_service_class, mock_get_db, client):
        """@spec FEAT-001/API-003 - Filter by status."""
        scan_id = uuid4()

        mock_service = MagicMock()
        mock_service.get_links = AsyncMock(return_value={
            "links": [
                {
                    "url": "https://example.com/404",
                    "status": "broken",
                    "status_code": 404,
                    "depth": 1,
                },
            ],
            "pagination": {
                "page": 1,
                "per_page": 50,
                "total": 1,
                "total_pages": 1,
            },
        })
        mock_service_class.return_value = mock_service

        response = client.get(f"/api/scans/{scan_id}/links?status=broken")

        assert response.status_code == 200
        data = response.json()
        assert all(link["status"] == "broken" for link in data["links"])


class TestStopScanEndpoint:
    """Tests for DELETE /api/scans/{scan_id}."""

    @patch("src.scanner.routes.get_db")
    @patch("src.scanner.routes.ScanService")
    def test_stop_scan_success(self, mock_service_class, mock_get_db, client):
        """@spec FEAT-001/API-004 - Stop in-progress scan."""
        scan_id = uuid4()
        mock_scan = ScanModel(
            id=scan_id,
            url="https://example.com",
            depth=3,
            status="stopped",
        )

        mock_service = MagicMock()
        mock_service.stop_scan = AsyncMock(return_value=mock_scan)
        mock_service_class.return_value = mock_service

        response = client.delete(f"/api/scans/{scan_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "stopped"

    @patch("src.scanner.routes.get_db")
    @patch("src.scanner.routes.ScanService")
    def test_stop_scan_not_found(self, mock_service_class, mock_get_db, client):
        """@spec FEAT-001/API-004 - Scan not found."""
        mock_service = MagicMock()
        mock_service.stop_scan = AsyncMock(side_effect=ScanError("not_found", "Scan not found"))
        mock_service_class.return_value = mock_service

        response = client.delete(f"/api/scans/{uuid4()}")

        assert response.status_code == 404


class TestExportScanEndpoint:
    """Tests for GET /api/scans/{scan_id}/export."""

    @patch("src.scanner.routes.get_db")
    @patch("src.scanner.routes.ScanService")
    def test_export_json(self, mock_service_class, mock_get_db, client):
        """@spec FEAT-001/API-005 - Export as JSON."""
        scan_id = uuid4()
        json_content = json.dumps({
            "scan": {"id": str(scan_id), "url": "https://example.com"},
            "links": [],
        }).encode("utf-8")

        mock_service = MagicMock()
        mock_service.export_scan = AsyncMock(return_value=("application/json", json_content))
        mock_service_class.return_value = mock_service

        response = client.get(f"/api/scans/{scan_id}/export?format=json")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

    @patch("src.scanner.routes.get_db")
    @patch("src.scanner.routes.ScanService")
    def test_export_csv(self, mock_service_class, mock_get_db, client):
        """@spec FEAT-001/API-005 - Export as CSV."""
        scan_id = uuid4()
        csv_content = b"url,status,status_code\nhttps://example.com,ok,200"

        mock_service = MagicMock()
        mock_service.export_scan = AsyncMock(return_value=("text/csv", csv_content))
        mock_service_class.return_value = mock_service

        response = client.get(f"/api/scans/{scan_id}/export?format=csv")

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv"

    @patch("src.scanner.routes.get_db")
    @patch("src.scanner.routes.ScanService")
    def test_export_invalid_format(self, mock_service_class, mock_get_db, client):
        """@spec FEAT-001/API-005 - Invalid format."""
        mock_service = MagicMock()
        mock_service.export_scan = AsyncMock(
            side_effect=ScanError("invalid_format", "Format must be 'json' or 'csv'")
        )
        mock_service_class.return_value = mock_service

        response = client.get(f"/api/scans/{uuid4()}/export?format=xml")

        assert response.status_code == 400


class TestSSEEndpoint:
    """Tests for GET /api/scans/{scan_id}/stream."""

    def test_sse_endpoint_exists(self, client):
        """@spec FEAT-001/API-006 - SSE endpoint exists."""
        # The endpoint should accept connections
        # Full SSE testing requires async client
        scan_id = uuid4()
        # Just verify the route is registered
        response = client.get(f"/api/scans/{scan_id}/stream")
        # SSE returns a streaming response, which TestClient handles differently
        # Just check it doesn't return 404 or 405
        assert response.status_code != 404
        assert response.status_code != 405
