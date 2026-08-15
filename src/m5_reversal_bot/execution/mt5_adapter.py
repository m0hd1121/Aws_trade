"""Live/demo order execution via the official `MetaTrader5` python package
(`mt5.order_send`, `mt5.positions_get`, etc.) — or, in
`bridge_mode="mt5linux"`, the same calls proxied to a remote MT5 terminal
over the `mt5linux` RPyC bridge (see data/mt5_feed.py for the full
rationale). Either way this is the MT5 **API**, talking to the broker's
trade server through the terminal's IPC channel; nothing here ever opens
or clicks anything in a desktop terminal UI. The same adapter class
serves both DEMO and LIVE modes — the account credentials (and therefore
whether it's a demo or funded account) come entirely from which MT5
login the settings point at (see .env / MT5_LOGIN, or POST
/api/bot/broker-connect for live updates from the dashboard).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from ..core.config import MT5Settings
from ..core.enums import Direction, Instrument
from .broker_interface import AccountInfo, ExecutionAdapter, OrderResult, PositionInfo


class MT5AdapterError(RuntimeError):
    pass


class MT5ExecutionAdapter(ExecutionAdapter):
    def __init__(self, settings: MT5Settings, symbol_map: dict):
        self._settings = settings
        self._symbol_map = symbol_map
        self._mt5 = None

    def _import_mt5(self):
        if self._mt5 is None:
            if self._settings.bridge_mode == "mt5linux":
                try:
                    from mt5linux import MetaTrader5 as _MT5Bridge
                except ImportError as e:
                    raise MT5AdapterError(
                        "mt5linux package is not installed. Run `pip install mt5linux` "
                        "and point MT5_BRIDGE_HOST/MT5_BRIDGE_PORT at the Wine+MT5 "
                        "bridge container — see docker/docker-compose.mt5-bridge.yml."
                    ) from e
                # mt5linux calls rpyc.classic.connect() with no config, so
                # there is no API to pass a per-connection timeout through.
                # RPyC reads its default from this dict at connect time, so
                # raising it here is the available lever. Needed because the
                # first thing mt5linux does after connecting is
                # `import MetaTrader5` on the Wine side, which routinely
                # exceeds RPyC's 30s default and then fails as an opaque
                # "TimeoutError: result expired".
                try:
                    from rpyc.core.protocol import DEFAULT_CONFIG

                    DEFAULT_CONFIG["sync_request_timeout"] = self._settings.bridge_request_timeout
                except Exception:  # pragma: no cover - rpyc internals moved
                    pass
                self._mt5 = _MT5Bridge(host=self._settings.bridge_host, port=self._settings.bridge_port)
            else:
                try:
                    import MetaTrader5 as mt5  # noqa: N814
                except ImportError as e:
                    raise MT5AdapterError(
                        "MetaTrader5 python package unavailable — Windows/Wine host required, "
                        "or set MT5_BRIDGE_MODE=mt5linux to talk to a remote bridge instead. "
                        "See docs/DEPLOYMENT.md."
                    ) from e
                self._mt5 = mt5
        return self._mt5

    def _symbol(self, instrument: Instrument) -> str:
        return self._symbol_map.get(instrument.value, instrument.value)

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=2, max=16))
    def connect(self) -> None:
        mt5 = self._import_mt5()
        kwargs = {}
        if self._settings.bridge_mode == "local" and self._settings.terminal_path:
            kwargs["path"] = self._settings.terminal_path
        if not mt5.initialize(**kwargs):
            raise MT5AdapterError(f"MT5 initialize() failed: {mt5.last_error()}")
        if self._settings.login and self._settings.password and self._settings.server:
            if not mt5.login(
                self._settings.login, password=self._settings.password, server=self._settings.server,
                timeout=self._settings.timeout_ms,
            ):
                mt5.shutdown()
                raise MT5AdapterError(f"MT5 login() failed: {mt5.last_error()}")

    def disconnect(self) -> None:
        if self._mt5 is not None:
            self._mt5.shutdown()

    def is_connected(self) -> bool:
        return self._mt5 is not None and self._mt5.terminal_info() is not None

    def get_account_info(self) -> AccountInfo:
        mt5 = self._import_mt5()
        info = mt5.account_info()
        if info is None:
            raise MT5AdapterError(f"account_info() failed: {mt5.last_error()}")
        return AccountInfo(equity=info.equity, balance=info.balance, currency=info.currency, margin_free=info.margin_free)

    def get_open_positions(self) -> List[PositionInfo]:
        mt5 = self._import_mt5()
        positions = mt5.positions_get()
        if positions is None:
            return []
        out = []
        for p in positions:
            instrument = next((i for i in Instrument if self._symbol(i) == p.symbol), None)
            if instrument is None:
                continue
            out.append(
                PositionInfo(
                    position_id=str(p.ticket),
                    instrument=instrument,
                    direction=Direction.LONG if p.type == mt5.ORDER_TYPE_BUY else Direction.SHORT,
                    volume=p.volume,
                    open_price=p.price_open,
                    stop_price=p.sl or None,
                    tp_price=p.tp or None,
                    unrealized_pnl=p.profit,
                )
            )
        return out

    def place_bracket_limit_order(self, instrument, direction, entry_price, stop_price, tp1_price, volume, valid_until) -> OrderResult:
        mt5 = self._import_mt5()
        symbol = self._symbol(instrument)
        order_type = mt5.ORDER_TYPE_BUY_LIMIT if direction == Direction.LONG else mt5.ORDER_TYPE_SELL_LIMIT
        request = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": entry_price,
            "sl": stop_price,
            "tp": tp1_price,
            "type_time": mt5.ORDER_TIME_SPECIFIED,
            "expiration": int(valid_until.timestamp()),
            "type_filling": mt5.ORDER_FILLING_RETURN,
            "comment": "M5-Liquidity-Reversal",
        }
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            return OrderResult(success=False, order_id=None, filled=False, fill_price=None, fill_time=None,
                                error=f"order_send failed: {result.retcode if result else mt5.last_error()}")
        return OrderResult(success=True, order_id=str(result.order), filled=False, fill_price=None, fill_time=None)

    def place_bracket_market_order(self, instrument, direction, stop_price, tp1_price, volume) -> OrderResult:
        mt5 = self._import_mt5()
        symbol = self._symbol(instrument)
        tick = mt5.symbol_info_tick(symbol)
        price = tick.ask if direction == Direction.LONG else tick.bid
        order_type = mt5.ORDER_TYPE_BUY if direction == Direction.LONG else mt5.ORDER_TYPE_SELL
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": stop_price,
            "tp": tp1_price,
            "type_filling": mt5.ORDER_FILLING_IOC,
            "comment": "M5-Liquidity-Reversal-Confirmation",
        }
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            return OrderResult(success=False, order_id=None, filled=False, fill_price=None, fill_time=None,
                                error=f"order_send failed: {result.retcode if result else mt5.last_error()}")
        return OrderResult(success=True, order_id=str(result.order), filled=True, fill_price=result.price,
                            fill_time=datetime.now(timezone.utc))

    def cancel_order(self, order_id: str) -> bool:
        mt5 = self._import_mt5()
        request = {"action": mt5.TRADE_ACTION_REMOVE, "order": int(order_id)}
        result = mt5.order_send(request)
        return result is not None and result.retcode == mt5.TRADE_RETCODE_DONE

    def poll_order_status(self, order_id: str) -> OrderResult:
        mt5 = self._import_mt5()
        orders = mt5.orders_get(ticket=int(order_id))
        if orders:
            return OrderResult(success=True, order_id=order_id, filled=False, fill_price=None, fill_time=None)
        deals = mt5.history_deals_get(position=int(order_id))
        if deals:
            d = deals[0]
            return OrderResult(success=True, order_id=order_id, filled=True, fill_price=d.price,
                                fill_time=datetime.fromtimestamp(d.time, tz=timezone.utc))
        return OrderResult(success=False, order_id=order_id, filled=False, fill_price=None, fill_time=None,
                            error="order not found (may have been cancelled/expired)")

    def modify_stop(self, position_id: str, new_stop_price: float) -> bool:
        mt5 = self._import_mt5()
        positions = mt5.positions_get(ticket=int(position_id))
        if not positions:
            return False
        p = positions[0]
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": p.symbol,
            "position": p.ticket,
            "sl": new_stop_price,
            "tp": p.tp,
        }
        result = mt5.order_send(request)
        return result is not None and result.retcode == mt5.TRADE_RETCODE_DONE

    def modify_target(self, position_id: str, new_tp_price: Optional[float]) -> bool:
        mt5 = self._import_mt5()
        positions = mt5.positions_get(ticket=int(position_id))
        if not positions:
            return False
        p = positions[0]
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": p.symbol,
            "position": p.ticket,
            "sl": p.sl,
            "tp": new_tp_price if new_tp_price is not None else 0.0,
        }
        result = mt5.order_send(request)
        return result is not None and result.retcode == mt5.TRADE_RETCODE_DONE

    def close_position_fraction(self, position_id: str, fraction: float) -> OrderResult:
        mt5 = self._import_mt5()
        positions = mt5.positions_get(ticket=int(position_id))
        if not positions:
            return OrderResult(success=False, order_id=position_id, filled=False, fill_price=None, fill_time=None, error="position not found")
        p = positions[0]
        volume = round(p.volume * fraction, 2)
        tick = mt5.symbol_info_tick(p.symbol)
        close_type = mt5.ORDER_TYPE_SELL if p.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask
        request = {
            "action": mt5.TRADE_ACTION_DEAL, "symbol": p.symbol, "volume": volume, "type": close_type,
            "position": p.ticket, "price": price, "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            return OrderResult(success=False, order_id=position_id, filled=False, fill_price=None, fill_time=None,
                                error=f"partial close failed: {result.retcode if result else mt5.last_error()}")
        return OrderResult(success=True, order_id=position_id, filled=True, fill_price=result.price,
                            fill_time=datetime.now(timezone.utc))

    def close_position(self, position_id: str) -> OrderResult:
        return self.close_position_fraction(position_id, 1.0)

    def get_current_spread(self, instrument: Instrument) -> float:
        mt5 = self._import_mt5()
        tick = mt5.symbol_info_tick(self._symbol(instrument))
        if tick is None:
            raise MT5AdapterError(f"symbol_info_tick failed: {mt5.last_error()}")
        return float(tick.ask - tick.bid)

    def pump(self, instrument: Instrument, time: datetime) -> list:
        # SL/TP execute server-side on the broker's trade server; the
        # order_manager detects fills/stops/TPs via poll_order_status()
        # and get_open_positions() diffing instead of a local simulation.
        return []
