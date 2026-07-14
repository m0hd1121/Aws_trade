"""Section 8 — Risk & Money Management.

Pure, stateless rule functions over an `AccountSnapshot`. The actual
mutable, persisted account state (today's realized P&L, consecutive-loss
counters, trade counts, etc.) is owned by `risk_manager/account_state.py`,
which calls into this module for every decision so the *rules* live in
exactly one place.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List

from ..core.constants import RISK, get_instrument_constants
from ..core.enums import Instrument

# 8.1 — "value per pip/point per lot" per the worked examples: EU is priced
# per standard lot ($10/pip); XAU per 1-lot (100oz, $100 per $1 move). The
# rulebook's EU example result (1.25) is re-labeled "mini lots (0.125 std)"
# in its own prose — a units aside in the source document, not a distinct
# formula. This module implements 8.1's formula literally and does not
# reinterpret that aside; the literal arithmetic is what the worked-example
# tests in tests/unit/test_worked_examples.py verify against (1.25 and 0.25).
VALUE_PER_UNIT_PER_LOT = {
    Instrument.EURUSD: 10.0,   # USD per pip, per standard lot
    Instrument.XAUUSD: 100.0,  # USD per $1 move, per 1 lot (100oz)
}

DEFAULT_LOT_STEP = 0.01


def stop_distance_in_formula_units(instrument: Instrument, stop_distance_price: float) -> float:
    """EU stop distance expressed in pips; XAU stop distance is already in
    dollars, which is the unit 8.1's XAU example uses directly."""
    if instrument == Instrument.EURUSD:
        return stop_distance_price / get_instrument_constants(instrument).pip_value_in_price
    return stop_distance_price


def compute_position_size(
    equity: float,
    risk_percent: float,
    stop_distance_price: float,
    instrument: Instrument,
    lot_step: float = DEFAULT_LOT_STEP,
) -> float:
    """8.1 — Position size = (Account equity x Risk%) / (Stop distance x
    value per pip/point per lot). Rounded DOWN to the broker's lot step,
    never up."""
    units = stop_distance_in_formula_units(instrument, stop_distance_price)
    if units <= 0:
        raise ValueError("stop distance must be positive")
    risk_amount = equity * (risk_percent / 100.0)
    raw_lots = risk_amount / (units * VALUE_PER_UNIT_PER_LOT[instrument])
    steps = math.floor(raw_lots / lot_step)
    return round(steps * lot_step, 8)


@dataclass
class AccountSnapshot:
    """A point-in-time view of account/session state, as of the moment a
    trade is being evaluated. Built by risk_manager/account_state.py from
    persisted trade history; 8.5 — all percentages here are computed on
    start-of-day equity, never intraday floating equity."""

    equity_start_of_day: float
    equity_current: float
    high_water_mark_month: float

    daily_realized_loss_percent: float          # positive number = a loss
    weekly_realized_loss_percent: float
    consecutive_losses_this_session: int
    consecutive_losses_running: int
    trades_this_kill_zone: int
    trades_today: int
    concurrent_positions_total: int
    concurrent_positions_by_instrument: dict     # {Instrument: int}
    combined_open_risk_percent: float

    live_trades_taken_lifetime: int              # for the 40-trade evaluation phase
    in_recovery_mode: bool                       # after a circuit-breaker event, until next winner
    monthly_drawdown_percent: float               # from HWM, this month
    monthly_brake_active: bool
    demo_requalification_trades_done: int


@dataclass(frozen=True)
class RiskDecision:
    risk_percent: float
    g3_pass: bool
    blocked_reasons: List[str]


def determine_risk_percent(snapshot: AccountSnapshot) -> float:
    """8.2 — 1.0% normal; 0.5% during the first 40 live trades (evaluation)
    and after any circuit-breaker event, until the next winner."""
    if snapshot.in_recovery_mode:
        return RISK.evaluation_risk_percent
    if snapshot.live_trades_taken_lifetime < RISK.evaluation_phase_trade_count:
        return RISK.evaluation_risk_percent
    return RISK.normal_risk_percent


def evaluate_g3(
    snapshot: AccountSnapshot,
    instrument: Instrument,
    proposed_risk_percent: float,
) -> RiskDecision:
    """G3 — Section 8 account risk limits, all of them, combined into a
    single gate. Any one breach fails G3."""
    reasons: List[str] = []

    if snapshot.daily_realized_loss_percent >= RISK.max_daily_loss_percent:
        reasons.append(f"daily loss {snapshot.daily_realized_loss_percent:.2f}% >= {RISK.max_daily_loss_percent}% limit")

    if snapshot.weekly_realized_loss_percent >= RISK.max_weekly_loss_percent:
        reasons.append(f"weekly loss {snapshot.weekly_realized_loss_percent:.2f}% >= {RISK.max_weekly_loss_percent}% limit")

    if snapshot.consecutive_losses_this_session >= RISK.consecutive_losses_session_limit:
        reasons.append(f"{snapshot.consecutive_losses_this_session} consecutive losses this session")

    if snapshot.consecutive_losses_running >= RISK.consecutive_losses_running_limit:
        reasons.append(f"{snapshot.consecutive_losses_running} consecutive running losses — next session skipped")

    if snapshot.trades_this_kill_zone >= RISK.max_trades_per_kill_zone:
        reasons.append(f"{snapshot.trades_this_kill_zone} trades already taken this kill zone")

    if snapshot.trades_today >= RISK.max_trades_per_day:
        reasons.append(f"{snapshot.trades_today} trades already taken today")

    if snapshot.concurrent_positions_total >= RISK.max_concurrent_positions_total:
        reasons.append(f"{snapshot.concurrent_positions_total} concurrent positions already open")

    per_instrument = snapshot.concurrent_positions_by_instrument.get(instrument, 0)
    if per_instrument >= RISK.max_concurrent_positions_per_instrument:
        reasons.append(f"{instrument.value} already has an open position")

    if snapshot.concurrent_positions_total >= 1:
        projected_combined_risk = snapshot.combined_open_risk_percent + proposed_risk_percent
        if projected_combined_risk > RISK.max_combined_open_risk_percent_multi_instrument:
            reasons.append(
                f"combined open risk would be {projected_combined_risk:.2f}% > "
                f"{RISK.max_combined_open_risk_percent_multi_instrument}% limit for simultaneous EU+XAU"
            )

    if snapshot.monthly_brake_active:
        reasons.append("monthly drawdown brake active — live trading halted pending re-qualification")

    return RiskDecision(risk_percent=proposed_risk_percent, g3_pass=len(reasons) == 0, blocked_reasons=reasons)


def check_monthly_brake(equity_current: float, high_water_mark_month: float) -> bool:
    """8.4 — halt live trading if equity closes a month -6% or worse from
    its high-water mark."""
    if high_water_mark_month <= 0:
        return False
    drawdown_percent = (high_water_mark_month - equity_current) / high_water_mark_month * 100.0
    return drawdown_percent >= RISK.monthly_drawdown_brake_percent


def requalification_complete(demo_trades_done: int) -> bool:
    """8.4 — 20 consecutive rule-compliant demo/micro trades before resuming."""
    return demo_trades_done >= RISK.monthly_brake_requalify_trades
