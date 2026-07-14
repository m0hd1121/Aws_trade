"""Persists analytics/execution-quality/anomaly output to the `ai_insights`
table and reads it back for the dashboard. This is the only place `ai/*`
touches persistence, and it only ever writes to `ai_insights` — never to
`trades`, `setups`, or anything the strategy engine reads.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..persistence import repository
from .analytics import PerformanceSummary
from .execution_quality import ExecutionQualityReport
from .anomaly_detection import AnomalyReport


def store_performance_summary(db: Session, summary: PerformanceSummary) -> None:
    repository.log_ai_insight(db, "performance", "win_rate", summary.win_rate, {
        "trades_count": summary.trades_count,
        "in_expected_range": summary.win_rate_in_expected_range,
    })
    repository.log_ai_insight(db, "performance", "expectancy_r", summary.expectancy_r, {
        "in_expected_range": summary.expectancy_in_expected_range,
    })
    repository.log_ai_insight(db, "performance", "rule_compliance_rate", summary.rule_compliance_rate, {})
    repository.log_ai_insight(db, "performance", "max_consecutive_losses", float(summary.max_consecutive_losses_observed), {})


def store_execution_quality(db: Session, report: ExecutionQualityReport) -> None:
    repository.log_ai_insight(db, "execution_quality", "avg_slippage", report.avg_slippage, {
        "fills_observed": report.fills_observed, "stddev": report.slippage_stddev,
    })
    repository.log_ai_insight(db, "execution_quality", "avg_fill_latency_seconds", report.avg_fill_latency_seconds, {
        "stddev": report.latency_stddev,
    })
    if report.degraded:
        repository.log_ai_insight(db, "execution_quality", "degradation_alert", 1.0, {"reasons": report.degraded_reasons})


def store_anomalies(db: Session, report: AnomalyReport) -> None:
    for a in report.anomalies:
        repository.log_ai_insight(db, "anomaly", "data_quality_alert", None, {"message": a})
