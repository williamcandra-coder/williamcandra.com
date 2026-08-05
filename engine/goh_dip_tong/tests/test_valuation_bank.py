"""Residual income, the cross-checks, and the guards that stop them exploding.

The reconciliation test here is the one that matters most. Three methods that
are algebraically identical under a steady state give a check with teeth: if
clean surplus breaks anywhere in the driver chain, or a discount is applied at
the wrong point, they stop agreeing and the test says so.
"""

from __future__ import annotations

import pytest

from engine.goh_dip_tong.contracts.enums import RefusalReason, ValuationMethod
from engine.goh_dip_tong.contracts.refusal import ValuationRefusal
from engine.goh_dip_tong.models.bank import BankModel, BankValuation
from engine.goh_dip_tong.valuation import methods
from engine.goh_dip_tong.valuation.guards import (
    TerminalAssumptionInvalid,
    TerminalGuards,
)

from .conftest_bank import context, evaluate, load

GUARDS = TerminalGuards()


# --- the identity ----------------------------------------------------------


@pytest.mark.parametrize("roe,payout,rate", [
    (0.15, 0.50, 0.12),
    (0.20, 0.60, 0.14),
    (0.11, 0.90, 0.10),
    (0.16, 0.55, 0.15),
])
def test_the_three_methods_reconcile_on_a_steady_state(roe, payout, rate):
    """Same expression, three ways of writing it. They must agree exactly."""
    result = methods.steady_state_value(1_000.0, roe, payout, rate, GUARDS)
    assert result["JUSTIFIED_PB"] == pytest.approx(
        result["RESIDUAL_INCOME"], rel=1e-12)
    assert result["DIVIDEND_DISCOUNT"] == pytest.approx(
        result["RESIDUAL_INCOME"], rel=1e-12)


def test_a_bank_earning_exactly_its_cost_of_equity_is_worth_book():
    """The sanity anchor. If ROE = r there is no abnormal return, so residual
    income is zero and value is book — whatever the growth rate."""
    result = methods.steady_state_value(1_000.0, 0.12, 0.5, 0.12, GUARDS)
    assert result["RESIDUAL_INCOME"] == pytest.approx(1_000.0, rel=1e-12)


def test_a_bank_earning_below_its_cost_of_equity_is_worth_less_than_book():
    result = methods.steady_state_value(1_000.0, 0.09, 0.5, 0.12, GUARDS)
    assert result["RESIDUAL_INCOME"] < 1_000.0


# --- guards ----------------------------------------------------------------


def test_growth_at_the_discount_rate_is_refused():
    """(r - g) -> 0 sends value to infinity smoothly and without warning."""
    with pytest.raises(TerminalAssumptionInvalid, match="spread"):
        GUARDS.check_spread(r=0.12, g=0.12)


def test_growth_inside_the_minimum_spread_is_refused():
    with pytest.raises(TerminalAssumptionInvalid, match="spread"):
        GUARDS.check_spread(r=0.12, g=0.115)


def test_growth_clear_of_the_spread_is_accepted():
    GUARDS.check_spread(r=0.12, g=0.10)


def test_the_spread_boundary_itself_refuses():
    """Ties go the conservative way. At exactly the minimum the continuing
    value is already denominator-dominated, and floating point makes "exactly"
    unreliable to test for anyway."""
    with pytest.raises(TerminalAssumptionInvalid):
        GUARDS.check_spread(r=0.12, g=0.11)


def test_growth_above_the_discount_rate_is_refused():
    """Otherwise the denominator flips sign and the value comes back negative,
    which reads as "worthless" rather than "the assumption is impossible"."""
    with pytest.raises(TerminalAssumptionInvalid):
        GUARDS.check_spread(r=0.12, g=0.15)


def test_a_non_positive_discount_rate_is_refused():
    with pytest.raises(TerminalAssumptionInvalid, match="not positive"):
        GUARDS.check_spread(r=0.0, g=-0.05)


@pytest.mark.parametrize("omega", [1.0, 1.5, 0.995])
def test_persistence_at_or_above_one_is_refused(omega):
    """At omega = 1 abnormal returns persist forever, which assumes
    competition never arrives."""
    with pytest.raises(TerminalAssumptionInvalid, match="persistence"):
        GUARDS.check_persistence(omega)


def test_negative_persistence_is_refused():
    with pytest.raises(TerminalAssumptionInvalid, match="negative"):
        GUARDS.check_persistence(-0.1)


@pytest.mark.parametrize("omega", [0.0, 0.5, 0.99])
def test_admissible_persistence_is_accepted(omega):
    GUARDS.check_persistence(omega)


def test_an_invalid_persistence_refuses_the_whole_valuation(synthetic_bank):
    """The guard has to stop the valuation, not just the continuing value."""
    result = BankModel().evaluate(load(synthetic_bank),
                                  context(synthetic_bank, persistence=1.0))
    assert isinstance(result, ValuationRefusal)
    assert result.reason == RefusalReason.TERMINAL_ASSUMPTION_INVALID


def test_the_guards_travel_with_the_output(synthetic_bank):
    """A reader has to be able to see which region the model was held to."""
    result = evaluate(synthetic_bank)
    guards = result.to_json()["guards"]
    assert guards["minSpread"] == 0.01
    assert guards["maxPersistence"] == 0.99


# --- the synthetic bank ----------------------------------------------------


