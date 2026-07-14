"""Configuration Management — operational config only (mode, enabled
instruments, poll cadence, dashboard settings). Strategy rule numbers live
in core/constants.py, hash-locked against the rulebook, and are exposed
here read-only for transparency — never writable through this API.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..core.constants import EU, EXITS, NEWS, RISK, SCORING, STRUCTURE, XAU
from .schemas import ConfigUpdateRequest
from .state import get_controller

router = APIRouter()


@router.get("/")
def get_operational_config():
    return get_controller().config.raw


@router.put("/")
def update_operational_config(body: ConfigUpdateRequest):
    try:
        return get_controller().update_config(body.config)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/strategy-rules")
def get_strategy_rules_readonly():
    """Read-only view of the frozen strategy constants, for dashboard
    transparency. There is no corresponding PUT — see
    docs/STRATEGY_INTEGRITY.md for how the rulebook may legitimately change."""
    return {
        "scoring": {
            "min_score_to_trade": SCORING.min_score_to_trade,
            "max_score": SCORING.max_score,
            "target_quality_min_r": SCORING.target_quality_min_r,
            "pool_seniority_min_age_hours": SCORING.pool_seniority_min_age_hours,
        },
        "structure": {
            "swing_fractal_lookback": STRUCTURE.swing_fractal_lookback,
            "displacement_body_lookback": STRUCTURE.displacement_body_lookback,
            "choch_max_candles_from_sweep": STRUCTURE.choch_max_candles_from_sweep,
        },
        "exits": {
            "tp1_r_multiple": EXITS.tp1_r_multiple,
            "tp1_pool_window_max_r": EXITS.tp1_pool_window_max_r,
            "tp1_partial_close_fraction": EXITS.tp1_partial_close_fraction,
        },
        "risk": {
            "normal_risk_percent": RISK.normal_risk_percent,
            "evaluation_risk_percent": RISK.evaluation_risk_percent,
            "max_daily_loss_percent": RISK.max_daily_loss_percent,
            "max_weekly_loss_percent": RISK.max_weekly_loss_percent,
            "max_trades_per_kill_zone": RISK.max_trades_per_kill_zone,
            "max_trades_per_day": RISK.max_trades_per_day,
            "monthly_drawdown_brake_percent": RISK.monthly_drawdown_brake_percent,
        },
        "instruments": {
            "EURUSD": {
                "stop_distance_min_pips": EU.stop_distance_min / EU.pip_value_in_price,
                "stop_distance_max_pips": EU.stop_distance_max / EU.pip_value_in_price,
                "asia_range_min_pips": EU.asia_range_min / EU.pip_value_in_price,
                "asia_range_max_pips": EU.asia_range_max / EU.pip_value_in_price,
                "max_spread_pips": EU.max_spread / EU.pip_value_in_price,
            },
            "XAUUSD": {
                "stop_distance_min": XAU.stop_distance_min,
                "stop_distance_max": XAU.stop_distance_max,
                "asia_range_min": XAU.asia_range_min,
                "asia_range_max": XAU.asia_range_max,
                "max_spread": XAU.max_spread,
            },
        },
    }
