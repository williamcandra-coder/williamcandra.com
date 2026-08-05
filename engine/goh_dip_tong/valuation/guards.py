"""Terminal-assumption guards.

Every closed-form continuing value in equity valuation has the same shape:
something divided by ``(r - g)`` or ``(1 + r - omega)``. As the denominator
approaches zero the value approaches infinity, smoothly and without any
warning in the output. A model that returns forty times book because ``g``
crept to within ten basis points of ``r`` has not made an arithmetic error —
it has faithfully computed a meaningless number, which is worse, because the
number looks like research.

So the admissible region is declared, checked before the division, and a
violation refuses. These are not sanity checks bolted on afterwards; they are
part of the method's definition.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class TerminalAssumptionInvalid(ValueError):
    """A terminal assumption falls outside the region where the method holds."""


@dataclass(frozen=True)
class TerminalGuards:
    """The admissible region for terminal assumptions."""

    #: Minimum spread between the discount rate and the perpetual growth rate.
    #: Below this the continuing value is dominated by the denominator rather
    #: than by anything the analyst believes.
    min_spread: float = 0.01
    #: Residual income must fade: persistence of 1.0 means abnormal returns
    #: last forever, which no competitive market allows.
    max_persistence: float = 0.99
    #: A discount rate at or below zero is not a discount rate.
    min_discount_rate: float = 0.0001

    # ---- checks ----------------------------------------------------------
    def check_spread(self, r: float, g: float) -> None:
        """``r - g`` must clear ``min_spread``.

        Checked before the division rather than after: catching an infinity
        afterwards tells you the result is wrong but not which assumption made
        it so, and by then the number may already have been rounded into
        something plausible-looking.
        """
        if r <= self.min_discount_rate:
            raise TerminalAssumptionInvalid(
                f"discount rate r={r:.6f} is not positive; a non-positive "
                f"discount rate has no economic meaning"
            )
        # Compared on the spread rather than by rearranging, so the number in
        # the message is the number that was tested. Ties refuse: at exactly
        # the minimum the continuing value is already dominated by the
        # denominator, and floating point makes "exactly" unreliable anyway.
        if (r - g) <= self.min_spread:
            raise TerminalAssumptionInvalid(
                f"terminal growth g={g:.6f} is not at least {self.min_spread:.4f} "
                f"below the discount rate r={r:.6f} (spread {r - g:.6f}). The "
                f"continuing value would be dominated by the denominator rather "
                f"than by the forecast."
            )

    def check_persistence(self, omega: float) -> None:
        """Residual-income persistence must lie in [0, max_persistence]."""
        if omega < 0:
            raise TerminalAssumptionInvalid(
                f"residual-income persistence omega={omega:.6f} is negative; "
                f"abnormal returns cannot alternate sign by assumption"
            )
        if omega > self.max_persistence:
            raise TerminalAssumptionInvalid(
                f"residual-income persistence omega={omega:.6f} exceeds "
                f"{self.max_persistence:.4f}. At omega=1 abnormal returns "
                f"persist forever, which assumes competition never arrives."
            )

    def spread_ok(self, r: float, g: float) -> bool:
        try:
            self.check_spread(r, g)
        except TerminalAssumptionInvalid:
            return False
        return True

    def to_json(self) -> dict:
        return {
            "minSpread": self.min_spread,
            "maxPersistence": self.max_persistence,
            "minDiscountRate": self.min_discount_rate,
        }


def load_guards(engine_config: dict) -> TerminalGuards:
    terminal = (engine_config.get("terminal") or {})
    return TerminalGuards(
        min_spread=float(terminal.get("min_spread", 0.01)),
        max_persistence=float(terminal.get("max_persistence", 0.99)),
        min_discount_rate=float(terminal.get("min_discount_rate", 0.0001)),
    )


def clamp(value: float, bounds: Optional[list]) -> float:
    """Hold a scenario-shifted anchor inside its declared range.

    A bear case that drives funding cost negative is not a pessimistic view of
    the world, it is a broken assumption, and letting it through would put a
    number in the output that nothing in the model believes.
    """
    if not bounds:
        return value
    low, high = float(bounds[0]), float(bounds[1])
    return max(low, min(high, value))


__all__ = [
    "TerminalGuards",
    "TerminalAssumptionInvalid",
    "load_guards",
    "clamp",
]
