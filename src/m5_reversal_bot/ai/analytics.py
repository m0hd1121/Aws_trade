"""Performance analytics — read-only observation of the bot's own trade
history. Compares live results against the rulebook's own honest
performance profile (Section 12: 35-45% win rate, ~2.2-2.6R blended
average winner, +0.25R to +0.45R expectancy) so a human can see whether
the bot is executing the system as intended.

HARD BOUNDARY: this module (and everything under `ai/`) only ever READS
trade history and WRITES rows to the `ai_insights` table. Nothing in
`strategy/*` imports from `ai/*`, and nothing in `ai/*` is capable of
changing an entry, exit, risk, or filter decision — see
tests/unit/test_ai_boundary.py, which fails the build if that ever
becomes untrue.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from ..core.constants import RISK

# Section 12.1 honest performance profile — used only as a comparison
# baseline for reporting, never as a target the bot optimizes toward.
EXPECTED_WIN_RATE_RANGE = (0.35, 0.45)
EXPECTED_AVG_WINNER_R_RANGE = (2.2, 2.6)
EXPECTED_EXPECTANCY_R_RANGE = (0.25, 0.45)


@dataclass
class WelfordAccumulator:
    """Streaming mean/variance (Welford's algorithm) — O(1) memory, no
    need to retain the full trade history to keep rolling statistics."""

    count: int = 0
    mean: float = 0.0
    m2: float = 0.0

    def update(self, value: float) -> None:
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        delta2 = value - self.mean
        self.m2 += delta * delta2

    @property
    def variance(self) -> float:
        return self.m2 / self.count if self.count > 1 else 0.0

    @property
    def stddev(self) -> float:
        return self.variance ** 0.5


@dataclass
class PerformanceSummary:
    trades_count: int
    win_rate: Optional[float]
    avg_winner_r: Optional[float]
    avg_loser_r: Optional[float]
    expectancy_r: Optional[float]
    win_rate_in_expected_range: Optional[bool]
    expectancy_in_expected_range: Optional[bool]
    max_consecutive_losses_observed: int
    rule_compliance_rate: Optional[float]


class PerformanceAnalytics:
    def __init__(self):
        self._wins = WelfordAccumulator()
        self._losses = WelfordAccumulator()
        self._compliance_hits = 0
        self._compliance_total = 0
        self._current_loss_streak = 0
        self._max_loss_streak = 0

    def record_trade(self, r_result: Optional[float], rule_compliant: bool) -> None:
        if r_result is not None:
            if r_result >= 0:
                self._wins.update(r_result)
                self._current_loss_streak = 0
            else:
                self._losses.update(r_result)
                self._current_loss_streak += 1
                self._max_loss_streak = max(self._max_loss_streak, self._current_loss_streak)
        self._compliance_total += 1
        if rule_compliant:
            self._compliance_hits += 1

    def summary(self) -> PerformanceSummary:
        total = self._wins.count + self._losses.count
        win_rate = self._wins.count / total if total else None
        avg_winner = self._wins.mean if self._wins.count else None
        avg_loser = self._losses.mean if self._losses.count else None
        expectancy = None
        if win_rate is not None and avg_winner is not None and avg_loser is not None:
            expectancy = win_rate * avg_winner + (1 - win_rate) * avg_loser

        return PerformanceSummary(
            trades_count=total,
            win_rate=win_rate,
            avg_winner_r=avg_winner,
            avg_loser_r=avg_loser,
            expectancy_r=expectancy,
            win_rate_in_expected_range=(
                EXPECTED_WIN_RATE_RANGE[0] <= win_rate <= EXPECTED_WIN_RATE_RANGE[1] if win_rate is not None else None
            ),
            expectancy_in_expected_range=(
                EXPECTED_EXPECTANCY_R_RANGE[0] <= expectancy <= EXPECTED_EXPECTANCY_R_RANGE[1]
                if expectancy is not None else None
            ),
            max_consecutive_losses_observed=self._max_loss_streak,
            rule_compliance_rate=(self._compliance_hits / self._compliance_total) if self._compliance_total else None,
        )


def build_summary_from_trade_records(trade_records: List) -> PerformanceSummary:
    """Convenience: build a PerformanceSummary from a list of persisted
    TradeRecord ORM rows (closed trades only)."""
    analytics = PerformanceAnalytics()
    for t in trade_records:
        if t.status != "CLOSED":
            continue
        analytics.record_trade(t.r_result, t.rule_compliance)
    return analytics.summary()
