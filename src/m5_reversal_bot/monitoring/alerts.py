"""Lightweight alerting. Records alerts to `system_logs` (always) and
exposes a hook (`notify_channels`) where a future integration — Slack,
email, PagerDuty — can be plugged in without touching the strategy or
execution layers. No alert here can suppress or alter a trading decision;
alerting is strictly downstream observation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, List, Optional

from sqlalchemy.orm import Session

from ..persistence import repository

SEVERITY_LEVELS = ("INFO", "WARNING", "ERROR", "CRITICAL")


@dataclass
class Alert:
    severity: str
    component: str
    message: str
    context: Optional[dict] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AlertManager:
    def __init__(self):
        self._channels: List[Callable[[Alert], None]] = []
        self._recent: List[Alert] = []

    def register_channel(self, fn: Callable[[Alert], None]) -> None:
        self._channels.append(fn)

    def raise_alert(self, db: Session, severity: str, component: str, message: str, context: Optional[dict] = None) -> Alert:
        if severity not in SEVERITY_LEVELS:
            severity = "INFO"
        alert = Alert(severity=severity, component=component, message=message, context=context)
        self._recent.append(alert)
        if len(self._recent) > 500:
            self._recent = self._recent[-500:]

        repository.log_system(db, severity, component, message, context)
        for channel in self._channels:
            try:
                channel(alert)
            except Exception:
                pass  # a broken notification channel must never crash the bot
        return alert

    def recent(self, limit: int = 50) -> List[Alert]:
        return self._recent[-limit:]
