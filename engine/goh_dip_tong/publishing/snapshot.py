"""Assembling and writing one issuer's research snapshot.

Two properties are carried over from Stage 1 deliberately, because both were
learned the expensive way there:

**Volatile fields are excluded from identity.** ``calculatedAt`` records when
we ran, not what we found. Leaving it inside the content hash would make every
rebuild look like new research, which is the same defect as the membership
heartbeat that rewrote thirty rows a day.

**No-change means no-write.** A dated snapshot is written only when its
substantive content differs from the newest one already stored for that issuer.
Otherwise a daily rebuild deposits an identical document under a new date every
day and the repository grows without gaining information.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pipeline.goh_dip_tong.contracts.records import ValidationReport
from pipeline.goh_dip_tong.publishing.writers import (
    VOLATILE_FIELDS,
    canonical_json,
    read_json,
    stable_content_hash,
    write_text_if_changed,
)
from pipeline.goh_dip_tong.validation.schema import validate_document

from .. import ENGINE_VERSION, FORMULA_REGISTRY_HASH, MODEL_VERSION
from ..contracts.enums import ResearchStatus
from ..contracts.model import ModelContext, SectorModel
from ..contracts.refusal import ValuationRefusal
from ..contracts.registry import REGISTRY
from ..inputs.loader import EngineInput
from ..inputs.provenance import disclaimers_for
from ..settings import EngineSettings

SCHEMA_VERSION = "1.0.0"

#: Stage 1's volatile set, plus three engine fields that record *when we ran*
#: rather than *what we found*. Anything here is excluded from the content hash
#: and from change comparison.
#:
#: ``asOf`` and ``ageDays`` are the subtle ones, and they are here because of
#: the defect Stage 1 hit: a value truncated to a date is stable *for a day*,
#: not stable. Leaving them in would give identical research a new hash every
#: morning, and every rebuild would deposit an identical document under a new
#: date. When the cutoff genuinely changes what was knowable — as it does
#: across a restatement — the facts themselves differ, so the hash moves on the
#: evidence rather than on the calendar.
ENGINE_VOLATILE_FIELDS: Tuple[str, ...] = tuple(VOLATILE_FIELDS) + (
    "calculatedAt",
    "asOf",
    "ageDays",
)

#: Sections this engine version does not produce, and why. Explicit absences —
#: an empty object would leave a reader guessing whether the engine tried.
_NOT_PRODUCED_REASON = (
    "Not produced by engine {version}. Forecast, valuation and narration "
    "mathematics are implemented in a later slice; emitting an empty section "
    "here would be indistinguishable from a calculation that returned nothing."
)


@dataclass
class BuildResult:
    """One issuer's snapshot and what happened to it."""

    ticker: str
    document: dict
    report: ValidationReport
    written_path: Optional[Path] = None
    pointer_path: Optional[Path] = None
    unchanged: bool = False

    @property
    def ok(self) -> bool:
        return self.report.ok


# ---------------------------------------------------------------------------
# building
# ---------------------------------------------------------------------------


