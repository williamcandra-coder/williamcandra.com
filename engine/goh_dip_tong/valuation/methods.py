"""Residual income, justified P/B and the dividend discount model.

All three are equity-side. `models.yml` states the rule they exist to honour:
for a bank, *"debt is raw material, not financing. EV/EBITDA and FCFF are
invalid here."*

**Why three, and why they should agree.** Under a consistent steady state —
constant ROE, constant payout, clean surplus, and g = ROE x (1 - payout) — the
three are algebraically the same expression:

    V_RI  = B0 + (ROE - r)·B0 / (r - g)
          = B0·[(r - g) + ROE - r] / (r - g)
          = B0·(ROE - g) / (r - g)          = V_justified_PB

    D1    = EPS1·payout = B0·ROE·(1 - g/ROE) = B0·(ROE - g)
    V_DDM = D1 / (r - g) = B0·(ROE - g)/(r - g)

So on a steady-state input they reconcile to the last decimal, and
`test_valuation_bank.py` asserts exactly that.

Over the explicit five-year forecast they will *not* agree, and the reason is
worth stating plainly rather than burying: residual income **fades** abnormal
returns at the persistence factor, while both cross-checks assume the terminal
ROE persists in perpetuity. That single difference dominates the gap, and it
widens sharply as growth approaches the discount rate. The divergence is
reported rather than reconciled away — a cross-check that always agrees is
measuring nothing.

Every division that could approach zero is guarded before it runs. See
`guards.py` for why that is part of the method rather than a safety net.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from pipeline.goh_dip_tong.contracts.enums import PeriodType, ValueBasis
from pipeline.goh_dip_tong.contracts.records import Measure

from ..contracts.calculated import Calculated, Period, from_assumption
from ..contracts.enums import ScenarioName, ValuationMethod
from ..contracts.registry import REGISTRY
from ..forecasting.bank import Projection
from .cost_of_capital import CostOfEquity
from .guards import TerminalAssumptionInvalid, TerminalGuards

_DERIVED = ValueBasis.DERIVED


# ---------------------------------------------------------------------------
# registered formulas
# ---------------------------------------------------------------------------


@REGISTRY.formula("valuation.residual_income",
                  inputs=("profit", "opening_book", "cost_of_equity"),
                  output_metric="residual_income")
def formula_residual_income(profit: Measure, opening_book: Measure,
                            cost_of_equity: Measure) -> Measure:
    """Profit above the charge for the equity used to earn it.

    RI_t = NP_t - r x B_{t-1}. The charge is on *opening* book: capital has to
    be in place before it can earn anything, and charging closing book would
    penalise a bank for the profit it just retained.
    """
    return Measure(
        value=profit.value - cost_of_equity.value * opening_book.value,
        unit=profit.unit, currency=profit.currency, basis=_DERIVED)


@REGISTRY.formula("valuation.discount", inputs=("amount", "rate", "periods"),
                  output_metric="present_value")
def formula_discount(amount: Measure, rate: Measure, periods: Measure) -> Measure:
    """Present value of an amount t periods out: amount / (1 + r)^t."""
    return Measure(value=amount.value / ((1.0 + rate.value) ** periods.value),
                   unit=amount.unit, currency=amount.currency, basis=_DERIVED)


@REGISTRY.formula("valuation.continuing_residual_income",
                  inputs=("terminal_residual_income", "rate", "persistence"),
                  output_metric="continuing_value")
def formula_continuing_ri(terminal_residual_income: Measure, rate: Measure,
                          persistence: Measure) -> Measure:
    """Ohlson continuing value of a fading residual-income stream.

    RI decays at ``persistence`` each year, so the value at the horizon of
    everything beyond it is

        CV_T = omega x RI_T / (1 + r - omega)

    At omega = 0 abnormal returns stop immediately and CV is zero; at omega
    near 1 they never fade, which `guards.py` refuses.
    """
    denominator = 1.0 + rate.value - persistence.value
    return Measure(
        value=persistence.value * terminal_residual_income.value / denominator,
        unit=terminal_residual_income.unit,
        currency=terminal_residual_income.currency, basis=_DERIVED)


@REGISTRY.formula("valuation.sum_present_values", inputs=("running", "addition"),
                  output_metric="present_value")
def formula_sum_pv(running: Measure, addition: Measure) -> Measure:
    """Accumulate present values in a fixed order.

    Float addition is not associative, so the order is the calculation. This
    runs over the projection years in ascending order, always.
    """
    return Measure(value=running.value + addition.value, unit=running.unit,
                   currency=running.currency, basis=_DERIVED)


@REGISTRY.formula("valuation.equity_value",
                  inputs=("opening_book", "explicit_period_value",
                          "continuing_value"),
                  output_metric="equity_value")
def formula_equity_value(opening_book: Measure, explicit_period_value: Measure,
                         continuing_value: Measure) -> Measure:
    """V0 = B0 + PV(explicit residual income) + PV(continuing value)."""
    return Measure(
        value=(opening_book.value + explicit_period_value.value
               + continuing_value.value),
        unit=opening_book.unit, currency=opening_book.currency, basis=_DERIVED)


@REGISTRY.formula("valuation.justified_pb",
                  inputs=("sustainable_roe", "growth", "cost_of_equity"),
                  output_metric="justified_pb")
def formula_justified_pb(sustainable_roe: Measure, growth: Measure,
                         cost_of_equity: Measure) -> Measure:
    """(ROE - g) / (r - g). The spread is guarded before this is called."""
    return Measure(
        value=((sustainable_roe.value - growth.value)
               / (cost_of_equity.value - growth.value)),
        unit="RATIO", basis=_DERIVED)


@REGISTRY.formula("valuation.apply_multiple", inputs=("book", "multiple"),
                  output_metric="equity_value")
def formula_apply_multiple(book: Measure, multiple: Measure) -> Measure:
    """Book value at a justified multiple."""
    return Measure(value=book.value * multiple.value, unit=book.unit,
                   currency=book.currency, basis=_DERIVED)


@REGISTRY.formula("valuation.gordon",
                  inputs=("next_dividend", "cost_of_equity", "growth"),
                  output_metric="equity_value")
def formula_gordon(next_dividend: Measure, cost_of_equity: Measure,
                   growth: Measure) -> Measure:
    """Gordon growth: D1 / (r - g). The spread is guarded before this runs."""
    return Measure(
        value=next_dividend.value / (cost_of_equity.value - growth.value),
        unit=next_dividend.unit, currency=next_dividend.currency, basis=_DERIVED)


@REGISTRY.formula("valuation.sustainable_growth", inputs=("roe", "payout"),
                  output_metric="sustainable_growth")
def formula_sustainable_growth(roe: Measure, payout: Measure) -> Measure:
    """g = ROE x (1 - payout). Growth a bank can fund from retained profit."""
    return Measure(value=roe.value * (1.0 - payout.value), unit="RATIO",
                   basis=_DERIVED)


# ---------------------------------------------------------------------------
# results
# ---------------------------------------------------------------------------


@dataclass
class MethodResult:
    """One method's answer, with the records behind it."""

    method: ValuationMethod
    equity_value: Calculated
    value_per_share: Calculated
    detail: Dict[str, Calculated] = field(default_factory=dict)
    note: str = ""

    def to_json(self) -> dict:
        return {
            "method": str(self.method),
            "equityValue": self.equity_value.to_json(),
            "valuePerShare": self.value_per_share.to_json(),
            "detail": {k: self.detail[k].to_json() for k in sorted(self.detail)},
            "note": self.note,
        }


