"""Why the valuation moved, in terms someone can disagree with.

Spec section 2.6 requires a reconciliation of the form

    previous value
      + operating-driver changes
      + balance-sheet changes
      + cost-of-capital changes
      + model roll-forward
      = current value

The legs are computed by **sequential single-factor substitution**: start from
the previous assumptions, swap one group for its current values, re-run the
valuation, and take the difference. Order matters because the factors interact,
so the order is pinned in code rather than left to whatever a dict yields.

**On the residual.** Sequential substitution telescopes: if the declared legs
cover every input, the deltas necessarily sum to the total move and the
residual is zero by construction — which would make an `unexplained` term
decorative. It is not decorative here, because the legs cover a *declared* set
of factors and nothing else. A change to something outside that set — a share
count, a payout ratio, a persistence assumption — lands in `unexplained` and
stays visible.

That is the behaviour worth testing, and `test_bridge.py` tests exactly it:
move a factor no leg claims, and assert the bridge reports it as unexplained
rather than quietly absorbing it into the nearest plausible leg.

``payout`` is the deliberate example. It is a capital-allocation decision, not
an operating driver, a balance-sheet movement, a cost-of-capital change or the
passage of time — so no leg claims it, and a change to it shows up as
unexplained. Adding it to a leg later would be a real decision about what the
bridge asserts, which is exactly the kind of decision that should require
editing this list rather than happening by default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple

#: The legs, in substitution order, and the factor groups each one owns.
#: Roll-forward comes last: it is the effect of time passing given everything
#: else already updated, which is only meaningful once the rest has moved.
BRIDGE_LEGS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("operatingDrivers", (
        "sustainable_roe",
        "earning_asset_growth", "asset_yield", "funding_cost", "fee_ratio",
        "cost_to_income", "cost_of_credit", "loans_to_earning_assets",
        "deposits_to_earning_assets", "casa_to_deposits", "tax_rate",
        "minority_share",
    )),
    ("balanceSheet", ("opening_book", "shares")),
    ("costOfCapital", ("cost_of_equity",)),
    ("rollForward", ("base_year",)),
)


@dataclass
class BridgeLeg:
    """One explained movement."""

    name: str
    amount: float
    factors: List[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return {"leg": self.name, "amount": self.amount,
                "factors": sorted(self.factors)}


@dataclass
class Bridge:
    """Previous value, the legs that explain the move, and what does not."""

    previous: float
    current: float
    legs: List[BridgeLeg]
    unexplained: float
    tolerance: float

    @property
    def total_move(self) -> float:
        return self.current - self.previous

    @property
    def explained(self) -> float:
        total = 0.0
        for leg in self.legs:  # ordered: float addition is not associative
            total += leg.amount
        return total

    @property
    def reconciles(self) -> bool:
        """Whether the legs account for the whole move within tolerance."""
        scale = max(abs(self.previous), abs(self.current), 1.0)
        return abs(self.unexplained) <= self.tolerance * scale

    def to_json(self) -> dict:
        return {
            "previousValue": self.previous,
            "legs": [leg.to_json() for leg in self.legs],
            "unexplained": self.unexplained,
            "currentValue": self.current,
            "totalMove": self.total_move,
            "explained": self.explained,
            "reconciles": self.reconciles,
            "tolerance": self.tolerance,
        }


def build(
    previous_state: Dict[str, object],
    current_state: Dict[str, object],
    evaluate: Callable[[Dict[str, object]], float],
    tolerance: float = 1e-4,
) -> Bridge:
    """Reconcile two valuations by substituting one factor group at a time.

    ``evaluate`` re-runs the valuation for a given state. States are plain
    dicts of factor name to value, so a factor the legs do not claim can exist
    in them and still be seen — which is exactly how it surfaces as
    unexplained.
    """
    previous_value = evaluate(previous_state)
    current_value = evaluate(current_state)

    state = dict(previous_state)
    running = previous_value
    legs: List[BridgeLeg] = []

    for name, factors in BRIDGE_LEGS:
        moved = [f for f in factors
                 if f in current_state and state.get(f) != current_state[f]]
        for factor in factors:
            if factor in current_state:
                state[factor] = current_state[factor]
        stepped = evaluate(state)
        legs.append(BridgeLeg(name=name, amount=stepped - running, factors=moved))
        running = stepped

    # Whatever the declared legs did not move is still different between the
    # two states. Reported, never redistributed.
    unexplained = current_value - running
    return Bridge(previous=previous_value, current=current_value, legs=legs,
                  unexplained=unexplained, tolerance=tolerance)


__all__ = ["Bridge", "BridgeLeg", "build", "BRIDGE_LEGS"]
