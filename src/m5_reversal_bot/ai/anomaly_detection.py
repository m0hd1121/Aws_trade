"""Data-quality / feed anomaly monitoring — observation only.

Flags stale feeds, missing candles, and implausible price prints so a
human (or the health/alerting layer) can act before bad data reaches the
strategy engine. Detection here never filters, edits, or drops the data
the strategy engine sees; it only raises an alert alongside it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from .analytics import WelfordAccumulator


@dataclass
class AnomalyReport:
    anomalies: List[str]

    @property
    def any_detected(self) -> bool:
        return len(self.anomalies) > 0


class FeedAnomalyDetector:
    def __init__(self, expected_candle_interval_minutes: int = 5, price_zscore_alert: float = 4.0):
        self._interval = timedelta(minutes=expected_candle_interval_minutes)
        self._price_change = WelfordAccumulator()
        self._price_zscore_alert = price_zscore_alert
        self._last_close: Optional[float] = None
        self._last_candle_time: Optional[datetime] = None

    def check_candle(self, open_time: datetime, close: float) -> AnomalyReport:
        anomalies: List[str] = []

        if self._last_candle_time is not None:
            gap = open_time - self._last_candle_time
            if gap > self._interval * 2:
                anomalies.append(f"candle gap of {gap} detected (expected ~{self._interval}) — possible feed dropout")
            elif gap < timedelta(0):
                anomalies.append(f"out-of-order candle: {open_time} arrived after {self._last_candle_time}")

        if self._last_close is not None:
            change = abs(close - self._last_close)
            if self._price_change.count >= 20 and self._price_change.stddev > 0:
                z = (change - self._price_change.mean) / self._price_change.stddev
                if z >= self._price_zscore_alert:
                    anomalies.append(f"implausible price jump: {change:.5f} is {z:.1f} std devs above rolling mean")
            self._price_change.update(change)
        else:
            self._price_change.update(0.0)

        self._last_close = close
        self._last_candle_time = open_time
        return AnomalyReport(anomalies=anomalies)

    def check_feed_staleness(self, now: datetime, max_staleness: timedelta) -> AnomalyReport:
        if self._last_candle_time is None:
            return AnomalyReport(anomalies=[])
        staleness = now - self._last_candle_time
        if staleness > max_staleness:
            return AnomalyReport(anomalies=[f"feed stale: no new candle in {staleness}, max allowed {max_staleness}"])
        return AnomalyReport(anomalies=[])