@dataclass
class ScenarioValuation:
    """Everything computed for one scenario."""

    scenario: str
    primary: MethodResult
    cross_checks: List[MethodResult] = field(default_factory=list)
    cost_of_equity: Optional[CostOfEquity] = None
    sustainable_roe: float = 0.0
    sustainable_growth: float = 0.0
    residual_income: List[Calculated] = field(default_factory=list)

    #: The same three quantities as calculated records rather than floats.
    #: The floats above are convenient for the solver and the bridge; a
    #: research rule that wants to cite one needs the record, because a claim
    #: has to point at something with a formula ID behind it.
    cost_of_equity_record: Optional[Calculated] = None
    growth_record: Optional[Calculated] = None
    terminal_roe_record: Optional[Calculated] = None

    def to_json(self) -> dict:
        primary = self.primary.value_per_share.value
        return {
            "scenario": self.scenario,
            "valuePerShare": primary,
            "equityValue": self.primary.equity_value.value,
            "primary": self.primary.to_json(),
            "crossChecks": [c.to_json() for c in self.cross_checks],
            "costOfEquity": self.cost_of_equity.to_json() if self.cost_of_equity else None,
            "sustainableRoe": self.sustainable_roe,
            "sustainableGrowth": self.sustainable_growth,
            "residualIncome": [r.to_json() for r in self.residual_income],
        }


# ---------------------------------------------------------------------------
# the methods
# ---------------------------------------------------------------------------


