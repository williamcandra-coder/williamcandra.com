"""Where the discount rate comes from, and why it usually does not exist.

There is no validated risk-free input for the Indonesian market in this
repository, so CAPM cannot be evaluated and no real issuer gets a cost of
equity. That is not a gap waiting to be filled with the nearest available
number — it is the reason every real issuer's valuation is refused.

BI_7DRR is the nearest available number, and it is explicitly refused.
`config/cost-of-capital.yml` records why: it is a short-term policy rate, and
discounting multi-decade equity cash flows with it understates the rate,
inflates the valuation, and leaves an output that looks like an ordinary CAPM
figure. A wrong discount rate does not announce itself.

The synthetic rate below exists so the mathematics can be exercised. Getting at
it requires asking for it by name.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class CostOfEquityUnavailable(ValueError):
    """No defensible discount rate can be formed from the available inputs."""


@dataclass(frozen=True)
class CostOfEquity:
    """A discount rate and an honest account of where it came from."""

    rate: float
    #: ``SYNTHETIC`` or ``CAPM``. Travels into every snapshot that uses it.
    basis: str
    risk_free: Optional[float] = None
    equity_risk_premium: Optional[float] = None
    beta: Optional[float] = None
    risk_free_source: Optional[str] = None
    note: str = ""

    @property
    def is_synthetic(self) -> bool:
        return self.basis == "SYNTHETIC"

    def to_json(self) -> dict:
        return {
            "rate": self.rate,
            "basis": self.basis,
            "riskFree": self.risk_free,
            "equityRiskPremium": self.equity_risk_premium,
            "beta": self.beta,
            "riskFreeSource": self.risk_free_source,
            "note": self.note,
        }


def resolve(config: dict, family: str, allow_synthetic: bool) -> CostOfEquity:
    """The discount rate for ``family``, or a refusal explaining its absence.

    ``allow_synthetic`` is the only route to a usable rate today. It is passed
    by the test harness and by nothing else — the CLI does not expose it, and
    ``test_refusal.py`` parses the CLI's source to keep it that way. So a
    published snapshot cannot rest on an invented rate no matter what is added
    to the command line later.
    """
    risk_free = config.get("risk_free") or {}
    premium = config.get("equity_risk_premium") or {}
    beta_config = config.get("beta") or {}

    if risk_free.get("validated") and premium.get("validated") and beta_config.get("validated"):
        beta = (beta_config.get("by_family") or {}).get(family)
        if beta is None:
            raise CostOfEquityUnavailable(
                f"no beta is configured for model family {family}"
            )
        rate = float(risk_free["value"]) + float(beta) * float(premium["value"])
        return CostOfEquity(
            rate=rate,
            basis="CAPM",
            risk_free=float(risk_free["value"]),
            equity_risk_premium=float(premium["value"]),
            beta=float(beta),
            risk_free_source=risk_free.get("instrument"),
            note="CAPM on a validated risk-free yield.",
        )

    if not allow_synthetic:
        rejected = ", ".join(
            r.get("id", "?") for r in (risk_free.get("rejected_substitutes") or [])
        )
        raise CostOfEquityUnavailable(
            "no validated risk-free input is available, so no defensible cost "
            "of equity can be formed. "
            + (f"Refused as substitutes: {rejected}. " if rejected else "")
            + "A validated long-dated government bond yield, with a documented "
            "source and retrieval date, is what would resolve this."
        )

    synthetic = config.get("synthetic") or {}
    if not synthetic:
        raise CostOfEquityUnavailable(
            "synthetic assumptions were permitted but none are configured"
        )
    return CostOfEquity(
        rate=float(synthetic["cost_of_equity"]),
        basis="SYNTHETIC",
        risk_free=synthetic.get("risk_free"),
        equity_risk_premium=synthetic.get("equity_risk_premium"),
        beta=synthetic.get("beta"),
        risk_free_source="SYNTHETIC — invented for engine fixtures",
        note=(
            "SYNTHETIC. Invented to exercise the engine's mathematics against "
            "the synthetic-bank fixture. Describes no real market and must "
            "never reach published output."
        ),
    )


__all__ = ["CostOfEquity", "CostOfEquityUnavailable", "resolve"]
