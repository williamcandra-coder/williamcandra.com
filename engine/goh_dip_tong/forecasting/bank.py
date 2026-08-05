"""The bank driver chain, and the five-year projection built from it.

Every line runs through a registered formula, so every projected figure carries
its own derivation and no number in the forecast can appear without one. That
is verbose compared with a spreadsheet of expressions, and it is the point: a
published projection whose provenance stops at "the model said so" is not
research.

THE CHAIN

    EA_t     = EA_{t-1} · (1 + g)
    loans_t  = EA_t · loans_to_earning_assets
    dep_t    = EA_t · deposits_to_earning_assets
    casa_t   = dep_t · casa_to_deposits

    II_t     = EA_t · asset_yield
    IE_t     = dep_t · funding_cost
    NII_t    = II_t − IE_t
    fee_t    = NII_t · fee_ratio
    opex_t   = (NII_t + fee_t) · cost_to_income
    prov_t   = loans_t · cost_of_credit

    PPOP_t   = NII_t + fee_t − opex_t
    PBT_t    = PPOP_t − prov_t
    NP_t     = PBT_t · (1 − tax_rate)
    NPpar_t  = NP_t · minority_share
    DIV_t    = NPpar_t · payout
    B_t      = B_{t-1} + NPpar_t − DIV_t

    ROE_t    = NPpar_t / avg(B_{t-1}, B_t)
    NIM_t    = NII_t / avg(EA_{t-1}, EA_t)
    BVPS_t   = B_t / shares
    EPS_t    = NPpar_t / shares

Book value rolls forward through retained profit — clean-surplus accounting —
because residual income is only equal to a dividend-discount value when it
does. Breaking clean surplus is how two methods that should agree quietly stop
agreeing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from pipeline.goh_dip_tong.contracts.enums import PeriodType, ValueBasis
from pipeline.goh_dip_tong.contracts.records import Measure

from ..common.arithmetic import safe_div, safe_mean
from ..contracts.calculated import Calculated, Period, from_assumption
from ..contracts.enums import ScenarioName
from ..contracts.registry import REGISTRY
from .assumptions import AssumptionSet

#: Everything the chain produces is a forecast, and is labelled as one all the
#: way to the UI. A projected margin must never be able to look like a reported
#: one.
_FORECAST = ValueBasis.FORECAST

#: Metrics the projection emits per year, in the order the chain computes them.
PROJECTED_METRICS = (
    "earning_assets", "loans", "deposits", "casa_deposits",
    "interest_income", "interest_expense", "net_interest_income",
    "fee_income", "operating_expense", "provision_expense",
    "pre_provision_operating_profit", "profit_before_tax",
    "net_profit", "net_profit_attributable_to_parent", "dividends_paid",
    "equity_attributable_to_parent",
    "roe", "nim", "bvps", "eps",
)


# ---------------------------------------------------------------------------
# registered formulas
# ---------------------------------------------------------------------------


@REGISTRY.formula("bank.grow", inputs=("prior", "growth"),
                  output_metric="earning_assets")
def formula_grow(prior: Measure, growth: Measure) -> Measure:
    """Compound a balance forward one year: prior x (1 + growth)."""
    return Measure(value=prior.value * (1.0 + growth.value), unit=prior.unit,
                   currency=prior.currency, basis=_FORECAST)


@REGISTRY.formula("bank.share_of", inputs=("base", "ratio"),
                  output_metric="balance")
def formula_share_of(base: Measure, ratio: Measure) -> Measure:
    """A balance held at a fixed share of another: base x ratio."""
    return Measure(value=base.value * ratio.value, unit=base.unit,
                   currency=base.currency, basis=_FORECAST)


@REGISTRY.formula("bank.yield_on", inputs=("balance", "rate"),
                  output_metric="income")
def formula_yield_on(balance: Measure, rate: Measure) -> Measure:
    """Income earned on a balance at a rate: balance x rate."""
    return Measure(value=balance.value * rate.value, unit=balance.unit,
                   currency=balance.currency, basis=_FORECAST)


@REGISTRY.formula("bank.net_interest_income",
                  inputs=("interest_income", "interest_expense"),
                  output_metric="net_interest_income")
def formula_nii(interest_income: Measure, interest_expense: Measure) -> Measure:
    """Interest income less interest expense."""
    return Measure(value=interest_income.value - interest_expense.value,
                   unit=interest_income.unit, currency=interest_income.currency,
                   basis=_FORECAST)


@REGISTRY.formula("bank.operating_expense",
                  inputs=("net_interest_income", "fee_income", "cost_to_income"),
                  output_metric="operating_expense")
def formula_opex(net_interest_income: Measure, fee_income: Measure,
                 cost_to_income: Measure) -> Measure:
    """Operating expense as a share of total operating income.

    Total income is net interest income plus fees. Applying the ratio to net
    interest income alone would understate costs at any bank with a fee
    business, and understate them more the better that business does.
    """
    income = net_interest_income.value + fee_income.value
    return Measure(value=income * cost_to_income.value,
                   unit=net_interest_income.unit,
                   currency=net_interest_income.currency, basis=_FORECAST)


@REGISTRY.formula("bank.ppop",
                  inputs=("net_interest_income", "fee_income", "operating_expense"),
                  output_metric="pre_provision_operating_profit")
def formula_ppop(net_interest_income: Measure, fee_income: Measure,
                 operating_expense: Measure) -> Measure:
    """Pre-provision operating profit: NII + fees - operating expense."""
    return Measure(
        value=net_interest_income.value + fee_income.value - operating_expense.value,
        unit=net_interest_income.unit, currency=net_interest_income.currency,
        basis=_FORECAST)


@REGISTRY.formula("bank.profit_before_tax",
                  inputs=("pre_provision_operating_profit", "provision_expense"),
                  output_metric="profit_before_tax")
def formula_pbt(pre_provision_operating_profit: Measure,
                provision_expense: Measure) -> Measure:
    """Pre-provision profit less the credit charge."""
    return Measure(
        value=pre_provision_operating_profit.value - provision_expense.value,
        unit=pre_provision_operating_profit.unit,
        currency=pre_provision_operating_profit.currency, basis=_FORECAST)


@REGISTRY.formula("bank.after_tax", inputs=("profit_before_tax", "tax_rate"),
                  output_metric="net_profit")
def formula_after_tax(profit_before_tax: Measure, tax_rate: Measure) -> Measure:
    """Profit after tax: PBT x (1 - tax rate)."""
    return Measure(value=profit_before_tax.value * (1.0 - tax_rate.value),
                   unit=profit_before_tax.unit,
                   currency=profit_before_tax.currency, basis=_FORECAST)


@REGISTRY.formula("bank.parent_share", inputs=("net_profit", "minority_share"),
                  output_metric="net_profit_attributable_to_parent")
def formula_parent_share(net_profit: Measure, minority_share: Measure) -> Measure:
    """The parent's share of group profit.

    This, not group profit, is the residual-income numerator and the EPS
    numerator. Confusing the two credits minorities' earnings to the parent's
    shareholders.
    """
    return Measure(value=net_profit.value * minority_share.value,
                   unit=net_profit.unit, currency=net_profit.currency,
                   basis=_FORECAST)


@REGISTRY.formula("bank.dividend",
                  inputs=("net_profit_attributable_to_parent", "payout"),
                  output_metric="dividends_paid")
def formula_dividend(net_profit_attributable_to_parent: Measure,
                     payout: Measure) -> Measure:
    """Dividend declared out of parent profit. Positive magnitude."""
    return Measure(value=net_profit_attributable_to_parent.value * payout.value,
                   unit=net_profit_attributable_to_parent.unit,
                   currency=net_profit_attributable_to_parent.currency,
                   basis=_FORECAST)


@REGISTRY.formula("bank.book_roll",
                  inputs=("opening_book", "net_profit_attributable_to_parent",
                          "dividends_paid"),
                  output_metric="equity_attributable_to_parent")
def formula_book_roll(opening_book: Measure,
                      net_profit_attributable_to_parent: Measure,
                      dividends_paid: Measure) -> Measure:
    """Clean-surplus roll-forward: B_t = B_{t-1} + profit - dividends.

    Clean surplus is what makes residual income and dividend discounting agree.
    Any equity movement that bypasses profit and loss breaks that equality
    silently, so nothing else may move book value here.
    """
    return Measure(
        value=(opening_book.value + net_profit_attributable_to_parent.value
               - dividends_paid.value),
        unit=opening_book.unit, currency=opening_book.currency, basis=_FORECAST)


@REGISTRY.formula("bank.return_on_average",
                  inputs=("profit", "opening_balance", "closing_balance"),
                  output_metric="roe")
def formula_return_on_average(profit: Measure, opening_balance: Measure,
                              closing_balance: Measure) -> Measure:
    """A flow over the average of its opening and closing stock.

    Closing balance alone understates the return of a growing bank, because the
    profit was earned on a smaller base than the one it is divided by.
    """
    average = safe_mean([opening_balance, closing_balance])
    return safe_div(profit, average, unit="RATIO")


# ---------------------------------------------------------------------------
# projection
# ---------------------------------------------------------------------------


@dataclass
class ProjectedYear:
    """One forecast year's line items."""

    fiscal_year: int
    period: Period
    values: Dict[str, Calculated] = field(default_factory=dict)

    def __getitem__(self, metric: str) -> Calculated:
        return self.values[metric]

    def to_json(self) -> list:
        return [self.values[m].to_json() for m in PROJECTED_METRICS
                if m in self.values]


