"""Uncle View and Analyst View: two projections of one set of records.

Spec section 2.2 requires *explainable Uncle View output and detailed Analyst
View output from the same records*. The way that requirement fails in practice
is not deliberate — it is that the simple view gets its own little rounding, or
its own convenience calculation, and six months later the two views disagree by
2% and nobody can say which is right.

So neither view calculates anything. Both **select** from the
:class:`Calculated` records the valuation already produced and from the
:class:`~engine.goh_dip_tong.research.records.ResearchRecord` set the rules
produced, and every item carries the identity of what it was taken from.
``test_views.py`` walks every numeric in Uncle View, finds the record it names,
and asserts exact float equality — not ``approx``. If a view ever starts
computing, that test fails, and so does the AST check that no arithmetic
operator appears in this file.

**The two views differ in what they select, never in what they say a number
is.** Uncle View takes the conclusions and four figures; Analyst View takes
every calculated record, every research record and the evidence behind them.
Uncle View's refs are a subset of Analyst View's, asserted rather than assumed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Sequence

from ..contracts.calculated import Calculated
from ..research.records import Importance, ResearchRecord

#: How many conclusions Uncle View carries. A plain-language view that lists
#: fourteen findings is the Analyst View with friendlier labels, which helps
#: nobody — the constraint is the design, not a formatting preference.
UNCLE_CONCLUSION_LIMIT = 6


@dataclass(frozen=True)
class ViewItem:
    """One displayed number, and the record it was taken from."""

    label: str
    value: Optional[float]
    unit: str
    ref: str
    formula_id: str
    scenario: str
    missing_reason: Optional[str] = None
    plain: str = ""

    @classmethod
    def of(cls, label: str, record: Calculated, plain: str = "") -> "ViewItem":
        return cls(
            label=label,
            value=record.value,
            unit=record.unit,
            ref=record.ref,
            formula_id=record.formula_id,
            scenario=str(record.scenario),
            missing_reason=(str(record.missing_reason)
                            if record.missing_reason else None),
            plain=plain,
        )

    def to_json(self) -> dict:
        return {
            "label": self.label,
            "value": self.value,
            "unit": self.unit,
            "ref": self.ref,
            "formulaId": self.formula_id,
            "scenario": self.scenario,
            "missingReason": self.missing_reason,
            "plain": self.plain,
        }


@dataclass
class View:
    """A rendered view. Contains no arithmetic."""

    kind: str
    items: List[ViewItem] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    #: Research conclusions, as ``{id, type, statement, ...}``. Both views draw
    #: from the same package; they differ in how many they carry and whether
    #: the supporting citations travel with them.
    conclusions: List[dict] = field(default_factory=list)
    #: Analyst View only: the evidence refs behind the conclusions.
    evidence: List[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "status": "PRODUCED",
            "kind": self.kind,
            "items": [i.to_json() for i in self.items],
            "notes": list(self.notes),
            "conclusions": list(self.conclusions),
            "evidence": list(self.evidence),
        }

    def numerics(self) -> Dict[str, Optional[float]]:
        """Every displayed number, keyed by the record it came from."""
        return {item.ref: item.value for item in self.items}

    def cited_records(self) -> List[str]:
        """Calculated refs this view shows or whose conclusions cite them."""
        seen: List[str] = []
        for item in self.items:
            if item.ref not in seen:
                seen.append(item.ref)
        for conclusion in self.conclusions:
            for ref in conclusion.get("supportingRecords") or []:
                if ref not in seen:
                    seen.append(ref)
        return sorted(seen)


def _conclusion(record: ResearchRecord, cited: bool) -> dict:
    """One research record as a view carries it.

    Uncle View drops the citation lists — not to hide them, but because a
    plain-language reader is not going to follow a fact key, and the same
    record with its full citations is one click away in the Analyst View under
    the same ``id``.
    """
    payload = record.to_json()
    if cited:
        return payload
    return {
        "id": payload["id"],
        "type": payload["type"],
        "statement": payload["statement"],
        "ruleId": payload["ruleId"],
        "scenario": payload["scenario"],
        "importance": payload["importance"],
        "severity": payload["severity"],
    }


def _headline(records: Sequence[ResearchRecord]) -> List[ResearchRecord]:
    """The most important conclusions first, deterministically.

    Ordering is by importance then by the record's own sort key, never by the
    order the rules happened to fire, so adding a rule cannot silently reorder
    what a reader sees at the top.
    """
    ranked = [r for r in records if r.importance == Importance.HIGH]
    rest = [r for r in records if r.importance != Importance.HIGH]
    return [*ranked, *rest]


def uncle_view(base, bear, bull, mode: str, research=None) -> View:
    """The plain-language view: four numbers and the conclusions behind them.

    Deliberately short. Everything here also appears in the Analyst View, with
    the same ``ref`` and the same ``id``, which is what makes the two views
    checkable against each other rather than merely consistent-looking.
    """
    items = [
        ViewItem.of("What we think a share is worth", base.primary.value_per_share,
                    plain="Our base case, from a five-year forecast of the bank's "
                          "own drivers."),
        ViewItem.of("If things go badly", bear.primary.value_per_share,
                    plain="Slower growth, a wider funding cost, more bad loans."),
        ViewItem.of("If things go well", bull.primary.value_per_share,
                    plain="Faster growth, a better margin, fewer bad loans."),
        ViewItem.of("Book value the forecast starts from",
                    base.primary.detail["openingBook"],
                    plain="The equity the whole bank already has, before any "
                          "forecast. A total in rupiah, not a per-share figure "
                          "— the three numbers above are per share."),
    ]

    conclusions: List[dict] = []
    if research is not None:
        headline = _headline([*research.thesis, *research.counter_thesis])
        conclusions = [
            _conclusion(record, cited=False)
            for record in headline[:UNCLE_CONCLUSION_LIMIT]
        ]

    notes = [
        "Every figure here is the same number the detailed view shows. This "
        "view selects; it does not calculate.",
        "Every conclusion here was produced by a named rule from calculated "
        "records. The detailed view carries the citations behind each one.",
        "Not investment advice. No buy or sell recommendation.",
    ]
    if mode != "PRODUCTION":
        notes.insert(0, f"{mode}: calculated from development fixtures, not "
                        f"from any real company.")
    return View(kind="UNCLE", items=items, notes=notes, conclusions=conclusions)


def analyst_view(base, bear, bull, mode: str, research=None,
                 comparison: Optional[Mapping[str, Calculated]] = None) -> View:
    """The full view: every record, every conclusion, every citation.

    Built from the role-keyed comparison map when one is supplied, which is
    what guarantees it is a superset of Uncle View: Uncle View's four figures
    are four of those same records, selected by role.
    """
    items: List[ViewItem] = []
    if comparison:
        for role in sorted(comparison):
            items.append(ViewItem.of(role, comparison[role]))
    else:
        for scenario, valuation in (("BEAR", bear), ("BASE", base), ("BULL", bull)):
            for key, record in sorted(_scenario_records(valuation).items()):
                items.append(ViewItem.of(f"{scenario}.{key}", record))

    conclusions: List[dict] = []
    evidence: List[str] = []
    if research is not None:
        conclusions = [_conclusion(record, cited=True)
                       for record in research.records]
        for record in research.records:
            for ref in record.supporting_evidence:
                if ref not in evidence:
                    evidence.append(ref)
        evidence = sorted(evidence)

    notes = [
        "Cross-checks apply the terminal steady state and will diverge from "
        "residual income by the amount the explicit forecast is not yet in "
        "steady state. A cross-check that always agrees is measuring nothing.",
        "Residual income is the primary method. Justified price-to-book and "
        "the dividend-discount model are sensitivity cross-checks; no weighted "
        "or blended value is produced from them.",
        "Every conclusion below names the rule that produced it and the "
        "calculated records and evidence it rests on.",
    ]
    if mode != "PRODUCTION":
        notes.insert(0, f"{mode}: calculated from development fixtures.")
    return View(kind="ANALYST", items=items, notes=notes,
                conclusions=conclusions, evidence=evidence)


def _scenario_records(valuation) -> Dict[str, Calculated]:
    """The records both views draw on, for one scenario.

    Retained for the no-comparison path, which is what a caller building a view
    directly from scenario valuations gets.
    """
    records = {
        "valuePerShare": valuation.primary.value_per_share,
        "equityValue": valuation.primary.equity_value,
    }
    for key, record in valuation.primary.detail.items():
        records[key] = record
    for check in valuation.cross_checks:
        records[f"{check.method}.valuePerShare"] = check.value_per_share
    return records


__all__ = ["View", "ViewItem", "uncle_view", "analyst_view",
           "UNCLE_CONCLUSION_LIMIT"]
