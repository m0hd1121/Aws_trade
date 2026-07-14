"""Process-wide singleton BotController the API routes share."""

from __future__ import annotations

from ..bot.controller import BotController
from ..core.config import REPO_ROOT

_controller: BotController | None = None


def get_controller() -> BotController:
    global _controller
    if _controller is None:
        _controller = BotController(REPO_ROOT / "config" / "config.yaml")
    return _controller
