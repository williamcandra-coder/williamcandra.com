"""As-of selection: what was knowable on a given date, and nothing later.

The mistake this module exists to prevent has a specific shape. A restatement
published in July revises a figure for the year ending in December. Filtering
facts by *period end* keeps that revision in a January-dated analysis, and the
resulting backtest quietly knows things nobody knew at the time. The cutoff
must therefore apply to ``publishedAt`` — when the information existed — never
to the period it describes.

Macro series have the same problem in a second dimension: the same observation
period is republished with a later release vintage. Selecting the newest
vintage regardless of cutoff is the same leak wearing a different hat.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

#: Later basis wins when two revisions were published at the same instant. A
#: restatement supersedes what it restates; that is what it is for.
_BASIS_RANK = {"REPORTED": 0, "RESTATED": 1, "NORMALIZED": 2}


class LeakageError(ValueError):
    """A record dated after the cutoff reached the selected set.

    Raised rather than filtered, because reaching this point means the filter
    itself is broken and silently dropping the row would hide that.
    """


@dataclass
class Selection:
    """The result of an as-of query, with its own audit trail."""

    rows: List[dict] = field(default_factory=list)
    considered: int = 0
    excluded_future: int = 0
    excluded_undated: int = 0
    superseded: int = 0

    def to_json(self) -> dict:
        return {
            "selected": len(self.rows),
            "considered": self.considered,
            "excludedPublishedAfterCutoff": self.excluded_future,
            "excludedUndated": self.excluded_undated,
            "supersededByLaterRevision": self.superseded,
        }


def published_date(row: dict) -> Optional[str]:
    """The ``YYYY-MM-DD`` on which a record became known, if it says.

    Reads the flat ``publishedAt`` of a snapshot fact or the nested
    ``source.publishedAt`` of a fact-store row, so both shapes can go through
    the same cutoff.
    """
    value = row.get("publishedAt")
    if value is None:
        value = (row.get("source") or {}).get("publishedAt")
    if not value:
        return None
    return str(value)[:10]


def is_known_by(row: dict, as_of: str) -> bool:
    """Whether ``row`` had been published by the end of ``as_of``.

    An undated record is treated as *not* known. That is deliberately strict:
    admitting it would mean assuming a publication date, and the whole point of
    a cutoff is to stop assuming things about time.
    """
    stamp = published_date(row)
    return stamp is not None and stamp <= as_of


def select_facts(rows: Sequence[dict], as_of: str) -> Selection:
    """Latest revision of each fact that was published on or before ``as_of``.

    ``rows`` may mix the live fact store with superseded revisions from
    ``restatements.jsonl``; that union is exactly what makes a historical
    cutoff answerable, since the revision valid in the past is by definition
    one that has since been superseded.
    """
    selection = Selection(considered=len(rows))
    best: Dict[str, dict] = {}

    for row in rows:
        if not is_known_by(row, as_of):
            if published_date(row) is None:
                selection.excluded_undated += 1
            else:
                selection.excluded_future += 1
            continue

        key = _fact_key(row)
        incumbent = best.get(key)
        if incumbent is None:
            best[key] = row
            continue
        selection.superseded += 1
        if _revision_key(row) > _revision_key(incumbent):
            best[key] = row

    selection.rows = [best[key] for key in sorted(best)]

    # Belt and braces: if anything dated after the cutoff survived, the filter
    # above is wrong and every downstream number is suspect.
    for row in selection.rows:
        if not is_known_by(row, as_of):
            raise LeakageError(
                f"{_fact_key(row)} published {published_date(row)} survived an "
                f"as-of {as_of} selection"
            )
    return selection


def select_macro(rows: Sequence[dict], as_of: str) -> Selection:
    """Newest release vintage of each observation, as known at ``as_of``.

    Keyed on ``(seriesId, observationPeriod)`` so a revised print of the same
    month replaces the earlier one — but only once its own release date has
    passed.
    """
    selection = Selection(considered=len(rows))
    best: Dict[Tuple[str, str], dict] = {}

    for row in rows:
        if not is_known_by(row, as_of):
            if published_date(row) is None:
                selection.excluded_undated += 1
            else:
                selection.excluded_future += 1
            continue

        key = (str(row.get("seriesId")), str(row.get("observationPeriod")))
        incumbent = best.get(key)
        if incumbent is None:
            best[key] = row
            continue
        selection.superseded += 1
        if _vintage_key(row) > _vintage_key(incumbent):
            best[key] = row

    selection.rows = [best[key] for key in sorted(best)]
    return selection


# ---------------------------------------------------------------------------
# keys
# ---------------------------------------------------------------------------


def _fact_key(row: dict) -> str:
    """The identity a revision revises.

    Uses the stored ``factKey`` when present. Stage 1 deliberately excludes
    ``basis`` from that key so a RESTATED revision supersedes the REPORTED
    original it replaces — rebuilding the key here without that property would
    undo the fix.
    """
    if row.get("factKey"):
        return str(row["factKey"])
    segment = row.get("segment") or "CONSOLIDATED"
    return "|".join(
        str(row.get(part, ""))
        for part in ("ticker", "metric", "periodType", "periodEnd")
    ) + f"|{segment}"


def _revision_key(row: dict) -> tuple:
    """Ordering between two revisions of the same fact.

    Revision number first, then publication date, then basis. Every component
    is deterministic, so two rows never swap places between runs.
    """
    return (
        int(row.get("revision") or 0),
        published_date(row) or "",
        _BASIS_RANK.get(str(row.get("basis") or ""), -1),
    )


def _vintage_key(row: dict) -> tuple:
    return (str(row.get("releaseVintage") or ""), published_date(row) or "")


__all__ = [
    "Selection",
    "LeakageError",
    "select_facts",
    "select_macro",
    "is_known_by",
    "published_date",
]
