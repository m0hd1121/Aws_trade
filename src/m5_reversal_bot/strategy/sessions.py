"""Section 2 — Sessions & Tradeable Windows, and the D1-D7 session
disqualifiers. Kill-zone time math itself lives in core/clock.py; this
module is the rulebook's objective tests layered on top of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import List, Optional, Set

from ..core.clock import GMT, kill_zone_bounds, to_gmt
from ..core.constants import NEWS, InstrumentConstants
from ..core.enums import Instrument, Session
from ..core.models import NewsEvent


@dataclass(frozen=True)
class DisqualifierResult:
    blocked: bool
    reason: Optional[str] = None


def _relevant_currencies(instrument: Instrument) -> Set[str]:
    return {"USD", "EUR"} if instrument == Instrument.EURUSD else {"USD"}


def _red_folder_events_for(instrument: Instrument, news_events: List[NewsEvent]) -> List[NewsEvent]:
    currencies = _relevant_currencies(instrument)
    return [e for e in news_events if e.is_red_folder and currencies.intersection(e.instrument_currencies)]


def blackout_window(event: NewsEvent) -> tuple:
    return (
        event.event_time - timedelta(minutes=NEWS.blackout_minutes_before),
        event.event_time + timedelta(minutes=NEWS.blackout_minutes_after),
    )


def event_in_blackout_at(dt: datetime, instrument: Instrument, news_events: List[NewsEvent]) -> Optional[NewsEvent]:
    dt = to_gmt(dt)
    for e in _red_folder_events_for(instrument, news_events):
        start, end = blackout_window(e)
        if start <= dt <= end:
            return e
    return None


def d1_kz_blackout_coverage_fraction(
    session: Session, ref_date: datetime, instrument: Instrument, news_events: List[NewsEvent]
) -> float:
    kz_start, kz_end = kill_zone_bounds(session, ref_date)
    total = (kz_end - kz_start).total_seconds()
    if total <= 0:
        return 0.0
    covered = 0.0
    for e in _red_folder_events_for(instrument, news_events):
        b_start, b_end = blackout_window(e)
        ov_start, ov_end = max(kz_start, b_start), min(kz_end, b_end)
        if ov_end > ov_start:
            covered += (ov_end - ov_start).total_seconds()
    return covered / total


def check_d1_session(
    session: Session, ref_date: datetime, instrument: Instrument, news_events: List[NewsEvent]
) -> DisqualifierResult:
    """D1, session-level: if the blackout covers >50% of the KZ, skip the
    entire KZ."""
    frac = d1_kz_blackout_coverage_fraction(session, ref_date, instrument, news_events)
    if frac > NEWS.blackout_kz_coverage_skip_fraction:
        return DisqualifierResult(True, f"D1: news blackout covers {frac:.0%} of the KZ (>50%) — KZ skipped entirely")
    return DisqualifierResult(False)


def check_d1_at_time(dt: datetime, instrument: Instrument, news_events: List[NewsEvent]) -> DisqualifierResult:
    """D1, moment-level: no entries/order-resting from -60 to +30 min of a
    scheduled red-folder release. A fresh sweep+CHoCH forming entirely
    after the release is separately allowed by the caller re-evaluating
    the setup from scratch post-release."""
    e = event_in_blackout_at(dt, instrument, news_events)
    if e:
        return DisqualifierResult(True, f"D1: inside blackout window for '{e.label}' at {e.event_time.isoformat()}")
    return DisqualifierResult(False)


def check_d2(
    session: Session, ref_date: datetime, current_time: datetime, instrument: Instrument, news_events: List[NewsEvent]
) -> DisqualifierResult:
    """D2 — FOMC/NFP/CPI day handling."""
    events = _red_folder_events_for(instrument, news_events)
    day = to_gmt(ref_date).date()

    fomc_today = [e for e in events if e.is_fomc and to_gmt(e.event_time).date() == day]
    if fomc_today and session == Session.NEWYORK_KZ:
        return DisqualifierResult(True, "D2: FOMC decision day — no NYKZ trades at all")

    nfp_cpi_today = [e for e in events if e.is_nfp_or_cpi and to_gmt(e.event_time).date() == day]
    if nfp_cpi_today and session == Session.NEWYORK_KZ:
        resume = datetime.combine(
            day, time(NEWS.nfp_cpi_nykz_resume_hour_gmt, NEWS.nfp_cpi_nykz_resume_minute_gmt), tzinfo=GMT
        )
        if to_gmt(current_time) < resume:
            return DisqualifierResult(
                True, f"D2: NFP/CPI day — NYKZ tradeable only from {resume.isoformat()} onward with a fully post-news setup"
            )
    return DisqualifierResult(False)


def check_d3_d4(instrument: Instrument, asia_range_value: float, inst_constants: InstrumentConstants) -> DisqualifierResult:
    if asia_range_value < inst_constants.asia_range_min:
        return DisqualifierResult(True, f"D3: Asia range {asia_range_value:.5f} below floor {inst_constants.asia_range_min:.5f}")
    if asia_range_value > inst_constants.asia_range_max:
        return DisqualifierResult(True, f"D4: Asia range {asia_range_value:.5f} above cap {inst_constants.asia_range_max:.5f}")
    return DisqualifierResult(False)


def _in_dec20_jan3(d: date) -> bool:
    return (d.month == 12 and d.day >= 20) or (d.month == 1 and d.day <= 3)


def _in_date_ranges(d: date, ranges: List[List[str]]) -> bool:
    for start_s, end_s in ranges:
        start = date.fromisoformat(start_s)
        end = date.fromisoformat(end_s)
        if start <= d <= end:
            return True
    return False


def check_d5(ref_date: datetime, holiday_calendar: dict) -> DisqualifierResult:
    """D5 — UK/US bank holiday, Dec 20-Jan 3 inclusive, Thanksgiving
    Thu-Fri, Good Friday week Thu-Fri. `holiday_calendar` is the parsed
    contents of config/holidays.yaml."""
    d = to_gmt(ref_date).date()
    if _in_dec20_jan3(d):
        return DisqualifierResult(True, "D5: Dec 20-Jan 3 holiday liquidity window")

    all_bank_holidays: Set[str] = set()
    for key, vals in holiday_calendar.items():
        if key.startswith("uk_us_bank_holidays"):
            all_bank_holidays.update(vals)
    if d.isoformat() in all_bank_holidays:
        return DisqualifierResult(True, "D5: UK/US bank holiday")

    if _in_date_ranges(d, holiday_calendar.get("thanksgiving_week_thu_fri", [])):
        return DisqualifierResult(True, "D5: Thanksgiving week Thu-Fri")
    if _in_date_ranges(d, holiday_calendar.get("good_friday_week_thu_fri", [])):
        return DisqualifierResult(True, "D5: Good Friday week Thu-Fri")

    return DisqualifierResult(False)


def check_d6(dt: datetime) -> DisqualifierResult:
    """D6 — Friday NYKZ after 15:00 GMT. Stated for completeness: this is
    already outside the NYKZ window (12:00-15:00), so it can never fire in
    practice, but is evaluated explicitly to mirror the rulebook 1:1."""
    dt = to_gmt(dt)
    if dt.weekday() == 4 and dt.time() >= time(15, 0):  # Friday
        return DisqualifierResult(True, "D6: Friday after 15:00 GMT — no new risk")
    return DisqualifierResult(False)


def check_d7(instrument: Instrument, current_spread: float, inst_constants: InstrumentConstants) -> DisqualifierResult:
    if current_spread > inst_constants.max_spread:
        return DisqualifierResult(
            True, f"D7: spread {current_spread:.5f} exceeds max {inst_constants.max_spread:.5f} at intended execution"
        )
    return DisqualifierResult(False)


def check_session_confluence(
    session: Session, pool_price: float, asia_extreme_price: Optional[float], inst_constants: InstrumentConstants
) -> bool:
    """2.1 — in the LKZ, a PDH/PDL sweep source only qualifies as the Asia
    model if within the confluence tolerance of the Asia extreme."""
    if session != Session.LONDON_KZ or asia_extreme_price is None:
        return True
    return abs(pool_price - asia_extreme_price) <= inst_constants.session_confluence_tolerance
