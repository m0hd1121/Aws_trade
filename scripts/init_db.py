#!/usr/bin/env python3
"""Creates all database tables. Safe to re-run (idempotent)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from m5_reversal_bot.core.config import app_settings  # noqa: E402
from m5_reversal_bot.persistence import db  # noqa: E402


def main() -> None:
    db.init_db()
    print(f"Database initialized at {app_settings.database_url}")
    print("Tables created (or already present).")


if __name__ == "__main__":
    main()