def _scalar(name: str, value: float, period: Period, model_version: str,
            calculated_at: str, scenario: ScenarioName, unit: str = "RATIO",
            note: Optional[str] = None) -> Calculated:
    return from_assumption(name, value, period, model_version, calculated_at,
                           unit=unit, scenario=scenario, note=note)


def value(
    projection: Projection,
    cost_of_equity: CostOfEquity,
    persistence: float,
    guards: TerminalGuards,
    model_version: str,
    calculated_at: str,
) -> ScenarioValuation:
    """Value one scenario by residual income, with two cross-checks.

    Raises :class:`TerminalAssumptionInvalid` if the terminal assumptions fall
    outside the admissible region. Refusing here rather than returning a very
    large number is the whole point of the guards.
    """
    guards.check_persistence(persistence)

    scenario = ScenarioName(projection.scenario) if projection.scenario in {
        s.value for s in ScenarioName} else ScenarioName.BASE
    horizon_period = projection.years[-1].period
    rate = _scalar("cost_of_equity", cost_of_equity.rate, horizon_period,
                   model_version, calculated_at, scenario,
                   note=cost_of_equity.basis)
    omega = _scalar("residual_income_persistence", persistence, horizon_period,
                    model_version, calculated_at, scenario)

    # --- residual income over the explicit horizon ------------------------
    opening_book = projection.opening_book
    residual_incomes: List[Calculated] = []
    running = _scalar("present_value", 0.0, horizon_period, model_version,
                      calculated_at, scenario, unit="IDR")

    book = opening_book
    for index, year in enumerate(projection.years, start=1):
        residual = REGISTRY.compute(
            "valuation.residual_income", year.period,
            {"profit": year["net_profit_attributable_to_parent"],
             "opening_book": book, "cost_of_equity": rate},
            model_version=model_version, calculated_at=calculated_at,
            scenario=scenario)
        residual_incomes.append(residual)

        periods = _scalar("periods", float(index), year.period, model_version,
                          calculated_at, scenario, unit="PERIODS")
        present = REGISTRY.compute(
            "valuation.discount", year.period,
            {"amount": residual, "rate": rate, "periods": periods},
            model_version=model_version, calculated_at=calculated_at,
            scenario=scenario)
        running = REGISTRY.compute(
            "valuation.sum_present_values", year.period,
            {"running": running, "addition": present},
            model_version=model_version, calculated_at=calculated_at,
            scenario=scenario)
        book = year["equity_attributable_to_parent"]

    # --- continuing value -------------------------------------------------
    continuing = REGISTRY.compute(
        "valuation.continuing_residual_income", horizon_period,
        {"terminal_residual_income": residual_incomes[-1], "rate": rate,
         "persistence": omega},
        model_version=model_version, calculated_at=calculated_at,
        scenario=scenario)
    horizon_periods = _scalar("periods", float(projection.horizon),
                              horizon_period, model_version, calculated_at,
                              scenario, unit="PERIODS")
    continuing_pv = REGISTRY.compute(
        "valuation.discount", horizon_period,
        {"amount": continuing, "rate": rate, "periods": horizon_periods},
        model_version=model_version, calculated_at=calculated_at,
        scenario=scenario)

    equity = REGISTRY.compute(
        "valuation.equity_value", horizon_period,
        {"opening_book": opening_book, "explicit_period_value": running,
         "continuing_value": continuing_pv},
        model_version=model_version, calculated_at=calculated_at,
        scenario=scenario)
    per_share = REGISTRY.compute(
        "core.per_share", horizon_period,
        {"total": equity, "shares": projection.shares},
        model_version=model_version, calculated_at=calculated_at,
        scenario=scenario, output_metric="value_per_share")

    primary = MethodResult(
        method=ValuationMethod.RESIDUAL_INCOME,
        equity_value=equity, value_per_share=per_share,
        detail={"openingBook": opening_book,
                "explicitPeriodPresentValue": running,
                "continuingValue": continuing,
                "continuingValuePresentValue": continuing_pv},
        note=("Residual income over a %d-year explicit horizon with a fading "
              "continuing value." % projection.horizon),
    )

    # --- terminal assumptions shared by both cross-checks -----------------
    terminal = projection.years[-1]
    sustainable_roe = terminal["roe"].value
    payout = projection.assumptions["payout"]
    growth_measure = REGISTRY.compute(
        "valuation.sustainable_growth", horizon_period,
        {"roe": terminal["roe"],
         "payout": _scalar("payout", payout, horizon_period, model_version,
                           calculated_at, scenario)},
        model_version=model_version, calculated_at=calculated_at,
        scenario=scenario)
    growth = growth_measure.value
    guards.check_spread(cost_of_equity.rate, growth)

    cross_checks = [
        _justified_pb(projection, terminal, growth_measure, rate,
                      model_version, calculated_at, scenario),
        _dividend_discount(projection, terminal, growth_measure, rate,
                           model_version, calculated_at, scenario),
    ]

    return ScenarioValuation(
        scenario=projection.scenario, primary=primary, cross_checks=cross_checks,
        cost_of_equity=cost_of_equity, sustainable_roe=sustainable_roe,
        sustainable_growth=growth, residual_income=residual_incomes,
        cost_of_equity_record=rate, growth_record=growth_measure,
        terminal_roe_record=terminal["roe"],
    )


