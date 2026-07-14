#!/usr/bin/env python3
"""Starts the bot in DEMO mode: real orders sent to a demo MT5 account via
the MetaTrader5 python API (MT5_LOGIN/MT5_PASSWORD/MT5_SERVER in .env must
point at a demo account). Section 12.3's validation requirement (60
demo/backtest trades at >=95% compliance) should be satisfied here before
ever running LIVE."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _run_mode import run  # noqa: E402

if __name__ == "__main__":
    run("DEMO")
