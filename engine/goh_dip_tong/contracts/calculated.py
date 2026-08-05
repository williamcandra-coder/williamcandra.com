"""The record every engine calculation produces.

Spec section 2.4 requires each calculated value to store its metric ID, value,
unit, currency, business period, formula ID, input record IDs, model version,
scenario, quality status and calculation timestamp. :class:`Calculated` is that
list made into a type, so a number that cannot say where it came from cannot be
constructed in the first place.

The value itself is a Stage 1 :class:`Measure`, deliberately rather than a
bare float. That is what keeps "missing" impossible to confuse with zero all
the way from the collector to the published snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from pipeline.goh_dip_tong.contracts.enums import (
    MissingReason,
    PeriodType,
    QualityStatus,
    ValueBasis,
)
from pipeline.goh_dip_tong.contracts.records import ContractError, Measure

from .enums import ScenarioName


@dataclass(frozen=True)
class Period:
    """The business period a value describes.

    Not the period we calculated in. Conflating the two is how a figure ends up
    filed under the year someone happened to run the engine.
    """

    period_type: PeriodType
    period_end: str
    period_start: Optional[str] = None
    fiscal_year: Optional[int] = None

    def __post_init__(self) -> None:
        if not self.period_end:
            raise ContractError("a Period must have a periodEnd")

    @classmethod
    def instant(cls, period_end: str, fiscal_year: Optional[int] = None) -> "Period":
        return cls(PeriodType.POINT_IN_TIME, period_end, None, fiscal_year)

    @property
    def key(self) -> tuple:
        """Deterministic sort key. Ordering by this is what keeps output stable."""
        return (self.period_end, str(self.period_type), self.fiscal_year or 0)

    def to_json(self) -> dict:
        return {
            "periodType": str(self.period_type),
            "periodStart": self.period_start,
            "periodEnd": self.period_end,
            "fiscalYear": self.fiscal_year,
        }


@dataclass(frozen=True)
class InputRef:
    """A pointer back to one record a calculation consumed.

    ``ref`` is the identity of the source record — a Stage 1 ``factKey``, a
    macro ``seriesId@observationPeriod``, or another ``Calculated``'s ref — so
    a published number can always be walked back to reported facts.
    """

    ref: str
    kind: str = "FACT"
    source_ref: Optional[str] = None
    published_at: Optional[str] = None

    def to_json(self) -> dict:
        return {
            "ref": self.ref,
            "kind": self.kind,
            "sourceRef": self.source_ref,
            "publishedAt": self.published_at,
        }


@dataclass(frozen=True)
class Calculated:
    """One value the engine produced, with its full derivation.

    Construct these through
    :class:`~engine.goh_dip_tong.contracts.registry.FormulaRegistry` rather than
    directly. Direct construction is possible — inputs from the fact store need
    it — but anything *computed* must come through the registry so its
    ``formula_id`` and ``input_refs`` are populated by machine rather than by
    whoever remembered to.
    """

    metric_id: str
    measure: Measure
    period: Period
    formula_id: str
    model_version: str
    calculated_at: str
    scenario: ScenarioName = ScenarioName.ACTUAL
    input_refs: Tuple[InputRef, ...] = ()
    segment: Optional[str] = None
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.metric_id:
            raise ContractError("a Calculated must name its metric")
        if not self.formula_id:
            raise ContractError(
                f"{self.metric_id}: a Calculated must name the formula that "
                f"produced it; an untraceable number is not publishable"
            )

    # ---- convenience passthroughs ----------------------------------------
    @property
    def value(self) -> Optional[float]:
        return self.measure.value

    @property
    def is_missing(self) -> bool:
        return self.measure.is_missing

    @property
    def missing_reason(self) -> Optional[MissingReason]:
        return self.measure.missing_reason

    @property
    def basis(self) -> ValueBasis:
        return self.measure.basis

    @property
    def unit(self) -> str:
        return self.measure.unit

    @property
    def currency(self) -> Optional[str]:
        return self.measure.currency

    @property
    def quality_status(self) -> QualityStatus:
        return self.measure.quality_status

    @property
    def ref(self) -> str:
        """This value's own identity, usable as another calculation's input ref.

        The formula ID is part of the identity, not decoration. Two methods can
        produce an "equity value" for the same issuer, period and scenario and
        mean different numbers; a reference that cannot tell them apart is not
        a reference, and a view resolving one to the other would show the wrong
        figure while passing every equality check.
        """
        segment = self.segment or "CONSOLIDATED"
        return (
            f"{self.metric_id}|{self.period.period_type}|{self.period.period_end}"
            f"|{segment}|{self.scenario}|{self.formula_id}"
        )

    def as_input(self) -> InputRef:
        return InputRef(ref=self.ref, kind="CALCULATED")

    def to_json(self) -> dict:
        """Serialised form. Key order is irrelevant — writers sort keys — but
        the field set is the contract Stage 3 reads."""
        return {
            "metric": self.metric_id,
            "segment": self.segment,
            "value": self.measure.value,
            "missingReason": (
                str(self.measure.missing_reason) if self.measure.missing_reason else None
            ),
            "unit": self.measure.unit,
            "currency": self.measure.currency,
            "basis": str(self.measure.basis),
            "qualityStatus": str(self.measure.quality_status),
            "scenario": str(self.scenario),
            "formulaId": self.formula_id,
            "inputRefs": [r.to_json() for r in self.input_refs],
            "modelVersion": self.model_version,
            "calculatedAt": self.calculated_at,
            "notes": self.notes,
            **self.period.to_json(),
        }


def from_fact(
    fact: dict, model_version: str, calculated_at: str, ticker: str = ""
) -> Calculated:
    """Lift one Stage 1 snapshot fact into the engine's record type.

    Reported facts are not calculated, so their ``formula_id`` is the sentinel
    ``source.fact`` rather than a real formula. That keeps the field populated
    — every value can say where it came from — while making it obvious in any
    audit trail that the engine did no arithmetic here.
    """
    unit = fact.get("unit") or "IDR"
    reason = fact.get("missingReason")
    basis = ValueBasis(fact.get("basis", "REPORTED"))
    quality = QualityStatus(fact.get("qualityStatus", "UNVALIDATED"))

    if fact.get("value") is None:
        if not reason:
            raise ContractError(
                f"{ticker or '?'}/{fact.get('metric')}: a null fact arrived without "
                f"a missingReason; Stage 1 guarantees one, so this input is corrupt"
            )
        measure = Measure.missing(
            MissingReason(reason), unit=unit, currency=fact.get("currency"), basis=basis
        )
    else:
        measure = Measure(
            value=float(fact["value"]),
            unit=unit,
            currency=fact.get("currency"),
            basis=basis,
            quality_status=quality,
        )

    return Calculated(
        metric_id=fact["metric"],
        measure=measure,
        period=Period(
            period_type=PeriodType(fact["periodType"]),
            period_end=fact["periodEnd"],
            period_start=fact.get("periodStart"),
            fiscal_year=fact.get("fiscalYear"),
        ),
        formula_id="source.fact",
        model_version=model_version,
        calculated_at=calculated_at,
        scenario=ScenarioName.ACTUAL,
        segment=fact.get("segment"),
        input_refs=(
            InputRef(
                ref=fact_key(ticker, fact),
                kind="FACT",
                source_ref=fact.get("sourceRef"),
                published_at=fact.get("publishedAt"),
            ),
        ),
    )


def from_assumption(
    driver_id: str,
    value: float,
    period: Period,
    model_version: str,
    calculated_at: str,
    unit: str = "RATIO",
    scenario: ScenarioName = ScenarioName.ACTUAL,
    note: Optional[str] = None,
) -> Calculated:
    """Lift a forecast assumption into the engine's record type.

    Assumptions are inputs to the mathematics but outputs of a derivation from
    history, so they carry ``source.assumption`` rather than a formula ID. The
    distinction matters in an audit trail: it marks the boundary between what
    was observed and what was assumed, which is the first thing anyone
    disagreeing with a valuation needs to find.
    """
    return Calculated(
        metric_id=driver_id,
        measure=Measure(
            value=float(value),
            unit=unit,
            currency=None if unit in ("RATIO", "PERIODS") else "IDR",
            basis=ValueBasis.FORECAST,
            quality_status=QualityStatus.UNVALIDATED,
        ),
        period=period,
        formula_id="source.assumption",
        model_version=model_version,
        calculated_at=calculated_at,
        scenario=scenario,
        notes=note,
        input_refs=(InputRef(ref=f"assumption|{driver_id}|{scenario}",
                             kind="ASSUMPTION"),),
    )


def fact_key(ticker: str, fact: dict) -> str:
    """Stage 1's factKey shape, rebuilt from a snapshot row.

    The snapshot does not carry ``factKey`` itself, but it carries every
    component of it, so a snapshot-derived value still points at the same
    identity as the fact-store row it came from.
    """
    segment = fact.get("segment") or "CONSOLIDATED"
    return (
        f"{ticker}|{fact['metric']}|{fact['periodType']}|{fact['periodEnd']}|{segment}"
    )


__all__ = [
    "Period",
    "InputRef",
    "Calculated",
    "from_fact",
    "from_assumption",
    "fact_key",
]
