"""Shared fill-simulation bookkeeping for PAPER and BACKTEST adapters.
Both simulate against the identical mechanics — the only difference is
where price updates come from (a live feed's ticks vs. historical bars).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from ..core.enums import Direction, Instrument
from .broker_interface import OrderResult


@dataclass
class SimOrder:
    order_id: str
    instrument: Instrument
    direction: Direction
    entry_price: float
    stop_price: float
    tp1_price: float
    volume: float
    valid_until: datetime
    status: str = "PENDING"  # PENDING | FILLED | CANCELLED | EXPIRED


@dataclass
class SimPosition:
    position_id: str
    instrument: Instrument
    direction: Direction
    volume: float
    open_price: float
    stop_price: float
    tp_price: Optional[float]
    unrealized_pnl: float = 0.0


class SimulationBroker:
    def __init__(self, initial_equity: float, spread_model: Dict[str, float], slippage_model: Dict[str, float]):
        self.equity = initial_equity
        self.balance = initial_equity
        self.spread_model = spread_model
        self.slippage_model = slippage_model
        self.orders: Dict[str, SimOrder] = {}
        self.positions: Dict[str, SimPosition] = {}
        self._next_id = 1000

    def _new_id(self) -> str:
        self._next_id += 1
        return str(self._next_id)

    def spread_for(self, instrument: Instrument) -> float:
        return self.spread_model.get(instrument.value, 0.0)

    def slippage_for(self, instrument: Instrument) -> float:
        return self.slippage_model.get(instrument.value, 0.0)

    def place_limit(self, instrument, direction, entry_price, stop_price, tp1_price, volume, valid_until) -> OrderResult:
        oid = self._new_id()
        self.orders[oid] = SimOrder(oid, instrument, direction, entry_price, stop_price, tp1_price, volume, valid_until)
        return OrderResult(success=True, order_id=oid, filled=False, fill_price=None, fill_time=None)

    def place_market(self, instrument, direction, stop_price, tp1_price, volume, bid, ask, time) -> OrderResult:
        price = ask if direction == Direction.LONG else bid
        slip = self.slippage_for(instrument)
        fill_price = price + slip if direction == Direction.LONG else price - slip
        pid = self._new_id()
        self.positions[pid] = SimPosition(pid, instrument, direction, volume, fill_price, stop_price, tp1_price)
        return OrderResult(success=True, order_id=pid, filled=True, fill_price=fill_price, fill_time=time)

    def cancel(self, order_id: str) -> bool:
        o = self.orders.get(order_id)
        if o and o.status == "PENDING":
            o.status = "CANCELLED"
            return True
        return False

    def order_status(self, order_id: str) -> OrderResult:
        o = self.orders.get(order_id)
        if o is None:
            return OrderResult(success=False, order_id=order_id, filled=False, fill_price=None, fill_time=None, error="unknown order")
        if o.status == "FILLED":
            return OrderResult(success=True, order_id=order_id, filled=True, fill_price=o.entry_price, fill_time=None)
        if o.status == "PENDING":
            return OrderResult(success=True, order_id=order_id, filled=False, fill_price=None, fill_time=None)
        return OrderResult(success=False, order_id=order_id, filled=False, fill_price=None, fill_time=None, error=o.status)

    def modify_stop(self, position_id: str, new_stop: float) -> bool:
        p = self.positions.get(position_id)
        if p is None:
            return False
        p.stop_price = new_stop
        return True

    def modify_target(self, position_id: str, new_tp: Optional[float]) -> bool:
        p = self.positions.get(position_id)
        if p is None:
            return False
        p.tp_price = new_tp
        return True

    def close_fraction(self, position_id: str, fraction: float, bid: float, ask: float, time: datetime) -> OrderResult:
        p = self.positions.get(position_id)
        if p is None:
            return OrderResult(success=False, order_id=position_id, filled=False, fill_price=None, fill_time=None, error="unknown position")
        close_price = bid if p.direction == Direction.LONG else ask
        closed_volume = round(p.volume * fraction, 8)
        pnl_per_unit = (close_price - p.open_price) if p.direction == Direction.LONG else (p.open_price - close_price)
        realized = pnl_per_unit * closed_volume
        self.balance += realized
        self.equity += realized
        p.volume = round(p.volume - closed_volume, 8)
        if p.volume <= 1e-9:
            del self.positions[position_id]
        return OrderResult(success=True, order_id=position_id, filled=True, fill_price=close_price, fill_time=time)

    def process_bar(self, instrument: Instrument, high: float, low: float, close: float, spread: float, time: datetime) -> List[dict]:
        """Backtest fill simulation using the bar's full range, not just its
        close — a resting limit or a stop can be touched intrabar. Modeling
        convention: if a bar's range could have hit both the stop and TP,
        the stop is assumed to have been hit first (the standard
        conservative backtest convention; it does not change any strategy
        rule, only how an ambiguous single bar is resolved when replaying
        history)."""
        events: List[dict] = []
        for oid, o in list(self.orders.items()):
            if o.status != "PENDING" or o.instrument != instrument:
                continue
            if time > o.valid_until:
                o.status = "EXPIRED"
                events.append({"type": "EXPIRED", "order_id": oid, "time": time})
                continue
            filled = (o.direction == Direction.LONG and low <= o.entry_price) or (
                o.direction == Direction.SHORT and high >= o.entry_price
            )
            if filled:
                o.status = "FILLED"
                pid = oid
                self.positions[pid] = SimPosition(pid, o.instrument, o.direction, o.volume, o.entry_price, o.stop_price, o.tp1_price)
                events.append({"type": "FILLED", "order_id": oid, "position_id": pid, "fill_price": o.entry_price, "time": time})

        for pid, p in list(self.positions.items()):
            if p.instrument != instrument:
                continue
            if p.direction == Direction.LONG:
                hit_stop = low <= p.stop_price
                hit_tp = p.tp_price is not None and high >= p.tp_price
            else:
                hit_stop = high >= p.stop_price
                hit_tp = p.tp_price is not None and low <= p.tp_price
            if hit_stop:
                events.append({"type": "STOP_HIT", "position_id": pid, "price": p.stop_price, "time": time})
            elif hit_tp:
                events.append({"type": "TP_HIT", "position_id": pid, "price": p.tp_price, "time": time})
        return events

    def process_price(self, instrument: Instrument, bid: float, ask: float, time: datetime) -> List[dict]:
        events: List[dict] = []
        for oid, o in list(self.orders.items()):
            if o.status != "PENDING" or o.instrument != instrument:
                continue
            if time > o.valid_until:
                o.status = "EXPIRED"
                events.append({"type": "EXPIRED", "order_id": oid, "time": time})
                continue
            filled = (o.direction == Direction.LONG and ask <= o.entry_price) or (
                o.direction == Direction.SHORT and bid >= o.entry_price
            )
            if filled:
                o.status = "FILLED"
                pid = oid
                self.positions[pid] = SimPosition(pid, o.instrument, o.direction, o.volume, o.entry_price, o.stop_price, o.tp1_price)
                events.append({"type": "FILLED", "order_id": oid, "position_id": pid, "fill_price": o.entry_price, "time": time})

        for pid, p in list(self.positions.items()):
            if p.instrument != instrument:
                continue
            if p.direction == Direction.LONG:
                if bid <= p.stop_price:
                    events.append({"type": "STOP_HIT", "position_id": pid, "price": p.stop_price, "time": time})
                elif p.tp_price is not None and bid >= p.tp_price:
                    events.append({"type": "TP_HIT", "position_id": pid, "price": p.tp_price, "time": time})
            else:
                if ask >= p.stop_price:
                    events.append({"type": "STOP_HIT", "position_id": pid, "price": p.stop_price, "time": time})
                elif p.tp_price is not None and ask <= p.tp_price:
                    events.append({"type": "TP_HIT", "position_id": pid, "price": p.tp_price, "time": time})
        return events
