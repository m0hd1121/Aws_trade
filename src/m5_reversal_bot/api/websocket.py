"""Real-time push for the dashboard — bot status, stage transitions,
positions, and account metrics, broadcast every couple seconds so the UI
never has to poll aggressively (keeps CPU usage low on both ends)."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .state import get_controller

log = logging.getLogger("m5_reversal_bot.api.websocket")

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict) -> None:
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(ws)


async def broadcast_loop(interval_seconds: float = 2.0) -> None:
    while True:
        try:
            if manager.active:
                controller = get_controller()
                await manager.broadcast({"type": "status", "data": controller.status()})
        except Exception:
            log.exception("broadcast_loop failed")
        await asyncio.sleep(interval_seconds)
