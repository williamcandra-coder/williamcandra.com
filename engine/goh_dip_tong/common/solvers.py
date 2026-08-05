"""Root finding that refuses rather than extrapolates.

A solver that always returns something is worse than one that sometimes says
no. Bisection on a bracket has exactly the property we want: if the target is
not inside the bracket, there is no root to find, and the honest answer is a
refusal naming the bracket that was searched — not the nearest endpoint, and
certainly not an extrapolation beyond it.

Determinism matters as much as correctness here. The iteration count is bounded
and the tolerance is absolute, so the same inputs always converge to the same
value in the same number of steps on any machine.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Tuple


class NoRootInBracket(ValueError):
    """The function does not cross the target anywhere inside the bracket."""


@dataclass(frozen=True)
class SolverResult:
    """What the solver found, and how hard it had to look."""

    root: float
    iterations: int
    residual: float
    bracket: Tuple[float, float]

    def to_json(self) -> dict:
        return {
            "root": self.root,
            "iterations": self.iterations,
            "residual": self.residual,
            "bracket": list(self.bracket),
        }


def bisect(
    fn: Callable[[float], Optional[float]],
    target: float,
    lo: float,
    hi: float,
    tolerance: float,
    max_iterations: int = 200,
) -> SolverResult:
    """Find ``x`` in ``[lo, hi]`` with ``fn(x) == target``, or raise.

    ``fn`` must be continuous and monotone over the bracket; both directions are
    handled, so the caller does not have to know which way it runs.

    ``fn`` returning ``None`` means "undefined here" — a guard rejected the
    assumption at that point. That is treated as a failure to bracket rather
    than as a value, because a point where the model refuses to produce a
    number cannot be compared against a target.
    """
    if not lo < hi:
        raise NoRootInBracket(f"empty bracket: [{lo}, {hi}]")

    f_lo, f_hi = fn(lo), fn(hi)
    if f_lo is None or f_hi is None:
        raise NoRootInBracket(
            f"the model is undefined at a bracket endpoint "
            f"([{lo}, {hi}] -> {f_lo}, {f_hi}); no root can be established"
        )

    low_side, high_side = f_lo - target, f_hi - target
    if low_side == 0:
        return SolverResult(lo, 0, 0.0, (lo, hi))
    if high_side == 0:
        return SolverResult(hi, 0, 0.0, (lo, hi))
    if (low_side > 0) == (high_side > 0):
        raise NoRootInBracket(
            f"target {target!r} is not bracketed: f({lo})={f_lo!r}, "
            f"f({hi})={f_hi!r}. Both endpoints fall on the same side, so the "
            f"target lies outside the range the model can produce here."
        )

    ascending = high_side > low_side
    left, right = lo, hi
    for iteration in range(1, max_iterations + 1):
        middle = (left + right) / 2.0
        value = fn(middle)
        if value is None:
            raise NoRootInBracket(
                f"the model became undefined at {middle!r} during the search"
            )
        residual = value - target
        if abs(residual) <= tolerance or (right - left) / 2.0 <= tolerance:
            return SolverResult(middle, iteration, residual, (lo, hi))
        if (residual > 0) == ascending:
            right = middle
        else:
            left = middle

    raise NoRootInBracket(
        f"did not converge within {max_iterations} iterations on [{lo}, {hi}]"
    )


__all__ = ["bisect", "SolverResult", "NoRootInBracket"]
