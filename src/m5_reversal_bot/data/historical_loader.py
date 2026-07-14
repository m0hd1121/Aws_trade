"""Historical OHLC loading for backtests.

Expects CSV files named `{INSTRUMENT}_{TIMEFRAME}.csv` (e.g.
`EURUSD_M5.csv`) with columns `time,open,high,low,close,volume` (time as
ISO-8601 or unix seconds, GMT). If H1/H4 files aren't supplied, they are
derived from M5 by resampling — the resample is a mechanical OHLC
aggregation, not a strategy decision, so it lives here rather than in
strategy/*.
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

from ..core.enums import Instrument
from ..core.models import TIMEFRAME_MINUTES, Candle


def _parse_time(value: str) -> datetime:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except ValueError:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt


def load_csv_candles(path: Path, instrument: Instrument, timeframe: str) -> List[Candle]:
    candles: List[Candle] = []
    with open(path, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            candles.append(
                Candle(
                    instrument=instrument,
                    timeframe=timeframe,
                    open_time=_parse_time(row["time"]),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row.get("volume", 0) or 0),
                )
            )
    candles.sort(key=lambda c: c.open_time)
    return candles


def load_instrument_history(data_dir: Path, instrument: Instrument) -> dict:
    """Returns {"M5": [...], "H1": [...], "H4": [...]}, deriving any
    missing higher timeframe from the M5 series."""
    result = {}
    m5_path = data_dir / f"{instrument.value}_M5.csv"
    if not m5_path.exists():
        raise FileNotFoundError(f"required M5 history file missing: {m5_path}")
    result["M5"] = load_csv_candles(m5_path, instrument, "M5")

    for tf in ("H1", "H4"):
        tf_path = data_dir / f"{instrument.value}_{tf}.csv"
        if tf_path.exists():
            result[tf] = load_csv_candles(tf_path, instrument, tf)
        else:
            result[tf] = resample(result["M5"], tf)
    return result


def resample(m5_candles: List[Candle], target_timeframe: str) -> List[Candle]:
    minutes = TIMEFRAME_MINUTES[target_timeframe]
    buckets: dict = {}
    for c in m5_candles:
        epoch_minutes = int(c.open_time.timestamp() // 60)
        bucket_start_minutes = epoch_minutes - (epoch_minutes % minutes)
        bucket_time = datetime.fromtimestamp(bucket_start_minutes * 60, tz=timezone.utc)
        buckets.setdefault(bucket_time, []).append(c)

    out: List[Candle] = []
    for bucket_time in sorted(buckets.keys()):
        group = buckets[bucket_time]
        out.append(
            Candle(
                instrument=group[0].instrument,
                timeframe=target_timeframe,
                open_time=bucket_time,
                open=group[0].open,
                high=max(c.high for c in group),
                low=min(c.low for c in group),
                close=group[-1].close,
                volume=sum(c.volume for c in group),
            )
        )
    return out
