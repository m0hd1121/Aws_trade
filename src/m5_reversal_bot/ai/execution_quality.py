"""Execution quality monitoring — slippage and fill-latency scoring.

This is the concrete "self-learning... operational efficiency" capability
the spec asks for: it observes how well the bot's actual fills matched its
intended orders and flags execution degradation (e.g. a broker connection
getting slow, spreads widening structurally) for a human to act on. It
NEVER changes entry price, stop, target, timing, or sizing — those numbers
are already final by the time a fill reaches this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .analytics import WelfordAccumulator


@dataclass
class ExecutionQualityReport:
    fills_observed: int
    avg_slippage: float
    slippage_stddev: float
    avg_fill_latency_seconds: float
    latency_stddev: float
    degraded: bool
    degraded_reasons: list


class ExecutionQualityMonitor:
    def __init__(self, slippage_zscore_alert: float = 2.5, latency_zscore_alert: float = 2.5):
        self._slippage = WelfordAccumulator()
        self._latency = WelfordAccumulator()
        self._slippage_alert_z = slippage_zscore_alert
        self._latency_alert_z = latency_zscore_alert
        self._last_slippage: Optional[float] = None
        self._last_latency: Optional[float] = None

    def record_fill(self, intended_price: float, actual_fill_price: float, submit_time, fill_time) -> None:
        slippage = abs(actual_fill_price - intended_price)
        latency = max(0.0, (fill_time - submit_time).total_seconds()) if submit_time and fill_time else 0.0
        self._slippage.update(slippage)
        self._latency.update(latency)
        self._last_slippage = slippage
        self._last_latency = latency

    def _zscore(self, value: float, acc: WelfordAccumulator) -> float:
        if acc.count < 5 or acc.stddev == 0:
            return 0.0
        return (value - acc.mean) / acc.stddev

    def report(self) -> ExecutionQualityReport:
        reasons = []
        degraded = False
        if self._last_slippage is not None:
            z = self._zscore(self._last_slippage, self._slippage)
            if z >= self._slippage_alert_z:
                degraded = True
                reasons.append(f"latest slippage {self._last_slippage:.5f} is {z:.1f} std devs above rolling mean")
        if self._last_latency is not None:
            z = self._zscore(self._last_latency, self._latency)
            if z >= self._latency_alert_z:
                degraded = True
                reasons.append(f"latest fill latency {self._last_latency:.2f}s is {z:.1f} std devs above rolling mean")

        return ExecutionQualityReport(
            fills_observed=self._slippage.count,
            avg_slippage=self._slippage.mean,
            slippage_stddev=self._slippage.stddev,
            avg_fill_latency_seconds=self._latency.mean,
            latency_stddev=self._latency.stddev,
            degraded=degraded,
            degraded_reasons=reasons,
        )