def build(
    settings: EngineSettings,
    engine_input: EngineInput,
    model: SectorModel,
    context: ModelContext,
    calculated_at: str,
) -> dict:
    """Assemble the output document. Pure: this writes nothing."""
    outcome = model.evaluate(engine_input, context)
    gates = model.gates(engine_input, context)
    valued = not isinstance(outcome, ValuationRefusal)

    facts = [c.to_json() for c in engine_input.facts]
    freshness = _freshness(engine_input, settings)
    status = _research_status(engine_input, model, outcome, freshness["stale"])
    not_produced = {
        "status": "NOT_PRODUCED",
        "reason": _NOT_PRODUCED_REASON.format(version=ENGINE_VERSION),
    }
    # Sections that exist only when a valuation was produced. A refusal leaves
    # them as explicit absences rather than empty objects, so a reader can tell
    # "the engine declined" from "the engine produced nothing".
    drivers = _driver_section(outcome) if valued else dict(not_produced)
    forecast = _forecast_section(outcome) if valued else dict(not_produced)
    uncle = (outcome.views["uncle"].to_json() if valued else dict(not_produced))
    analyst = (outcome.views["analyst"].to_json() if valued else dict(not_produced))

    document = {
        "schemaVersion": SCHEMA_VERSION,
        "mode": str(engine_input.provenance.mode),
        "ticker": engine_input.ticker,
        "asOf": engine_input.as_of,
        "modelVersion": MODEL_VERSION,
        "engineVersion": ENGINE_VERSION,
        "generatedAt": calculated_at,
        "researchStatus": str(status),

        "company": {
            "name": engine_input.identity.get("name"),
            "sectorCode": engine_input.identity.get("sectorCode"),
            "sectorName": engine_input.identity.get("sectorName"),
            "industryCode": engine_input.identity.get("industryCode"),
            "industryName": engine_input.identity.get("industryName"),
            "modelFamily": engine_input.identity.get("modelFamily"),
            "reportingCurrency": engine_input.identity.get("reportingCurrency"),
            "inIdx30": bool(engine_input.identity.get("inIdx30", False)),
        },

        "coverage": {
            # Stage 1's value, carried through untouched. The engine reads
            # coverageStatus and never writes it: two vocabularies, one owner
            # each.
            "coverageStatus": engine_input.identity.get("coverageStatus"),
            "researchStatus": str(status),
            "modelFamily": engine_input.identity.get("modelFamily"),
            "modelImplemented": bool(model.implemented),
            "permittedMethods": sorted(str(m) for m in model.permitted_methods),
            "forbiddenMethods": sorted(str(m) for m in model.forbidden_methods),
            "notApplicableMetrics": sorted(model.not_applicable_metrics),
        },

        "freshness": freshness,
        "quality": _quality(engine_input, model),

        "reported": {"values": facts, "count": len(facts)},
        "normalized": dict(not_produced),
        "derivedMetrics": dict(not_produced),
        "drivers": drivers,
        "forecast": forecast,
        "thesis": dict(not_produced),
        "counterThesis": dict(not_produced),
        "uncleView": uncle,
        "analystView": analyst,

        "valuation": outcome.to_json(),

        "marketImplied": _market_implied(engine_input, outcome if valued else None),

        "catalysts": [],
        "risks": [],
        "breakers": [],

        "evidence": _evidence(engine_input),

        "modelAudit": {
            "engineVersion": ENGINE_VERSION,
            "modelVersion": MODEL_VERSION,
            "formulaRegistryHash": FORMULA_REGISTRY_HASH,
            "formulaCount": len(REGISTRY),
            "gates": gates.to_json(),
            "macroContext": _macro_context(engine_input),
            **engine_input.to_audit_json(),
        },

        "disclaimers": disclaimers_for(
            engine_input.provenance, engine_input.base_disclaimers
        ),
    }

    document["contentHash"] = stable_content_hash(
        {k: v for k, v in document.items() if k != "generatedAt"},
        ENGINE_VOLATILE_FIELDS,
    )
    return document


def validate(settings: EngineSettings, document: dict) -> ValidationReport:
    return validate_document(
        "research-snapshot", document,
        subject=document.get("ticker", ""), settings=settings.pipeline,
    )


# ---------------------------------------------------------------------------
# writing
# ---------------------------------------------------------------------------


def write(
    settings: EngineSettings, document: dict
) -> Tuple[Optional[Path], Optional[Path], bool]:
    """Write the dated snapshot and refresh the pointer.

    Returns ``(snapshot_path, pointer_path, unchanged)``. When the content
    matches the newest stored snapshot, nothing is written and the existing
    pointer is left exactly as it is — including its date, which stays truthful
    as "when this research was produced" rather than "when we last rebuilt".
    """
    ticker = document["ticker"]
    as_of = document["asOf"]
    model_version = document["modelVersion"]

    newest = _newest_stored(settings, ticker)
    if newest is not None and newest.get("contentHash") == document["contentHash"]:
        return None, None, True

    path = settings.output_snapshot(ticker, as_of, model_version)
    write_text_if_changed(path, canonical_json(document))

    pointer = settings.output_current / f"{ticker}.json"
    write_text_if_changed(pointer, canonical_json(_pointer(settings, document, path)))
    return path, pointer, False


