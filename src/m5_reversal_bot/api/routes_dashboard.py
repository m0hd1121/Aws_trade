"""Dashboard read endpoints — status, positions, trades, P&L/drawdown,
risk metrics, trade history, strategy execution log, system health,
connection status, AI insights.
"""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter
from sqlalchemy import select

from ..ai.analytics import build_summary_from_trade_records
from ..core.enums import Mode
from ..persistence import db, repository
from ..persistence.schema import AIInsight
from .state import get_controller

router = APIRouter()


def _mode() -> Mode:
    return Mode(get_controller().config.mode)


@router.get("/status")
def dashboard_status():
    return get_controller().status()


@router.get("/account")
def account_info():
    controller = get_controller()
    if controller.runner and controller.runner.adapter and controller.runner.adapter.is_connected():
        info = controller.runner.adapter.get_account_info()
        return {"equity": info.equity, "balance": info.balance, "currency": info.currency, "margin_free": info.margin_free}
    return {}


@router.get("/positions")
def open_positions():
    controller = get_controller()
    if not controller.runner or not controller.runner.adapter:
        return []
    try:
        positions = controller.runner.adapter.get_open_positions()
    except Exception:
        return []
    return [
        {
            "position_id": p.position_id, "instrument": p.instrument.value, "direction": p.direction.value,
            "volume": p.volume, "open_price": p.open_price, "stop_price": p.stop_price,
            "tp_price": p.tp_price, "unrealized_pnl": p.unrealized_pnl,
        }
        for p in positions
    ]


def _serialize_trade(t) -> dict:
    return {
        "id": t.id, "mode": t.mode, "instrument": t.instrument, "session": t.session, "direction": t.direction,
        "entry_method": t.entry_method, "entry_price": t.entry_price, "stop_price": t.stop_price,
        "initial_stop_price": t.initial_stop_price, "tp1_price": t.tp1_price,
        "runner_target_price": t.runner_target_price, "position_size_lots": t.position_size_lots,
        "risk_percent": t.risk_percent, "status": t.status, "be_applied": t.be_applied,
        "filled_time": t.filled_time.isoformat() if t.filled_time else None,
        "tp1_filled_time": t.tp1_filled_time.isoformat() if t.tp1_filled_time else None,
        "exit_time": t.exit_time.isoformat() if t.exit_time else None,
        "exit_price": t.exit_price, "close_reason": t.close_reason, "r_result": t.r_result, "pnl": t.pnl,
        "rule_compliance": t.rule_compliance, "trail_events": t.trail_events_json,
    }


@router.get("/trades/open")
def open_trades(limit: int = 100):
    with db.session_scope() as s:
        return [_serialize_trade(t) for t in repository.list_open_trades(s, _mode())][:limit]


@router.get("/trades/closed")
def closed_trades(limit: int = 200):
    with db.session_scope() as s:
        recs = repository.list_recent_trades(s, _mode(), limit=5000)
        closed = [t for t in recs if t.status == "CLOSED"]
        return [_serialize_trade(t) for t in closed][:limit]


@router.get("/trades/skips")
def skips(limit: int = 100):
    with db.session_scope() as s:
        recs = repository.list_recent_skips(s, _mode(), limit)
        return [
            {"id": r.id, "timestamp": r.timestamp.isoformat(), "instrument": r.instrument, "session": r.session,
             "reason": r.reason, "score": r.score_json}
            for r in recs
        ]


@router.get("/performance")
def performance():
    with db.session_scope() as s:
        recs = repository.list_recent_trades(s, _mode(), limit=100000)
        summary = build_summary_from_trade_records(recs)
        return asdict(summary)


@router.get("/equity-curve")
def equity_curve(limit: int = 500):
    with db.session_scope() as s:
        recs = repository.list_recent_trades(s, _mode(), limit=100000)
        closed = [t for t in recs if t.status == "CLOSED" and (t.exit_time or t.filled_time)]
        closed.sort(key=lambda t: t.exit_time or t.filled_time)
        curve = []
        r_running = 0.0
        peak = 0.0
        max_dd = 0.0
        for t in closed:
            r_running += t.r_result or 0.0
            peak = max(peak, r_running)
            dd = peak - r_running
            max_dd = max(max_dd, dd)
            curve.append({
                "time": (t.exit_time or t.filled_time).isoformat(),
                "cumulative_r": round(r_running, 4),
                "drawdown_r": round(dd, 4),
            })
        return {"curve": curve[-limit:], "max_drawdown_r": round(max_dd, 4)}


@router.get("/execution-log")
def execution_log(limit: int = 200):
    """Strategy execution transparency — step-by-step stage log."""
    with db.session_scope() as s:
        rows = repository.list_recent_stage_logs(s, _mode(), limit)
        return [
            {"timestamp": r.timestamp.isoformat(), "instrument": r.instrument, "stage": r.stage, "detail": r.detail}
            for r in rows
        ]


@router.get("/system-logs")
def system_logs(limit: int = 200):
    from ..persistence.schema import SystemLog

    with db.session_scope() as s:
        rows = list(s.execute(select(SystemLog).order_by(SystemLog.id.desc()).limit(limit)).scalars())
        return [
            {"timestamp": r.timestamp.isoformat(), "level": r.level, "component": r.component,
             "message": r.message, "context": r.context_json}
            for r in rows
        ]


@router.get("/connection-health")
def connection_health():
    with db.session_scope() as s:
        rows = repository.latest_connection_health(s)
        return [
            {"component": r.component, "status": r.status, "latency_ms": r.latency_ms,
             "detail": r.detail, "timestamp": r.timestamp.isoformat()}
            for r in rows
        ]


@router.get("/ai-insights")
def ai_insights(limit: int = 100):
    with db.session_scope() as s:
        rows = list(s.execute(select(AIInsight).order_by(AIInsight.id.desc()).limit(limit)).scalars())
        return [
            {"timestamp": r.timestamp.isoformat(), "category": r.category, "metric": r.metric,
             "value": r.value, "detail": r.detail_json}
            for r in rows
        ]
