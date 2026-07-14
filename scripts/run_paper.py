#!/usr/bin/env python3
"""Starts the bot in PAPER mode: simulated fills against real live/demo
market prices, no real orders ever sent. Use this to validate the system
end-to-end before touching a demo or live account."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _run_mode import run  # noqa: E402

if __name__ == "__main__":
    run("PAPER")
