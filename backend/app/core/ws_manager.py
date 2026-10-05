"""
WebSocket Real-Time Event & Progress Broadcast Manager
Provides live pub/sub streaming to connected frontend clients:
- Scrape progress & portal scan logs
- Real-time LLM token / step streaming
- Auto-apply status changes & human-in-the-loop approval triggers
- Instant notifications (seen jobs, ghost alerts, deadline sweeps)
"""

import asyncio
import json
from typing import Dict, Any, List, Set, Optional
from fastapi import WebSocket, WebSocketDisconnect
from backend.app.core.event_logger import agent_logger
from backend.app.core.tenant import get_tenant_id

class WebSocketManager:
    """Manages active WebSocket connections and channel broadcasting."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.connection_tenants: Dict[WebSocket, Optional[str]] = {}
        self._lock = asyncio.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def connect(self, websocket: WebSocket):
        """Accept connection and register client."""
        self._loop = asyncio.get_running_loop()
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
            self.connection_tenants[websocket] = get_tenant_id()
        agent_logger.log_event("WEBSOCKET", f"Client connected. Active: {len(self.active_connections)}")
        
        # Send initial handshake welcome
        await self.send_personal_message({
            "type": "connection_established",
            "message": "Connected to Autonomous Career Agent Real-Time Stream",
            "active_clients": len(self.active_connections)
        }, websocket)

    async def disconnect(self, websocket: WebSocket):
        """Unregister client upon disconnect."""
        async with self._lock:
            self.active_connections.discard(websocket)
            self.connection_tenants.pop(websocket, None)
        agent_logger.log_event("WEBSOCKET", f"Client disconnected. Active: {len(self.active_connections)}")

    async def broadcast(self, event_type: str, data: Dict[str, Any]):
        """
        Broadcast structured JSON payload to all active frontend connections.
        Non-blocking: skips or cleans up dead sockets safely.
        """
        if not self.active_connections:
            return

        payload = json.dumps({
            "type": event_type,
            "data": data
        })

        dead_connections = []
        current_tenant = get_tenant_id()
        async with self._lock:
            for connection in list(self.active_connections):
                if self.connection_tenants.get(connection) != current_tenant:
                    continue
                try:
                    await connection.send_text(payload)
                except Exception:
                    dead_connections.append(connection)

            for dead in dead_connections:
                self.active_connections.discard(dead)
                self.connection_tenants.pop(dead, None)

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket):
        """Send message directly to a specific socket connection."""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception:
            pass

    def broadcast_sync(self, event_type: str, data: Dict[str, Any]):
        """Synchronous wrapper for broadcasting from non-async contexts."""
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = self._loop

            if loop is None or loop.is_closed():
                return
            if loop.is_running():
                loop.call_soon_threadsafe(
                    lambda: asyncio.create_task(self.broadcast(event_type, data))
                )
            else:
                loop.run_until_complete(self.broadcast(event_type, data))
        except RuntimeError:
            pass

ws_manager = WebSocketManager()
