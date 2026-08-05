"""The sector-model contract, and the gates every model must pass to value.

A model family declares what it needs; the base class checks it and produces a
refusal when anything is short. Putting the gate logic here rather than in each
family means a new family cannot accidentally ship without the checks, and the
refusal vocabulary stays consistent across all of them.

``BANK`` implements its mathematics; every other family declares
``implemented = False`` and fails the ``MODEL_IMPLEMENTED`` gate. That is the
honest state of affairs and is visible in every snapshot, rather than being an
absence a reader has to infer.

Passing the gates is necessary but not sufficient for a number to appear: the
data gates, the risk-free gate and the terminal guards each refuse
independently, and for every real issuer today several of them do.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence, Tuple

from ..valuation.guards import TerminalGuards
from .enums import GateId, RefusalReason, ValuationMethod
from .refusal import GateReport, MethodNotPermitted, ValuationRefusal

#: Which failed gate wins the headline, most fundamental first.
#:
#: ``MODEL_IMPLEMENTED`` is deliberately last. When an issuer lacks the data,
#: implementing the mathematics would not produce a number, so reporting "model
#: not implemented" as the headline would point at the wrong problem.
_REASON_PRECEDENCE: Tuple[Tuple[GateId, RefusalReason], ...] = (
    (GateId.COVERAGE_ACTIVE, RefusalReason.COVERAGE_SUSPENDED),
    (GateId.MODEL_REGISTERED, RefusalReason.NO_MODEL_FAMILY),
    (GateId.MODEL_FAMILY_SUPPORTED, RefusalReason.MODEL_FAMILY_UNSUPPORTED),
    (GateId.FACTS_UNAMBIGUOUS, RefusalReason.AMBIGUOUS_FACTS),
    (GateId.INPUTS_FRESH, RefusalReason.INPUTS_STALE),
    (GateId.REQUIRED_INPUTS_PRESENT, RefusalReason.INSUFFICIENT_INPUTS),
    (GateId.PER_SHARE_INPUTS, RefusalReason.INSUFFICIENT_INPUTS),
    (GateId.MIN_HISTORY_PERIODS, RefusalReason.INSUFFICIENT_HISTORY),
    (GateId.VALIDATED_RISK_FREE_RATE, RefusalReason.NO_VALIDATED_RISK_FREE_RATE),
    (GateId.MARKET_DATA_AVAILABLE, RefusalReason.NO_MARKET_DATA),
    (GateId.MODEL_IMPLEMENTED, RefusalReason.MODEL_NOT_IMPLEMENTED),
)


@dataclass(frozen=True)
class ModelContext:
    """Run-time permissions and configuration handed to a model.

    ``allow_synthetic_cost_of_equity`` is the one switch that lets a model
    proceed without a validated risk-free rate, and it exists solely so the
    engine's own golden tests can exercise valuation mathematics against the
    synthetic bank fixture. The CLI never sets it — ``test_refusal.py`` asserts
    that — so no published snapshot can be produced on a synthetic assumption.
    """

    models_config: dict = field(default_factory=dict)
    allow_synthetic_cost_of_equity: bool = False
    min_annual_periods: int = 3
    max_input_age_days: Optional[int] = None

    # ---- valuation configuration ----------------------------------------
    #: `cost-of-capital.yml`. Carries the risk-free decision and, behind the
    #: switch above, the SYNTHETIC rate used only by fixtures.
    cost_of_capital_config: dict = field(default_factory=dict)
    #: `scenarios.yml`. Offsets, bounds and the pinned scenario order.
    scenario_config: dict = field(default_factory=dict)
    #: Residual-income persistence. Guarded to stay below 1: at 1, abnormal
    #: returns never fade, which assumes competition never arrives.
    persistence: float = 0.6
    guards: TerminalGuards = field(default_factory=lambda: TerminalGuards())
    #: Stamped onto every value the model produces.
    model_version: str = "0.0.0"
    calculated_at: str = ""


class SectorModel:
    """Base class for every model family."""

    #: models.yml family key.
    family: str = ""
    #: Whether the family's mathematics exists. False for every family today.
    implemented: bool = False
    #: Metrics without which no valuation is attempted.
    required_metrics: Tuple[str, ...] = ()
    #: Methods this family may use.
    permitted_methods: Tuple[ValuationMethod, ...] = ()
    #: Methods that are wrong for this family and raise if invoked.
    forbidden_methods: Tuple[ValuationMethod, ...] = ()
    #: Metrics that are meaningless here and must resolve to null +
    #: NOT_APPLICABLE_TO_MODEL rather than to a number.
    not_applicable_metrics: Tuple[str, ...] = ()
    #: Historical annual periods needed to anchor an equation-driven forecast.
    min_annual_periods: int = 3

    #: Gates that are reported but do not prevent a valuation. A price is
    #: required to solve the market-implied case; it is not required to value
    #: a business, and treating it as blocking would make research impossible
    #: precisely where market data is hardest to license.
    non_blocking_gates: Tuple[GateId, ...] = (GateId.MARKET_DATA_AVAILABLE,)

    # ---- method policy ---------------------------------------------------
    def assert_method_permitted(self, method: ValuationMethod) -> None:
        """Raise if ``method`` is invalid for this family.

        Raising rather than refusing is the point. A bank short of data is a
        data problem and returns a refusal; a bank run through EV/EBITDA is a
        programming error, and it should stop the build rather than reach a
        reader.
        """
        if method in self.forbidden_methods:
            raise MethodNotPermitted(
                f"{self.family}: {method} is not a valid method for this model "
                f"family. Permitted: "
                f"{', '.join(str(m) for m in self.permitted_methods) or 'none'}."
            )
        if self.permitted_methods and method not in self.permitted_methods:
            raise MethodNotPermitted(
                f"{self.family}: {method} is not among this family's permitted "
                f"methods ({', '.join(str(m) for m in self.permitted_methods)})."
            )

    # ---- gates -----------------------------------------------------------
    def gates(self, engine_input, context: ModelContext) -> GateReport:
        """Check every precondition, collecting all failures rather than the first."""
        report = GateReport()
        identity = engine_input.identity

        report.check(
            GateId.COVERAGE_ACTIVE,
            identity.get("coverageStatus") != "SUSPENDED",
            f"coverageStatus={identity.get('coverageStatus')}",
        )
        report.check(
            GateId.MODEL_REGISTERED,
            bool(self.family),
            f"modelFamily={identity.get('modelFamily')}",
        )
        report.check(
            GateId.MODEL_FAMILY_SUPPORTED,
            self._family_supported(context),
            f"models.yml declares {self.family} "
            f"supported={self._family_supported(context)}",
        )
        report.check(
            GateId.FACTS_UNAMBIGUOUS,
            not engine_input.ambiguous,
            "; ".join(engine_input.ambiguous)
            or "no duplicate metric/period/segment rows",
        )
        report.check(
            GateId.MODEL_IMPLEMENTED,
            self.implemented,
            "valuation mathematics is implemented"
            if self.implemented
            else "valuation mathematics for this family is not implemented yet",
        )

        present = engine_input.metrics_present()
        report.require_inputs(
            GateId.REQUIRED_INPUTS_PRESENT,
            [m for m in self.required_metrics if m not in present],
        )
        report.require_inputs(
            GateId.PER_SHARE_INPUTS,
            [m for m in ("shares_outstanding",) if m not in present],
            "a share count is required before any per-share figure can exist",
        )

        periods = engine_input.annual_periods()
        minimum = context.min_annual_periods or self.min_annual_periods
        report.check(
            GateId.MIN_HISTORY_PERIODS,
            len(periods) >= minimum,
            f"{len(periods)} annual period(s) available, {minimum} required to "
            f"anchor an equation-driven forecast",
        )

        report.check(
            GateId.VALIDATED_RISK_FREE_RATE,
            bool(context.allow_synthetic_cost_of_equity),
            "SYNTHETIC cost of equity permitted for this fixture run"
            if context.allow_synthetic_cost_of_equity
            else "no validated risk-free input is available; BI_7DRR is a policy "
                 "rate, not a risk-free yield, and is contextual macro data only",
        )

        market = engine_input.market_context or {}
        report.check(
            GateId.MARKET_DATA_AVAILABLE,
            bool(market.get("available")),
            str(market.get("reason") or "no market context supplied"),
        )
        return report

    def evaluate(self, engine_input, context: ModelContext):
        """Value the issuer, or refuse.

        No family values anything in this slice, so this always refuses. The
        return type stays a union so later slices can add a valuation without
        changing every caller.
        """
        report = self.gates(engine_input, context)
        return self.refuse(report, engine_input)

    # ---- refusal ---------------------------------------------------------
    def refuse(self, report: GateReport, engine_input) -> ValuationRefusal:
        reason = self._headline_reason(report)
        return report.refusal(reason, self._note(reason, report, engine_input))

    @staticmethod
    def _headline_reason(report: GateReport) -> RefusalReason:
        failed = {g.gate_id for g in report.failed}
        for gate_id, reason in _REASON_PRECEDENCE:
            if gate_id in failed:
                return reason
        return RefusalReason.MODEL_NOT_IMPLEMENTED

    def _note(self, reason: RefusalReason, report: GateReport, engine_input) -> str:
        missing = sorted(set(report.missing_inputs))
        if reason == RefusalReason.INSUFFICIENT_INPUTS:
            return (
                f"{engine_input.ticker}: the {self.family} model requires "
                f"{len(self.required_metrics)} reported metrics and a share count. "
                f"{len(missing)} are absent from the inputs "
                f"({', '.join(missing)}). No valuation is produced and no value "
                f"is estimated in their place."
            )
        if reason == RefusalReason.INSUFFICIENT_HISTORY:
            return (
                f"{engine_input.ticker}: {len(engine_input.annual_periods())} annual "
                f"period(s) available. An equation-driven forecast needs a "
                f"historical anchor, and a single period is a level, not a trend."
            )
        if reason == RefusalReason.MODEL_FAMILY_UNSUPPORTED:
            return (
                f"{engine_input.ticker}: model family {self.family} is declared in "
                f"models.yml with supported=false. No generic valuation is "
                f"substituted."
            )
        if reason == RefusalReason.NO_MODEL_FAMILY:
            return (
                f"{engine_input.ticker}: the classification maps to no model "
                f"family, so coverage is ONBOARDING and no valuation applies."
            )
        if reason == RefusalReason.MODEL_NOT_IMPLEMENTED:
            return (
                f"{engine_input.ticker}: the {self.family} model's valuation "
                f"mathematics is not implemented in this engine version "
                f"({', '.join(str(g.gate_id) for g in report.failed)})."
            )
        if reason == RefusalReason.AMBIGUOUS_FACTS:
            return (
                f"{engine_input.ticker}: two facts describe the same metric, "
                f"period and segment ({'; '.join(engine_input.ambiguous)}). "
                f"Choosing between them would be a silent guess."
            )
        if reason == RefusalReason.COVERAGE_SUSPENDED:
            return f"{engine_input.ticker}: coverage is suspended."
        if reason == RefusalReason.NO_VALIDATED_RISK_FREE_RATE:
            return (
                f"{engine_input.ticker}: no validated risk-free input exists, so "
                f"no defensible cost of equity can be formed. BI_7DRR is a "
                f"short-term policy rate held as macro context and is refused as "
                f"a substitute — using it would understate the discount rate and "
                f"inflate the valuation invisibly. A validated long-dated "
                f"government bond yield, with a documented source and retrieval "
                f"date, is what would resolve this."
            )
        if reason == RefusalReason.NO_MARKET_DATA:
            return (
                f"{engine_input.ticker}: no price is available, so no "
                f"price-dependent output can be produced."
            )
        return (
            f"{engine_input.ticker}: refused ({reason}). Failed gates: "
            f"{', '.join(sorted(str(g.gate_id) for g in report.failed))}."
        )

    # ---- helpers ---------------------------------------------------------
    def _family_supported(self, context: ModelContext) -> bool:
        families = (context.models_config or {}).get("model_families") or {}
        return bool((families.get(self.family) or {}).get("supported", False))


class DeclaredOnlyModel(SectorModel):
    """A family that exists in models.yml but has no engine implementation.

    Registered rather than absent on purpose: an unregistered family would fall
    through to whatever the caller did next, and "whatever the caller did next"
    is how a generic valuation gets applied to a bank.
    """

    def __init__(self, family: str, required_metrics: Sequence[str] = ()) -> None:
        self.family = family
        self.required_metrics = tuple(required_metrics)


__all__ = ["SectorModel", "DeclaredOnlyModel", "ModelContext"]
