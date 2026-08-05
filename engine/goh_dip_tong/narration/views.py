"""Uncle View and Analyst View: two projections of one set of records.

Spec section 2.2 requires *explainable Uncle View output and detailed Analyst
View output from the same records*. The way that requirement fails in practice
is not deliberate — it is that the simple view gets its own little rounding, or
its own convenience calculation, and six months later the two views disagree by
2% and nobody can say which is right.

So neither view calculates anything. Both **select** from the
:class:`Calculated` records the valuation already produced, and each item
carries the `ref` of the record it came from. `test_views.py` walks every
numeric in Uncle View, finds the record it names, and asserts exact float
equality — not `approx`. If a view ever starts computing, that test fails.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..contracts.calculated import Calculated


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

    def to_json(self) -> dict:
        return {
            "status": "PRODUCED",
            "kind": self.kind,
            "items": [i.to_json() for i in self.items],
            "notes": list(self.notes),
        }

    def numerics(self) -> Dict[str, Optional[float]]:
        """Every displayed number, keyed by the record it came from."""
        return {item.ref: item.value for item in self.items}


def _scenario_records(valuation) -> Dict[str, Calculated]:
    """The records both views draw on, for one scenario."""
    records = {
        "valuePerShare": valuation.primary.value_per_share,
        "equityValue": valuation.primary.equity_value,
    }
    for key, record in valuation.primary.detail.items():
        records[key] = record
    for check in valuation.cross_checks:
        records[f"{check.method}.valuePerShare"] = check.value_per_share
    return records


def uncle_view(base, bear, bull, mode: str) -> View:
    """The plain-language view. Five numbers, no arithmetic.

    Deliberately short. A view that shows everything is the Analyst View with
    friendlier labels, which helps nobody.
    """
    items = [
        ViewItem.of("What we think a share is worth", base.primary.value_per_share,
                    plain="Our base case, from a five-year forecast of the bank's "
                          "own drivers."),
        ViewItem.of("If things go badly", bear.primary.value_per_share,
                    plain="Slower growth, a wider funding cost, more bad loans."),
        ViewItem.of("If things go well", bull.primary.value_per_share,
                    plain="Faster growth, a better margin, fewer bad loans."),
        ViewItem.of("The return the bank earns on its own money",
                    base.primary.detail.get("openingBook")
                    if "openingBook" in base.primary.detail
                    else base.primary.equity_value,
                    plain="Book value the forecast starts from."),
    ]
    notes = [
        "Every figure here is the same number the detailed view shows. This "
        "view selects; it does not calculate.",
        "Not investment advice. No buy or sell recommendation.",
    ]
    if mode != "PRODUCTION":
        notes.insert(0, f"{mode}: calculated from development fixtures, not "
                        f"from any real company.")
    return View(kind="UNCLE", items=items, notes=notes)


def analyst_view(base, bear, bull, mode: str) -> View:
    """The full view. Same records, every one of them."""
    items: List[ViewItem] = []
    for scenario, valuation in (("BEAR", bear), ("BASE", base), ("BULL", bull)):
        for key, record in sorted(_scenario_records(valuation).items()):
            items.append(ViewItem.of(f"{scenario}.{key}", record))
    for index, record in enumerate(base.residual_income, start=1):
        items.append(ViewItem.of(f"BASE.residualIncome.year{index}", record))

    notes = [
        "Cross-checks apply the terminal steady state and will diverge from "
        "residual income by the amount the explicit forecast is not yet in "
        "steady state. A cross-check that always agrees is measuring nothing.",
    ]
    if mode != "PRODUCTION":
        notes.insert(0, f"{mode}: calculated from development fixtures.")
    return View(kind="ANALYST", items=items, notes=notes)


__all__ = ["View", "ViewItem", "uncle_view", "analyst_view"]
