"""Live/demo market data via the official `MetaTrader5` python package —
or, in `bridge_mode="mt5linux"`, via a remote MT5 terminal (typically a
Dockerized Wine container) reached over the `mt5linux` RPyC bridge.

Either way this is the MT5 **API**, not the desktop terminal UI: no
manual clicking, no terminal automation, no screen-scraping.
`initialize()`/`login()` drive the terminal purely as a data/execution
bridge; a human never interacts with it, in local mode or bridge mode.

The real `MetaTrader5` package only ships prebuilt wheels for Windows —
`bridge_mode="local"` needs a Windows host or Wine on THIS machine. The
`mt5linux` client has no such restriction (it's pure-Python RPyC), which
is what lets `bridge_mode="mt5linux"` run on a plain Linux box talking to
a separate container that owns the Wine/MT5 side — see
docker/docker-compose.mt5-bridge.yml and docs/DEPLOYMENT.md. Import is
deferred either way so the rest of the codebase (and its test suite) can
run without either package installed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Tuple

from tenacity import retry, stop_after_attempt, wait_exponential

from ..core.config import MT5Settings
from ..core.enums import Instrument
from ..core.models import Candle
from .feed import MarketDataFeed

_TIMEFRAME_MAP_NAMES = {"M5": "TIMEFRAME_M5", "H1": "TIMEFRAME_H1", "H4": "TIMEFRAME_H4"}


class MT5ConnectionError(RuntimeError):
    pass


class MT5MarketDataFeed(MarketDataFeed):
    def __init__(self, settings: MT5Settings, symbol_map: dict):
        self._settings = settings
        self._symbol_map = symbol_map  # {"EURUSD": "EURUSD", "XAUUSD": "XAUUSD"} (broker suffix support)
        self._mt5 = None
        self._connected = False

    def _import_mt5(self):
        if self._mt5 is None:
            if self._settings.bridge_mode == "mt5linux":
                try:
                    from mt5linux import MetaTrader5 as _MT5Bridge
                except ImportError as e:
                    raise MT5ConnectionError(
                        "mt5linux package is not installed. Run `pip install mt5linux` "
                        "and point MT5_BRIDGE_HOST/MT5_BRIDGE_PORT at the Wine+MT5 "
                        "bridge container — see docker/docker-compose.mt5-bridge.yml."
                    ) from e
                self._mt5 = _MT5Bridge(host=self._settings.bridge_host, port=self._settings.bridge_port)
            else:
                try:
                    import MetaTrader5 as mt5  # noqa: N814
                except ImportError as e:
                    raise MT5ConnectionError(
                        "MetaTrader5 python package is not installed/available on this "
                        "platform. It only ships Windows wheels — run this feed on a "
                        "Windows host or under Wine, or set MT5_BRIDGE_MODE=mt5linux to "
                        "talk to a remote bridge instead. See docs/DEPLOYMENT.md."
                    ) from e
                self._mt5 = mt5
        return self._mt5

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=2, max=16))
    def connect(self) -> None:
        mt5 = self._import_mt5()
        kwargs = {}
        # `path` is a local Windows filesystem path — meaningless for a
        # remote mt5linux bridge, whose terminal path is fixed inside its
        # own container.
        if self._settings.bridge_mode == "local" and self._settings.terminal_path:
            kwargs["path"] = self._settings.terminal_path
        if not mt5.initialize(**kwargs):
            raise MT5ConnectionError(f"MT5 initialize() failed: {mt5.last_error()}")
        if self._settings.login and self._settings.password and self._settings.server:
            authorized = mt5.login(
                self._settings.login, password=self._settings.password, server=self._settings.server,
                timeout=self._settings.timeout_ms,
            )
            if not authorized:
                mt5.shutdown()
                raise MT5ConnectionError(f"MT5 login() failed: {mt5.last_error()}")
        self._connected = True

    def disconnect(self) -> None:
        if self._mt5 is not None:
            self._mt5.shutdown()
        self._connected = False

    def is_connected(self) -> bool:
        if not self._connected or self._mt5 is None:
            return False
        return self._mt5.terminal_info() is not None

    def _broker_symbol(self, instrument: Instrument) -> str:
        return self._symbol_map.get(instrument.value, instrument.value)

    def _to_candle(self, instrument: Instrument, timeframe: str, row) -> Candle:
        return Candle(
            instrument=instrument,
            timeframe=timeframe,
            open_time=datetime.fromtimestamp(int(row["time"]), tz=timezone.utc),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["tick_volume"]),
        )

    def get_recent_candles(self, instrument: Instrument, timeframe: str, count: int) -> List[Candle]:
        mt5 = self._import_mt5()
        symbol = self._broker_symbol(instrument)
        tf = getattr(mt5, _TIMEFRAME_MAP_NAMES[timeframe])
        # pos=1 skips the currently-forming (unclosed) bar at pos=0.
        rates = mt5.copy_rates_from_pos(symbol, tf, 1, count)
        if rates is None:
            raise MT5ConnectionError(f"copy_rates_from_pos failed for {symbol}/{timeframe}: {mt5.last_error()}")
        return [self._to_candle(instrument, timeframe, r) for r in rates]

    def get_current_tick(self, instrument: Instrument) -> Tuple[float, float, datetime]:
        mt5 = self._import_mt5()
        symbol = self._broker_symbol(instrument)
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            raise MT5ConnectionError(f"symbol_info_tick failed for {symbol}: {mt5.last_error()}")
        return float(tick.bid), float(tick.ask), datetime.fromtimestamp(tick.time, tz=timezone.utc)

    def get_reference_candles(self, reference_symbol: str, timeframe: str, count: int) -> List[Candle]:
        mt5 = self._import_mt5()
        tf = getattr(mt5, _TIMEFRAME_MAP_NAMES[timeframe])
        rates = mt5.copy_rates_from_pos(reference_symbol, tf, 1, count)
        if rates is None:
            return []
        # Reference candles are tagged with a placeholder Instrument since
        # they aren't one of the two traded instruments; only OHLC/time
        # matter to smt.py, which never reads `.instrument`.
        return [self._to_candle(Instrument.EURUSD, timeframe, r) for r in rates]
