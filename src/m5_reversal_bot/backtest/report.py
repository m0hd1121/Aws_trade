"""Backtest performance reporting — win rate, R statistics, drawdown,
equity curve, and per-factor pass rates, built entirely from what's
already persisted (trades, setups, skips) so backtest, paper, demo, and
live all produce the exact same *shape* of report from the same tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.analytics import build_summary_from_trade_records
from ..core.enums import Mode
from ..persistence.schema import SetupRecord, SkipRecord, TradeRecord

FACTOR_KEYS = [
    "F1_htf_bias", "F2_qualified_sweep", "F3_m5_choch", "F4_displacement_fvg",
    "F5_poi_correct_zone", "F6_inducement", "F7_target_quality",
    "F8_pool_seniority", "F9_smt_divergence", "F10_session_narrative",
]


@dataclass
class BacktestReport:
    mode: str
    trades_count: int
    win_rate: Optional[float]
    avg_winner_r: Optional[float]
    avg_loser_r: Optional[float]
    expectancy_r: Optional[float]
    total_r: float
    max_drawdown_r: float
    rule_compliance_rate: Optional[float]
    equity_curve: List[dict] = field(default_factory=list)
    trades: List[dict] = field(default_factory=list)
    skips_count: int = 0
    setups_scored_count: int = 0
    factor_pass_rates: Dict[str, float] = field(default_factory=dict)


def build_report(db: Session, mode: Mode) -> BacktestReport:
    trades = list(db.execute(select(TradeRecord).where(TradeRecord.mode == mode.value)).scalars())
    closed = [t for t in trades if t.status == "CLOSED"]
    closed.sort(key=lambda t: t.exit_time or t.filled_time or t.submitted_time)

    summary = build_summary_from_trade_records(closed)

    equity_curve = []
    r_running = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in closed:
        r_running += t.r_result or 0.0
        peak = max(peak, r_running)
        max_dd = max(max_dd, peak - r_running)
        equity_curve.append({
            "time": t.exit_time.isoformat() if t.exit_time else None,
            "cumulative_r": round(r_running, 4),
        })

    skips = list(db.execute(select(SkipRecord).where(SkipRecord.mode == mode.value)).scalars())
    setups = list(db.execute(select(SetupRecord).where(SetupRecord.mode == mode.value)).scalars())

    factor_pass_rates = {}
    scored_setups = [s for s in setups if s.score_json]
    for key in FACTOR_KEYS:
        weight_full = 2 if key in ("F1_htf_bias", "F2_qualified_sweep", "F3_m5_choch") else 1
        if not scored_setups:
            factor_pass_rates[key] = 0.0
            continue
        hits = sum(1 for s in scored_setups if (s.score_json or {}).get(key, 0) == weight_full)
        factor_pass_rates[key] = hits / len(scored_setups)

    return BacktestReport(
        mode=mode.value,
        trades_count=summary.trades_count,
        win_rate=summary.win_rate,
        avg_winner_r=summary.avg_winner_r,
        avg_loser_r=summary.avg_loser_r,
        expectancy_r=summary.expectancy_r,
        total_r=round(r_running, 4),
        max_drawdown_r=round(max_dd, 4),
        rule_compliance_rate=summary.rule_compliance_rate,
        equity_curve=equity_curve,
        trades=[
            {
                "id": t.id, "instrument": t.instrument, "session": t.session, "direction": t.direction,
                "entry_price": t.entry_price, "stop_price": t.initial_stop_price, "tp1_price": t.tp1_price,
                "exit_price": t.exit_price, "close_reason": t.close_reason, "r_result": t.r_result,
                "pnl": t.pnl, "rule_compliance": t.rule_compliance,
                "filled_time": t.filled_time.isoformat() if t.filled_time else None,
                "exit_time": t.exit_time.isoformat() if t.exit_time else None,
            }
            for t in closed
        ],
        skips_count=len(skips),
        setups_scored_count=len(scored_setups),
        factor_pass_rates=factor_pass_rates,
    )
