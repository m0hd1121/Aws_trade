"""BotController — the state machine behind every dashboard control:
Start / Stop / Pause / Resume / Restart / Reset Session / Emergency Stop /
Manual Refresh / Configuration Management. This is the only object the API
layer talks to; it owns the single `BotRunner` instance for the configured
mode and enforces valid state transitions.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from ..core.config import RuntimeConfig
from ..core.enums import BotState, Mode
from .runner import BotRunner

log = logging.getLogger("m5_reversal_bot.controller")

_VALID_TRANSITIONS = {
    BotState.IDLE: {BotState.RUNNING},
    BotState.RUNNING: {BotState.PAUSED, BotState.STOPPED, BotState.EMERGENCY_STOPPED, BotState.RESTARTING},
    BotState.PAUSED: {BotState.RUNNING, BotState.STOPPED, BotState.EMERGENCY_STOPPED, BotState.RESTARTING},
    BotState.STOPPED: {BotState.RUNNING, BotState.RESTARTING},
    BotState.EMERGENCY_STOPPED: {BotState.RESTARTING, BotState.IDLE},
    BotState.RESTARTING: {BotState.RUNNING},
}


class InvalidTransition(RuntimeError):
    pass


class BotController:
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config = RuntimeConfig.load(config_path)
        self.state = BotState.IDLE
        self.runner: Optional[BotRunner] = None

    def _transition(self, new_state: BotState) -> None:
        allowed = _VALID_TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            raise InvalidTransition(f"cannot go from {self.state.value} to {new_state.value}")
        log.info("bot state %s -> %s", self.state.value, new_state.value)
        self.state = new_state

    # ------------------------------------------------------------------ controls
    def start(self) -> dict:
        if self.runner is None:
            self.runner = BotRunner(Mode(self.config.mode), self.config)
        self._transition(BotState.RUNNING)
        self.runner.start()
        return self.status()

    def stop(self) -> dict:
        self._transition(BotState.STOPPED)
        if self.runner:
            self.runner.stop()
        return self.status()

    def pause(self) -> dict:
        self._transition(BotState.PAUSED)
        if self.runner:
            self.runner.pause()
        return self.status()

    def resume(self) -> dict:
        self._transition(BotState.RUNNING)
        if self.runner:
            self.runner.resume()
        return self.status()

    def restart(self) -> dict:
        self._transition(BotState.RESTARTING)
        if self.runner:
            self.runner.restart()
        else:
            self.runner = BotRunner(Mode(self.config.mode), self.config)
            self.runner.start()
        self._transition(BotState.RUNNING)
        return self.status()

    def reset_session(self) -> dict:
        if self.runner:
            self.runner.reset_session()
        return self.status()

    def emergency_stop(self) -> dict:
        self._transition(BotState.EMERGENCY_STOPPED)
        if self.runner:
            self.runner.emergency_stop()
        return self.status()

    def manual_refresh(self) -> dict:
        return self.status()

    def update_config(self, new_config_yaml: dict) -> dict:
        """Configuration Management — operational config only (mode,
        enabled instruments, poll cadence, dashboard settings). Strategy
        rule numbers are not present in config.yaml and cannot be changed
        through this path; see core/constants.py."""
        import yaml

        with open(self.config_path, "w") as f:
            yaml.safe_dump(new_config_yaml, f, sort_keys=False)
        self.config.reload(self.config_path)
        return {"config": self.config.raw}

    # ------------------------------------------------------------------ status
    def status(self) -> dict:
        base = {"state": self.state.value, "config_mode": self.config.mode}
        if self.runner:
            base["runner"] = self.runner.snapshot_for_dashboard()
        return base