@dataclass
class Projection:
    """A complete scenario forecast."""

    scenario: str
    assumptions: AssumptionSet
    years: List[ProjectedYear]
    opening_book: Calculated
    shares: Calculated
    base_year: int

    @property
    def horizon(self) -> int:
        return len(self.years)

    def to_json(self) -> dict:
        return {
            "scenario": self.scenario,
            "baseYear": self.base_year,
            "horizon": self.horizon,
            "assumptions": self.assumptions.to_json(),
            "years": [
                {"fiscalYear": y.fiscal_year, "values": y.to_json()}
                for y in self.years
            ],
        }

    def all_values(self) -> List[Calculated]:
        out: List[Calculated] = []
        for year in self.years:
            out.extend(year.values[m] for m in PROJECTED_METRICS
                       if m in year.values)
        return out


class Projector:
    """Runs formulas with a fixed model version, scenario and timestamp."""

    def __init__(self, model_version: str, calculated_at: str, scenario: str) -> None:
        self.model_version = model_version
        self.calculated_at = calculated_at
        self.scenario = ScenarioName(scenario) if scenario in {
            s.value for s in ScenarioName} else ScenarioName.BASE

    def compute(self, formula_id: str, period: Period,
                output_metric: Optional[str] = None, **inputs) -> Calculated:
        return REGISTRY.compute(
            formula_id, period, inputs,
            model_version=self.model_version, calculated_at=self.calculated_at,
            scenario=self.scenario, output_metric=output_metric,
        )

    def assumption(self, driver_id: str, value: float, period: Period,
                   unit: str = "RATIO") -> Calculated:
        return from_assumption(
            driver_id, value, period, self.model_version, self.calculated_at,
            unit=unit, scenario=self.scenario,
        )


