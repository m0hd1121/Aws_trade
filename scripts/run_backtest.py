#!/usr/bin/env python3
"""Runs a backtest over historical CSV data using the exact same strategy
engine and order-management path production trading uses.

Usage:
    python scripts/run_backtest.py \\
        --instruments EURUSD,XAUUSD \\
        --start 2024-01-01 --end 2024-12-31 \\
        --data-dir ./data/history --equity 10000

CSV files are expected at ./data/history/{INSTRUMENT}_M5.csv (H1/H4 are
derived by resampling if not supplied separately) — see
data/historical_loader.py for the exact format.
"""

import argparse
import json
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from m5_reversal_bot.backtest.engine import BacktestRunner  # noqa: E402
from m5_reversal_bot.core.enums import Instrument  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--instruments", default="EURUSD,XAUUSD")
    parser.add_argument("--start", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD")
    parser.add_argument("--data-dir", default="./data/history")
    parser.add_argument("--equity", type=float, default=10_000.0)
    parser.add_argument("--eu-spread", type=float, default=0.00007)
    parser.add_argument("--xau-spread", type=float, default=0.20)
    parser.add_argument("--output", default=None, help="optional path to write the JSON report")
    args = parser.parse_args()

    instruments = [Instrument(s.strip()) for s in args.instruments.split(",")]

    runner = BacktestRunner(
        instruments=instruments,
        data_dir=Path(args.data_dir),
        start_date=date.fromisoformat(args.start),
        end_date=date.fromisoformat(args.end),
        initial_equity=args.equity,
        spread_model={"EURUSD": args.eu_spread, "XAUUSD": args.xau_spread},
        slippage_model={"EURUSD": 0.00002, "XAUUSD": 0.05},
    )

    print(f"Running backtest: {[i.value for i in instruments]} {args.start} -> {args.end}")
    report = runner.run()

    print("\n=== Backtest Report ===")
    print(f"Trades:              {report.trades_count}")
    print(f"Win rate:            {report.win_rate:.1%}" if report.win_rate is not None else "Win rate:            n/a")
    print(f"Avg winner (R):      {report.avg_winner_r:.2f}" if report.avg_winner_r is not None else "Avg winner (R):      n/a")
    print(f"Avg loser (R):       {report.avg_loser_r:.2f}" if report.avg_loser_r is not None else "Avg loser (R):       n/a")
    print(f"Expectancy (R):      {report.expectancy_r:.3f}" if report.expectancy_r is not None else "Expectancy (R):      n/a")
    print(f"Total R:             {report.total_r:.2f}")
    print(f"Max drawdown (R):    {report.max_drawdown_r:.2f}")
    print(f"Rule compliance:     {report.rule_compliance_rate:.1%}" if report.rule_compliance_rate is not None else "n/a")
    print(f"Scored skips logged: {report.skips_count}")
    print(f"Setups scored:       {report.setups_scored_count}")
    print("\nFactor pass rates (share of scored setups scoring full marks):")
    for k, v in report.factor_pass_rates.items():
        print(f"  {k:24s} {v:.1%}")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(asdict(report), f, indent=2, default=str)
        print(f"\nFull report written to {args.output}")


if __name__ == "__main__":
    main()
