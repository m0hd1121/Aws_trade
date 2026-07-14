"""Section 10 — Pre-Trade Checklist (all 15 must be YES).

This is a materialized, auditable record of a decision the engine has
already made rule-by-rule elsewhere. It exists because the rulebook is
explicit: "The checklist is completed in writing... before order
placement, every time." Persisting this exact 15-row structure (and
showing it live on the dashboard) is that writing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class ChecklistRow:
    index: int
    description: str
    passed: bool


CHECKLIST_DESCRIPTIONS = [
    "Time is inside LKZ (07:00-10:00 GMT) or NYKZ (12:00-15:00 GMT)",
    "No session disqualifier D1-D7 active",
    "Asia range inside the D3/D4 band",
    "No red news within -60/+30 min",
    "Chop condition (1.14) NOT met",
    "H1 bias supports direction (F1 = 2)",
    "Qualified pool swept per 1.6 (F2 = 2)",
    "M5 CHoCH confirmed within 12 candles of sweep (F3 = 2)",
    "Total score >= 9/12",
    "POI defined, unmitigated, in correct premium/discount half",
    "Stop = sweep extreme +/- buffer, distance inside G2 band",
    "TP1 >= 2.0R to a real level (F7 verified with exact prices)",
    "Position size computed by 8.1, rounded down",
    "Daily/weekly/consecutive-loss/trade-count limits all clear",
    "Bracket order (entry+SL+TP1) ready to submit as one unit",
]


def build_checklist(flags: List[bool]) -> List[ChecklistRow]:
    if len(flags) != len(CHECKLIST_DESCRIPTIONS):
        raise ValueError(f"expected {len(CHECKLIST_DESCRIPTIONS)} checklist flags, got {len(flags)}")
    return [
        ChecklistRow(index=i + 1, description=desc, passed=flag)
        for i, (desc, flag) in enumerate(zip(CHECKLIST_DESCRIPTIONS, flags))
    ]


def checklist_passed(rows: List[ChecklistRow]) -> bool:
    """One 'NO' anywhere = no trade."""
    return all(r.passed for r in rows)
