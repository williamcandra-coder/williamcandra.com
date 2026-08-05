"""The market-implied case, and its refusal to guess.

Solving a price back to assumptions is the output people argue about, so the
solver has to be checkable. The round trip is the check: take a value the model
produced, feed it back as a price, and the ROE that comes out must be the ROE
that went in.
"""

from __future__ import annotations

import pytest

from engine.goh_dip_tong.common.solvers import NoRootInBracket, bisect
from engine.goh_dip_tong.expectations import reverse_solver
from engine.goh_dip_tong.models.bank import BankModel
from engine.goh_dip_tong.valuation import methods
from engine.goh_dip_tong.valuation.guards import TerminalGuards

from .conftest_bank import context, evaluate, load, with_price

GUARDS = TerminalGuards()
BOOK, SHARES, PAYOUT, RATE = 200e12, 1.2e11, 0.5, 0.12
BRACKET = reverse_solver.admissible_bracket(RATE, PAYOUT, GUARDS)


def _value_at(roe: float):
    try:
        steady = methods.steady_state_value(BOOK, roe, PAYOUT, RATE, GUARDS)
    except Exception:
        return None
    return steady["RESIDUAL_INCOME"] / SHARES


# --- the bracket -----------------------------------------------------------


def test_the_bracket_stops_where_the_guards_do():
    """Growth is ROE x (1 - payout), so a high enough ROE pushes growth past
    the discount rate. Searching past that point would report "no root" for a
    price that is perfectly reachable."""
    lo, hi = BRACKET
    assert lo == 0.0
    assert _value_at(hi) is not None, "the upper endpoint must be valuable"
    assert _value_at(hi * 1.2) is None, "beyond it, the guards refuse"


def test_a_full_payout_leaves_growth_at_zero_and_the_bracket_wide():
    lo, hi = reverse_solver.admissible_bracket(0.12, 1.0, GUARDS)
    assert hi == reverse_solver.MAX_SUSTAINABLE_ROE


# --- the round trip --------------------------------------------------------


@pytest.mark.parametrize("roe", [0.02, 0.08, 0.13, 0.17, 0.21])
def test_the_round_trip_recovers_the_input(roe):
    """Value at a known ROE, feed it back as a price, get the ROE back."""
    price = _value_at(roe)
    result = reverse_solver.solve_implied_roe(
        _value_at, price_per_share=price, base_case_roe=roe,
        base_case_value=price, bracket=BRACKET)
    assert result.implied_sustainable_roe == pytest.approx(roe, abs=1e-6)


def test_the_expectation_gap_is_ours_minus_the_market():
    price = _value_at(0.13)
    result = reverse_solver.solve_implied_roe(
        _value_at, price_per_share=price, base_case_roe=0.16,
        base_case_value=_value_at(0.16), bracket=BRACKET)
    assert result.expectation_gap == pytest.approx(0.16 - 0.13, abs=1e-6)
    assert result.expectation_gap > 0, "a higher base case means we are more bullish"


def test_the_result_states_all_three_cases():
    price = _value_at(0.14)
    payload = reverse_solver.solve_implied_roe(
        _value_at, price, 0.15, _value_at(0.15), bracket=BRACKET).to_json()
    assert set(payload) >= {"marketImpliedCase", "gdtBaseCase", "expectationGap"}
    assert payload["solver"]["iterations"] > 0


# --- refusing ---------------------------------------------------------------


def test_a_price_above_everything_the_model_can_produce_refuses():
    """Extrapolating past the bracket would answer a question nobody asked."""
    with pytest.raises(NoRootInBracket, match="not bracketed"):
        reverse_solver.solve_implied_roe(_value_at, 1e12, 0.15, _value_at(0.15),
                                         bracket=BRACKET)


def test_a_price_below_everything_the_model_can_produce_refuses():
    with pytest.raises(NoRootInBracket, match="not bracketed"):
        reverse_solver.solve_implied_roe(_value_at, -5.0, 0.15, _value_at(0.15),
                                         bracket=BRACKET)


def test_an_empty_bracket_refuses():
    with pytest.raises(NoRootInBracket, match="empty bracket"):
        bisect(lambda x: x, target=1.0, lo=1.0, hi=1.0, tolerance=1e-9)


def test_a_bracket_endpoint_the_model_will_not_value_refuses():
    """A region the valuation refuses is not a region a root can hide in."""
    def undefined_high(x):
        return None if x > 0.5 else x

    with pytest.raises(NoRootInBracket, match="undefined at a bracket endpoint"):
        bisect(undefined_high, target=0.3, lo=0.0, hi=1.0, tolerance=1e-9)


def test_the_solver_handles_a_descending_function():
    """The caller should not have to know which way the function runs."""
    result = bisect(lambda x: 10.0 - x, target=4.0, lo=0.0, hi=10.0,
                    tolerance=1e-9)
    assert result.root == pytest.approx(6.0, abs=1e-6)


def test_an_endpoint_that_is_already_the_target_is_returned_exactly():
    result = bisect(lambda x: x, target=2.0, lo=2.0, hi=5.0, tolerance=1e-9)
    assert result.root == 2.0 and result.iterations == 0


def test_the_solver_is_deterministic():
    price = _value_at(0.17)
    runs = [reverse_solver.solve_implied_roe(_value_at, price, 0.15,
                                             _value_at(0.15), bracket=BRACKET)
            for _ in range(3)]
    assert len({r.implied_sustainable_roe for r in runs}) == 1
    assert len({r.solver.iterations for r in runs}) == 1


# --- through the model -----------------------------------------------------


def test_no_price_means_no_market_implied_case(synthetic_bank):
    """The default. Rights withhold the price, so the section is absent and
    says why rather than being quietly empty."""
    result = evaluate(synthetic_bank)
    assert result.implied is None
    assert "No price is supplied" in result.market_implied_note


def test_an_injected_price_produces_a_market_implied_case(synthetic_bank):
    with_price(synthetic_bank, 2000.0)
    result = BankModel().evaluate(load(synthetic_bank), context(synthetic_bank))
    assert result.implied is not None
    assert 0.0 <= result.implied.implied_sustainable_roe <= 0.60


def test_an_unreachable_price_leaves_the_case_unsolved(synthetic_bank):
    """The model refuses rather than returning the nearest endpoint."""
    with_price(synthetic_bank, 1e15)
    result = BankModel().evaluate(load(synthetic_bank), context(synthetic_bank))
    assert result.implied is None
