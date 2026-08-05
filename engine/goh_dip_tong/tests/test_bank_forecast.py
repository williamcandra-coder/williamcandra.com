"""The driver chain, checked against hand calculations rather than itself.

The synthetic-bank fixture was generated from the same equations this chain
implements, so every anchor inverts exactly. That is what makes a hand
calculation possible: the expected value of a projected year can be written out
by hand from the anchors and compared, rather than compared against another run
of the code under test.
"""

from __future__ import annotations

import pytest

from engine.goh_dip_tong.forecasting import assumptions as assumptions_mod
from engine.goh_dip_tong.forecasting.bank import PROJECTED_METRICS
from engine.goh_dip_tong.models.bank import build_history
from pipeline.goh_dip_tong.contracts.enums import ValueBasis

from .conftest_bank import anchors, load, projection

#: The anchors the fixture was built from. Hard-coded rather than recomputed:
#: comparing the derivation against itself would pass no matter what it did.
EXPECTED_ANCHORS = {
    "earning_asset_growth": 0.08,
    "asset_yield": 0.082,
    "funding_cost": 0.021,
    "fee_ratio": 0.20,
    "cost_to_income": 0.42,
    "cost_of_credit": 0.012,
    "loans_to_earning_assets": 0.62,
    "deposits_to_earning_assets": 0.85,
    "casa_to_deposits": 0.72,
    "tax_rate": 0.21,
    "minority_share": 0.985,
    "payout": 0.50,
}


# --- anchors ---------------------------------------------------------------


@pytest.mark.parametrize("driver,expected", sorted(EXPECTED_ANCHORS.items()))
def test_each_anchor_is_recovered_from_history(synthetic_bank, driver, expected):
    assert anchors(synthetic_bank)[driver] == pytest.approx(expected, abs=1e-9)


def test_every_declared_anchor_is_derived(synthetic_bank):
    derived = anchors(synthetic_bank)
    assert set(assumptions_mod.BANK_ANCHORS) == set(derived)


def test_payout_is_a_magnitude_not_a_negative(synthetic_bank):
    """Dividends are stored as a negative outflow. Taking the raw sign would
    give a negative payout and a book value that grows by paying dividends."""
    assert anchors(synthetic_bank)["payout"] > 0


def test_growth_is_a_cagr_not_a_single_year(synthetic_bank):
    """One unusual year must not set the trajectory."""
    history = build_history(load(synthetic_bank))
    years = sorted(history)
    first = history[years[0]]["earning_assets"]
    last = history[years[-1]]["earning_assets"]
    expected = (last / first) ** (1 / (len(years) - 1)) - 1
    assert anchors(synthetic_bank)["earning_asset_growth"] == pytest.approx(expected)


def test_two_periods_are_required_for_a_growth_anchor():
    with pytest.raises(assumptions_mod.InsufficientHistory, match="not a trend"):
        assumptions_mod.derive_bank_anchors({2025: {"earning_assets": 1.0}})


def test_a_zero_denominator_anchor_refuses_rather_than_returning_zero():
    history = {
        2024: {"earning_assets": 100.0}, 2025: {
            "earning_assets": 108.0, "loans": 0.0, "deposits": 85.0,
            "casa_deposits": 60.0, "interest_income": 8.0,
            "interest_expense": 2.0, "fee_income": 1.0,
            "operating_expense": 3.0, "provision_expense": 0.5,
            "net_profit": 2.0, "net_profit_attributable_to_parent": 2.0,
            "dividends_paid": -1.0,
        },
    }
    with pytest.raises(assumptions_mod.InsufficientHistory, match="undefined"):
        assumptions_mod.derive_bank_anchors(history)


# --- the chain, by hand ----------------------------------------------------


