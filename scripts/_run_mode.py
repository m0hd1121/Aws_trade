"""Shared launcher for run_paper.py / run_demo.py / run_live.py. Starts the
API+dashboard server with the requested mode forced into config.yaml (so
the dashboard's Start Bot control launches a BotRunner in that mode). The
bot does NOT start trading automatically on process launch — an operator
(or --autostart) must explicitly Start it, per the Bot Controls
requirement; a live trading process should never begin sending orders
just because it was deployed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))


def run(mode: str) -> None:
    import uvicorn
    import yaml

    from m5_reversal_bot.core.config import app_settings

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=app_settings.api_host)
    parser.add_argument("--port", type=int, default=app_settings.api_port)
    parser.add_argument("--autostart", action="store_true", help="start the bot immediately on launch")
    parser.add_argument("--config", default=str(REPO_ROOT / "config" / "config.yaml"))
    args = parser.parse_args()

    config_path = Path(args.config)
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    if cfg.get("mode") != mode:
        cfg["mode"] = mode
        with open(config_path, "w") as f:
            yaml.safe_dump(cfg, f, sort_keys=False)
        print(f"config.yaml mode set to {mode}")

    if mode == "LIVE":
        print("=" * 70)
        print(" LIVE TRADING MODE — real orders, real money.")
        print(" The strategy rulebook hash is verified at every engine start.")
        print(" Use the dashboard's Start Bot control (or --autostart) to begin.")
        print("=" * 70)

    if args.autostart:
        import os

        os.environ["M5BOT_AUTOSTART"] = "1"

    uvicorn.run("m5_reversal_bot.api.main:app", host=args.host, port=args.port, log_level="info")
