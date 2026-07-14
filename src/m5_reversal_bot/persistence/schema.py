"""SQLAlchemy ORM schema. SQLite by default (zero external dependency, low
resource footprint); point DATABASE_URL at Postgres for multi-process
production deployments — no code changes required.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mode: Mapped[str] = mapped_column(String(16), index=True)          # BACKTEST|PAPER|DEMO|LIVE
    broker_login: Mapped[str | None] = mapped_column(String(64), nullable=True)
    equity_start_of_day: Mapped[float] = mapped_column(Float, default=0.0)
    equity_current: Mapped[float] = mapped_column(Float, default=0.0)
    high_water_mark_month: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    trades: Mapped[list["TradeRecord"]] = relationship(back_populates="account")


class SetupRecord(Base):
    __tablename__ = "setups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    instrument: Mapped[str] = mapped_column(String(16), index=True)
    session: Mapped[str] = mapped_column(String(16))
    direction: Mapped[str] = mapped_column(String(8))
    mode: Mapped[str] = mapped_column(String(16), index=True)

    sweep_pool_type: Mapped[str] = mapped_column(String(24))
    sweep_price: Mapped[float] = mapped_column(Float)
    sweep_extreme: Mapped[float] = mapped_column(Float)
    choch_close_price: Mapped[float] = mapped_column(Float)
    choch_time: Mapped[datetime] = mapped_column(DateTime)

    poi_source: Mapped[str | None] = mapped_column(String(24), nullable=True)
    poi_entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    dealing_range_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    dealing_range_high: Mapped[float | None] = mapped_column(Float, nullable=True)

    score_json: Mapped[dict] = mapped_column(JSON)
    score_total: Mapped[int] = mapped_column(Integer)
    spine_full: Mapped[bool] = mapped_column(Boolean)
    authorized: Mapped[bool] = mapped_column(Boolean)
    outcome: Mapped[str] = mapped_column(String(24))       # TAKEN|SCORED_SKIP|VOIDED|FILTERED
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    checklist_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    trades: Mapped[list["TradeRecord"]] = relationship(back_populates="setup")


class TradeRecord(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    setup_id: Mapped[int | None] = mapped_column(ForeignKey("setups.id"), nullable=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)

    mode: Mapped[str] = mapped_column(String(16), index=True)
    instrument: Mapped[str] = mapped_column(String(16), index=True)
    session: Mapped[str] = mapped_column(String(16))
    direction: Mapped[str] = mapped_column(String(8))
    entry_method: Mapped[str] = mapped_column(String(24))

    entry_price: Mapped[float] = mapped_column(Float)
    stop_price: Mapped[float] = mapped_column(Float)
    initial_stop_price: Mapped[float] = mapped_column(Float)
    buffer: Mapped[float] = mapped_column(Float)
    tp1_price: Mapped[float] = mapped_column(Float)
    runner_target_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    position_size_lots: Mapped[float] = mapped_column(Float)
    risk_percent: Mapped[float] = mapped_column(Float)

    status: Mapped[str] = mapped_column(String(16), index=True)
    order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    submitted_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    filled_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    tp1_filled_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    be_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    exit_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    close_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    r_result: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl: Mapped[float | None] = mapped_column(Float, nullable=True)

    rule_compliance: Mapped[bool] = mapped_column(Boolean, default=True)
    deviations_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    trail_events_json: Mapped[list | None] = mapped_column(JSON, nullable=True)

    screenshot_entry_path: Mapped[str | None] = mapped_column(String(256), nullable=True)
    screenshot_exit_path: Mapped[str | None] = mapped_column(String(256), nullable=True)

    setup: Mapped[SetupRecord | None] = relationship(back_populates="trades")
    account: Mapped[Account | None] = relationship(back_populates="trades")
    events: Mapped[list["TradeEvent"]] = relationship(back_populates="trade")


class TradeEvent(Base):
    """Append-only audit log — one row per state transition a trade goes
    through, so every trade is fully traceable and auditable end to end."""

    __tablename__ = "trade_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade_id: Mapped[int] = mapped_column(ForeignKey("trades.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    event_type: Mapped[str] = mapped_column(String(48))
    details_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    trade: Mapped[TradeRecord] = relationship(back_populates="events")


class SkipRecord(Base):
    """7.5 — scored skips must be logged with the same rigor as taken trades."""

    __tablename__ = "skips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    mode: Mapped[str] = mapped_column(String(16), index=True)
    instrument: Mapped[str] = mapped_column(String(16), index=True)
    session: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(Text)
    score_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    checklist_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class AccountStateDaily(Base):
    __tablename__ = "account_state_daily"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[str] = mapped_column(String(10), index=True)  # ISO date, GMT
    mode: Mapped[str] = mapped_column(String(16), index=True)
    starting_equity: Mapped[float] = mapped_column(Float)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    trades_count: Mapped[int] = mapped_column(Integer, default=0)
    consecutive_losses_running: Mapped[int] = mapped_column(Integer, default=0)
    session_losses_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    daily_loss_percent: Mapped[float] = mapped_column(Float, default=0.0)
    breaker_tripped: Mapped[bool] = mapped_column(Boolean, default=False)
    in_recovery_mode: Mapped[bool] = mapped_column(Boolean, default=False)


class SystemLog(Base):
    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    level: Mapped[str] = mapped_column(String(16), index=True)
    component: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(Text)
    context_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class StrategyStageLog(Base):
    """Powers the dashboard's step-by-step "what is the bot doing right
    now" transparency panel."""

    __tablename__ = "strategy_stage_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    mode: Mapped[str] = mapped_column(String(16), index=True)
    instrument: Mapped[str] = mapped_column(String(16), index=True)
    stage: Mapped[str] = mapped_column(String(48))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)


class AIInsight(Base):
    """Analytics-only. Nothing here is ever read back by strategy/*."""

    __tablename__ = "ai_insights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    category: Mapped[str] = mapped_column(String(48), index=True)  # performance|execution_quality|anomaly
    metric: Mapped[str] = mapped_column(String(64))
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    detail_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ConnectionHealth(Base):
    __tablename__ = "connection_health"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    component: Mapped[str] = mapped_column(String(48), index=True)  # mt5|data_feed|news_feed|api
    status: Mapped[str] = mapped_column(String(16))                  # UP|DOWN|DEGRADED
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
