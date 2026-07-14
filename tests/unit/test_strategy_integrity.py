from __future__ import annotations

import pytest

from m5_reversal_bot.core.constants import RULEBOOK_PATH, StrategyIntegrityError, verify_strategy_integrity


def test_frozen_rulebook_hash_matches():
    verify_strategy_integrity()  # must not raise


def test_tampered_rulebook_is_rejected(tmp_path):
    original = RULEBOOK_PATH.read_bytes()
    tampered = tmp_path / "tampered_playbook.md"
    tampered.write_bytes(original + b"\nunauthorized edit")
    with pytest.raises(StrategyIntegrityError):
        verify_strategy_integrity(tampered)


def test_missing_rulebook_is_rejected(tmp_path):
    missing = tmp_path / "does_not_exist.md"
    with pytest.raises(StrategyIntegrityError):
        verify_strategy_integrity(missing)
