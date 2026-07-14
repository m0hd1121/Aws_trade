"""FastAPI application entry point. Serves the REST + WebSocket API and,
if present, the static dashboard build — one lightweight process, no
Node/Nginx required for a small deployment (see docker/ for a fuller
production layout)."""

from __future__ import annotations

import asyncio
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from ..core.config import REPO_ROOT, app_settings
from ..monitoring.logger import configure_logging
from ..persistence import db as db_module
from . import routes_bot, routes_config, routes_dashboard, websocket
from .auth import BasicAuthASGIMiddleware, warn_if_auth_disabled
from .state import get_controller

configure_logging(app_settings.log_dir, app_settings.log_level)
db_module.init_db()
warn_if_auth_disabled()

app = FastAPI(title="M5 Liquidity Reversal Bot", version="1.0.0")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)
app.add_middleware(BasicAuthASGIMiddleware)

app.include_router(routes_bot.router, prefix="/api/bot", tags=["bot"])
app.include_router(routes_dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(routes_config.router, prefix="/api/config", tags=["config"])
app.include_router(websocket.router, prefix="/api")


@app.on_event("startup")
async def on_startup():
    asyncio.create_task(websocket.broadcast_loop())
    if os.environ.get("M5BOT_AUTOSTART") == "1":
        get_controller().start()


@app.get("/api/healthz")
def healthz():
    return {"status": "ok"}


dashboard_dir = REPO_ROOT / "dashboard"
if dashboard_dir.exists():
    app.mount("/", StaticFiles(directory=str(dashboard_dir), html=True), name="dashboard")
