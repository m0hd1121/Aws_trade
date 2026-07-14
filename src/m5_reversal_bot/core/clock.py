"""GMT time/session utilities. The rulebook is defined entirely in GMT
(Section 2 preamble); every timestamp that reaches the strategy layer must
already be tz-aware UTC/GMT. This module is the single place that converts.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from .constants import SESSIONS
from .enums import Session

GMT = timezone.utc  # GMT == UTC for this system's purposes (no DST offset)


def to_gmt(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=GMT)
    return dt.astimezone(GMT)


def now_gmt() -> datetime:
    return datetime.now(GMT)


def current_session(dt: datetime) -> Session:
    dt = to_gmt(dt)
    t = dt.time()
    if time(SESSIONS.london_kz_start_hour, 0) <= t < time(SESSIONS.london_kz_end_hour, 0):
        return Session.LONDON_KZ
    if time(SESSIONS.newyork_kz_start_hour, 0) <= t < time(SESSIONS.newyork_kz_end_hour, 0):
        return Session.NEWYORK_KZ
    return Session.OUTSIDE_KZ


def is_inside_kill_zone(dt: datetime) -> bool:
    return current_session(dt) != Session.OUTSIDE_KZ


def kill_zone_bounds(session: Session, ref_date: datetime) -> tuple[datetime, datetime]:
    d = to_gmt(ref_date).date()
    if session == Session.LONDON_KZ:
        start = datetime.combine(d, time(SESSIONS.london_kz_start_hour, 0), tzinfo=GMT)
        end = datetime.combine(d, time(SESSIONS.london_kz_end_hour, 0), tzinfo=GMT)
    elif session == Session.NEWYORK_KZ:
        start = datetime.combine(d, time(SESSIONS.newyork_kz_start_hour, 0), tzinfo=GMT)
        end = datetime.combine(d, time(SESSIONS.newyork_kz_end_hour, 0), tzinfo=GMT)
    else:
        raise ValueError("No kill zone bounds outside LKZ/NYKZ")
    return start, end


def order_validity_deadline(session: Session, ref_date: datetime) -> datetime:
    """2.3 — pending orders rest until KZ close + 30 minutes."""
    _, end = kill_zone_bounds(session, ref_date)
    return end + timedelta(minutes=SESSIONS.order_validity_extension_minutes)


def hard_flat_time(ref_date: datetime) -> datetime:
    """2.4 — all positions closed by 19:30 GMT."""
    d = to_gmt(ref_date).date()
    return datetime.combine(
        d, time(SESSIONS.hard_flat_hour, SESSIONS.hard_flat_minute), tzinfo=GMT
    )


def is_past_hard_flat(dt: datetime) -> bool:
    dt = to_gmt(dt)
    return dt >= hard_flat_time(dt)


def asia_window(ref_date: datetime) -> tuple[datetime, datetime]:
    """1.13 / Section 2.1 — 00:00-06:00 GMT."""
    d = to_gmt(ref_date).date()
    start = datetime.combine(d, time(SESSIONS.asia_start_hour, 0), tzinfo=GMT)
    end = datetime.combine(d, time(SESSIONS.asia_end_hour, 0), tzinfo=GMT)
    return start, end


def london_session_window(ref_date: datetime) -> tuple[datetime, datetime]:
    """2.1 note — 07:00-12:00 GMT, valid sweep source for NY session."""
    d = to_gmt(ref_date).date()
    start = datetime.combine(d, time(SESSIONS.london_session_start_hour, 0), tzinfo=GMT)
    end = datetime.combine(d, time(SESSIONS.london_session_end_hour, 0), tzinfo=GMT)
    return start, end


def previous_day_window(ref_date: datetime) -> tuple[datetime, datetime]:
    """1.5 — PDH/PDL measured 00:00-00:00 GMT of the prior calendar day."""
    d = to_gmt(ref_date).date() - timedelta(days=1)
    start = datetime.combine(d, time(0, 0), tzinfo=GMT)
    end = start + timedelta(days=1)
    return start, end


def previous_week_window(ref_date: datetime) -> tuple[datetime, datetime]:
    """1.5 — previous week high/low, Mon 00:00 - Mon 00:00 GMT."""
    d = to_gmt(ref_date).date()
    this_monday = d - timedelta(days=d.weekday())
    prev_monday = this_monday - timedelta(days=7)
    start = datetime.combine(prev_monday, time(0, 0), tzinfo=GMT)
    end = datetime.combine(this_monday, time(0, 0), tzinfo=GMT)
    return start, end


def map_marking_time(ref_date: datetime) -> datetime:
    d = to_gmt(ref_date).date()
    return datetime.combine(
        d, time(SESSIONS.map_marking_hour, SESSIONS.map_marking_minute), tzinfo=GMT
    )


def minutes_between(a: datetime, b: datetime) -> float:
    return abs((to_gmt(b) - to_gmt(a)).total_seconds()) / 60.0
