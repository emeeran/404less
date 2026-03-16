"""
Scanner Routes Module

@spec FEAT-001
@api_endpoints API-001, API-002, API-003, API-004, API-005, API-006
"""

import asyncio
from io import BytesIO
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.config import RATE_LIMIT_SCAN_CREATE
from src.shared.db.connection import get_db

from .service import ScanService, ScanError
from .sse import sse_manager


router = APIRouter(prefix="/api/scans", tags=["Scanner"])
limiter = Limiter(key_func=get_remote_address)


# ============================================================================
# Request/Response Models
# ============================================================================

class ScanCreateRequest(BaseModel):
    """Request model for creating a scan."""
    url: str = Field(..., max_length=2048)
    depth: int = Field(default=3, ge=1, le=10)
    respect_robots: bool = Field(default=True)
    user_agent: Optional[str] = Field(default=None, max_length=256)

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """@spec FEAT-001/EC-006 - Validate URL format"""
        v = v.strip()
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class ScanResponse(BaseModel):
    """Response model for scan creation."""
    scan_id: UUID
    status: str
    url: str
    depth: int
    created_at: str


class ScanStatusResponse(BaseModel):
    """Response model for scan status."""
    scan_id: UUID
    url: str
    depth: int
    status: str
    total_links: int
    checked_links: int
    broken_links: int
    started_at: Optional[str]
    completed_at: Optional[str]


# ============================================================================
# Routes
# ============================================================================

@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit(RATE_LIMIT_SCAN_CREATE)
async def create_scan(
    request: Request,
    scan_request: ScanCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> ScanResponse:
    """
    Create and start a new scan.

    @spec FEAT-001/API-001
    @spec FEAT-001/AC-001 - Start scan with URL input
    """
    service = ScanService(db)

    try:
        scan = await service.create_scan(
            url=scan_request.url,
            depth=scan_request.depth,
            respect_robots=scan_request.respect_robots,
            user_agent=scan_request.user_agent,
        )

        # Start the scan in background
        await service.start_scan(scan.id)

        return ScanResponse(
            scan_id=scan.id,
            status=scan.status,
            url=scan.url,
            depth=scan.depth,
            created_at=scan.created_at.isoformat() if scan.created_at else "",
        )

    except ScanError as e:
        if e.error_code == "invalid_url":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": e.error_code, "message": e.message},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": e.error_code, "message": e.message},
        )


@router.get("/{scan_id}")
async def get_scan(
    scan_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ScanStatusResponse:
    """
    Get scan status.

    @spec FEAT-001/API-002
    """
    service = ScanService(db)
    scan = await service.get_scan(scan_id)

    if not scan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Scan not found"},
        )

    return ScanStatusResponse(
        scan_id=scan.id,
        url=scan.url,
        depth=scan.depth,
        status=scan.status,
        total_links=scan.total_links,
        checked_links=scan.checked_links,
        broken_links=scan.broken_links,
        started_at=scan.started_at.isoformat() if scan.started_at else None,
        completed_at=scan.completed_at.isoformat() if scan.completed_at else None,
    )


@router.get("/{scan_id}/links")
async def get_links(
    scan_id: UUID,
    status: Optional[str] = None,
    page: int = 1,
    per_page: int = 50,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get paginated links for a scan.

    @spec FEAT-001/API-003
    @spec FEAT-001/EC-002 - Pagination
    """
    service = ScanService(db)

    try:
        return await service.get_links(
            scan_id=scan_id,
            status_filter=status,
            page=page,
            per_page=per_page,
        )
    except ScanError as e:
        if e.error_code == "not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "not_found", "message": "Scan not found"},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": e.error_code, "message": e.message},
        )


@router.delete("/{scan_id}")
async def stop_scan(
    scan_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Stop an in-progress scan.

    @spec FEAT-001/API-004
    @spec FEAT-001/AC-007 - Preserve partial results
    """
    service = ScanService(db)

    try:
        scan = await service.stop_scan(scan_id)
        return {
            "scan_id": scan.id,
            "status": scan.status,
        }
    except ScanError as e:
        if e.error_code == "not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "not_found", "message": "Scan not found"},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": e.error_code, "message": e.message},
        )


@router.get("/{scan_id}/export")
async def export_scan(
    scan_id: UUID,
    format: str,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Export scan results.

    @spec FEAT-001/API-005
    @spec FEAT-001/AC-006
    """
    service = ScanService(db)

    try:
        content_type, content = await service.export_scan(scan_id, format)

        return StreamingResponse(
            BytesIO(content),
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="scan-{scan_id}.{format}"'
            },
        )
    except ScanError as e:
        if e.error_code == "invalid_format":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "invalid_format", "message": e.message},
            )
        if e.error_code == "not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "not_found", "message": "Scan not found"},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": e.error_code, "message": e.message},
        )


@router.get("/{scan_id}/stream")
async def stream_scan(scan_id: UUID) -> StreamingResponse:
    """
    Server-Sent Events endpoint for real-time scan updates.

    @spec FEAT-001/API-006
    @spec FEAT-001/AC-002 - Real-time progress display
    """
    from sse_starlette.sse import EventSourceResponse

    async def event_generator():
        # Register connection
        queue = await sse_manager.connect(scan_id)

        try:
            # Send keepalive and wait for events
            while True:
                try:
                    # Wait for event with timeout
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield event

                    # If completed or stopped, close connection
                    if event.get("event") in ("completed", "stopped", "error"):
                        break

                except asyncio.TimeoutError:
                    # Send keepalive comment
                    yield {"event": "keepalive", "data": ""}

        finally:
            await sse_manager.disconnect(scan_id, queue)

    return EventSourceResponse(event_generator())
