#!/usr/bin/env python3
"""Starts the bot in LIVE mode: real orders against a funded MT5 account.

Do not run this until:
  - 60 recorded demo/backtest trades with >=95% rule-compliance (12.3), and
  - 40 live trades at 0.5% risk have validated the edge for this account (8.2).

MT5_LOGIN/MT5_PASSWORD/MT5_SERVER in .env must point at the live account.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _run_mode import run  # noqa: E402

if __name__ == "__main__":
    run("LIVE")
