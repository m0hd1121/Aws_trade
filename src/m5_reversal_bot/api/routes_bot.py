"""Bot control endpoints — Start / Stop / Pause / Resume / Restart /
Reset Session / Emergency Stop / Manual Refresh / Broker Connection."""

from __future__ import annotations

import logging
from pathlib import Path

from dotenv import set_key
from fastapi import APIRouter, HTTPException

from ..bot.controller import InvalidTransition
from ..core.config import REPO_ROOT, app_settings
from .schemas import BrokerConnectRequest
from .state import get_controller

log = logging.getLogger("m5_reversal_bot.api.routes_bot")

router = APIRouter()


@router.post("/start")
def start_bot():
    try:
        return get_controller().start()
    except InvalidTransition as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/stop")
def stop_bot():
    try:
        return get_controller().stop()
    except InvalidTransition as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/pause")
def pause_bot():
    try:
        return get_controller().pause()
    except InvalidTransition as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/resume")
def resume_bot():
    try:
        return get_controller().resume()
    except InvalidTransition as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/restart")
def restart_bot():
    try:
        return get_controller().restart()
    except InvalidTransition as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/reset-session")
def reset_session():
    return get_controller().reset_session()


@router.post("/emergency-stop")
def emergency_stop():
    try:
        return get_controller().emergency_stop()
    except InvalidTransition as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/refresh")
def manual_refresh():
    return get_controller().manual_refresh()


@router.get("/status")
def status():
    return get_controller().status()


_ENV_PATH = REPO_ROOT / ".env"


@router.post("/broker-connect")
def broker_connect(body: BrokerConnectRequest):
    """Broker Connection panel — updates MT5 credentials live (no .env
    edit or restart) and attempts to (re)connect. Login happens purely
    via initialize()/login() API calls, exactly as it always has — this
    endpoint doesn't script or need any terminal GUI interaction, in
    either bridge_mode."""
    mt5 = app_settings.mt5
    updated = {}
    if body.login is not None:
        mt5.login, updated["MT5_LOGIN"] = body.login, str(body.login)
    if body.password is not None:
        mt5.password, updated["MT5_PASSWORD"] = body.password, body.password
    if body.server is not None:
        mt5.server, updated["MT5_SERVER"] = body.server, body.server
    if body.bridge_mode is not None:
        mt5.bridge_mode, updated["MT5_BRIDGE_MODE"] = body.bridge_mode, body.bridge_mode
    if body.bridge_host is not None:
        mt5.bridge_host, updated["MT5_BRIDGE_HOST"] = body.bridge_host, body.bridge_host
    if body.bridge_port is not None:
        mt5.bridge_port, updated["MT5_BRIDGE_PORT"] = body.bridge_port, str(body.bridge_port)

    if body.persist and updated and _ENV_PATH.exists():
        try:
            for key, value in updated.items():
                set_key(str(_ENV_PATH), key, value, quote_mode="never")
        except Exception:
            log.exception("failed to persist broker credentials to .env")

    controller = get_controller()
    runner = controller.runner

    if runner is not None and runner.feed is not None and runner.adapter is not None:
        for component in (runner.feed, runner.adapter):
            try:
                component.disconnect()
            except Exception:
                pass
        try:
            runner.feed.connect()
            runner.adapter.connect()
            return {"success": True, "live": True, "message": "Reconnected with the updated credentials."}
        except Exception as e:
            return {"success": False, "live": True, "message": f"Reconnect failed: {e}"}

    # Bot isn't running yet — test connectivity with a throwaway feed
    # rather than silently just saving unverified credentials.
    from ..data.mt5_feed import MT5MarketDataFeed

    symbol_map = controller.config.raw.get("mt5", {}).get("symbol_map", {})
    test_feed = MT5MarketDataFeed(app_settings.mt5, symbol_map)
    try:
        test_feed.connect()
        connected = test_feed.is_connected()
        test_feed.disconnect()
        if connected:
            return {"success": True, "live": False, "message": "Test connection OK. Start Bot to begin trading."}
        return {"success": False, "live": False, "message": "Connected but terminal reports not-ready — check server/login."}
    except Exception as e:
        return {"success": False, "live": False, "message": f"Test connection failed: {e}"}
