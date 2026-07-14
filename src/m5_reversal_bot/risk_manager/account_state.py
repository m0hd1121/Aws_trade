"""Owns the mutable, in-memory (and persisted) account/session state and
turns it into the `AccountSnapshot` that `strategy/risk.py`'s pure
functions consume. One instance per mode — EU and XAU share it, since
Section 8's limits are account-wide except where explicitly
per-instrument (max 1 concurrent position per instrument).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable, Dict, Optional

from ..core.clock import current_session, now_gmt
from ..core.constants import RISK
from ..core.enums import Instrument, Mode, Session
from ..strategy import risk as risk_mod


class AccountStateManager:
    def __init__(self, mode: Mode, initial_equity: float, clock: Callable[[], datetime] = now_gmt):
        self.mode = mode
        self.clock = clock

        self.equity_current = initial_equity
        self.equity_start_of_day = initial_equity
        self.weekly_start_equity = initial_equity
        self.high_water_mark_month = initial_equity

        self.daily_realized_pnl = 0.0
        self.weekly_realized_pnl = 0.0
        self.consecutive_losses_this_session = 0
        self.consecutive_losses_running = 0
        self.trades_this_kill_zone: Dict[Session, int] = {}
        self.trades_today = 0
        self.open_positions: Dict[Instrument, int] = {}
        self.combined_open_risk_percent = 0.0
        self.live_trades_taken_lifetime = 0
        self.in_recovery_mode = False
        self.monthly_brake_active = False
        self.demo_requalification_trades_done = 0

        self._current_day = None
        self._current_week_start = None
        self._current_kz_session: Optional[Session] = None

    # ------------------------------------------------------------------
    def _roll_if_needed(self) -> None:
        now = self.clock()
        day = now.date()
        if self._current_day != day:
            self.equity_start_of_day = self.equity_current
            self.daily_realized_pnl = 0.0
            self.trades_today = 0
            self.trades_this_kill_zone = {}
            self._current_day = day

            monday = day - timedelta(days=day.weekday())
            if self._current_week_start != monday:
                self.weekly_start_equity = self.equity_current
                self.weekly_realized_pnl = 0.0
                self._current_week_start = monday

            self.high_water_mark_month = max(self.high_water_mark_month, self.equity_current)
            self.monthly_brake_active = risk_mod.check_monthly_brake(self.equity_current, self.high_water_mark_month)

        session = current_session(now)
        if session != Session.OUTSIDE_KZ and session != self._current_kz_session:
            self.consecutive_losses_this_session = 0
            self._current_kz_session = session

    # ------------------------------------------------------------------ mutation
    def record_trade_result(self, instrument: Instrument, session: Session, r_result: Optional[float], pnl: float) -> None:
        self._roll_if_needed()
        self.equity_current += pnl
        self.daily_realized_pnl += pnl
        self.weekly_realized_pnl += pnl
        self.trades_today += 1
        self.trades_this_kill_zone[session] = self.trades_this_kill_zone.get(session, 0) + 1
        if self.mode == Mode.LIVE:
            self.live_trades_taken_lifetime += 1

        is_loss = r_result is not None and r_result < 0
        if is_loss:
            self.consecutive_losses_this_session += 1
            self.consecutive_losses_running += 1
        else:
            self.consecutive_losses_running = 0
            self.in_recovery_mode = False  # 8.3 — restore 1.0% risk after the next winner

        if self.consecutive_losses_running >= RISK.consecutive_losses_running_limit:
            self.in_recovery_mode = True

        self.high_water_mark_month = max(self.high_water_mark_month, self.equity_current)
        self.monthly_brake_active = risk_mod.check_monthly_brake(self.equity_current, self.high_water_mark_month)

    def record_position_opened(self, instrument: Instrument, risk_percent: float) -> None:
        self.open_positions[instrument] = self.open_positions.get(instrument, 0) + 1
        self.combined_open_risk_percent += risk_percent

    def record_position_closed(self, instrument: Instrument, risk_percent: float) -> None:
        self.open_positions[instrument] = max(0, self.open_positions.get(instrument, 0) - 1)
        self.combined_open_risk_percent = max(0.0, self.combined_open_risk_percent - risk_percent)

    def record_demo_requalification_trade(self, rule_compliant: bool) -> None:
        if rule_compliant:
            self.demo_requalification_trades_done += 1
        else:
            self.demo_requalification_trades_done = 0  # must be CONSECUTIVE per 8.4

    # ------------------------------------------------------------------ read
    def snapshot(self) -> risk_mod.AccountSnapshot:
        self._roll_if_needed()
        now = self.clock()
        session = current_session(now)
        trades_this_kz = self.trades_this_kill_zone.get(session, 0)

        daily_loss_pct = max(0.0, -self.daily_realized_pnl / self.equity_start_of_day * 100.0) if self.equity_start_of_day else 0.0
        weekly_loss_pct = max(0.0, -self.weekly_realized_pnl / self.weekly_start_equity * 100.0) if self.weekly_start_equity else 0.0
        monthly_dd_pct = (
            (self.high_water_mark_month - self.equity_current) / self.high_water_mark_month * 100.0
            if self.high_water_mark_month else 0.0
        )

        return risk_mod.AccountSnapshot(
            equity_start_of_day=self.equity_start_of_day,
            equity_current=self.equity_current,
            high_water_mark_month=self.high_water_mark_month,
            daily_realized_loss_percent=daily_loss_pct,
            weekly_realized_loss_percent=weekly_loss_pct,
            consecutive_losses_this_session=self.consecutive_losses_this_session,
            consecutive_losses_running=self.consecutive_losses_running,
            trades_this_kill_zone=trades_this_kz,
            trades_today=self.trades_today,
            concurrent_positions_total=sum(self.open_positions.values()),
            concurrent_positions_by_instrument=dict(self.open_positions),
            combined_open_risk_percent=self.combined_open_risk_percent,
            live_trades_taken_lifetime=self.live_trades_taken_lifetime,
            in_recovery_mode=self.in_recovery_mode,
            monthly_drawdown_percent=monthly_dd_pct,
            monthly_brake_active=self.monthly_brake_active,
            demo_requalification_trades_done=self.demo_requalification_trades_done,
        )
