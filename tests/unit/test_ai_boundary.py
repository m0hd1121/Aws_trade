"""Enforces the architectural boundary the spec requires: AI/learning
capabilities may only do analytics, execution-quality scoring, error
detection, data-quality monitoring, and operational enhancements — they
must never be able to alter, override, disable, weaken, or strengthen a
strategy rule. The mechanical guarantee is that `strategy/*` never imports
`ai/*`, so no code path exists for an AI module to feed back into a
trading decision.
"""

from __future__ import annotations

import ast
from pathlib import Path

STRATEGY_DIR = Path(__file__).resolve().parents[2] / "src" / "m5_reversal_bot" / "strategy"


def _imports_ai_package(py_file: Path) -> bool:
    tree = ast.parse(py_file.read_text(), filename=str(py_file))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith("m5_reversal_bot.ai") or module.startswith(".ai") or module == "ai":
                return True
            if node.level and node.module and "ai" in node.module.split("."):
                return True
        if isinstance(node, ast.Import):
            for alias in node.names:
                if "ai" in alias.name.split("."):
                    return True
    return False


def test_no_strategy_module_imports_the_ai_package():
    offenders = [str(f) for f in STRATEGY_DIR.glob("*.py") if _imports_ai_package(f)]
    assert offenders == [], f"strategy/* must never import ai/*, found imports in: {offenders}"
