"""Append-only IDX30 membership history.

`idx30.history.jsonl` is the audit trail. Two invariants:

* rows are only ever appended — existing rows are never rewritten or reordered;
* appending is idempotent — rerunning a collector that found the same change on
  the same day does not create a second row.

Idempotency comes from the composite key (observedAt, ticker, changeType,
detail). A genuinely new change on a later day has a different observedAt and so
is a different row, which is correct.
"""

from __future__ import annotations

from typing import Iterable, Optional

from ..contracts.records import Constituent, MembershipChange
from ..settings import Settings, get_settings
from .writers import append_jsonl_unique, read_jsonl


def history_key(row: dict) -> tuple:
    return (
        row.get("observedAt", ""),
        row.get("ticker", ""),
        row.get("changeType", ""),
        row.get("detail") or "",
    )


def append_changes(
    changes: Iterable[MembershipChange], settings: Optional[Settings] = None
) -> tuple:
    """Append change rows. Returns ``(file_changed, rows_appended)``."""
    settings = settings or get_settings()
    rows = [c.to_json() for c in changes]
    return append_jsonl_unique(settings.idx30_history, rows, key=history_key)


def load_history(settings: Optional[Settings] = None) -> list:
    settings = settings or get_settings()
    return read_jsonl(settings.idx30_history)


def membership_at(
    date_iso: str, settings: Optional[Settings] = None, basis: str = "effective"
) -> set:
    """Reconstruct the membership set as of a date by replaying history.

    This is the function that proves the history is genuinely useful rather
    than decorative: if it can rebuild any past universe, nothing was lost.

    Two different questions, and conflating them produces subtly wrong answers:

    ``basis="effective"`` (default)
        *What was the index on that date?* Replays by ``effectiveFrom``, the
        date a change actually took effect. This is the factual view, and what
        you want when attributing returns to a historical universe.

    ``basis="observed"``
        *What did we know on that date?* Replays by ``observedAt``, the date we
        recorded the change. A change discovered a week late only appears a week
        late, which is the point-in-time-correct view for backtesting.

    The two diverge whenever collection lags the effective date — which is
    normal, since an index review is published before it takes effect.
    """
    if basis not in ("effective", "observed"):
        raise ValueError(f"basis must be 'effective' or 'observed', got {basis!r}")

    def key(row: dict) -> str:
        if basis == "observed":
            return (row.get("observedAt") or "")[:10]
        # effectiveFrom is the truth when present; observedAt is the fallback
        # for a row recorded without one.
        return ((row.get("effectiveFrom") or row.get("observedAt")) or "")[:10]

    members: set = set()
    # Sorted rather than short-circuited: the file is append-only in observation
    # order, so effective dates are not necessarily monotonic and a `break`
    # would silently truncate the replay.
    for row in sorted(load_history(settings), key=key):
        if key(row) > date_iso:
            break
        change_type = row.get("changeType")
        ticker = row.get("ticker")
        if change_type == "ADDED":
            members.add(ticker)
        elif change_type == "REMOVED":
            members.discard(ticker)
    return members


def former_members(current: Iterable[Constituent], settings: Optional[Settings] = None) -> set:
    """Tickers that were members at some point and are not now."""
    current_tickers = {c.ticker for c in current}
    ever: set = set()
    for row in load_history(settings):
        if row.get("changeType") in ("ADDED", "RECLASSIFIED", "RENAMED"):
            ticker = row.get("ticker")
            if ticker and ticker != "*":
                ever.add(ticker)
    return ever - current_tickers
