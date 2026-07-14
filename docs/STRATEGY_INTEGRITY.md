# Strategy Integrity

This document explains the mechanism that keeps the M5 Liquidity Reversal
Playbook frozen, and what to do (and not do) when the strategy legitimately
needs to change.

## The frozen source of truth

`docs/strategy/M5_Liquidity_Reversal_Playbook.md` is a byte-for-byte copy
of the rulebook you provided. It is never edited by the bot, by the AI
analytics layer, or by any automated process.

`src/m5_reversal_bot/core/constants.py` records the SHA-256 hash of that
file (`EXPECTED_RULEBOOK_SHA256`). Every process entry point
(`bot/runner.py::BotRunner.__init__`, `backtest/engine.py::BacktestRunner.__init__`)
calls `core.constants.verify_strategy_integrity()` before doing anything
else. If the on-disk rulebook no longer hashes to the recorded value, the
bot refuses to start — it will not trade against an unverified rule set.

```
StrategyIntegrityError: Strategy rulebook hash mismatch...
```

This means the only way to change a trading rule is to:

1. Edit `docs/strategy/M5_Liquidity_Reversal_Playbook.md` yourself.
2. Update the corresponding constant(s) in `core/constants.py` to match.
3. Recompute the hash (`sha256sum docs/strategy/M5_Liquidity_Reversal_Playbook.md`)
   and update `EXPECTED_RULEBOOK_SHA256`.
4. Commit all three changes together, with a commit message explaining
   *why* the rule changed.

There is no code path that does this automatically. The AI/learning
modules (`src/m5_reversal_bot/ai/*`) cannot reach `core/constants.py` or
`strategy/*` at all — see the architectural boundary below.

## Where every rule lives

Every module under `src/m5_reversal_bot/strategy/` corresponds to one or
more numbered sections of the rulebook, cited in its docstrings:

| Module | Rulebook section |
|---|---|
| `structure.py` | 1.1-1.4 (swings, BOS, CHoCH) |
| `liquidity.py` | 1.5-1.6 (pools, sweeps) |
| `displacement.py` | 1.7-1.8 (displacement, FVG) |
| `order_block.py` | 1.9 (Order Block) |
| `poi.py` | 1.10-1.11 (POI, dealing range) |
| `inducement.py` | 1.12 |
| `chop.py` | 1.14 |
| `smt.py` | 1.15 |
| `sessions.py` | Section 2 (kill zones, D1-D7) |
| `scoring.py` | Section 3 (12-point model, gates) |
| `entry.py` | Section 4 |
| `stop_loss.py` | Section 5 |
| `exits.py` | Section 6 |
| `trade_management.py` | Section 7 |
| `risk.py` | Section 8 |
| `filters.py` | Section 9 |
| `checklist.py` | Section 10 |
| `engine.py` | Section 13 (orchestration) |

`core/constants.py` holds every numeric threshold as a frozen dataclass,
each field commented with the rulebook clause it transcribes.

## Two constants that legitimately change

The rulebook itself designates exactly two numbers as periodic, off-chart
statistics rather than fixed rules:

- The D3/D4 Asia-range disqualifier band (Section 2.5 note).
- The XAU G2 stop-distance band (Section 5.3).

`strategy/calibration.py` computes their recalibrated values; `scripts/
recalibrate_bands.py` runs that computation against recent history and
prints the result — it never writes to `constants.py` automatically.
Applying a recalibration is a manual edit, logged below.

### Recalibration log

| Date | Instrument | Band | Old | New | Sample size | By |
|---|---|---|---|---|---|---|
| (none yet) | | | | | | |

## The AI/learning boundary

`src/m5_reversal_bot/ai/*` (analytics, execution-quality monitoring,
anomaly detection) is architecturally barred from influencing a trading
decision:

- No module under `strategy/*` imports anything from `ai/*` — enforced by
  `tests/unit/test_ai_boundary.py`, which fails the build if that ever
  becomes false.
- `ai/*` only ever reads persisted trade history and writes to the
  `ai_insights` table. It has no write path into `setups`, `trades`, or
  any in-memory engine state.
- AI output surfaces on the dashboard as read-only insights (win rate vs.
  Section 12's honest performance profile, execution slippage/latency,
  data-quality alerts) for a human to act on — never as an automatic
  strategy adjustment.

## Verifying it yourself

```bash
python -c "
import sys; sys.path.insert(0, 'src')
from m5_reversal_bot.core.constants import verify_strategy_integrity
verify_strategy_integrity()
print('OK: rulebook hash verified')
"
```

Tampering with the rulebook file (even appending a single character) and
re-running this raises `StrategyIntegrityError` —
`tests/unit/test_strategy_integrity.py` checks exactly this.
