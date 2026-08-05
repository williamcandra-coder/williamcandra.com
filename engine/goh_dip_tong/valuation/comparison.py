"""The comparison quantities the research rules read.

This module exists because of a constraint the research layer places on itself:
**narrative modules contain no arithmetic.** A rule may compare two numbers, but
it may not produce a third. Anything a rule needs that is not already a
calculated record has to be calculated here first, through the formula
registry, so it arrives carrying a ``formula_id`` and its own derivation like
every other number in the engine.

Nothing new is registered. Every quantity below is one of the generic
primitives — ``core.ratio`` and ``core.difference`` — renamed through
``output_metric`` so the audit trail says ``terminal_spread`` rather than
``difference``. That is deliberate: the registry hash is a promise about
valuation behaviour, and a slice that only assembles research conclusions
should not be moving it.

The role keys are the vocabulary the rules are written against. They are stable
strings rather than positions, so a rule that asks for ``BASE.terminalSpread``
keeps asking for the same thing when a scenario is added or a section is
reordered.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Sequence

from ..contracts.calculated import Calculated
from ..contracts.enums import ScenarioName
from ..contracts.registry import REGISTRY

#: Role keys that exist for every scenario, so a rule can iterate scenarios
#: without knowing which comparisons were computed.
PER_SCENARIO_ROLES = (
    "valuePerShare",
    "equityValue",
    "openingBook",
    "costOfEquity",
    "terminalRoe",
    "sustainableGrowth",
    "terminalSpread",
    "continuingValuePresentValue",
    "continuingValueShare",
)


def _scenario_enum(name: str) -> ScenarioName:
    return ScenarioName(name) if name in {s.value for s in ScenarioName} \
        else ScenarioName.BASE


def build(
    scenarios: Mapping[str, object],
    scenario_order: Sequence[str],
    projections: Mapping[str, object],
    model_version: str,
    calculated_at: str,
) -> Dict[str, Calculated]:
    """Every calculated record the research rules may cite, keyed by role.

    Takes the scenario valuations rather than the ``BankValuation`` wrapper so
    this module stays independent of the model families that use it — a second
    family with a residual-income shape should be able to reuse it without the
    import going the wrong way.
    """
    records: Dict[str, Calculated] = {}

    for name in scenario_order:
        valuation = scenarios[name]
        projection = projections[name]
        scenario = _scenario_enum(name)
        period = projection.years[-1].period

        primary = valuation.primary
        records[f"{name}.valuePerShare"] = primary.value_per_share
        records[f"{name}.equityValue"] = primary.equity_value
        for key, record in primary.detail.items():
            records[f"{name}.{key}"] = record

        rate = valuation.cost_of_equity_record
        growth = valuation.growth_record
        roe = valuation.terminal_roe_record
        if rate is not None:
            records[f"{name}.costOfEquity"] = rate
        if growth is not None:
            records[f"{name}.sustainableGrowth"] = growth
        if roe is not None:
            records[f"{name}.terminalRoe"] = roe

        if rate is not None and growth is not None:
            records[f"{name}.terminalSpread"] = REGISTRY.compute(
                "core.difference", period,
                {"left": rate, "right": growth},
                model_version=model_version, calculated_at=calculated_at,
                scenario=scenario, output_metric="terminal_spread")

        continuing = primary.detail.get("continuingValuePresentValue")
        if continuing is not None:
            records[f"{name}.continuingValueShare"] = REGISTRY.compute(
                "core.ratio", period,
                {"numerator": continuing, "denominator": primary.equity_value},
                model_version=model_version, calculated_at=calculated_at,
                scenario=scenario, output_metric="continuing_value_share")

        for index, residual in enumerate(valuation.residual_income, start=1):
            records[f"{name}.residualIncome.year{index}"] = residual

        for check in valuation.cross_checks:
            method = str(check.method)
            records[f"{name}.{method}.valuePerShare"] = check.value_per_share
            records[f"{name}.{method}.ratio"] = REGISTRY.compute(
                "core.ratio", period,
                {"numerator": check.value_per_share,
                 "denominator": primary.value_per_share},
                model_version=model_version, calculated_at=calculated_at,
                scenario=scenario,
                output_metric=f"cross_check_ratio_{method.lower()}")

        for driver, record in sorted(projection.assumption_records.items()):
            records[f"{name}.assumption.{driver}"] = record

    first, last = scenario_order[0], scenario_order[-1]
    if first != last:
        span_period = projections[last].years[-1].period
        records["scenarioSpan"] = REGISTRY.compute(
            "core.ratio", span_period,
            {"numerator": scenarios[last].primary.value_per_share,
             "denominator": scenarios[first].primary.value_per_share},
            model_version=model_version, calculated_at=calculated_at,
            scenario=ScenarioName.ACTUAL, output_metric="scenario_span")

    return records


def refs(records: Mapping[str, Calculated], roles: Sequence[str]) -> List[str]:
    """The ``Calculated.ref`` of each named role that exists.

    Absent roles are skipped rather than raising: a rule cites what supports it,
    and a rule that fires on two of three available records should cite two.
    """
    return [records[role].ref for role in roles if role in records]


__all__ = ["build", "refs", "PER_SCENARIO_ROLES"]