def test_year_one_matches_a_hand_calculation(synthetic_bank):
    """Written out from the anchors, not from a second run of the chain."""
    plan = projection(synthetic_bank, "BASE")
    year = plan.years[0]

    ea0 = 1_088_391_167_385.6 * 1000 / 1000  # FY2025 closing earning assets
    history = build_history(load(synthetic_bank))
    ea0 = history[max(history)]["earning_assets"]

    ea = ea0 * 1.08
    loans = ea * 0.62
    deposits = ea * 0.85
    interest_income = ea * 0.082
    interest_expense = deposits * 0.021
    nii = interest_income - interest_expense
    fee = nii * 0.20
    opex = (nii + fee) * 0.42
    provisions = loans * 0.012
    ppop = nii + fee - opex
    pbt = ppop - provisions
    net_profit = pbt * (1 - 0.21)
    parent = net_profit * 0.985
    dividend = parent * 0.50

    assert year["earning_assets"].value == pytest.approx(ea, rel=1e-9)
    assert year["loans"].value == pytest.approx(loans, rel=1e-9)
    assert year["deposits"].value == pytest.approx(deposits, rel=1e-9)
    assert year["interest_income"].value == pytest.approx(interest_income, rel=1e-9)
    assert year["interest_expense"].value == pytest.approx(interest_expense, rel=1e-9)
    assert year["net_interest_income"].value == pytest.approx(nii, rel=1e-9)
    assert year["fee_income"].value == pytest.approx(fee, rel=1e-9)
    assert year["operating_expense"].value == pytest.approx(opex, rel=1e-9)
    assert year["provision_expense"].value == pytest.approx(provisions, rel=1e-9)
    assert year["pre_provision_operating_profit"].value == pytest.approx(ppop, rel=1e-9)
    assert year["profit_before_tax"].value == pytest.approx(pbt, rel=1e-9)
    assert year["net_profit"].value == pytest.approx(net_profit, rel=1e-9)
    assert year["net_profit_attributable_to_parent"].value == pytest.approx(
        parent, rel=1e-9)
    assert year["dividends_paid"].value == pytest.approx(dividend, rel=1e-9)


def test_the_first_projected_year_continues_the_history(synthetic_bank):
    """The chain reproduces the fixture's own next step, because the fixture
    was built from these equations. If it did not, one of the two is wrong."""
    plan = projection(synthetic_bank, "BASE")
    history = build_history(load(synthetic_bank))
    last = history[max(history)]
    assert plan.years[0]["earning_assets"].value == pytest.approx(
        last["earning_assets"] * 1.08, rel=1e-9)


def test_book_value_rolls_forward_by_clean_surplus(synthetic_bank):
    """B_t = B_{t-1} + parent profit - dividends, with nothing else moving it.

    Breaking clean surplus is how residual income and dividend discounting
    quietly stop agreeing.
    """
    plan = projection(synthetic_bank, "BASE")
    book = plan.opening_book.value
    for year in plan.years:
        expected = (book + year["net_profit_attributable_to_parent"].value
                    - year["dividends_paid"].value)
        assert year["equity_attributable_to_parent"].value == pytest.approx(
            expected, rel=1e-12)
        book = year["equity_attributable_to_parent"].value


def test_roe_uses_average_equity_not_closing(synthetic_bank):
    """Closing book alone understates a growing bank's return."""
    plan = projection(synthetic_bank, "BASE")
    first = plan.years[0]
    average = (plan.opening_book.value
               + first["equity_attributable_to_parent"].value) / 2
    assert first["roe"].value == pytest.approx(
        first["net_profit_attributable_to_parent"].value / average, rel=1e-12)


def test_operating_expense_is_a_share_of_total_income(synthetic_bank):
    """Applying the ratio to net interest income alone would understate costs
    at any bank with a fee business."""
    plan = projection(synthetic_bank, "BASE")
    year = plan.years[0]
    total_income = year["net_interest_income"].value + year["fee_income"].value
    assert year["operating_expense"].value == pytest.approx(
        total_income * 0.42, rel=1e-12)


def test_the_horizon_is_five_years(synthetic_bank):
    plan = projection(synthetic_bank, "BASE")
    assert plan.horizon == 5
    assert [y.fiscal_year for y in plan.years] == [2026, 2027, 2028, 2029, 2030]


