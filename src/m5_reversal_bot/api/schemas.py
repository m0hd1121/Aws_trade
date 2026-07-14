"""Pydantic request models for the few endpoints that accept a body.
Dashboard read endpoints return plain dicts built directly from ORM rows —
see routes_dashboard.py — since their shape mirrors the DB schema closely
enough that a parallel pydantic model would just be duplication."""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel


class ConfigUpdateRequest(BaseModel):
    config: Dict[str, Any]


class BrokerConnectRequest(BaseModel):
    """POST /api/bot/broker-connect — updates MT5 credentials live, no
    .env edit or restart required. All fields optional: only the ones
    supplied are changed. `password` is never echoed back in any
    response."""

    login: Optional[int] = None
    password: Optional[str] = None
    server: Optional[str] = None
    bridge_mode: Optional[Literal["local", "mt5linux"]] = None
    bridge_host: Optional[str] = None
    bridge_port: Optional[int] = None
    persist: bool = True  # write to .env so it survives a process restart
