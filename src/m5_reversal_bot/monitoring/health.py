"""Connection/component health monitoring — heartbeats for the dashboard's
System Health and Connection Status panels.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional


@dataclass
class ComponentHealth:
    component: str
    status: str  # UP | DOWN | DEGRADED
    last_heartbeat: Optional[datetime]
    latency_ms: Optional[float] = None
    detail: Optional[str] = None


class HealthMonitor:
    def __init__(self, stale_after_seconds: float = 30.0):
        self._stale_after = timedelta(seconds=stale_after_seconds)
        self._components: Dict[str, ComponentHealth] = {}

    def heartbeat(self, component: str, status: str = "UP", latency_ms: Optional[float] = None, detail: Optional[str] = None) -> None:
        self._components[component] = ComponentHealth(
            component=component, status=status, last_heartbeat=datetime.now(timezone.utc),
            latency_ms=latency_ms, detail=detail,
        )

    def snapshot(self) -> Dict[str, dict]:
        now = datetime.now(timezone.utc)
        out = {}
        for name, ch in self._components.items():
            effective_status = ch.status
            if ch.last_heartbeat and (now - ch.last_heartbeat) > self._stale_after and ch.status == "UP":
                effective_status = "DEGRADED"
            out[name] = {
                "status": effective_status,
                "last_heartbeat": ch.last_heartbeat.isoformat() if ch.last_heartbeat else None,
                "latency_ms": ch.latency_ms,
                "detail": ch.detail,
            }
        return out

    def overall_status(self) -> str:
        statuses = [c["status"] for c in self.snapshot().values()]
        if not statuses:
            return "UNKNOWN"
        if any(s == "DOWN" for s in statuses):
            return "DOWN"
        if any(s == "DEGRADED" for s in statuses):
            return "DEGRADED"
        return "UP"
