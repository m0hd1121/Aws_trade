"""Bridges the strategy engine's `EngineAction` stream to a concrete
`ExecutionAdapter`, and translates broker-reported fill/stop/TP events back
into engine notifications. This is the only module that touches both the
strategy layer and a broker — the strategy never calls the adapter
directly, and the adapter never makes a trading decision.
"""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Dict, Optional

from sqlalchemy.orm import Session

from ..core.constants import EXITS
from ..core.enums import CloseReason, Direction, TradeStatus
from ..core.models import Trade
from ..persistence import repository
from ..strategy import stop_loss as stop_loss_mod
from ..strategy.engine import EngineAction, EngineActionType, InstrumentEngine
from ..strategy.exits import r_multiple
from ..strategy.risk import VALUE_PER_UNIT_PER_LOT, stop_distance_in_formula_units
from .broker_interface import ExecutionAdapter


class OrderManager:
    def __init__(
        self,
        adapter: ExecutionAdapter,
        mode,
        account_id: Optional[int],
        on_trade_closed: Optional[Callable[[Trade], None]] = None,
    ):
        self.adapter = adapter
        self.mode = mode
        self.account_id = account_id
        self.on_trade_closed = on_trade_closed
        self._db_id_by_trade: Dict[int, int] = {}

    # ------------------------------------------------------------ P&L / R bookkeeping
    def _signed_leg_value(self, trade: Trade, fraction: float, exit_price: float) -> float:
        signed_delta = (exit_price - trade.entry_price) if trade.direction == Direction.LONG else (trade.entry_price - exit_price)
        units = stop_distance_in_formula_units(trade.instrument, signed_delta)
        return units * VALUE_PER_UNIT_PER_LOT[trade.instrument] * (trade.position_size_lots * fraction)

    def _finalize_trade_result(self, trade: Trade) -> None:
        """Computes the blended R-multiple and P&L exactly once, at final
        close — blended 50/50 across the TP1 partial and the runner's exit
        per Section 6.4, or 100% at the stop if TP1 was never reached."""
        if trade.exit_price is None:
            return
        initial_distance = stop_loss_mod.stop_distance(trade.entry_price, trade.initial_stop_price)
        if initial_distance <= 0:
            return
        if trade.tp1_filled_time is not None:
            r_tp1 = r_multiple(trade.direction, trade.entry_price, trade.tp1_price, initial_distance)
            r_final = r_multiple(trade.direction, trade.entry_price, trade.exit_price, initial_distance)
            trade.r_result = EXITS.tp1_partial_close_fraction * r_tp1 + (1 - EXITS.tp1_partial_close_fraction) * r_final
            trade.pnl = self._signed_leg_value(trade, EXITS.tp1_partial_close_fraction, trade.tp1_price) + \
                self._signed_leg_value(trade, 1 - EXITS.tp1_partial_close_fraction, trade.exit_price)
        else:
            trade.r_result = r_multiple(trade.direction, trade.entry_price, trade.exit_price, initial_distance)
            trade.pnl = self._signed_leg_value(trade, 1.0, trade.exit_price)

    # ------------------------------------------------------------ dispatch
    def handle_actions(self, actions, db: Session) -> None:
        for action in actions:
            handler = getattr(self, f"_handle_{action.type.lower()}", None)
            if handler:
                handler(action, db)

    def _record_id(self, trade: Trade):
        return self._db_id_by_trade.get(id(trade))

    # ---------------------------------------------------------------- log-only actions
    def _handle_stage_changed(self, action: EngineAction, db: Session) -> None:
        repository.log_stage(db, self.mode, action.payload["instrument"], action.payload["stage"], action.payload.get("detail"))

    def _handle_day_locked_out(self, action: EngineAction, db: Session) -> None:
        repository.log_system(db, "INFO", "engine", f"day locked out: {action.payload.get('reason')}", action.payload)

    def _handle_kz_skipped(self, action: EngineAction, db: Session) -> None:
        repository.log_system(db, "INFO", "engine", f"KZ skipped: {action.payload.get('reason')}", action.payload)

    def _handle_setup_scored_skip(self, action: EngineAction, db: Session) -> None:
        setup = action.payload["setup"]
        repository.save_setup(db, setup, self.mode)
        repository.save_skip(
            db, setup.created_time, self.mode, setup.instrument.value, setup.session.value,
            "score below 9/12 or spine (F1+F2+F3) incomplete", setup.score.as_dict(),
        )

    def _handle_setup_voided(self, action: EngineAction, db: Session) -> None:
        repository.log_system(db, "INFO", "order_manager", f"setup voided: {action.payload.get('reason')}", action.payload)

    # ---------------------------------------------------------------- order lifecycle
    def _handle_submit_bracket_order(self, action: EngineAction, db: Session) -> None:
        trade: Trade = action.payload["trade"]
        setup = action.payload["setup"]
        valid_until = action.payload["order_valid_until"]

        setup_rec = repository.save_setup(db, setup, self.mode)
        trade_rec = repository.create_trade(db, trade, setup_rec.id, self.account_id)
        self._db_id_by_trade[id(trade)] = trade_rec.id

        result = self.adapter.place_bracket_limit_order(
            trade.instrument, trade.direction, trade.entry_price, trade.stop_price,
            trade.tp1_price, trade.position_size_lots, valid_until,
        )
        if not result.success:
            trade.status = TradeStatus.CANCELLED
            repository.update_trade_from_domain(db, trade_rec.id, trade)
            repository.append_trade_event(db, trade_rec.id, "ORDER_REJECTED", {"error": result.error})
            return

        trade.order_id = result.order_id
        trade.submitted_time = datetime.utcnow()
        repository.update_trade_from_domain(db, trade_rec.id, trade)
        repository.append_trade_event(db, trade_rec.id, "BRACKET_SUBMITTED", {"order_id": result.order_id})

    def _handle_cancel_order(self, action: EngineAction, db: Session) -> None:
        trade: Trade = action.payload["trade"]
        reason = action.payload.get("reason")
        if trade.order_id:
            self.adapter.cancel_order(trade.order_id)
        db_id = self._record_id(trade)
        if db_id:
            repository.update_trade_from_domain(db, db_id, trade)
            repository.append_trade_event(db, db_id, "ORDER_CANCELLED", {"reason": reason})

    def _handle_apply_breakeven(self, action: EngineAction, db: Session) -> None:
        trade: Trade = action.payload["trade"]
        new_stop = action.payload["new_stop"]
        if trade.order_id:
            self.adapter.modify_stop(trade.order_id, new_stop)
        db_id = self._record_id(trade)
        if db_id:
            repository.update_trade_from_domain(db, db_id, trade)
            repository.append_trade_event(db, db_id, "BREAKEVEN_APPLIED", {"new_stop": new_stop})

    def _handle_trail_stop(self, action: EngineAction, db: Session) -> None:
        trade: Trade = action.payload["trade"]
        new_stop = action.payload["new_stop"]
        if trade.order_id:
            self.adapter.modify_stop(trade.order_id, new_stop)
        db_id = self._record_id(trade)
        if db_id:
            repository.update_trade_from_domain(db, db_id, trade)
            repository.append_trade_event(db, db_id, "STOP_TRAILED", {"new_stop": new_stop})

    def _handle_close_all(self, action: EngineAction, db: Session) -> None:
        trade: Trade = action.payload["trade"]
        reason = action.payload["reason"]
        if trade.order_id:
            result = self.adapter.close_position(trade.order_id)
            if result.success:
                trade.exit_price = result.fill_price
                trade.exit_time = result.fill_time
        trade.status = TradeStatus.CLOSED
        trade.close_reason = reason if isinstance(reason, CloseReason) else CloseReason(reason)
        self._finalize_trade_result(trade)
        db_id = self._record_id(trade)
        if db_id:
            repository.update_trade_from_domain(db, db_id, trade)
            repository.append_trade_event(db, db_id, "TRADE_CLOSED", {
                "reason": trade.close_reason.value, "event": action.payload.get("event"),
                "r_result": trade.r_result, "pnl": trade.pnl,
            })
        if self.on_trade_closed:
            self.on_trade_closed(trade)

    def _handle_log_trade(self, action: EngineAction, db: Session) -> None:
        trade: Trade = action.payload["trade"]
        if trade.r_result is None:
            self._finalize_trade_result(trade)
        db_id = self._record_id(trade)
        if db_id:
            repository.update_trade_from_domain(db, db_id, trade)
            repository.append_trade_event(db, db_id, "TRADE_LOGGED", {
                "rule_compliance": trade.rule_compliance, "r_result": trade.r_result, "pnl": trade.pnl,
            })
        if self.on_trade_closed:
            self.on_trade_closed(trade)

    # ------------------------------------------------------------ fill polling
    def poll_fills(self, engine: InstrumentEngine, db: Session, at_time: datetime) -> None:
        """Call periodically (paper/live/demo) between candle closes to
        translate adapter-reported fill/stop/TP events into engine calls,
        whose resulting EngineActions are executed immediately after."""
        events = self.adapter.pump(engine.instrument, at_time)
        for ev in events:
            self._translate_event(ev, engine, db)

    def _translate_event(self, ev: dict, engine: InstrumentEngine, db: Session) -> None:
        if ev["type"] == "FILLED":
            trade = engine.pending_trade
            actions = engine.on_order_filled(ev["fill_price"], ev["time"])
            if trade:
                trade.order_id = ev["position_id"]
            self.handle_actions(actions, db)

        elif ev["type"] == "TP_HIT":
            trade = engine.active_trade
            if trade is None:
                return
            self.adapter.close_position_fraction(ev["position_id"], EXITS.tp1_partial_close_fraction)
            if trade.runner_target_price is not None:
                self.adapter.modify_target(ev["position_id"], trade.runner_target_price)
            else:
                self.adapter.modify_target(ev["position_id"], None)
            spread = self.adapter.get_current_spread(engine.instrument)
            actions = engine.on_tp1_filled(ev["time"], spread)
            self.handle_actions(actions, db)

        elif ev["type"] == "STOP_HIT":
            actions = engine.on_trade_closed(ev["price"], ev["time"], CloseReason.STOP_LOSS)
            self.handle_actions(actions, db)

        elif ev["type"] == "EXPIRED":
            # Authoritative cancellation happens via the engine's own
            # per-candle order-validity check (2.3); this is log-only.
            repository.log_system(db, "INFO", "order_manager", "adapter reported order expiry", ev)
