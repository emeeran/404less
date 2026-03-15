"""
SSE Manager Module

@spec FEAT-001/C-002 - Real-time updates via SSE
@spec FEAT-001/API-006 - SSE endpoint

Manages Server-Sent Events connections for real-time scan updates.
"""

import asyncio
import json
from typing import Dict, List, Set
from uuid import UUID


class SSEManager:
    """
    Manages Server-Sent Events connections for real-time updates.

    @spec FEAT-001/C-002
    @spec FEAT-001/API-006
    @spec FEAT-001/AC-002 - Real-time progress display
    """

    def __init__(self):
        """Initialize SSE manager."""
        # Map scan_id -> set of queues for connected clients
        self._connections: Dict[UUID, Set[asyncio.Queue]] = {}

    async def connect(self, scan_id: UUID) -> asyncio.Queue:
        """
        Register a new SSE connection for a scan.

        Args:
            scan_id: Scan ID to subscribe to

        Returns:
            Queue that will receive SSE events
        """
        queue = asyncio.Queue()

        if scan_id not in self._connections:
            self._connections[scan_id] = set()

        self._connections[scan_id].add(queue)
        return queue

    async def disconnect(self, scan_id: UUID, queue: asyncio.Queue) -> None:
        """
        Remove an SSE connection.

        Args:
            scan_id: Scan ID
            queue: Queue to remove
        """
        if scan_id in self._connections:
            self._connections[scan_id].discard(queue)
            if not self._connections[scan_id]:
                del self._connections[scan_id]

    async def broadcast_progress(
        self,
        scan_id: UUID,
        checked_links: int,
        total_links: int,
        broken_links: int,
        current_url: str,
    ) -> None:
        """
        Broadcast progress update to all connected clients.

        @spec FEAT-001/AC-002 - Real-time progress
        @spec FEAT-001/API-006 - progress event
        """
        event = {
            "event": "progress",
            "data": json.dumps({
                "checked_links": checked_links,
                "total_links": total_links,
                "broken_links": broken_links,
                "current_url": current_url,
            }),
        }

        await self._broadcast(scan_id, event)

    async def broadcast_link_checked(
        self,
        scan_id: UUID,
        url: str,
        status: str,
        status_code: int | None,
        depth: int,
    ) -> None:
        """
        Broadcast link checked event.

        @spec FEAT-001/API-006 - link_checked event
        """
        event = {
            "event": "link_checked",
            "data": json.dumps({
                "url": url,
                "status": status,
                "status_code": status_code,
                "depth": depth,
            }),
        }

        await self._broadcast(scan_id, event)

    async def broadcast_completed(
        self,
        scan_id: UUID,
        total_links: int,
        broken_links: int,
    ) -> None:
        """
        Broadcast scan completed event.

        @spec FEAT-001/API-006 - completed event
        """
        event = {
            "event": "completed",
            "data": json.dumps({
                "total_links": total_links,
                "broken_links": broken_links,
            }),
        }

        await self._broadcast(scan_id, event)

    async def broadcast_stopped(self, scan_id: UUID) -> None:
        """
        Broadcast scan stopped event.
        """
        event = {
            "event": "stopped",
            "data": json.dumps({"message": "Scan stopped by user"}),
        }

        await self._broadcast(scan_id, event)

    async def broadcast_error(self, scan_id: UUID, error_message: str) -> None:
        """
        Broadcast scan error event.
        """
        event = {
            "event": "error",
            "data": json.dumps({"error": error_message}),
        }

        await self._broadcast(scan_id, event)

    async def _broadcast(self, scan_id: UUID, event: dict) -> None:
        """
        Internal method to broadcast event to all connected clients.
        """
        if scan_id not in self._connections:
            return

        # Create list to avoid modification during iteration
        queues = list(self._connections.get(scan_id, set()))

        for queue in queues:
            try:
                await queue.put(event)
            except Exception:
                # Queue might be closed, ignore
                pass

    def get_connection_count(self, scan_id: UUID) -> int:
        """Get number of connected clients for a scan."""
        return len(self._connections.get(scan_id, set()))


# Global SSE manager instance
sse_manager = SSEManager()