def _pointer(settings: EngineSettings, document: dict, path: Path) -> dict:
    """The ``current/<TICKER>.json`` pointer.

    Carries the *snapshot's* asOf, not today's date. A pointer stamped with the
    rebuild date would churn daily even when it points at the same unchanged
    research.
    """
    return {
        "schemaVersion": SCHEMA_VERSION,
        "ticker": document["ticker"],
        "mode": document["mode"],
        "asOf": document["asOf"],
        "modelVersion": document["modelVersion"],
        "engineVersion": document["engineVersion"],
        "researchStatus": document["researchStatus"],
        "valuationStatus": document["valuation"].get("status"),
        "contentHash": document["contentHash"],
        "snapshot": settings.rel(path),
    }


def _newest_stored(settings: EngineSettings, ticker: str) -> Optional[dict]:
    """The most recent snapshot already on disk for this issuer, if any."""
    directory = settings.output_root / ticker
    if not directory.is_dir():
        return None
    candidates = sorted(directory.glob("*/*.json"))
    if not candidates:
        return None
    return read_json(candidates[-1])


def stored_snapshots(settings: EngineSettings, ticker: str) -> List[Path]:
    directory = settings.output_root / ticker
    return sorted(directory.glob("*/*.json")) if directory.is_dir() else []


# ---------------------------------------------------------------------------
# sections
# ---------------------------------------------------------------------------


def _research_status(
    engine_input: EngineInput, model: SectorModel, valuation, stale: bool
) -> ResearchStatus:
    """Where research has actually got to for this issuer.

    Deliberately conservative at every branch: the engine never promotes an
    issuer past what its inputs support, and it never promotes one past what
    Stage 1's own coverageStatus says.
    """
    if engine_input.identity.get("coverageStatus") == "SUSPENDED":
        return ResearchStatus.MODEL_SUSPENDED
    if stale:
        return ResearchStatus.STALE
    if not engine_input.metrics_present():
        return ResearchStatus.DISCOVERY
    if not engine_input.identity.get("modelFamily"):
        # Facts are sound, but no model applies — Stage 1's ONBOARDING rule.
        return ResearchStatus.FINANCIALS_VALIDATED
    if isinstance(valuation, ValuationRefusal):
        return ResearchStatus.MODEL_UNDER_VALIDATION
    return ResearchStatus.FULL_RESEARCH


def _freshness(engine_input: EngineInput, settings: EngineSettings) -> dict:
    published = [
        r.published_at
        for c in engine_input.facts
        for r in c.input_refs
        if r.published_at
    ]
    newest = max(published) if published else None
    age = _age_days(newest, engine_input.as_of)
    limit = (settings.engine_config().get("gates") or {}).get("max_input_age_days")
    return {
        "asOf": engine_input.as_of,
        "newestPublishedAt": newest,
        "newestRetrievedAt": None,
        "ageDays": age,
        "stale": bool(limit and age is not None and age > int(limit)),
    }


def _age_days(published_at: Optional[str], as_of: str) -> Optional[int]:
    if not published_at:
        return None
    try:
        then = date.fromisoformat(str(published_at)[:10])
        now = date.fromisoformat(as_of)
    except ValueError:
        return None
    return (now - then).days


def _quality(engine_input: EngineInput, model: SectorModel) -> dict:
    """Output quality, which is not the same as input quality.

    ``completeness`` here measures what the *model* needs, not what the issuer
    happened to report. An issuer whose reported facts are all present is 100%
    complete by Stage 1's measure and can still be missing fifteen of the
    seventeen metrics the model requires — and it is that second number that
    determines whether anything can be valued.
    """
    present = engine_input.metrics_present()
    required = list(model.required_metrics)
    missing = sorted(m for m in required if m not in present)
    completeness = (
        round((len(required) - len(missing)) / len(required), 4) if required else 1.0
    )

    flags = sorted({
        *(engine_input.input_quality.get("flags") or []),
        str(engine_input.provenance.mode),
        "NO_VALUATION_PRODUCED",
    })
    if engine_input.ambiguous:
        flags = sorted({*flags, "AMBIGUOUS_FACTS"})

    return {
        "status": engine_input.input_quality.get("status", "UNVALIDATED"),
        "completeness": completeness,
        "flags": flags,
        "missingCriticalMetrics": missing,
        "inputQuality": dict(engine_input.input_quality),
    }


