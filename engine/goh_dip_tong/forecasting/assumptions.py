"""Historical anchors, and the scenarios that shift them.

Spec section 2.6: *forecasts must be equation-driven, not percentage guesses.*
The distinction is not stylistic. A forecast that multiplies last year's profit
by 1.08 cannot say what would have to be true for it to be wrong. A forecast
built from earning-asset growth, asset yield, funding cost and cost of credit
can, because each of those is a claim about the business that someone can
disagree with individually.

So every assumption here is derived from history, records the anchor it came
from, and is shifted by scenario offsets that are themselves declared in
config rather than embedded in code.

**On closing versus average balances.** The projection anchors — asset yield,
funding cost, cost of credit — are defined on *closing* balances. The reported
ratios in `metrics.yml` (NIM, ROE) are defined on averages, and this module
does not change that: they are different quantities and both are computed.
Using closing balances for the anchors is what makes them invert exactly
against the history they were derived from, which is what allows a projection
to be checked against a hand calculation rather than against itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..valuation.guards import clamp

#: Every anchor the bank driver chain consumes, in the order the chain uses
#: them. Ordering is fixed so assumption records serialise identically run to
#: run.
BANK_ANCHORS = (
    "earning_asset_growth",
    "asset_yield",
    "funding_cost",
    "fee_ratio",
    "cost_to_income",
    "cost_of_credit",
    "loans_to_earning_assets",
    "deposits_to_earning_assets",
    "casa_to_deposits",
    "tax_rate",
    "minority_share",
    "payout",
)


class InsufficientHistory(ValueError):
    """Not enough historical periods to anchor an assumption."""


@dataclass(frozen=True)
class Assumption:
    """One driver assumption, with everything spec section 2.6 requires.

    ``historical_anchor`` is the value observed in history; ``value`` is what
    the forecast will use. When a scenario shifts an anchor, the difference
    between the two is exactly the claim the scenario is making.
    """

    driver_id: str
    value: float
    historical_anchor: float
    formula: str
    scenario: str
    offset: float = 0.0
    clamped: bool = False
    evidence: List[str] = field(default_factory=list)
    reason_for_change: str = ""
    confidence: str = "DERIVED_FROM_HISTORY"

    def to_json(self) -> dict:
        return {
            "driverId": self.driver_id,
            "value": self.value,
            "historicalAnchor": self.historical_anchor,
            "formula": self.formula,
            "scenario": self.scenario,
            "offset": self.offset,
            "clamped": self.clamped,
            "evidence": sorted(self.evidence),
            "reasonForChange": self.reason_for_change,
            "confidence": self.confidence,
        }


@dataclass
class AssumptionSet:
    """All anchors for one scenario."""

    scenario: str
    assumptions: Dict[str, Assumption]

    def __getitem__(self, driver_id: str) -> float:
        return self.assumptions[driver_id].value

    def get(self, driver_id: str, default: Optional[float] = None) -> Optional[float]:
        item = self.assumptions.get(driver_id)
        return item.value if item else default

    def to_json(self) -> list:
        return [self.assumptions[k].to_json() for k in BANK_ANCHORS
                if k in self.assumptions]


# ---------------------------------------------------------------------------
# deriving anchors from history
# ---------------------------------------------------------------------------


def _series(history: Dict[int, Dict[str, float]], metric: str) -> List[float]:
    return [history[year][metric] for year in sorted(history)
            if history[year].get(metric) is not None]


def _latest(history: Dict[int, Dict[str, float]], metric: str) -> float:
    year = max(history)
    value = history[year].get(metric)
    if value is None:
        raise InsufficientHistory(f"{metric} is absent in the latest period {year}")
    return float(value)


def _ratio(numerator: float, denominator: float, label: str) -> float:
    if denominator == 0:
        raise InsufficientHistory(
            f"{label}: denominator is zero, so the anchor is undefined"
        )
    return numerator / denominator


def derive_bank_anchors(history: Dict[int, Dict[str, float]]) -> Dict[str, float]:
    """Recover the driver anchors implied by the issuer's own history.

    Growth is a CAGR across the whole window, so a single unusual year cannot
    set the trajectory. Every ratio is taken from the latest period, because
    the starting point of a forecast is the business as it is now, not as it
    averaged over five years.
    """
    years = sorted(history)
    if len(years) < 2:
        raise InsufficientHistory(
            f"{len(years)} annual period(s) available; a growth anchor needs at "
            f"least two, and a level is not a trend"
        )

    earning_assets = _series(history, "earning_assets")
    if len(earning_assets) < 2 or earning_assets[0] <= 0:
        raise InsufficientHistory("earning_assets history is too short or non-positive")
    periods = len(earning_assets) - 1
    growth = (earning_assets[-1] / earning_assets[0]) ** (1.0 / periods) - 1.0

    latest = {m: _latest(history, m) for m in (
        "earning_assets", "loans", "deposits", "casa_deposits",
        "interest_income", "interest_expense", "fee_income",
        "operating_expense", "provision_expense",
        "net_profit", "net_profit_attributable_to_parent", "dividends_paid",
    )}

    net_interest_income = latest["interest_income"] - latest["interest_expense"]
    pre_provision = (
        net_interest_income + latest["fee_income"] - latest["operating_expense"]
    )
    profit_before_tax = pre_provision - latest["provision_expense"]

    return {
        "earning_asset_growth": growth,
        "asset_yield": _ratio(latest["interest_income"], latest["earning_assets"],
                              "asset_yield"),
        "funding_cost": _ratio(latest["interest_expense"], latest["deposits"],
                               "funding_cost"),
        "fee_ratio": _ratio(latest["fee_income"], net_interest_income, "fee_ratio"),
        "cost_to_income": _ratio(
            latest["operating_expense"], net_interest_income + latest["fee_income"],
            "cost_to_income"),
        "cost_of_credit": _ratio(latest["provision_expense"], latest["loans"],
                                 "cost_of_credit"),
        "loans_to_earning_assets": _ratio(latest["loans"], latest["earning_assets"],
                                          "loans_to_earning_assets"),
        "deposits_to_earning_assets": _ratio(
            latest["deposits"], latest["earning_assets"],
            "deposits_to_earning_assets"),
        "casa_to_deposits": _ratio(latest["casa_deposits"], latest["deposits"],
                                   "casa_to_deposits"),
        # Dividends are stored as a negative outflow; payout is its magnitude
        # over parent profit. Taking the raw sign here would produce a negative
        # payout and, downstream, a book value that grows by paying dividends.
        "tax_rate": 1.0 - _ratio(latest["net_profit"], profit_before_tax, "tax_rate"),
        "minority_share": _ratio(
            latest["net_profit_attributable_to_parent"], latest["net_profit"],
            "minority_share"),
        "payout": _ratio(
            abs(latest["dividends_paid"]),
            latest["net_profit_attributable_to_parent"], "payout"),
    }


#: How each anchor is computed, carried into the assumption record so a reader
#: can check the derivation without reading this file.
ANCHOR_FORMULAS = {
    "earning_asset_growth": "(earning_assets_last / earning_assets_first)^(1/n) - 1",
    "asset_yield": "interest_income / earning_assets",
    "funding_cost": "interest_expense / deposits",
    "fee_ratio": "fee_income / net_interest_income",
    "cost_to_income": "operating_expense / (net_interest_income + fee_income)",
    "cost_of_credit": "provision_expense / loans",
    "loans_to_earning_assets": "loans / earning_assets",
    "deposits_to_earning_assets": "deposits / earning_assets",
    "casa_to_deposits": "casa_deposits / deposits",
    "tax_rate": "1 - net_profit / (pre_provision_profit - provision_expense)",
    "minority_share": "net_profit_attributable_to_parent / net_profit",
    "payout": "abs(dividends_paid) / net_profit_attributable_to_parent",
}


# ---------------------------------------------------------------------------
# scenarios
# ---------------------------------------------------------------------------


def build(
    anchors: Dict[str, float],
    scenario: str,
    scenario_config: dict,
    evidence: Optional[List[str]] = None,
) -> AssumptionSet:
    """Apply one scenario's offsets to the historical anchors."""
    offsets = scenario_config.get("offsets") or {}
    bounds = scenario_config.get("bounds") or {}
    evidence = list(evidence or [])

    assumptions: Dict[str, Assumption] = {}
    for driver_id in BANK_ANCHORS:
        if driver_id not in anchors:
            continue
        anchor = float(anchors[driver_id])
        offset = float((offsets.get(driver_id) or {}).get(scenario, 0.0))
        shifted = anchor + offset
        bounded = clamp(shifted, bounds.get(driver_id))
        assumptions[driver_id] = Assumption(
            driver_id=driver_id,
            value=bounded,
            historical_anchor=anchor,
            formula=ANCHOR_FORMULAS.get(driver_id, ""),
            scenario=scenario,
            offset=offset,
            clamped=bounded != shifted,
            evidence=evidence,
            reason_for_change=(
                f"{scenario} scenario offset {offset:+.4f} applied to the "
                f"historical anchor" if offset else "at the historical anchor"
            ),
        )
    return AssumptionSet(scenario=scenario, assumptions=assumptions)


def scenario_order(scenario_config: dict) -> List[str]:
    """Pinned order. Iterating a dict here would let output ordering drift."""
    return list(scenario_config.get("order") or ["BEAR", "BASE", "BULL"])


__all__ = [
    "Assumption",
    "AssumptionSet",
    "BANK_ANCHORS",
    "ANCHOR_FORMULAS",
    "InsufficientHistory",
    "derive_bank_anchors",
    "build",
    "scenario_order",
]
