"""The valuation bridge, and the residual it refuses to hide.

Sequential substitution telescopes, so a bridge whose legs cover every input
reconciles to zero by construction. That makes the interesting test the other
one: move something no leg claims, and check the bridge says so instead of
folding it into whichever leg happens to be adjacent.
"""

from __future__ import annotations

import pytest

from engine.goh_dip_tong.common.bridge import BRIDGE_LEGS
from engine.goh_dip_tong.models.bank import build_bridge
from engine.goh_dip_tong.valuation.guards import TerminalGuards

GUARDS = TerminalGuards()
BOOK, SHARES, PAYOUT, RATE = 200e12, 1.2e11, 0.5, 0.12

PREVIOUS = {
    "sustainable_roe": 0.15, "payout": PAYOUT, "cost_of_equity": RATE,
    "opening_book": BOOK, "shares": SHARES,
}


def _bridge(current, tolerance=1e-9):
    return build_bridge(BOOK, SHARES, PAYOUT, RATE, GUARDS, PREVIOUS, current,
                        tolerance=tolerance)


# --- reconciliation --------------------------------------------------------


def test_an_unchanged_state_moves_nothing():
    bridge = _bridge(dict(PREVIOUS))
    assert bridge.total_move == pytest.approx(0.0, abs=1e-9)
    assert bridge.unexplained == pytest.approx(0.0, abs=1e-9)
    assert bridge.reconciles


def test_changes_inside_the_declared_legs_reconcile_exactly():
    current = dict(PREVIOUS, sustainable_roe=0.17, cost_of_equity=0.11,
                   opening_book=218e12)
    bridge = _bridge(current)
    assert bridge.unexplained == pytest.approx(0.0, abs=1e-9)
    assert bridge.reconciles
    assert bridge.explained == pytest.approx(bridge.total_move, rel=1e-9)


def test_the_legs_sum_to_the_total_move_when_complete():
    current = dict(PREVIOUS, sustainable_roe=0.18)
    bridge = _bridge(current)
    total = 0.0
    for leg in bridge.legs:
        total += leg.amount
    assert total == pytest.approx(bridge.current - bridge.previous, rel=1e-9)


@pytest.mark.parametrize("factor,value", [
    ("sustainable_roe", 0.18),
    ("cost_of_equity", 0.11),
    ("opening_book", 230e12),
    ("shares", 1.3e11),
])
def test_each_declared_factor_lands_in_a_leg(factor, value):
    bridge = _bridge(dict(PREVIOUS, **{factor: value}))
    claimed = [leg.name for leg in bridge.legs if factor in leg.factors]
    assert len(claimed) == 1, f"{factor} should be claimed by exactly one leg"
    assert bridge.reconciles


# --- the unexplained residual ---------------------------------------------


def test_a_factor_no_leg_claims_surfaces_as_unexplained():
    """Payout is a capital-allocation decision, not an operating driver, a
    balance-sheet movement, a cost-of-capital change, or the passage of time.
    No leg claims it, and the bridge has to say so."""
    bridge = _bridge(dict(PREVIOUS, payout=0.6))
    assert bridge.unexplained != 0.0
    assert not bridge.reconciles
    assert all("payout" not in leg.factors for leg in bridge.legs)


def test_the_unexplained_residual_is_not_redistributed():
    """The legs keep the amounts they earned; the remainder stays separate."""
    both = _bridge(dict(PREVIOUS, sustainable_roe=0.17, payout=0.6))
    roe_only = _bridge(dict(PREVIOUS, sustainable_roe=0.17))
    operating = [leg for leg in both.legs if leg.name == "operatingDrivers"][0]
    reference = [leg for leg in roe_only.legs if leg.name == "operatingDrivers"][0]
    assert operating.amount == pytest.approx(reference.amount, rel=1e-9)


def test_the_unexplained_amount_is_reported_in_the_payload():
    payload = _bridge(dict(PREVIOUS, payout=0.65)).to_json()
    assert "unexplained" in payload
    assert payload["unexplained"] != 0.0
    assert payload["reconciles"] is False


def test_the_payload_states_previous_legs_and_current_in_that_order():
    """Spec 2.6's shape: previous + legs = current, readable in one pass."""
    payload = _bridge(dict(PREVIOUS, sustainable_roe=0.16)).to_json()
    assert list(payload)[:3] == ["previousValue", "legs", "unexplained"]
    assert [leg["leg"] for leg in payload["legs"]] == [
        name for name, _ in BRIDGE_LEGS]


# --- structure -------------------------------------------------------------


def test_every_leg_the_spec_names_is_present():
    names = [name for name, _ in BRIDGE_LEGS]
    assert names == ["operatingDrivers", "balanceSheet", "costOfCapital",
                     "rollForward"]


def test_no_factor_is_claimed_by_two_legs():
    """Otherwise a movement would be counted twice and the bridge would
    reconcile while being wrong."""
    seen = set()
    for _, factors in BRIDGE_LEGS:
        for factor in factors:
            assert factor not in seen, factor
            seen.add(factor)


def test_the_bridge_is_deterministic():
    current = dict(PREVIOUS, sustainable_roe=0.17, opening_book=210e12)
    first, second = _bridge(current).to_json(), _bridge(current).to_json()
    assert first == second