def test_every_projected_metric_is_present_every_year(synthetic_bank):
    plan = projection(synthetic_bank, "BASE")
    for year in plan.years:
        assert set(year.values) == set(PROJECTED_METRICS)


def test_generic_formulas_still_name_the_metric_they_produced(synthetic_bank):
    """core.per_share is reused for book value and earnings. Without an output
    name both would be called "per_share", which is no name at all."""
    plan = projection(synthetic_bank, "BASE")
    year = plan.years[0]
    assert year["bvps"].metric_id == "bvps"
    assert year["eps"].metric_id == "eps"
    assert year["roe"].metric_id == "roe"


# --- traceability ----------------------------------------------------------


def test_every_projected_value_is_labelled_forecast(synthetic_bank):
    """A projected margin must never be able to look like a reported one.

    Including the ratios: a ROE computed off projected profit is a forecast,
    however derived its arithmetic, and the registry promotes it accordingly.
    """
    plan = projection(synthetic_bank, "BASE")
    for record in plan.all_values():
        assert record.basis == ValueBasis.FORECAST, record.metric_id


def test_every_projected_value_names_the_formula_that_made_it(synthetic_bank):
    plan = projection(synthetic_bank, "BASE")
    for record in plan.all_values():
        assert record.formula_id
        assert record.formula_id != "source.fact"
        assert record.input_refs


def test_assumptions_record_their_anchor_and_offset(synthetic_bank):
    """Spec 2.6: the scenario's claim is the difference between the anchor and
    the value used, so both have to be on the record."""
    plan = projection(synthetic_bank, "BEAR")
    rows = plan.assumptions.to_json()
    assert rows
    for row in rows:
        assert row["formula"], row["driverId"]
        assert "historicalAnchor" in row
        assert row["scenario"] == "BEAR"
    growth = [r for r in rows if r["driverId"] == "earning_asset_growth"][0]
    assert growth["offset"] == pytest.approx(-0.020)
    assert growth["value"] == pytest.approx(growth["historicalAnchor"] - 0.020)


def test_scenario_offsets_move_the_drivers_in_the_declared_direction(synthetic_bank):
    bear = projection(synthetic_bank, "BEAR").assumptions
    base = projection(synthetic_bank, "BASE").assumptions
    bull = projection(synthetic_bank, "BULL").assumptions

    assert bear["earning_asset_growth"] < base["earning_asset_growth"] < bull[
        "earning_asset_growth"]
    assert bear["asset_yield"] < base["asset_yield"] < bull["asset_yield"]
    # Inverted drivers: the bear case is the higher cost.
    assert bear["funding_cost"] > base["funding_cost"] > bull["funding_cost"]
    assert bear["cost_of_credit"] > base["cost_of_credit"] > bull["cost_of_credit"]
    assert bear["cost_to_income"] > base["cost_to_income"] > bull["cost_to_income"]


def test_the_inverted_driver_list_matches_the_offsets(synthetic_bank):
    """The sign discipline is declared in config; this asserts the config is
    telling the truth about itself."""
    config = synthetic_bank.scenarios()
    for driver in config["inverted_drivers"]:
        offsets = config["offsets"][driver]
        assert offsets["BEAR"] > 0 >= offsets["BULL"], driver
    for driver in set(config["offsets"]) - set(config["inverted_drivers"]):
        offsets = config["offsets"][driver]
        assert offsets["BEAR"] < 0 <= offsets["BULL"], driver


def test_an_anchor_pushed_out_of_bounds_is_clamped_and_says_so():
    """A bear case that drives funding cost negative is a broken assumption,
    not a pessimistic one."""
    config = {
        "offsets": {"funding_cost": {"BEAR": -1.0}},
        "bounds": {"funding_cost": [0.0, 0.30]},
    }
    built = assumptions_mod.build({"funding_cost": 0.02}, "BEAR", config)
    assumption = built.assumptions["funding_cost"]
    assert assumption.value == 0.0
    assert assumption.clamped is True