def _driver_section(valuation) -> dict:
    """The assumption set behind each scenario, with its historical anchor.

    Spec section 2.6 wants every assumption to state where it came from. The
    anchor and the offset are both here, so the scenario's claim is the
    difference between them rather than an unexplained number.
    """
    return {
        "status": "PRODUCED",
        "scenarios": {
            name: valuation.projections[name].assumptions.to_json()
            for name in valuation.scenario_order
        },
    }


def _forecast_section(valuation) -> dict:
    """The projected line items, per scenario, per year."""
    return {
        "status": "PRODUCED",
        "horizon": valuation.projections[valuation.scenario_order[0]].horizon,
        "scenarios": {
            name: valuation.projections[name].to_json()
            for name in valuation.scenario_order
        },
    }


def _market_implied(engine_input: EngineInput, valuation=None) -> dict:
    """Spec section 2.7, structurally unavailable.

    Solving a price back to operating assumptions requires a price. The
    market-price provider is PRIVATE_RESEARCH_ONLY, so there is none — this is
    a rights outcome, not an unimplemented feature, and saying so is more
    useful than an empty object.
    """
    market = engine_input.market_context or {}
    if valuation is not None and getattr(valuation, "implied", None):
        return {
            "available": True,
            "reason": None,
            "rightsStatus": market.get("rightsStatus"),
            "cases": valuation.implied.to_json(),
        }
    if market.get("available"):
        return {
            "available": False,
            "reason": "A price is available but no sustainable ROE reproduces "
                      "it within the solver's bracket, so no market-implied "
                      "case can be stated.",
            "rightsStatus": market.get("rightsStatus"),
            "cases": {},
        }
    return {
        "available": False,
        "reason": market.get("reason")
        or "No market data is available, so no market-implied case can be solved.",
        "rightsStatus": market.get("rightsStatus"),
        "cases": {},
    }


def _evidence(engine_input: EngineInput) -> List[dict]:
    """Every contributing record, deduplicated and ordered."""
    seen: Dict[str, dict] = {}
    for calculated in engine_input.facts:
        for ref in calculated.input_refs:
            seen.setdefault(ref.ref, ref.to_json())
    for row in engine_input.macro:
        ref = f"{row.get('seriesId')}@{row.get('observationPeriod')}"
        seen.setdefault(ref, {
            "ref": ref,
            "kind": "MACRO",
            "sourceRef": row.get("providerId"),
            "publishedAt": row.get("publishedAt"),
        })
    return [seen[key] for key in sorted(seen)]


def _macro_context(engine_input: EngineInput) -> List[dict]:
    """Macro observations as at the cutoff.

    Context only. Nothing here feeds a discount rate: BI_7DRR is a policy rate,
    not a risk-free yield, and cost-of-capital.yml records why it is refused as
    a substitute.
    """
    return [
        {
            "seriesId": row.get("seriesId"),
            "observationPeriod": row.get("observationPeriod"),
            "value": row.get("value"),
            "missingReason": row.get("missingReason"),
            "unit": row.get("unit"),
            "releaseVintage": row.get("releaseVintage"),
            "publishedAt": row.get("publishedAt"),
            "usedInCalculation": False,
        }
        for row in sorted(
            engine_input.macro,
            key=lambda r: (str(r.get("seriesId")), str(r.get("observationPeriod"))),
        )
    ]


__all__ = [
    "BuildResult",
    "SCHEMA_VERSION",
    "ENGINE_VOLATILE_FIELDS",
    "build",
    "validate",
    "write",
    "stored_snapshots",
]
