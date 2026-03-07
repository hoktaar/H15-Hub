from __future__ import annotations
import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from h15hub.engine.device_registry import DeviceRegistry

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    def __init__(self) -> None:
        self._active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._active.remove(ws)

    async def broadcast(self, data: dict) -> None:
        dead = []
        for ws in self._active:
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._active.remove(ws)


manager = ConnectionManager()


def make_ws_router(registry: DeviceRegistry) -> APIRouter:
    @router.websocket("/ws/status")
    async def websocket_status(ws: WebSocket) -> None:
        await manager.connect(ws)
        try:
            # Initiales Status-Update sofort senden
            devices = registry.get_all()
            await ws.send_text(json.dumps({
                "type": "full_update",
                "devices": [d.model_dump() for d in devices],
            }))

            # Verbindung offen halten, regelmäßig pingen
            while True:
                await asyncio.sleep(5)
                devices = registry.get_all()
                await ws.send_text(json.dumps({
                    "type": "full_update",
                    "devices": [d.model_dump() for d in devices],
                }))
        except WebSocketDisconnect:
            manager.disconnect(ws)

    return router


async def notify_status_change(old, new) -> None:
    """Callback für DeviceRegistry – sendet Status-Änderungen an alle Browser."""
    await manager.broadcast({
        "type": "status_change",
        "device_id": new.id,
        "old_status": old.status.value,
        "new_status": new.status.value,
        "device": new.model_dump(),
    })