def test_the_synthetic_bank_is_valued(synthetic_bank):
    result = evaluate(synthetic_bank)
    assert isinstance(result, BankValuation)
    assert result.to_json()["status"] == "VALUED"
    assert result.method == ValuationMethod.RESIDUAL_INCOME


def test_scenarios_are_ordered_bear_base_bull(synthetic_bank):
    result = evaluate(synthetic_bank)
    assert result.scenario_order == ["BEAR", "BASE", "BULL"]


def test_bear_is_at_or_below_base_which_is_at_or_below_bull(synthetic_bank):
    """The monotonicity guarantee. It holds because every scenario offset in
    `scenarios.yml` is signed so bull is the favourable direction — asserted
    separately in `test_bank_forecast.py`."""
    result = evaluate(synthetic_bank)
    bear, base, bull = (result.scenarios[s].primary.value_per_share.value
                        for s in ("BEAR", "BASE", "BULL"))
    assert bear <= base <= bull


@pytest.mark.parametrize("method_index", [0, 1])
def test_the_cross_checks_are_also_monotone(synthetic_bank, method_index):
    result = evaluate(synthetic_bank)
    values = [result.scenarios[s].cross_checks[method_index].value_per_share.value
              for s in ("BEAR", "BASE", "BULL")]
    assert values[0] <= values[1] <= values[2]


def test_both_cross_checks_are_produced(synthetic_bank):
    checks = evaluate(synthetic_bank).base.cross_checks
    assert [c.method for c in checks] == [
        ValuationMethod.JUSTIFIED_PB, ValuationMethod.DIVIDEND_DISCOUNT]


def test_the_cross_checks_state_why_they_differ(synthetic_bank):
    """They assume the terminal ROE persists; residual income fades it. A
    cross-check whose divergence is unexplained is just a second number."""
    for check in evaluate(synthetic_bank).base.cross_checks:
        assert "persist" in check.note or "perpetuity" in check.note


def test_residual_income_is_charged_on_opening_book(synthetic_bank):
    """Charging closing book would penalise a bank for profit it just retained."""
    result = evaluate(synthetic_bank)
    projection = result.projections["BASE"]
    first_ri = result.scenarios["BASE"].residual_income[0]
    rate = result.scenarios["BASE"].cost_of_equity.rate
    expected = (projection.years[0]["net_profit_attributable_to_parent"].value
                - rate * projection.opening_book.value)
    assert first_ri.value == pytest.approx(expected, rel=1e-12)


def test_one_residual_income_record_per_forecast_year(synthetic_bank):
    result = evaluate(synthetic_bank)
    assert len(result.base.residual_income) == BankModel.horizon


def test_the_equity_value_is_book_plus_present_values(synthetic_bank):
    result = evaluate(synthetic_bank)
    detail = result.base.primary.detail
    expected = (detail["openingBook"].value
                + detail["explicitPeriodPresentValue"].value
                + detail["continuingValuePresentValue"].value)
    assert result.base.primary.equity_value.value == pytest.approx(
        expected, rel=1e-12)


def test_value_per_share_divides_by_the_share_count(synthetic_bank):
    result = evaluate(synthetic_bank)
    shares = result.projections["BASE"].shares.value
    assert result.base.primary.value_per_share.value == pytest.approx(
        result.base.primary.equity_value.value / shares, rel=1e-12)


# --- the synthetic label ---------------------------------------------------


def test_the_discount_rate_is_labelled_synthetic(synthetic_bank):
    """It is invented. Nothing in the output may imply otherwise."""
    equity_cost = evaluate(synthetic_bank).base.cost_of_equity
    assert equity_cost.basis == "SYNTHETIC"
    assert equity_cost.is_synthetic
    assert "SYNTHETIC" in equity_cost.note
    assert "never reach published output" in equity_cost.note


def test_without_the_explicit_permission_the_bank_refuses(synthetic_bank):
    """Complete data is not enough. The synthetic rate is asked for by name."""
    result = BankModel().evaluate(load(synthetic_bank),
                                  context(synthetic_bank, allow_synthetic=False))
    assert isinstance(result, ValuationRefusal)
    assert result.reason == RefusalReason.NO_VALIDATED_RISK_FREE_RATE
    assert "BI_7DRR" in result.note or "risk-free" in result.note


def test_the_refusal_names_what_would_resolve_it(synthetic_bank):
    """A refusal a reader cannot act on is barely better than a wrong number."""
    result = BankModel().evaluate(load(synthetic_bank),
                                  context(synthetic_bank, allow_synthetic=False))
    assert "government bond yield" in result.note
    assert "BI_7DRR" in result.note


# --- missing propagation, end to end --------------------------------------


def test_no_projected_value_is_a_zero_standing_in_for_missing(synthetic_bank):
    """Every figure the valuation produced is either a real number or missing
    with a reason. There is no third state."""
    result = evaluate(synthetic_bank)
    for record in result.all_records():
        assert (record.value is not None) != record.is_missing
        if record.is_missing:
            assert record.missing_reason is not None


def test_the_valuation_survives_json_serialisation(synthetic_bank):
    """Stage 1's writers pass allow_nan=False, so an infinity anywhere in the
    valuation would fail here rather than in a published file."""
    import json

    json.dumps(evaluate(synthetic_bank).to_json(), allow_nan=False)
