"""Structured JSON logging setup. Low overhead (stdlib logging + a JSON
formatter, no external log shipping agent) so it fits the "low RAM/CPU"
requirement; point log aggregation (ELK, Loki, CloudWatch, etc.) at the
rotating file in production by tailing it — no code change needed here.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from pythonjsonlogger import jsonlogger


def configure_logging(log_dir: str, level: str = "INFO") -> None:
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("m5_reversal_bot")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()

    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s", rename_fields={"asctime": "timestamp", "levelname": "level"}
    )

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = logging.handlers.RotatingFileHandler(
        Path(log_dir) / "m5_reversal_bot.log", maxBytes=10_000_000, backupCount=5
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    root.propagate = False
