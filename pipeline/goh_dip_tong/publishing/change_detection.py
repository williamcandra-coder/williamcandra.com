"""IDX30 membership and identity change detection.

Compares a newly collected universe against the committed one and emits the
change events that go into `idx30.history.jsonl`.

The rule that shapes everything here: **a former member is never deleted.** It
is marked inactive and kept, because the whole point of history is being able to
answer "what did this index look like in March" two years from now.
"""

from __future__ import annotations

from typing import Iterable, Optional

from ..contracts.enums import ChangeType
from ..contracts.records import Constituent, MembershipChange


def _snapshot(constituent: Constituent) -> dict:
    """The identity fields a change is described in terms of."""
    return {
        "name": constituent.name,
        "sectorCode": constituent.sector_code,
        "sectorName": constituent.sector_name,
        "industryCode": constituent.industry_code,
        "industryName": constituent.industry_name,
        "modelFamily": constituent.model_family,
        "coverageStatus": str(constituent.coverage_status),
    }


def detect_changes(
    previous: Iterable[Constituent],
    current: Iterable[Constituent],
    observed_at: str,
    effective_from: Optional[str] = None,
    source_ref: Optional[str] = None,
) -> list:
    """Diff two universes.

    Emits ADDED / REMOVED / RENAMED / RECLASSIFIED — events only. A run that
    finds nothing returns an empty list and therefore writes nothing.

    This used to also emit an ``UNCHANGED`` snapshot row so that a run which
    found nothing still left a trace that it looked. That was a mistake. The row
    is keyed on the observation *date*, so the first run of every new calendar
    day appended one, which made a no-change run rewrite the history file and
    open a pull request containing no facts — exactly the churn the no-change /
    no-commit rule exists to prevent. Worse, the defect was invisible for as
    long as every run happened on the date the seed data was generated.

    "We looked and nothing had changed" is a statement about a pipeline run, not
    about the index, and it is already recorded per run under
    ``data/goh-dip-tong/pipeline-runs/``. The membership history holds membership
    events, and a file that only grows when something actually happened is one a
    reviewer can read.

    A single ticker can produce both a RENAMED and a RECLASSIFIED row in one
    run; they are distinct facts and collapsing them would lose information.
    """
    # Membership is a date-granularity concept, and the history file is keyed on
    # observedAt. Recording a full timestamp would make every rerun on the same
    # day a "new" row, so a workflow that runs four times a day would append four
    # identical entries for one real event. Truncating to the date keeps the
    # trail idempotent per day while still distinguishing separate days.
    observed_at = observed_at[:10]

    prev_by_ticker = {c.ticker: c for c in previous}
    curr_by_ticker = {c.ticker: c for c in current}
    changes: list = []

    for ticker in sorted(set(curr_by_ticker) - set(prev_by_ticker)):
        c = curr_by_ticker[ticker]
        changes.append(
            MembershipChange(
                change_type=ChangeType.ADDED,
                ticker=ticker,
                observed_at=observed_at,
                effective_from=effective_from or c.entered_at,
                before=None,
                after=_snapshot(c),
                detail=f"entered IDX30 as {c.name}",
                source_ref=source_ref or c.source_ref,
            )
        )

    for ticker in sorted(set(prev_by_ticker) - set(curr_by_ticker)):
        p = prev_by_ticker[ticker]
        changes.append(
            MembershipChange(
                change_type=ChangeType.REMOVED,
                ticker=ticker,
                observed_at=observed_at,
                effective_from=effective_from,
                before=_snapshot(p),
                after=None,
                detail=f"left IDX30; retained in companies.json as inactive",
                source_ref=source_ref or p.source_ref,
            )
        )

    for ticker in sorted(set(prev_by_ticker) & set(curr_by_ticker)):
        p, c = prev_by_ticker[ticker], curr_by_ticker[ticker]

        if p.name != c.name:
            changes.append(
                MembershipChange(
                    change_type=ChangeType.RENAMED,
                    ticker=ticker,
                    observed_at=observed_at,
                    effective_from=effective_from,
                    before={"name": p.name},
                    after={"name": c.name},
                    detail=f"{p.name!r} → {c.name!r}",
                    source_ref=source_ref or c.source_ref,
                )
            )

        classification_changed = (
            p.sector_code != c.sector_code
            or p.industry_code != c.industry_code
            or p.model_family != c.model_family
            or p.coverage_status != c.coverage_status
        )
        if classification_changed:
            parts = []
            if p.sector_code != c.sector_code:
                parts.append(f"sector {p.sector_code} → {c.sector_code}")
            if p.industry_code != c.industry_code:
                parts.append(f"industry {p.industry_code} → {c.industry_code}")
            if p.model_family != c.model_family:
                parts.append(f"model {p.model_family} → {c.model_family}")
            if p.coverage_status != c.coverage_status:
                parts.append(f"coverage {p.coverage_status} → {c.coverage_status}")
            changes.append(
                MembershipChange(
                    change_type=ChangeType.RECLASSIFIED,
                    ticker=ticker,
                    observed_at=observed_at,
                    effective_from=effective_from,
                    before=_snapshot(p),
                    after=_snapshot(c),
                    detail="; ".join(parts),
                    source_ref=source_ref or c.source_ref,
                )
            )

    return changes


def summarise_changes(changes: list) -> str:
    """Human-readable diff for a pull-request body.

    A reviewer approving an index change should be able to see what changed
    without reading a JSONL diff.
    """
    if not changes:
        return "No IDX30 membership or classification changes detected."

    buckets: dict = {}
    for change in changes:
        buckets.setdefault(str(change.change_type), []).append(change)

    lines = []
    order = [
        ChangeType.ADDED,
        ChangeType.REMOVED,
        ChangeType.RENAMED,
        ChangeType.RECLASSIFIED,
        ChangeType.UNCHANGED,
    ]
    for change_type in order:
        items = buckets.get(str(change_type))
        if not items:
            continue
        lines.append(f"### {change_type} ({len(items)})")
        lines.append("")
        for change in items:
            lines.append(f"- **{change.ticker}** — {change.detail}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def has_material_change(changes: list) -> bool:
    """Whether anything happened that justifies rewriting the current config.

    ``UNCHANGED`` is no longer emitted, but rows written before that fix are
    still in the committed history and must never count as material — so the
    filter stays rather than collapsing to ``bool(changes)``.
    """
    return any(str(c.change_type) != str(ChangeType.UNCHANGED) for c in changes)
