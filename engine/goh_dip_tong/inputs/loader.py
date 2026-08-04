"""Loading one issuer's inputs, as at a cutoff date.

Stage 1's ``research-input.schema.json`` calls itself *"the ONLY shape Stage 2
should have to read"*, and for a current-date run that is true. It is not true
for a historical one: the snapshot carries the latest revision of each fact and
nothing else, so it cannot answer "what did we believe in July". Point-in-time
reproducibility therefore needs the fact store and the restatement log as well.

Hence two tiers. The snapshot is always read — it is the validation gate, the
identity record and the rights statement — and the fact store is preferred as
the source of facts when it is present, because only it carries the revision
history a cutoff has to choose between.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from pipeline.goh_dip_tong.contracts.records import ValidationReport
from pipeline.goh_dip_tong.publishing.writers import read_json, read_jsonl
from pipeline.goh_dip_tong.validation.schema import validate_document

from ..contracts.calculated import Calculated, from_fact
from ..settings import EngineSettings
from . import point_in_time as pit
from .provenance import Provenance, assess


class InputError(ValueError):
    """The inputs for an issuer could not be assembled."""


class SnapshotMissing(InputError):
    """No Stage 1 research-input snapshot exists for this ticker."""


@dataclass
class EngineInput:
    """Everything the engine knows about one issuer at one cutoff."""

    ticker: str
    as_of: str
    identity: dict
    facts: List[Calculated]
    macro: List[dict]
    market_context: dict
    provenance: Provenance
    input_quality: dict
    base_disclaimers: List[str]
    fact_source: str
    selection: pit.Selection
    macro_selection: pit.Selection
    ambiguous: List[str] = field(default_factory=list)
    universe: dict = field(default_factory=dict)

    # ---- lookups ---------------------------------------------------------
    @property
    def consolidated(self) -> List[Calculated]:
        """Facts describing the whole issuer. Segment detail is supplementary
        and must never be substituted for it."""
        return [c for c in self.facts if c.segment is None]

    def metrics_present(self) -> set:
        """Metrics with an actual value at the consolidated level.

        A metric that is present-but-null does not count. For deciding whether
        a model has what it needs, "reported as not reported" and "never
        collected" are the same answer.
        """
        return {c.metric_id for c in self.consolidated if not c.is_missing}

    def periods_for(self, metric_id: str) -> List[str]:
        return sorted(
            {c.period.period_end for c in self.consolidated
             if c.metric_id == metric_id and not c.is_missing}
        )

    def annual_periods(self) -> List[str]:
        return sorted(
            {c.period.period_end for c in self.consolidated
             if str(c.period.period_type) == "FY" and not c.is_missing}
        )

    def to_audit_json(self) -> dict:
        return {
            "asOf": self.as_of,
            "factSource": self.fact_source,
            "factSelection": self.selection.to_json(),
            "macroSelection": self.macro_selection.to_json(),
            "ambiguousFacts": sorted(self.ambiguous),
            "inputProvenance": self.provenance.to_json(),
            "inputQuality": self.input_quality,
        }


def today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load(
    settings: EngineSettings,
    ticker: str,
    as_of: Optional[str] = None,
    model_version: str = "0.0.0",
    calculated_at: str = "",
) -> EngineInput:
    """Assemble one issuer's inputs, applying the cutoff to every source."""
    ticker = ticker.upper()
    as_of = as_of or today_utc()

    snapshot_path = settings.input_snapshots / f"{ticker}.json"
    snapshot = read_json(snapshot_path)
    if snapshot is None:
        raise SnapshotMissing(
            f"{ticker}: no Stage 1 research-input snapshot at "
            f"{settings.rel(snapshot_path)}. Stage 1 has produced snapshots for "
            f"only the issuers that have collected facts; the engine will not "
            f"invent one."
        )

    report = validate_snapshot(settings, ticker, snapshot)
    if not report.ok:
        raise InputError(
            f"{ticker}: input snapshot failed schema validation — "
            + "; ".join(i.message for i in report.critical_failures[:5])
        )

    universe = read_json(settings.pipeline.idx30_current) or {}

    rows, fact_source = _fact_rows(settings, ticker, snapshot)
    selection = pit.select_facts(rows, as_of)
    normalised = [_normalise(row) for row in selection.rows]
    ambiguous = _ambiguous(normalised)

    facts = [
        from_fact(row, model_version=model_version, calculated_at=calculated_at,
                  ticker=ticker)
        for row in sorted(normalised, key=_fact_sort_key)
    ]

    macro_rows = _macro_rows(settings)
    macro_selection = pit.select_macro(macro_rows, as_of)

    provenance = assess(
        settings, universe, snapshot,
        extra_providers=sorted({str(r.get("providerId")) for r in macro_selection.rows
                                if r.get("providerId")}),
    )

    return EngineInput(
        ticker=ticker,
        as_of=as_of,
        identity=dict(snapshot.get("identity") or {}),
        facts=facts,
        macro=macro_selection.rows,
        market_context=dict(
            snapshot.get("marketContext")
            or {"available": False, "reason": "absent"}
        ),
        provenance=provenance,
        input_quality=dict(snapshot.get("quality") or {}),
        base_disclaimers=list(snapshot.get("disclaimers") or []),
        fact_source=fact_source,
        selection=selection,
        macro_selection=macro_selection,
        ambiguous=ambiguous,
        universe=universe,
    )


