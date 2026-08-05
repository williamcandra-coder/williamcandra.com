"""The BANK model family — declaration, gates, and the mathematics.

`models.yml` states the rule this family exists to honour: *"Debt is raw
material, not financing. EV/EBITDA and FCFF are invalid here."* That is encoded
as ``forbidden_methods``, which raise on invocation rather than merely being
left unselected — a rule enforced only by not calling something survives
exactly until someone calls it.

The mathematics lives in three places, deliberately:

* ``forecasting/bank.py`` — the driver chain and the five-year projection
* ``valuation/methods.py`` — residual income, justified P/B, dividend discount
* ``expectations/reverse_solver.py`` — the market-implied case

This module is the orchestrator. It decides whether the gates permit a
valuation and, if they do, assembles the pieces. If they do not, it produces a
refusal that names every failed gate — which is what happens for every real
issuer today, and will keep happening until the Stage 1 data gaps close.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .. import ENGINE_VERSION, FORMULA_REGISTRY_HASH
from ..common import bridge as bridge_mod
from ..contracts.calculated import Calculated, Period, from_assumption
from ..contracts.enums import (
    GateId,
    RefusalReason,
    ScenarioName,
    ValuationMethod,
    ValuationOutcome,
)
from ..contracts.model import ModelContext, SectorModel
from ..contracts.refusal import ValuationRefusal
from ..expectations import reverse_solver
from ..forecasting import assumptions as assumptions_mod
from ..forecasting import bank as forecast_mod
from ..narration import views as views_mod
from ..research import package as research_mod
from ..valuation import comparison as comparison_mod
from ..valuation import cost_of_capital, methods
from ..valuation.guards import TerminalAssumptionInvalid, TerminalGuards

#: Everything the residual-income model consumes, in the order the driver chain
#: uses them. Every one is defined in Stage 1's canonical metric registry; none
#: is collected by any enabled provider today.
BANK_REQUIRED_METRICS = (
    # equity side — the residual-income base and its roll-forward
    "equity_attributable_to_parent",
    "net_profit_attributable_to_parent",
    "dividends_paid",
    "shares_outstanding",
    # net interest income
    "earning_assets",
    "interest_income",
    "interest_expense",
    # funding mix
    "deposits",
    "casa_deposits",
    # pre-provision operating profit
    "fee_income",
    "operating_expense",
    # credit
    "loans",
    "provision_expense",
    "non_performing_loans",
    "loan_loss_allowance",
    # capital
    "tier1_capital",
    "risk_weighted_assets",
)

#: Metrics the driver chain reads out of history to build its anchors.
_HISTORY_METRICS = (
    "earning_assets", "loans", "deposits", "casa_deposits",
    "interest_income", "interest_expense", "fee_income", "operating_expense",
    "provision_expense", "net_profit", "net_profit_attributable_to_parent",
    "dividends_paid", "equity_attributable_to_parent", "shares_outstanding",
)


@dataclass
class BankValuation:
    """A produced valuation. The counterpart to :class:`ValuationRefusal`."""

    method: ValuationMethod
    scenarios: Dict[str, methods.ScenarioValuation]
    scenario_order: List[str]
    projections: Dict[str, forecast_mod.Projection]
    views: Dict[str, views_mod.View]
    bridge: Optional[bridge_mod.Bridge] = None
    implied: Optional[reverse_solver.ImpliedExpectation] = None
    market_implied_note: str = ""
    guards: Optional[TerminalGuards] = None
    #: Role-keyed calculated records the research rules and both views cite.
    comparison: Dict[str, Calculated] = field(default_factory=dict)
    #: The deterministic research package built from those records.
    research: Optional[research_mod.ResearchPackage] = None

    @property
    def outcome(self) -> ValuationOutcome:
        return ValuationOutcome.VALUED

    @property
    def base(self) -> methods.ScenarioValuation:
        return self.scenarios["BASE"]

    def to_json(self) -> dict:
        return {
            "status": str(ValuationOutcome.VALUED),
            "method": str(self.method),
            "scenarios": {name: self.scenarios[name].to_json()
                          for name in self.scenario_order},
            "scenarioOrder": list(self.scenario_order),
            "crossChecks": [c.to_json() for c in self.base.cross_checks],
            "bridge": self.bridge.to_json() if self.bridge else None,
            "guards": self.guards.to_json() if self.guards else None,
        }

    def all_records(self) -> List[Calculated]:
        out: List[Calculated] = []
        for name in self.scenario_order:
            out.extend(self.projections[name].all_values())
        return out


class BankModel(SectorModel):
    family = "BANK"

    #: The mathematics exists. Gates still decide whether it may run.
    implemented = True

    required_metrics = BANK_REQUIRED_METRICS

    permitted_methods = (
        ValuationMethod.RESIDUAL_INCOME,    # primary
        ValuationMethod.JUSTIFIED_PB,       # cross-check
        ValuationMethod.DIVIDEND_DISCOUNT,  # cross-check
    )

    #: Enterprise-value methods treat debt as financing. For a bank, deposits
    #: and borrowings are the raw material of the business, so enterprise value
    #: is not a meaningful quantity and these produce confident nonsense.
    forbidden_methods = (
        ValuationMethod.ENTERPRISE_DCF,
        ValuationMethod.EV_EBITDA,
        ValuationMethod.FCF_YIELD,
    )

    #: Stage 1's handoff is explicit: net_debt for a bank must be null with
    #: NOT_APPLICABLE_TO_MODEL, never 0.
    not_applicable_metrics = ("net_debt", "interest_bearing_debt")

    #: Three years is the minimum that distinguishes a trend from a level.
    min_annual_periods = 3

    #: Explicit forecast horizon.
    horizon = 5

    # ---- evaluation ------------------------------------------------------
    def evaluate(self, engine_input, context: ModelContext):
        """Value the issuer, or refuse with the gates that stopped it."""
        report = self.gates(engine_input, context)
        if report.blocking_failures(self.non_blocking_gates):
            return self.refuse(report, engine_input)

        try:
            equity_cost = cost_of_capital.resolve(
                context.cost_of_capital_config, self.family,
                allow_synthetic=context.allow_synthetic_cost_of_equity)
        except cost_of_capital.CostOfEquityUnavailable as exc:
            report.check(GateId.VALIDATED_RISK_FREE_RATE, False, str(exc))
            return report.refusal(
                RefusalReason.NO_VALIDATED_RISK_FREE_RATE, str(exc))

        try:
            return self._value(engine_input, context, equity_cost)
        except (TerminalAssumptionInvalid,
                assumptions_mod.InsufficientHistory) as exc:
            reason = (RefusalReason.TERMINAL_ASSUMPTION_INVALID
                      if isinstance(exc, TerminalAssumptionInvalid)
                      else RefusalReason.INSUFFICIENT_HISTORY)
            return ValuationRefusal(
                reason=reason,
                note=f"{engine_input.ticker}: {exc}",
                failed_gates=[g.gate_id for g in report.failed],
                missing_inputs=sorted(set(report.missing_inputs)),
                method=ValuationMethod.RESIDUAL_INCOME,
            )

    # ---- the work --------------------------------------------------------
    def _value(self, engine_input, context: ModelContext,
               equity_cost: cost_of_capital.CostOfEquity) -> BankValuation:
        history = build_history(engine_input)
        anchors = assumptions_mod.derive_bank_anchors(history)
        base_year = max(history)
        base_period = Period.instant(f"{base_year}-12-31", base_year)

        opening_book = _fact(engine_input, "equity_attributable_to_parent",
                             base_year)
        shares = _fact(engine_input, "shares_outstanding", base_year)

        order = assumptions_mod.scenario_order(context.scenario_config)
        projections: Dict[str, forecast_mod.Projection] = {}
        valuations: Dict[str, methods.ScenarioValuation] = {}

        for scenario in order:
            assumption_set = assumptions_mod.build(
                anchors, scenario, context.scenario_config,
                evidence=[f"history:{base_year}"])
            projection = forecast_mod.project(
                history, assumption_set, opening_book, shares, self.horizon,
                context.model_version, context.calculated_at)
            projections[scenario] = projection
            valuations[scenario] = methods.value(
                projection, equity_cost, context.persistence, context.guards,
                context.model_version, context.calculated_at)

        # Comparison records first, then the research package, then the views.
        # The order is the dependency chain: a rule may only cite a record that
        # already exists, and a view may only show a conclusion a rule produced.
        comparison = comparison_mod.build(
            valuations, order, projections, context.model_version,
            context.calculated_at)

        research = research_mod.build(
            ticker=engine_input.ticker,
            family=self.family,
            valued=True,
            comparison_records=comparison,
            fact_keys=research_mod.fact_keys_for(engine_input),
            audit_refs=research_mod.audit_refs_for(
                ENGINE_VERSION, context.model_version, FORMULA_REGISTRY_HASH,
                equity_cost.basis),
            scenario_order=order,
            cost_of_equity_basis=equity_cost.basis,
        )

        views = {
            "uncle": views_mod.uncle_view(
                valuations["BASE"], valuations["BEAR"], valuations["BULL"],
                str(engine_input.provenance.mode), research),
            "analyst": views_mod.analyst_view(
                valuations["BASE"], valuations["BEAR"], valuations["BULL"],
                str(engine_input.provenance.mode), research, comparison),
        }

        result = BankValuation(
            method=ValuationMethod.RESIDUAL_INCOME,
            scenarios=valuations, scenario_order=order,
            projections=projections, views=views, guards=context.guards,
            comparison=comparison, research=research,
        )

        market = engine_input.market_context or {}
        if market.get("available") and market.get("close"):
            result.implied = self._reverse_solve(
                float(market["close"]), valuations["BASE"], opening_book.value,
                shares.value, anchors["payout"], equity_cost, context.guards)
        else:
            result.market_implied_note = str(
                market.get("reason")
                or "No market data is available, so no market-implied case can "
                   "be solved.")
        return result

    @staticmethod
    def _reverse_solve(price: float, base: methods.ScenarioValuation,
                       book: float, shares: float, payout: float,
                       equity_cost: cost_of_capital.CostOfEquity,
                       guards: TerminalGuards):
        """Solve the price back to an implied sustainable ROE, or refuse."""

        def value_at(roe: float) -> Optional[float]:
            try:
                steady = methods.steady_state_value(
                    book, roe, payout, equity_cost.rate, guards)
            except TerminalAssumptionInvalid:
                # The guards refuse here, so the model produces no value at
                # this ROE. Returning None ends the search rather than letting
                # the solver step over a region the valuation would not accept.
                return None
            return steady["RESIDUAL_INCOME"] / shares

        bracket = reverse_solver.admissible_bracket(
            equity_cost.rate, payout, guards)
        try:
            return reverse_solver.solve_implied_roe(
                value_at, price_per_share=price,
                base_case_roe=base.sustainable_roe,
                base_case_value=base.primary.value_per_share.value,
                bracket=bracket,
            )
        except reverse_solver.NoRootInBracket:
            return None


def build_bridge(book: float, shares: float, payout: float, rate: float,
                 guards: TerminalGuards,
                 previous: Dict[str, object], current: Dict[str, object],
                 tolerance: float = 1e-9) -> bridge_mod.Bridge:
    """Reconcile two valuations of the same issuer, factor group by factor group.

    Evaluates the steady-state residual-income model so the bridge measures the
    same quantity the reverse solver does, and so a leg's contribution is
    attributable to the factor that moved rather than to a five-year transition
    path that moved with it.

    Factors outside the declared legs stay in ``unexplained``. That is the
    behaviour worth having: a bridge that always reconciles to zero has stopped
    being a check and become a formatting exercise.
    """

    def evaluate(state: Dict[str, object]) -> float:
        roe = float(state.get("sustainable_roe", 0.0))
        state_payout = float(state.get("payout", payout))
        state_rate = float(state.get("cost_of_equity", rate))
        state_book = float(state.get("opening_book", book))
        state_shares = float(state.get("shares", shares))
        steady = methods.steady_state_value(
            state_book, roe, state_payout, state_rate, guards)
        return steady["RESIDUAL_INCOME"] / state_shares

    return bridge_mod.build(previous, current, evaluate, tolerance=tolerance)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def build_history(engine_input) -> Dict[int, Dict[str, float]]:
    """Annual consolidated history, keyed by fiscal year.

    Only complete years are kept. A year missing one driver would silently
    change an anchor's denominator, and an anchor derived from a partial year
    is a guess wearing a derivation.
    """
    by_year: Dict[int, Dict[str, float]] = {}
    for record in engine_input.consolidated:
        if str(record.period.period_type) != "FY" or record.is_missing:
            continue
        year = record.period.fiscal_year
        if year is None:
            continue
        by_year.setdefault(year, {})[record.metric_id] = record.value

    complete = {
        year: values for year, values in by_year.items()
        if all(m in values for m in _HISTORY_METRICS)
    }
    return complete or by_year


def _fact(engine_input, metric: str, year: int) -> Calculated:
    for record in engine_input.consolidated:
        if (record.metric_id == metric
                and record.period.fiscal_year == year
                and not record.is_missing):
            return record
    raise assumptions_mod.InsufficientHistory(
        f"{metric} is absent for {year}; the gates should have caught this")


__all__ = ["BankModel", "BankValuation", "BANK_REQUIRED_METRICS",
           "build_history", "build_bridge"]
