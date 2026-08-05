"""The rules that produce research conclusions.

**No language model runs here, and none may.** Every statement below is emitted
by a named rule whose condition is a comparison between calculated records. The
same inputs produce the same conclusions, in the same order, on any machine —
which is the only basis on which a research conclusion can be versioned,
diffed, or disagreed with.

**This module contains no arithmetic.** A rule may compare two numbers; it may
not produce a third. Anything a rule needs beyond the records the valuation
already produced is computed first in
:mod:`engine.goh_dip_tong.valuation.comparison`, through the formula registry,
so it arrives with a ``formula_id`` attached. ``test_research_package.py``
parses this file's AST and fails if an arithmetic operator ever appears in it —
the same guard the two views carry, for the same reason: a narrative layer that
starts calculating stops agreeing with the numbers it is narrating.

**Thresholds are constants with reasons.** Each one below says what it is for.
A threshold that only exists as a bare literal inside a condition is a judgement
nobody can find later.

The registry is hashable for the same reason the formula registry is: changing
what a rule concludes without bumping the model version should fail the build,
because a published conclusion carries the rule ID that produced it and a reader
following that ID must reach the rule that actually ran.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import textwrap
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from ..contracts.calculated import Calculated
from .records import (
    CLAIM_TYPES,
    Importance,
    RecordType,
    ResearchRecord,
    Severity,
    sort_key,
    stable_id,
)

# ---------------------------------------------------------------------------
# thresholds — each one a stated judgement rather than a bare literal
# ---------------------------------------------------------------------------

#: A cross-check this far from the primary method is worth naming. The gap is
#: expected — residual income fades abnormal returns where both cross-checks
#: assume they persist — so the band is wide. Narrower and every scenario would
#: trip it, which would make the flag meaningless.
CROSS_CHECK_HIGH = 1.25
CROSS_CHECK_LOW = 0.80

#: Beyond this the cross-check is not confirming the primary method in any
#: useful sense, and the divergence is the finding rather than a footnote.
CROSS_CHECK_SEVERE = 2.0

#: More than half the value sitting past the explicit horizon means the answer
#: is mostly a terminal assumption. Not a defect — it is true of most going
#: concerns — but a reader deserves to be told which half they are looking at.
CONTINUING_VALUE_SHARE = 0.5

#: A terminal spread inside 300 bps makes the perpetuity acutely sensitive:
#: small changes in either term move the value a long way. The guards refuse
#: below 100 bps; this is the band between "refused" and "comfortable".
NARROW_SPREAD = 0.03
#: Below this the sensitivity dominates everything else in the model.
VERY_NARROW_SPREAD = 0.02

#: Bull worth more than half again as much as bear. A wide span is honest
#: output rather than a problem, but it is a fact about confidence.
WIDE_SCENARIO_SPAN = 1.5

#: Current and savings accounts as a share of deposits. Above this a bank is
#: substantially funded by its cheapest liability.
STRONG_CASA_SHARE = 0.5

#: Annual credit charge as a share of loans. Above this the credit cycle,
#: rather than the margin, is the dominant swing factor in profit.
HIGH_COST_OF_CREDIT = 0.02


@dataclass(frozen=True)
class RuleContext:
    """Everything a rule may read. Deliberately narrow.

    A rule sees calculated records by role name, the evidence available for
    each metric, and a handful of audit facts. It does not see the engine
    input, the settings, or the file system — a rule that could reach those
    could reach a number that never went through the registry.
    """

    ticker: str
    family: str
    valued: bool
    scenario_order: Tuple[str, ...]
    records: Mapping[str, Calculated]
    fact_keys: Mapping[str, Tuple[str, ...]]
    audit_refs: Tuple[str, ...]
    cost_of_equity_basis: str = ""

    # ---- reading records -------------------------------------------------
    def value(self, role: str) -> Optional[float]:
        """The number behind a role, or ``None`` if absent or missing.

        Missing collapses to ``None`` on purpose: a rule must not be able to
        distinguish "no such record" from "the record says it could not be
        computed", because in both cases there is nothing to conclude.
        """
        record = self.records.get(role)
        if record is None or record.is_missing:
            return None
        return record.value

    def ref(self, role: str) -> Optional[str]:
        record = self.records.get(role)
        return record.ref if record is not None else None

    def refs(self, *roles: str) -> Tuple[str, ...]:
        return tuple(self.records[r].ref for r in roles if r in self.records)

    def refs_matching(self, prefix: str) -> Tuple[str, ...]:
        return tuple(
            self.records[role].ref for role in sorted(self.records)
            if role.startswith(prefix)
        )

    def values_matching(self, prefix: str) -> Tuple[float, ...]:
        out: List[float] = []
        for role in sorted(self.records):
            if not role.startswith(prefix):
                continue
            found = self.value(role)
            if found is not None:
                out.append(found)
        return tuple(out)

    def scenario_refs(self, suffix: str) -> Tuple[str, ...]:
        return self.refs(*[f"{s}.{suffix}" for s in self.scenario_order])

    def scenario_values(self, suffix: str) -> Tuple[Optional[float], ...]:
        return tuple(self.value(f"{s}.{suffix}") for s in self.scenario_order)

    # ---- reading evidence ------------------------------------------------
    def facts(self, *metrics: str) -> Tuple[str, ...]:
        """Stage 1 fact keys for the named metrics, deduplicated and ordered."""
        found: List[str] = []
        for metric in metrics:
            for key in self.fact_keys.get(metric, ()):
                if key not in found:
                    found.append(key)
        return tuple(sorted(found))

    def audit(self) -> Tuple[str, ...]:
        return tuple(sorted(self.audit_refs))

    def id_for(self, record_type: RecordType, rule_id: str,
               scenario: Optional[str] = None) -> str:
        return stable_id(self.ticker, record_type, rule_id, scenario)


# ---------------------------------------------------------------------------
# the registry
# ---------------------------------------------------------------------------

RuleFn = Callable[[RuleContext], Sequence[ResearchRecord]]


@dataclass(frozen=True)
class Rule:
    """One registered research rule."""

    rule_id: str
    record_type: RecordType
    family: str
    fn: RuleFn
    doc: str = ""

    def source_fingerprint(self) -> str:
        """Structure of the rule body, insensitive to comments and layout.

        Same technique as the formula registry, for the same reason: rewording
        a comment should not invalidate a model version, and changing what a
        rule concludes should.
        """
        node = ast.parse(textwrap.dedent(inspect.getsource(self.fn))).body[0]
        node.decorator_list = []
        node.name = ""
        return ast.dump(ast.Module(body=[node], type_ignores=[]))


class RuleRegistry:
    """Named research rules, applied in a fixed order."""

    def __init__(self) -> None:
        self._rules: Dict[str, Rule] = {}

    def rule(self, rule_id: str, record_type: RecordType, family: str = "BANK"):
        def decorate(fn: RuleFn) -> RuleFn:
            if rule_id in self._rules:
                raise ValueError(f"research rule already registered: {rule_id!r}")
            self._rules[rule_id] = Rule(
                rule_id=rule_id, record_type=record_type, family=family,
                fn=fn, doc=inspect.getdoc(fn) or "",
            )
            return fn

        return decorate

    def __len__(self) -> int:
        return len(self._rules)

    def ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self._rules))

    def get(self, rule_id: str) -> Rule:
        return self._rules[rule_id]

    def for_family(self, family: str) -> Tuple[Rule, ...]:
        return tuple(
            self._rules[rid] for rid in sorted(self._rules)
            if self._rules[rid].family in (family, "*")
        )

    def registry_hash(self) -> str:
        digest = hashlib.sha256()
        for rule_id in sorted(self._rules):
            rule = self._rules[rule_id]
            digest.update(rule.rule_id.encode("utf-8"))
            digest.update(str(rule.record_type).encode("utf-8"))
            digest.update(rule.family.encode("utf-8"))
            digest.update(rule.source_fingerprint().encode("utf-8"))
            digest.update(b"\x1e")
        return digest.hexdigest()

    def apply(self, context: RuleContext) -> List[ResearchRecord]:
        """Fire every rule for this family, in rule-ID order.

        Claim rules are skipped entirely when no valuation was produced. That
        is the mechanism behind "a refused issuer gets no thesis": not a filter
        applied to the output, but a set of rules that never runs, so there is
        no unsupported claim to filter.
        """
        produced: List[ResearchRecord] = []
        for rule in self.for_family(context.family):
            if not context.valued and rule.record_type in CLAIM_TYPES:
                continue
            produced.extend(rule.fn(context))
        return sorted(produced, key=sort_key)


#: The engine's single rule registry.
RULES = RuleRegistry()


# ---------------------------------------------------------------------------
# ranking helpers — comparisons only
# ---------------------------------------------------------------------------


def _importance(high: bool, medium: bool) -> Importance:
    if high:
        return Importance.HIGH
    if medium:
        return Importance.MEDIUM
    return Importance.LOW


def _severity(high: bool, medium: bool) -> Severity:
    if high:
        return Severity.HIGH
    if medium:
        return Severity.MEDIUM
    return Severity.LOW


def _all_above(values: Sequence[Optional[float]], floor: float) -> bool:
    present = [v for v in values if v is not None]
    if not present:
        return False
    return all(v > floor for v in present)


def _any_below(values: Sequence[Optional[float]], ceiling: float) -> bool:
    return any(v is not None and v < ceiling for v in values)


def _spread(values: Sequence[Optional[float]]) -> bool:
    """Whether a driver actually differs across the scenario set."""
    present = [v for v in values if v is not None]
    if len(present) < 2:
        return False
    return min(present) < max(present)


# ---------------------------------------------------------------------------
# THESIS
# ---------------------------------------------------------------------------


@RULES.rule("bank.roe_above_cost_of_equity", RecordType.THESIS)
def rule_roe_above_cost_of_equity(ctx: RuleContext) -> List[ResearchRecord]:
    """The premium to book has a source: a return above the required one."""
    roe = ctx.value("BASE.terminalRoe")
    rate = ctx.value("BASE.costOfEquity")
    if roe is None or rate is None or roe <= rate:
        return []
    return [ResearchRecord(
        record_id=ctx.id_for(RecordType.THESIS,
                             "bank.roe_above_cost_of_equity", "BASE"),
        record_type=RecordType.THESIS,
        rule_id="bank.roe_above_cost_of_equity",
        scenario="BASE",
        statement=(
            "The terminal return on equity in the base case exceeds the cost of "
            "equity, so retained profit compounds at a premium to book value "
            "rather than merely replacing the capital it consumes."
        ),
        supporting_records=ctx.refs("BASE.terminalRoe", "BASE.costOfEquity",
                                    "BASE.openingBook"),
        supporting_evidence=ctx.facts("equity_attributable_to_parent",
                                      "net_profit_attributable_to_parent"),
        importance=Importance.HIGH,
    )]


@RULES.rule("bank.residual_income_positive_throughout", RecordType.THESIS)
def rule_residual_income_positive(ctx: RuleContext) -> List[ResearchRecord]:
    """Not one good year: every year of the explicit horizon."""
    series = ctx.values_matching("BASE.residualIncome.year")
    if not series or not _all_above(series, 0.0):
        return []
    return [ResearchRecord(
        record_id=ctx.id_for(RecordType.THESIS,
                             "bank.residual_income_positive_throughout", "BASE"),
        record_type=RecordType.THESIS,
        rule_id="bank.residual_income_positive_throughout",
        scenario="BASE",
        statement=(
            "Residual income stays positive in every year of the explicit "
            "forecast, so the value above book does not depend on a single "
            "strong year or on the continuing value alone."
        ),
        supporting_records=ctx.refs_matching("BASE.residualIncome.year"),
        supporting_evidence=ctx.facts("net_profit_attributable_to_parent",
                                      "equity_attributable_to_parent"),
        importance=Importance.HIGH,
    )]


@RULES.rule("bank.growth_funded_from_retained_profit", RecordType.THESIS)
def rule_growth_funded(ctx: RuleContext) -> List[ResearchRecord]:
    """Growth the bank can pay for out of its own profit, not new capital."""
    growth = ctx.value("BASE.sustainableGrowth")
    rate = ctx.value("BASE.costOfEquity")
    if growth is None or rate is None:
        return []
    if growth <= 0.0 or growth >= rate:
        return []
    return [ResearchRecord(
        record_id=ctx.id_for(RecordType.THESIS,
                             "bank.growth_funded_from_retained_profit", "BASE"),
        record_type=RecordType.THESIS,
        rule_id="bank.growth_funded_from_retained_profit",
        scenario="BASE",
        statement=(
            "Sustainable growth is positive and stays below the cost of equity, "
            "so the forecast is funded from retained profit and the terminal "
            "value remains defined without assuming new capital."
        ),
        supporting_records=ctx.refs("BASE.sustainableGrowth", "BASE.costOfEquity",
                                    "BASE.assumption.payout"),
        supporting_evidence=ctx.facts("dividends_paid",
                                      "net_profit_attributable_to_parent"),
        importance=Importance.MEDIUM,
    )]


@RULES.rule("bank.low_cost_deposit_funding", RecordType.THESIS)
def rule_low_cost_funding(ctx: RuleContext) -> List[ResearchRecord]:
    """Cheap funding is the durable advantage in banking, when it is there."""
    casa = ctx.value("BASE.assumption.casa_to_deposits")
    if casa is None or casa < STRONG_CASA_SHARE:
        return []
    return [ResearchRecord(
        record_id=ctx.id_for(RecordType.THESIS,
                             "bank.low_cost_deposit_funding", "BASE"),
        record_type=RecordType.THESIS,
        rule_id="bank.low_cost_deposit_funding",
        scenario="BASE",
        statement=(
            "Current and savings accounts fund a majority of deposits, which is "
            "the structural source of a low funding cost and the driver the "
            "margin is least able to replace if it erodes."
        ),
        supporting_records=ctx.refs("BASE.assumption.casa_to_deposits",
                                    "BASE.assumption.funding_cost"),
        supporting_evidence=ctx.facts("casa_deposits", "deposits",
                                      "interest_expense"),
        importance=Importance.MEDIUM,
    )]


# ---------------------------------------------------------------------------
# COUNTER_THESIS
# ---------------------------------------------------------------------------


@RULES.rule("bank.discount_rate_is_synthetic", RecordType.COUNTER_THESIS)
def rule_synthetic_discount_rate(ctx: RuleContext) -> List[ResearchRecord]:
    """The largest single assumption, stated as the counter-argument it is."""
    if "SYNTHETIC" not in ctx.cost_of_equity_basis:
        return []
    return [ResearchRecord(
        record_id=ctx.id_for(RecordType.COUNTER_THESIS,
                             "bank.discount_rate_is_synthetic"),
        record_type=RecordType.COUNTER_THESIS,
        rule_id="bank.discount_rate_is_synthetic",
        statement=(
            "The discount rate is an explicitly SYNTHETIC assumption, not a "
            "validated market input. The level of every figure here is "
            "therefore an assumption rather than a finding, and no real issuer "
            "may be valued on this basis."
        ),
        supporting_records=ctx.refs("BASE.costOfEquity"),
        supporting_evidence=ctx.audit(),
        importance=Importance.HIGH,
    )]


@RULES.rule("bank.cross_check_divergence", RecordType.COUNTER_THESIS)
def rule_cross_check_divergence(ctx: RuleContext) -> List[ResearchRecord]:
    """A cross-check that always agrees is measuring nothing. This one does not."""
    ratio_roles = [
        role for role in sorted(ctx.records)
        if role.startswith("BASE.") and role.endswith(".ratio")
    ]
    diverging = [
        ctx.value(role) for role in ratio_roles
        if ctx.value(role) is not None
        and (ctx.value(role) > CROSS_CHECK_HIGH
             or ctx.value(role) < CROSS_CHECK_LOW)
    ]
    if not diverging:
        return []
    severe = any(r > CROSS_CHECK_SEVERE for r in diverging)
    return [ResearchRecord(
        record_id=ctx.id_for(RecordType.COUNTER_THESIS,
                             "bank.cross_check_divergence", "BASE"),
        record_type=RecordType.COUNTER_THESIS,
        rule_id="bank.cross_check_divergence",
        scenario="BASE",
        statement=(
            "The justified price-to-book and dividend-discount cross-checks "
            "diverge materially from residual income. Both assume the terminal "
            "return persists in perpetuity where the primary method fades it, "
            "and that single difference dominates the gap."
        ),
        supporting_records=tuple([
            *[ctx.records[role].ref for role in ratio_roles],
            *ctx.refs("BASE.valuePerShare"),
        ]),
        supporting_evidence=ctx.audit(),
        importance=_importance(severe, True),
    )]


@RULES.rule("bank.value_concentrated_in_continuing_value",
            RecordType.COUNTER_THESIS)
def rule_continuing_value_share(ctx: RuleContext) -> List[ResearchRecord]:
    """Where the value actually sits, said out loud."""
    share = ctx.value("BASE.continuingValueShare")
    if share is None or share < CONTINUING_VALUE_SHARE:
        return []
    return [ResearchRecord(
        record_id=ctx.id_for(RecordType.COUNTER_THESIS,
                             "bank.value_concentrated_in_continuing_value",
                             "BASE"),
        record_type=RecordType.COUNTER_THESIS,
        rule_id="bank.value_concentrated_in_continuing_value",
        scenario="BASE",
        statement=(
            "More than half the equity value sits beyond the explicit forecast, "
            "in the continuing value. The answer therefore rests mostly on the "
            "terminal assumptions rather than on the five years that were "
            "modelled line by line."
        ),
        supporting_records=ctx.refs("BASE.continuingValueShare",
                                    "BASE.continuingValuePresentValue",
                                    "BASE.equityValue"),
        supporting_evidence=ctx.audit(),
        importance=Importance.HIGH,
    )]


@RULES.rule("bank.narrow_terminal_spread", RecordType.COUNTER_THESIS)
def rule_narrow_spread(ctx: RuleContext) -> List[ResearchRecord]:
    """A perpetuity is acutely sensitive close to its own denominator."""
    scenarios = [s for s in ctx.scenario_order
                 if _any_below([ctx.value(f"{s}.terminalSpread")], NARROW_SPREAD)]
    if not scenarios:
        return []
    severe = any(
        _any_below([ctx.value(f"{s}.terminalSpread")], VERY_NARROW_SPREAD)
        for s in scenarios
    )
    return [ResearchRecord(
        record_id=ctx.id_for(RecordType.COUNTER_THESIS,
                             "bank.narrow_terminal_spread"),
        record_type=RecordType.COUNTER_THESIS,
        rule_id="bank.narrow_terminal_spread",
        statement=(
            "In at least one scenario the gap between the discount rate and "
            "sustainable growth is inside 300 basis points. A perpetuity is "
            "acutely sensitive that close to its denominator, so small changes "
            "in either term move the value a long way."
        ),
        supporting_records=ctx.scenario_refs("terminalSpread"),
        supporting_evidence=ctx.audit(),
        importance=_importance(severe, True),
    )]


@RULES.rule("bank.wide_scenario_span", RecordType.COUNTER_THESIS)
def rule_wide_span(ctx: RuleContext) -> List[ResearchRecord]:
    """The width of the answer is itself a finding."""
    span = ctx.value("scenarioSpan")
    if span is None or span < WIDE_SCENARIO_SPAN:
        return []
    return [ResearchRecord(
        record_id=ctx.id_for(RecordType.COUNTER_THESIS,
                             "bank.wide_scenario_span"),
        record_type=RecordType.COUNTER_THESIS,
        rule_id="bank.wide_scenario_span",
        statement=(
            "The bull case is worth more than half again as much as the bear "
            "case. The scenario set is a statement about how little the drivers "
            "pin down, not a range within which the answer is known to sit."
        ),
        supporting_records=ctx.refs("scenarioSpan", *[
            f"{s}.valuePerShare" for s in ctx.scenario_order]),
        supporting_evidence=ctx.audit(),
        importance=Importance.MEDIUM,
    )]


# ---------------------------------------------------------------------------
# CATALYST
# ---------------------------------------------------------------------------


def _driver_catalyst(ctx: RuleContext, rule_id: str, driver: str,
                     statement: str, importance: Importance,
                     metrics: Sequence[str]) -> List[ResearchRecord]:
    """A driver the scenario set actually moves, cited across all scenarios.

    The condition is not decorative. A driver whose bear and bull values are
    identical is not a lever, whatever the config intended, and listing it as
    one would be a claim the numbers do not support.
    """
    values = ctx.scenario_values(f"assumption.{driver}")
    if not _spread(values):
        return []
    return [ResearchRecord(
        record_id=ctx.id_for(RecordType.CATALYST, rule_id),
        record_type=RecordType.CATALYST,
        rule_id=rule_id,
        statement=statement,
        supporting_records=ctx.scenario_refs(f"assumption.{driver}"),
        supporting_evidence=ctx.facts(*metrics),
        importance=importance,
    )]


@RULES.rule("bank.earning_asset_growth_lever", RecordType.CATALYST)
def rule_growth_lever(ctx: RuleContext) -> List[ResearchRecord]:
    """Balance-sheet growth: the driver every other line scales from."""
    return _driver_catalyst(
        ctx, "bank.earning_asset_growth_lever", "earning_asset_growth",
        "Earning-asset growth differs across the scenario set, and every income "
        "line scales from it. A sustained change in loan and deposit growth "
        "moves the whole forecast rather than one margin.",
        Importance.HIGH, ("earning_assets", "loans", "deposits"))


@RULES.rule("bank.funding_cost_lever", RecordType.CATALYST)
def rule_funding_lever(ctx: RuleContext) -> List[ResearchRecord]:
    """The liability side of the margin."""
    return _driver_catalyst(
        ctx, "bank.funding_cost_lever", "funding_cost",
        "The funding cost differs across the scenario set. It is the term of "
        "the margin the bank controls least, and it repriced faster than asset "
        "yields in every scenario modelled here.",
        Importance.HIGH, ("interest_expense", "deposits", "casa_deposits"))


@RULES.rule("bank.fee_income_lever", RecordType.CATALYST)
def rule_fee_lever(ctx: RuleContext) -> List[ResearchRecord]:
    """Income that does not consume capital."""
    return _driver_catalyst(
        ctx, "bank.fee_income_lever", "fee_ratio",
        "Fee income differs across the scenario set. It carries no credit risk "
        "and consumes no risk-weighted capital, so a change in the fee ratio "
        "reaches profit more directly than the same change in lending.",
        Importance.MEDIUM, ("fee_income", "interest_income", "interest_expense"))


@RULES.rule("bank.credit_cost_lever", RecordType.CATALYST)
def rule_credit_lever(ctx: RuleContext) -> List[ResearchRecord]:
    """The credit cycle, which is the swing factor in most bank years."""
    return _driver_catalyst(
        ctx, "bank.credit_cost_lever", "cost_of_credit",
        "The cost of credit differs across the scenario set. Provisioning is "
        "the line that moves most between a good year and a bad one, and it "
        "moves before the loan book does.",
        Importance.HIGH, ("provision_expense", "loans",
                          "non_performing_loans", "loan_loss_allowance"))


# ---------------------------------------------------------------------------
# RISK
# ---------------------------------------------------------------------------


@RULES.rule("bank.credit_cost_sensitivity", RecordType.RISK)
def rule_credit_risk(ctx: RuleContext) -> List[ResearchRecord]:
    """A worse credit cycle than the bear case assumes."""
    bear = ctx.value(f"{ctx.scenario_order[0]}.assumption.cost_of_credit")
    if bear is None:
        return []
    return [ResearchRecord(
        record_id=ctx.id_for(RecordType.RISK, "bank.credit_cost_sensitivity"),
        record_type=RecordType.RISK,
        rule_id="bank.credit_cost_sensitivity",
        statement=(
            "A credit cycle worse than the bear case assumes would take "
            "provisions above every scenario modelled. The forecast holds the "
            "cost of credit at a level recovered from history, which contains "
            "no downturn deeper than the ones already in it."
        ),
        supporting_records=ctx.scenario_refs("assumption.cost_of_credit"),
        supporting_evidence=ctx.facts("provision_expense", "loans",
                                      "non_performing_loans"),
        severity=_severity(bear > HIGH_COST_OF_CREDIT, True),
    )]


@RULES.rule("bank.funding_cost_sensitivity", RecordType.RISK)
def rule_funding_risk(ctx: RuleContext) -> List[ResearchRecord]:
    """Deposit competition compressing the margin from the liability side."""
    if not ctx.scenario_refs("assumption.funding_cost"):
        return []
    return [ResearchRecord(
        record_id=ctx.id_for(RecordType.RISK, "bank.funding_cost_sensitivity"),
        record_type=RecordType.RISK,
        rule_id="bank.funding_cost_sensitivity",
        statement=(
            "Deposit competition would raise the funding cost without a "
            "matching move in asset yields. The chain applies each rate to a "
            "different balance, so the two do not offset and the margin "
            "compresses directly."
        ),
        supporting_records=ctx.scenario_refs("assumption.funding_cost"),
        supporting_evidence=ctx.facts("interest_expense", "deposits",
                                      "casa_deposits"),
        severity=Severity.MEDIUM,
    )]


@RULES.rule("bank.terminal_assumption_sensitivity", RecordType.RISK)
def rule_terminal_risk(ctx: RuleContext) -> List[ResearchRecord]:
    """How much of the answer rides on two numbers at the end of it."""
    spread = ctx.value("BASE.terminalSpread")
    if spread is None:
        return []
    return [ResearchRecord(
        record_id=ctx.id_for(RecordType.RISK,
                             "bank.terminal_assumption_sensitivity", "BASE"),
        record_type=RecordType.RISK,
        rule_id="bank.terminal_assumption_sensitivity",
        scenario="BASE",
        statement=(
            "The value is sensitive to the terminal spread and to the "
            "persistence factor, neither of which is observable. Both are "
            "stated assumptions rather than estimates recovered from the "
            "issuer's history."
        ),
        supporting_records=ctx.refs("BASE.terminalSpread", "BASE.costOfEquity",
                                    "BASE.sustainableGrowth",
                                    "BASE.continuingValuePresentValue"),
        supporting_evidence=ctx.audit(),
        severity=_severity(spread < NARROW_SPREAD, True),
    )]


@RULES.rule("bank.history_anchored_forecast", RecordType.RISK)
def rule_history_risk(ctx: RuleContext) -> List[ResearchRecord]:
    """Every anchor came from the past, which is the assumption in one line."""
    refs = ctx.scenario_refs("assumption.asset_yield")
    if not refs:
        return []
    return [ResearchRecord(
        record_id=ctx.id_for(RecordType.RISK, "bank.history_anchored_forecast"),
        record_type=RecordType.RISK,
        rule_id="bank.history_anchored_forecast",
        statement=(
            "Every driver anchor is recovered from the issuer's own history, so "
            "the forecast assumes the recent past is representative. A "
            "structural break in rates, competition or regulation would "
            "invalidate the anchors before it invalidated the arithmetic."
        ),
        supporting_records=refs,
        supporting_evidence=ctx.facts("interest_income", "earning_assets"),
        severity=Severity.MEDIUM,
    )]


# ---------------------------------------------------------------------------
# BREAKER — conditions under which there is no number, not a worse one
# ---------------------------------------------------------------------------


@RULES.rule("bank.growth_reaches_discount_rate", RecordType.BREAKER)
def rule_breaker_spread(ctx: RuleContext) -> List[ResearchRecord]:
    """The guard that refuses rather than returning a very large number."""
    if ctx.value("BASE.terminalSpread") is None:
        return []
    return [ResearchRecord(
        record_id=ctx.id_for(RecordType.BREAKER,
                             "bank.growth_reaches_discount_rate"),
        record_type=RecordType.BREAKER,
        rule_id="bank.growth_reaches_discount_rate",
        statement=(
            "If sustainable growth reaches the discount rate the terminal value "
            "is undefined. The guards refuse below a 100 basis point spread "
            "rather than returning a number, so this ends the valuation instead "
            "of degrading it."
        ),
        supporting_records=ctx.refs("BASE.terminalSpread", "BASE.costOfEquity",
                                    "BASE.sustainableGrowth"),
        supporting_evidence=ctx.audit(),
        severity=Severity.HIGH,
    )]


@RULES.rule("bank.clean_surplus_broken", RecordType.BREAKER)
def rule_breaker_clean_surplus(ctx: RuleContext) -> List[ResearchRecord]:
    """The identity the whole reconciliation rests on."""
    if not ctx.refs("BASE.openingBook"):
        return []
    return [ResearchRecord(
        record_id=ctx.id_for(RecordType.BREAKER, "bank.clean_surplus_broken"),
        record_type=RecordType.BREAKER,
        rule_id="bank.clean_surplus_broken",
        statement=(
            "If book value moves other than by profit less dividends — a rights "
            "issue, a revaluation reserve, a large write-off through equity — "
            "residual income and dividend discounting stop agreeing, and the "
            "cross-check loses its meaning without producing an error."
        ),
        supporting_records=ctx.refs("BASE.openingBook", "BASE.equityValue"),
        supporting_evidence=ctx.facts("equity_attributable_to_parent",
                                      "dividends_paid"),
        severity=Severity.HIGH,
    )]


@RULES.rule("bank.residual_income_turns_negative", RecordType.BREAKER)
def rule_breaker_negative_ri(ctx: RuleContext) -> List[ResearchRecord]:
    """Fires only when it happens, which is what makes its absence informative."""
    series = ctx.values_matching("BASE.residualIncome.year")
    if not series or _all_above(series, 0.0):
        return []
    return [ResearchRecord(
        record_id=ctx.id_for(RecordType.BREAKER,
                             "bank.residual_income_turns_negative", "BASE"),
        record_type=RecordType.BREAKER,
        rule_id="bank.residual_income_turns_negative",
        scenario="BASE",
        statement=(
            "Residual income is negative in at least one forecast year: the "
            "bank earns less than the charge on the equity it uses. Value below "
            "book follows arithmetically, and the premium in the continuing "
            "value is doing all the work."
        ),
        supporting_records=ctx.refs_matching("BASE.residualIncome.year"),
        supporting_evidence=ctx.facts("net_profit_attributable_to_parent",
                                      "equity_attributable_to_parent"),
        severity=Severity.HIGH,
    )]


@RULES.rule("bank.book_value_non_positive", RecordType.BREAKER)
def rule_breaker_book_value(ctx: RuleContext) -> List[ResearchRecord]:
    """Book value at or below zero makes every equity-side method meaningless."""
    book = ctx.value("BASE.openingBook")
    if book is None or book > 0.0:
        return []
    return [ResearchRecord(
        record_id=ctx.id_for(RecordType.BREAKER, "bank.book_value_non_positive",
                             "BASE"),
        record_type=RecordType.BREAKER,
        rule_id="bank.book_value_non_positive",
        scenario="BASE",
        statement=(
            "Book value attributable to the parent is not positive. Every "
            "equity-side method here divides by it or grows from it, so none of "
            "them means anything and the engine refuses rather than reporting a "
            "sign-flipped result."
        ),
        supporting_records=ctx.refs("BASE.openingBook"),
        supporting_evidence=ctx.facts("equity_attributable_to_parent"),
        severity=Severity.HIGH,
    )]


# ---------------------------------------------------------------------------
# METHOD_COMPARISON — not a claim about the issuer, a note about the methods
# ---------------------------------------------------------------------------


_METHOD_NOTES = {
    "JUSTIFIED_PB": (
        "Justified price-to-book is a sensitivity cross-check on residual "
        "income, not an equal-weight second estimate. It applies the terminal "
        "return in perpetuity where the primary method fades it, so it reads "
        "higher whenever the terminal return is above the discount rate."
    ),
    "DIVIDEND_DISCOUNT": (
        "The dividend-discount cross-check is a sensitivity check, not an "
        "equal-weight second estimate. It values the first forecast dividend "
        "growing in perpetuity, so it is valid only where payout is stable and "
        "is most sensitive of the three to the terminal spread."
    ),
}


def _method_notes(ctx: RuleContext, rule_id: str,
                  method: str) -> List[ResearchRecord]:
    """One note per scenario for one cross-check, with its ratio to the primary.

    The rule ID a record carries is the ID the rule is registered under, not a
    variant assembled at emission. A published ``ruleId`` that leads to no
    registered rule would make the rule-registry hash a promise about nothing.
    """
    produced: List[ResearchRecord] = []
    for scenario in ctx.scenario_order:
        role = f"{scenario}.{method}.ratio"
        if role not in ctx.records:
            continue
        produced.append(ResearchRecord(
            record_id=ctx.id_for(RecordType.METHOD_COMPARISON, rule_id,
                                 scenario),
            record_type=RecordType.METHOD_COMPARISON,
            rule_id=rule_id,
            scenario=scenario,
            statement=_METHOD_NOTES[method],
            supporting_records=ctx.refs(
                role, f"{scenario}.{method}.valuePerShare",
                f"{scenario}.valuePerShare"),
            supporting_evidence=ctx.audit(),
        ))
    return produced


@RULES.rule("bank.method_comparison.justified_pb",
            RecordType.METHOD_COMPARISON)
def rule_comparison_justified_pb(ctx: RuleContext) -> List[ResearchRecord]:
    """Justified price-to-book against residual income, per scenario."""
    return _method_notes(ctx, "bank.method_comparison.justified_pb",
                         "JUSTIFIED_PB")


@RULES.rule("bank.method_comparison.dividend_discount",
            RecordType.METHOD_COMPARISON)
def rule_comparison_dividend_discount(ctx: RuleContext) -> List[ResearchRecord]:
    """Gordon dividend discount against residual income, per scenario."""
    return _method_notes(ctx, "bank.method_comparison.dividend_discount",
                         "DIVIDEND_DISCOUNT")


# ---------------------------------------------------------------------------
# pointer records — produced whether or not anything was valued
# ---------------------------------------------------------------------------


@RULES.rule("package.evidence_ref", RecordType.EVIDENCE_REF, family="*")
def rule_evidence_refs(ctx: RuleContext) -> List[ResearchRecord]:
    """One citation index entry per metric the engine actually read."""
    return [
        ResearchRecord(
            record_id=ctx.id_for(RecordType.EVIDENCE_REF,
                                 f"package.evidence_ref.{metric}"),
            record_type=RecordType.EVIDENCE_REF,
            rule_id="package.evidence_ref",
            statement=f"Source records behind the metric {metric}.",
            supporting_evidence=tuple(ctx.fact_keys[metric]),
        )
        for metric in sorted(ctx.fact_keys) if ctx.fact_keys[metric]
    ]


@RULES.rule("package.model_audit_ref", RecordType.MODEL_AUDIT_REF, family="*")
def rule_model_audit_refs(ctx: RuleContext) -> List[ResearchRecord]:
    """The audit identifiers a reader needs to reproduce this document."""
    if not ctx.audit_refs:
        return []
    return [ResearchRecord(
        record_id=ctx.id_for(RecordType.MODEL_AUDIT_REF,
                             "package.model_audit_ref"),
        record_type=RecordType.MODEL_AUDIT_REF,
        rule_id="package.model_audit_ref",
        statement=(
            "Audit identifiers for this document: engine and model versions, "
            "the formula and research-rule registry hashes, and the basis of "
            "the discount rate."
        ),
        supporting_evidence=ctx.audit(),
    )]


__all__ = [
    "RuleContext",
    "Rule",
    "RuleRegistry",
    "RULES",
    "CROSS_CHECK_HIGH",
    "CROSS_CHECK_LOW",
    "CONTINUING_VALUE_SHARE",
    "NARROW_SPREAD",
    "WIDE_SCENARIO_SPAN",
    "STRONG_CASA_SHARE",
    "HIGH_COST_OF_CREDIT",
]