def validate_snapshot(
    settings: EngineSettings, ticker: str, snapshot: dict
) -> ValidationReport:
    return validate_document(
        "research-input", snapshot, subject=ticker, settings=settings.pipeline
    )


def available_tickers(settings: EngineSettings) -> List[str]:
    """Issuers Stage 1 has produced a snapshot for, in deterministic order."""
    directory = settings.input_snapshots
    if not directory.is_dir():
        return []
    return sorted(p.stem for p in directory.glob("*.json"))


# ---------------------------------------------------------------------------
# sources
# ---------------------------------------------------------------------------


def _fact_rows(
    settings: EngineSettings, ticker: str, snapshot: dict
) -> Tuple[List[dict], str]:
    """Prefer the fact store; fall back to the snapshot's flattened facts.

    The fact store is preferred because it holds every revision, including the
    ones a historical cutoff has to select between. Falling back to the
    snapshot is honest for a current-date run and is recorded as such, so an
    audit can tell which happened.
    """
    store: List[dict] = []
    for directory in (settings.facts_annual, settings.facts_quarterly):
        store.extend(read_jsonl(Path(directory) / f"{ticker}.jsonl"))

    if store:
        superseded = [
            row for row in read_jsonl(settings.restatements_file)
            if row.get("ticker") == ticker
        ]
        return store + superseded, "FACT_STORE"

    return list(snapshot.get("facts") or []), "INPUT_SNAPSHOT"


def _macro_rows(settings: EngineSettings) -> List[dict]:
    rows: List[dict] = []
    root = Path(settings.macro_dir)
    if not root.is_dir():
        return rows
    for path in sorted(root.rglob("*.jsonl")):
        rows.extend(read_jsonl(path))
    return rows


# ---------------------------------------------------------------------------
# shaping
# ---------------------------------------------------------------------------


def _normalise(row: dict) -> dict:
    """One fact shape, whichever tier it came from.

    Fact-store rows nest their provenance under ``source``; snapshot rows carry
    it flat. Downstream code should not have to know which.
    """
    source = row.get("source") or {}
    return {
        "metric": row["metric"],
        "segment": row.get("segment"),
        "periodType": row["periodType"],
        "periodStart": row.get("periodStart"),
        "periodEnd": row["periodEnd"],
        "fiscalYear": row.get("fiscalYear"),
        "basis": row.get("basis", "REPORTED"),
        "value": row.get("value"),
        "missingReason": row.get("missingReason"),
        "unit": row.get("unit") or "IDR",
        "currency": row.get("currency"),
        "revision": row.get("revision"),
        "qualityStatus": row.get("qualityStatus", "UNVALIDATED"),
        "sourceRef": row.get("sourceRef") or source.get("documentRef"),
        "publishedAt": row.get("publishedAt") or source.get("publishedAt"),
        "retrievedAt": row.get("retrievedAt") or source.get("retrievedAt"),
    }


def _fact_sort_key(row: dict) -> tuple:
    return (
        row["periodEnd"],
        row["metric"],
        row.get("segment") or "",
        str(row.get("basis") or ""),
    )


def _ambiguous(rows: Sequence[dict]) -> List[str]:
    """Facts that cannot be told apart.

    Two rows describing the same metric, period and segment leave no basis for
    choosing between them, and choosing anyway would be a silent guess that
    changes a published number. Reported, not resolved.
    """
    seen: Dict[tuple, int] = {}
    for row in rows:
        key = (row["metric"], row["periodType"], row["periodEnd"],
               row.get("segment") or "CONSOLIDATED")
        seen[key] = seen.get(key, 0) + 1
    return sorted("|".join(k) for k, count in seen.items() if count > 1)


__all__ = [
    "EngineInput",
    "InputError",
    "SnapshotMissing",
    "load",
    "available_tickers",
    "today_utc",
]
