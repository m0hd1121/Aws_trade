#!/usr/bin/env python3
"""Quarterly recalibration of the D3/D4 Asia-range band and the XAU G2
stop-distance band — the two values the rulebook itself calls out as
periodic, off-chart statistics (Section 2.5 note, Section 5.3). This
script only PRINTS the recalibrated numbers; it deliberately does not
write them into core/constants.py automatically. Updating the frozen
constants is a manual, audited action — see docs/STRATEGY_INTEGRITY.md —
because it changes the strategy's numeric bands and must be a conscious,
logged decision, not something a cron job silently does.

Usage:
    python scripts/recalibrate_bands.py --data-dir ./data/history \\
        --instrument EURUSD --lookback-sessions 60
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from m5_reversal_bot.core.enums import Instrument  # noqa: E402
from m5_reversal_bot.data.historical_loader import load_instrument_history  # noqa: E402
from m5_reversal_bot.strategy import calibration, liquidity  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", default="./data/history")
    parser.add_argument("--instrument", required=True, choices=["EURUSD", "XAUUSD"])
    parser.add_argument("--lookback-sessions", type=int, default=60)
    args = parser.parse_args()

    instrument = Instrument(args.instrument)
    history = load_instrument_history(Path(args.data_dir), instrument)
    m5 = history["M5"]

    days = sorted({c.open_time.date() for c in m5})[-args.lookback_sessions:]
    asia_ranges = []
    for d in days:
        from datetime import datetime, timezone

        ref = datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc)
        result = liquidity.compute_asia_range(m5, ref)
        if result:
            asia_ranges.append(result[2])

    print(f"{instrument.value}: {len(asia_ranges)} Asia sessions in the last {args.lookback_sessions}")
    if len(asia_ranges) >= 20:
        band = calibration.recalibrate_asia_band(asia_ranges)
        print(f"  Recalibrated D3/D4 band: {band.min_range:.5f} - {band.max_range:.5f} (n={band.sample_size})")
    else:
        print("  Not enough sessions to recalibrate (need >= 20).")

    if instrument == Instrument.XAUUSD:
        # Approximate daily NY-session range from H1 data for the same window.
        h1 = history["H1"]
        from m5_reversal_bot.core.clock import kill_zone_bounds
        from m5_reversal_bot.core.enums import Session

        ranges = []
        for d in days:
            from datetime import datetime, timezone

            ref = datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc)
            start, end = kill_zone_bounds(Session.NEWYORK_KZ, ref)
            window = [c for c in h1 if start <= c.open_time < end]
            if window:
                ranges.append(max(c.high for c in window) - min(c.low for c in window))
        if len(ranges) >= 20:
            xau_band = calibration.recalibrate_xau_stop_band(ranges)
            print(f"  Recalibrated XAU G2 band: {xau_band.suggested_min:.2f} - {xau_band.suggested_max:.2f} "
                  f"(median NY range {xau_band.median_ny_range:.2f}, n={xau_band.sample_size})")
        else:
            print("  Not enough NY sessions to recalibrate the G2 band.")

    print("\nTo apply: update EU/XAU in src/m5_reversal_bot/core/constants.py by hand, "
          "and record the change (old value, new value, date, sample size) in "
          "docs/STRATEGY_INTEGRITY.md's recalibration log, then update "
          "EXPECTED_RULEBOOK_SHA256 only if the rulebook document itself also changed.")


if __name__ == "__main__":
    main()
