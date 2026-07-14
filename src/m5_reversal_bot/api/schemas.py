"""Pydantic request models for the few endpoints that accept a body.
Dashboard read endpoints return plain dicts built directly from ORM rows —
see routes_dashboard.py — since their shape mirrors the DB schema closely
enough that a parallel pydantic model would just be duplication."""

from __future__ import annotations

from typing import Any, Dict

from pydantic import BaseModel


class ConfigUpdateRequest(BaseModel):
    config: Dict[str, Any]