def _justified_pb(projection, terminal, growth, rate, model_version,
                  calculated_at, scenario) -> MethodResult:
    period = terminal.period
    multiple = REGISTRY.compute(
        "valuation.justified_pb", period,
        {"sustainable_roe": terminal["roe"], "growth": growth,
         "cost_of_equity": rate},
        model_version=model_version, calculated_at=calculated_at,
        scenario=scenario)
    equity = REGISTRY.compute(
        "valuation.apply_multiple", period,
        {"book": projection.opening_book, "multiple": multiple},
        model_version=model_version, calculated_at=calculated_at,
        scenario=scenario, output_metric="equity_value_justified_pb")
    per_share = REGISTRY.compute(
        "core.per_share", period,
        {"total": equity, "shares": projection.shares},
        model_version=model_version, calculated_at=calculated_at,
        scenario=scenario, output_metric="value_per_share_justified_pb")
    return MethodResult(
        method=ValuationMethod.JUSTIFIED_PB, equity_value=equity,
        value_per_share=per_share, detail={"justifiedPb": multiple},
        note=("Cross-check, not a second opinion. It assumes the terminal ROE "
              "persists in perpetuity, where residual income fades it at the "
              "persistence factor. That single difference dominates the gap "
              "between them, and it widens sharply as growth approaches the "
              "discount rate."),
    )


def _dividend_discount(projection, terminal, growth, rate, model_version,
                       calculated_at, scenario) -> MethodResult:
    """Gordon growth on the *next* dividend, not the terminal one.

    D1 is the dividend one year out. Using the terminal year's dividend would
    value the business as at the horizon and then present it as today's value,
    overstating it by roughly (1 + g)^(T-1) — an error that grows with the
    forecast horizon and looks like nothing at all in the output.
    """
    first = projection.years[0]
    period = first.period
    equity = REGISTRY.compute(
        "valuation.gordon", period,
        {"next_dividend": first["dividends_paid"], "cost_of_equity": rate,
         "growth": growth},
        model_version=model_version, calculated_at=calculated_at,
        scenario=scenario, output_metric="equity_value_dividend_discount")
    per_share = REGISTRY.compute(
        "core.per_share", period,
        {"total": equity, "shares": projection.shares},
        model_version=model_version, calculated_at=calculated_at,
        scenario=scenario, output_metric="value_per_share_dividend_discount")
    return MethodResult(
        method=ValuationMethod.DIVIDEND_DISCOUNT, equity_value=equity,
        value_per_share=per_share, detail={},
        note=("Cross-check, not a second opinion. Gordon growth on the first "
              "forecast dividend, assuming the terminal growth rate holds in "
              "perpetuity. Valid only where payout is stable, which the "
              "forecast assumes, and sensitive to the r-g spread."),
    )


def steady_state_value(book: float, roe: float, payout: float, rate: float,
                       guards: TerminalGuards) -> Dict[str, float]:
    """The three methods evaluated on a genuine steady state.

    Exists so the reconciliation identity can be asserted directly rather than
    inferred from a five-year forecast that is not in steady state. If these
    three ever disagree, the algebra in this module's docstring is wrong or
    clean surplus has been broken somewhere.
    """
    growth = roe * (1.0 - payout)
    guards.check_spread(rate, growth)
    residual_income = book + (roe - rate) * book / (rate - growth)
    justified = book * (roe - growth) / (rate - growth)
    dividend = (book * roe * payout) / (rate - growth)
    return {
        "growth": growth,
        "RESIDUAL_INCOME": residual_income,
        "JUSTIFIED_PB": justified,
        "DIVIDEND_DISCOUNT": dividend,
    }


__all__ = [
    "MethodResult",
    "ScenarioValuation",
    "value",
    "steady_state_value",
    "TerminalAssumptionInvalid",
]