def project(
    history: Dict[int, Dict[str, float]],
    assumptions: AssumptionSet,
    opening_book: Calculated,
    shares: Calculated,
    horizon: int,
    model_version: str,
    calculated_at: str,
) -> Projection:
    """Run the driver chain forward ``horizon`` years."""
    base_year = max(history)
    projector = Projector(model_version, calculated_at, assumptions.scenario)

    previous_ea = float(history[base_year]["earning_assets"])
    book = opening_book
    years: List[ProjectedYear] = []

    for step in range(1, horizon + 1):
        fiscal_year = base_year + step
        period = Period(PeriodType.FY, f"{fiscal_year}-12-31",
                        f"{fiscal_year}-01-01", fiscal_year)
        a = {driver: projector.assumption(driver, assumptions[driver], period)
             for driver in assumptions.assumptions}
        year = ProjectedYear(fiscal_year=fiscal_year, period=period)

        prior_ea = projector.assumption(
            "opening_earning_assets", previous_ea, period, unit="IDR")
        ea = projector.compute("bank.grow", period, prior=prior_ea,
                               growth=a["earning_asset_growth"])
        loans = projector.compute("bank.share_of", period, base=ea,
                                  ratio=a["loans_to_earning_assets"])
        deposits = projector.compute("bank.share_of", period, base=ea,
                                     ratio=a["deposits_to_earning_assets"])
        casa = projector.compute("bank.share_of", period, base=deposits,
                                 ratio=a["casa_to_deposits"])

        interest_income = projector.compute("bank.yield_on", period, balance=ea,
                                            rate=a["asset_yield"])
        interest_expense = projector.compute("bank.yield_on", period,
                                             balance=deposits,
                                             rate=a["funding_cost"])
        nii = projector.compute("bank.net_interest_income", period,
                                interest_income=interest_income,
                                interest_expense=interest_expense)
        fee = projector.compute("bank.share_of", period, base=nii,
                                ratio=a["fee_ratio"])
        opex = projector.compute("bank.operating_expense", period,
                                 net_interest_income=nii, fee_income=fee,
                                 cost_to_income=a["cost_to_income"])
        provisions = projector.compute("bank.yield_on", period, balance=loans,
                                       rate=a["cost_of_credit"])

        ppop = projector.compute("bank.ppop", period, net_interest_income=nii,
                                 fee_income=fee, operating_expense=opex)
        pbt = projector.compute("bank.profit_before_tax", period,
                                pre_provision_operating_profit=ppop,
                                provision_expense=provisions)
        net_profit = projector.compute("bank.after_tax", period,
                                       profit_before_tax=pbt,
                                       tax_rate=a["tax_rate"])
        parent = projector.compute("bank.parent_share", period,
                                   net_profit=net_profit,
                                   minority_share=a["minority_share"])
        dividend = projector.compute("bank.dividend", period,
                                     net_profit_attributable_to_parent=parent,
                                     payout=a["payout"])
        closing_book = projector.compute(
            "bank.book_roll", period, opening_book=book,
            net_profit_attributable_to_parent=parent, dividends_paid=dividend)

        roe = projector.compute("bank.return_on_average", period, profit=parent,
                                opening_balance=book, closing_balance=closing_book,
                                output_metric="roe")
        nim = projector.compute("bank.return_on_average", period, profit=nii,
                                opening_balance=prior_ea, closing_balance=ea,
                                output_metric="nim")
        bvps = projector.compute("core.per_share", period, total=closing_book,
                                 shares=shares, output_metric="bvps")
        eps = projector.compute("core.per_share", period, total=parent,
                                shares=shares, output_metric="eps")

        year.values.update({
            "earning_assets": ea, "loans": loans, "deposits": deposits,
            "casa_deposits": casa,
            "interest_income": interest_income,
            "interest_expense": interest_expense,
            "net_interest_income": nii, "fee_income": fee,
            "operating_expense": opex, "provision_expense": provisions,
            "pre_provision_operating_profit": ppop, "profit_before_tax": pbt,
            "net_profit": net_profit,
            "net_profit_attributable_to_parent": parent,
            "dividends_paid": dividend,
            "equity_attributable_to_parent": closing_book,
            "roe": roe, "nim": nim, "bvps": bvps, "eps": eps,
        })
        years.append(year)

        previous_ea = ea.value
        book = closing_book

    return Projection(
        scenario=assumptions.scenario, assumptions=assumptions, years=years,
        opening_book=opening_book, shares=shares, base_year=base_year,
    )


__all__ = ["Projection", "ProjectedYear", "Projector", "project",
           "PROJECTED_METRICS"]
