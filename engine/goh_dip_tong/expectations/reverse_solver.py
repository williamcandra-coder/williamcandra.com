"""What would have to be true for today's price to be right.

Spec section 2.7. The output people actually argue about is not the target
price — it is the gap between what the market is assuming and what we are.
So the solver holds the discount rate and payout fixed and asks the single
question the answer can be checked against: *what sustainable return on equity
does this price imply?*

Three design choices are load-bearing.

**It solves the steady-state residual-income model.** "What sustainable ROE
does this price imply" is a question about the terminal state, so mixing it
with a five-year transition would make the answer depend on the path rather
than on the steady state being asked about. The implied ROE is therefore
directly comparable with the forecast's own terminal ROE, which is the
comparison worth publishing.

**It bisects rather than inverting algebraically.** The closed form exists.
Using it would bypass the terminal guards, and a solver that can return an
answer the valuation itself would refuse to produce is not measuring the same
model. Running the guarded valuation function means a region the model will
not value is a region the solver will not search.

**No root means no answer.** If the price lies outside the range the model can
produce across the whole ROE bracket, the solver refuses and names the bracket.
Extrapolating past the endpoint would answer a question nobody asked.

None of this runs for a real issuer today: solving a price back to assumptions
requires a price, and the market-data provider is `PRIVATE_RESEARCH_ONLY`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from ..common.solvers import NoRootInBracket, SolverResult, bisect
from .. import MODEL_VERSION

#: Absolute ceiling on the search, for the degenerate case where payout is 1
#: and growth is zero regardless of ROE. No bank sustains this.
MAX_SUSTAINABLE_ROE = 1.0

#: Fallback range. Real searches use :func:`admissible_bracket`, which is
#: narrower and derived from the assumptions rather than guessed.
DEFAULT_BRACKET = (0.0, 0.60)

#: Convergence tolerance on value per share, in currency units.
DEFAULT_TOLERANCE = 1e-6


def admissible_bracket(rate: float, payout: float, guards,
                       lo: float = 0.0) -> tuple:
    """The range of sustainable ROE over which the model is actually defined.

    Sustainable growth is ``ROE x (1 - payout)``, so a high enough ROE pushes
    growth past the discount rate and the terminal guard refuses. Searching a
    fixed wide bracket would therefore hit an undefined endpoint and report "no
    root" for a price that is perfectly reachable — the bracket has to come
    from the assumptions, not from a guess about what banks look like.

    The upper bound is shaded just inside the guard, because the guard refuses
    ties and an endpoint it rejects is an endpoint the solver cannot use.
    """
    retention = 1.0 - payout
    if retention <= 0:
        return (lo, MAX_SUSTAINABLE_ROE)
    ceiling = (rate - guards.min_spread * (1.0 + 1e-6)) / retention
    return (lo, min(MAX_SUSTAINABLE_ROE, max(lo, ceiling)))


@dataclass(frozen=True)
class ImpliedExpectation:
    """The market-implied case, and the gap against our own."""

    implied_sustainable_roe: float
    base_case_sustainable_roe: float
    price_per_share: float
    base_case_value_per_share: float
    solver: SolverResult

    @property
    def expectation_gap(self) -> float:
        """Ours minus the market's. Positive means we are more optimistic."""
        return self.base_case_sustainable_roe - self.implied_sustainable_roe

    def to_json(self) -> dict:
        return {
            "marketImpliedCase": {
                "sustainableRoe": self.implied_sustainable_roe,
                "pricePerShare": self.price_per_share,
            },
            "gdtBaseCase": {
                "sustainableRoe": self.base_case_sustainable_roe,
                "valuePerShare": self.base_case_value_per_share,
            },
            "expectationGap": {
                "sustainableRoe": self.expectation_gap,
                "valuePerShare": self.base_case_value_per_share - self.price_per_share,
            },
            "solver": self.solver.to_json(),
        }


def solve_implied_roe(
    value_at_roe: Callable[[float], Optional[float]],
    price_per_share: float,
    base_case_roe: float,
    base_case_value: float,
    bracket: tuple = DEFAULT_BRACKET,
    tolerance: float = DEFAULT_TOLERANCE,
) -> ImpliedExpectation:
    """Find the sustainable ROE at which the model returns ``price_per_share``.

    ``value_at_roe`` re-runs the valuation with the terminal ROE overridden and
    returns value per share, or ``None`` where the terminal guards refuse. A
    ``None`` inside the bracket ends the search rather than being skipped:
    a region the model will not value is not a region a root can hide in.

    Raises :class:`NoRootInBracket` when the price is unreachable.
    """
    result = bisect(
        value_at_roe, target=price_per_share, lo=bracket[0], hi=bracket[1],
        tolerance=tolerance,
    )
    return ImpliedExpectation(
        implied_sustainable_roe=result.root,
        base_case_sustainable_roe=base_case_roe,
        price_per_share=price_per_share,
        base_case_value_per_share=base_case_value,
        solver=result,
    )


__all__ = [
    "ImpliedExpectation",
    "admissible_bracket",
    "solve_implied_roe",
    "NoRootInBracket",
    "DEFAULT_BRACKET",
    "DEFAULT_TOLERANCE",
    "MAX_SUSTAINABLE_ROE",
    "MODEL_VERSION",
]
