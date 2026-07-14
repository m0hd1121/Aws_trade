"""News calendar ingestion for the D1/D2 filters. Only data acquisition
lives here — the blackout-window RULE is entirely in strategy/sessions.py
and core/constants.py::NEWS. See config/news_calendar.yaml.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List

import yaml

from ..core.models import NewsEvent


def load_static_news_events(path: Path) -> List[NewsEvent]:
    if not path.exists():
        return []
    with open(path, "r") as f:
        data = yaml.safe_load(f) or {}
    events: List[NewsEvent] = []
    for row in data.get("events", []):
        t = row["time"]
        if isinstance(t, str):
            dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
        else:
            dt = t
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        events.append(
            NewsEvent(
                instrument_currencies=tuple(row.get("currencies", [])),
                event_time=dt,
                label=row.get("label", "unlabeled event"),
                is_red_folder=bool(row.get("red_folder", False)),
                is_nfp_or_cpi=bool(row.get("nfp_or_cpi", False)),
                is_fomc=bool(row.get("fomc", False)),
                unscheduled=bool(row.get("unscheduled", False)),
            )
        )
    return events


def load_holiday_calendar(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}
