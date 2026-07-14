"""Operational configuration — everything that is *not* a strategy rule.

This is deliberately narrow. Nothing in here can change an entry/exit/risk
rule; it only controls where the bot runs, which broker account it talks
to, and how it reports itself. Strategy numbers live exclusively in
`core/constants.py`. See docs/STRATEGY_INTEGRITY.md.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_YAML = REPO_ROOT / "config" / "config.yaml"


class MT5Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MT5_", env_file=".env", extra="ignore")

    login: int | None = None
    password: str | None = None
    server: str | None = None
    terminal_path: str | None = None  # path to terminal64.exe, MT5 python API still connects via IPC, no manual UI use
    timeout_ms: int = 10_000


class AppSettings(BaseSettings):
    """Loaded from environment / .env. Broker credentials never touch YAML."""

    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./data/m5_bot.db"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"
    log_dir: str = "./logs"
    news_calendar_path: str = "./config/news_calendar.yaml"
    holiday_calendar_path: str = "./config/holidays.yaml"

    mt5: MT5Settings = Field(default_factory=MT5Settings)


class RuntimeConfig:
    """Operational config loaded from config/config.yaml — mode, enabled
    instruments, poll cadence, dashboard/reporting toggles. Reloadable at
    runtime via the Configuration Management dashboard control; strategy
    constants are never part of this object.
    """

    def __init__(self, data: dict):
        self._data = data

    @classmethod
    def load(cls, path: Path = DEFAULT_CONFIG_YAML) -> "RuntimeConfig":
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}
        return cls(data)

    def reload(self, path: Path = DEFAULT_CONFIG_YAML) -> None:
        with open(path, "r") as f:
            self._data = yaml.safe_load(f) or {}

    @property
    def mode(self) -> Literal["BACKTEST", "PAPER", "DEMO", "LIVE"]:
        return self._data.get("mode", "PAPER")

    @property
    def enabled_instruments(self) -> list[str]:
        return self._data.get("enabled_instruments", ["EURUSD", "XAUUSD"])

    @property
    def poll_interval_seconds(self) -> float:
        return float(self._data.get("poll_interval_seconds", 5.0))

    @property
    def timezone(self) -> str:
        # The strategy is defined entirely in GMT (Section 2). This is
        # informational for display only — all comparisons happen in GMT.
        return self._data.get("display_timezone", "GMT")

    @property
    def initial_equity(self) -> float:
        return float(self._data.get("initial_equity", 10_000.0))

    @property
    def backtest(self) -> dict:
        return self._data.get("backtest", {})

    @property
    def raw(self) -> dict:
        return dict(self._data)


app_settings = AppSettings()
