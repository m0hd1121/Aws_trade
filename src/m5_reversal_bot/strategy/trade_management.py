"""Section 7 — Trade Management (post-entry).

Most of Section 7 is enforced structurally elsewhere: 7.1/7.2 (never
intervene pre-TP1) and 7.4 (no adding/pyramiding) are guaranteed by the
order_manager only ever calling into exits.py's mechanical trail/BE
functions and never exposing a manual-close path outside 7.3. This module
holds the one conditional exception and the audit-log completeness gate.
"""

from __future__ import annotations

from typing import List, Optional

from ..core.models import NewsEvent, Trade


def unscheduled_news_flatten_required(open_trade: Trade, unscheduled_events: List[NewsEvent]) -> Optional[NewsEvent]:
    """7.3 — the single manual-exit exception: an UNSCHEDULED red-folder
    event breaking during an open trade requires an immediate market
    flatten. Scheduled news never qualifies here (it was filtered by D1 or
    accepted pre-entry)."""
    for e in unscheduled_events:
        if e.unscheduled and e.is_red_folder:
            return e
    return None


def violates_no_pyramiding(setup_id: int, open_trades: List[Trade]) -> bool:
    """7.4 — one position per setup, sized once. No adding, no pyramiding,
    no averaging."""
    return any(t.setup_id == setup_id and t.status.value in ("OPEN", "PARTIAL", "PENDING") for t in open_trades)


REQUIRED_LOG_FIELDS = (
    "instrument", "session", "direction", "score_sheet", "entry_price",
    "stop_price", "tp1_price", "r_result", "rule_compliance",
)


def is_log_entry_complete(log_record: dict) -> bool:
    """7.5 — post-trade logging is mandatory, same day, with zero missing
    fields. Fewer than 100% logged trades = not trading this system."""
    return all(field in log_record and log_record[field] is not None for field in REQUIRED_LOG_FIELDS)
