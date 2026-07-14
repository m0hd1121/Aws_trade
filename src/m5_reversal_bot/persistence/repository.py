"""Typed persistence operations. Converts between the strategy layer's pure
dataclasses (core/models.py) and the ORM (schema.py). `trade_events` is
append-only by convention — callers only ever INSERT into it, never update
or delete, which is what makes a trade's history auditable end to end.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.enums import Mode
from ..core.models import Setup, Trade
from .schema import (
    Account,
    AccountStateDaily,
    AIInsight,
    ConnectionHealth,
    SetupRecord,
    SkipRecord,
    StrategyStageLog,
    SystemLog,
    TradeEvent,
    TradeRecord,
)


# ---------------------------------------------------------------- accounts
def get_or_create_account(db: Session, mode: Mode, initial_equity: float) -> Account:
    acct = db.execute(select(Account).where(Account.mode == mode.value)).scalars().first()
    if acct is None:
        acct = Account(
            mode=mode.value,
            equity_start_of_day=initial_equity,
            equity_current=initial_equity,
            high_water_mark_month=initial_equity,
        )
        db.add(acct)
        db.flush()
    return acct


# ------------------------------------------------------------------ setups
def save_setup(db: Session, setup: Setup, mode: Mode) -> SetupRecord:
    rec = SetupRecord(
        created_time=setup.created_time,
        instrument=setup.instrument.value,
        session=setup.session.value,
        direction=setup.direction.value,
        mode=mode.value,
        sweep_pool_type=setup.sweep.pool.pool_type.value,
        sweep_price=setup.sweep.pool.price,
        sweep_extreme=setup.sweep.sweep_extreme_price,
        choch_close_price=setup.choch.close_price,
        choch_time=setup.choch.confirm_candle_time,
        poi_source=setup.poi.source.value if setup.poi else None,
        poi_entry_price=setup.poi.entry_price if setup.poi else None,
        dealing_range_low=setup.dealing_range.low if setup.dealing_range else None,
        dealing_range_high=setup.dealing_range.high if setup.dealing_range else None,
        score_json=setup.score.as_dict(),
        score_total=setup.score.total,
        spine_full=setup.score.spine_full,
        authorized=setup.score.authorized,
        outcome=setup.outcome.value,
        void_reason=setup.void_reason,
    )
    db.add(rec)
    db.flush()
    return rec


def save_skip(
    db: Session, timestamp: datetime, mode: Mode, instrument: str, session_name: str,
    reason: str, score_json: Optional[dict] = None, checklist_json: Optional[dict] = None,
) -> SkipRecord:
    rec = SkipRecord(
        timestamp=timestamp, mode=mode.value, instrument=instrument, session=session_name,
        reason=reason, score_json=score_json, checklist_json=checklist_json,
    )
    db.add(rec)
    db.flush()
    return rec


# ------------------------------------------------------------------ trades
def create_trade(db: Session, trade: Trade, setup_id: Optional[int], account_id: Optional[int]) -> TradeRecord:
    rec = TradeRecord(
        setup_id=setup_id,
        account_id=account_id,
        mode=trade.mode.value,
        instrument=trade.instrument.value,
        session=trade.session.value,
        direction=trade.direction.value,
        entry_method=trade.entry_method.value,
        entry_price=trade.entry_price,
        stop_price=trade.stop_price,
        initial_stop_price=trade.initial_stop_price,
        buffer=trade.buffer,
        tp1_price=trade.tp1_price,
        runner_target_price=trade.runner_target_price,
        position_size_lots=trade.position_size_lots,
        risk_percent=trade.risk_percent,
        status=trade.status.value,
        order_id=trade.order_id,
        submitted_time=trade.submitted_time,
        rule_compliance=trade.rule_compliance,
        deviations_json=trade.deviations,
        trail_events_json=trade.trail_events,
    )
    db.add(rec)
    db.flush()
    append_trade_event(db, rec.id, "TRADE_CREATED", {"status": trade.status.value})
    return rec


def update_trade_from_domain(db: Session, trade_record_id: int, trade: Trade) -> None:
    rec = db.get(TradeRecord, trade_record_id)
    if rec is None:
        return
    rec.stop_price = trade.stop_price
    rec.status = trade.status.value
    rec.filled_time = trade.filled_time
    rec.tp1_filled_time = trade.tp1_filled_time
    rec.be_applied = trade.be_applied
    rec.exit_time = trade.exit_time
    rec.exit_price = trade.exit_price
    rec.close_reason = trade.close_reason.value if trade.close_reason else None
    rec.r_result = trade.r_result
    rec.pnl = trade.pnl
    rec.rule_compliance = trade.rule_compliance
    rec.deviations_json = trade.deviations
    rec.trail_events_json = trade.trail_events
    db.flush()


def append_trade_event(db: Session, trade_id: int, event_type: str, details: Optional[dict] = None) -> None:
    db.add(TradeEvent(trade_id=trade_id, timestamp=datetime.utcnow(), event_type=event_type, details_json=details))
    db.flush()


def list_open_trades(db: Session, mode: Mode) -> List[TradeRecord]:
    return list(
        db.execute(
            select(TradeRecord).where(TradeRecord.mode == mode.value, TradeRecord.status.in_(["OPEN", "PARTIAL", "PENDING"]))
        ).scalars()
    )


def list_recent_trades(db: Session, mode: Mode, limit: int = 100) -> List[TradeRecord]:
    return list(
        db.execute(
            select(TradeRecord).where(TradeRecord.mode == mode.value).order_by(TradeRecord.id.desc()).limit(limit)
        ).scalars()
    )


def list_recent_skips(db: Session, mode: Mode, limit: int = 100) -> List[SkipRecord]:
    return list(
        db.execute(select(SkipRecord).where(SkipRecord.mode == mode.value).order_by(SkipRecord.id.desc()).limit(limit)).scalars()
    )


# ------------------------------------------------------------- account state
def get_or_create_daily_state(db: Session, date_iso: str, mode: Mode, starting_equity: float) -> AccountStateDaily:
    rec = db.execute(
        select(AccountStateDaily).where(AccountStateDaily.date == date_iso, AccountStateDaily.mode == mode.value)
    ).scalars().first()
    if rec is None:
        rec = AccountStateDaily(date=date_iso, mode=mode.value, starting_equity=starting_equity)
        db.add(rec)
        db.flush()
    return rec


# --------------------------------------------------------------------- logs
def log_system(db: Session, level: str, component: str, message: str, context: Optional[dict] = None) -> None:
    db.add(SystemLog(level=level, component=component, message=message, context_json=context))
    db.flush()


def log_stage(db: Session, mode: Mode, instrument: str, stage: str, detail: Optional[str] = None) -> None:
    db.add(StrategyStageLog(mode=mode.value, instrument=instrument, stage=stage, detail=detail))
    db.flush()


def list_recent_stage_logs(db: Session, mode: Mode, limit: int = 200) -> List[StrategyStageLog]:
    return list(
        db.execute(
            select(StrategyStageLog).where(StrategyStageLog.mode == mode.value).order_by(StrategyStageLog.id.desc()).limit(limit)
        ).scalars()
    )


def log_ai_insight(db: Session, category: str, metric: str, value: Optional[float], detail: Optional[dict] = None) -> None:
    db.add(AIInsight(category=category, metric=metric, value=value, detail_json=detail))
    db.flush()


def log_connection_health(db: Session, component: str, status: str, latency_ms: Optional[float] = None, detail: Optional[str] = None) -> None:
    db.add(ConnectionHealth(component=component, status=status, latency_ms=latency_ms, detail=detail))
    db.flush()


def latest_connection_health(db: Session) -> List[ConnectionHealth]:
    """Most recent status row per component."""
    all_rows = db.execute(select(ConnectionHealth).order_by(ConnectionHealth.id.desc()).limit(200)).scalars()
    seen = set()
    latest = []
    for row in all_rows:
        if row.component in seen:
            continue
        seen.add(row.component)
        latest.append(row)
    return latest
