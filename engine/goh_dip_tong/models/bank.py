"""The BANK model family — declaration and gates only.

`models.yml` states the rule this family exists to honour: *"Debt is raw
material, not financing. EV/EBITDA and FCFF are invalid here."* That is encoded
below as ``forbidden_methods``, which raise on invocation rather than merely
being left unselected — a rule enforced only by not calling something is a rule
that survives exactly until someone calls it.

The mathematics (residual income, justified P/B, dividend discount, the driver
chain and the reverse solver) belongs to a later slice. What is real here is the
declaration of what the model needs, which is what turns "we cannot value this
issuer" into a list of seventeen named metrics.
"""

from __future__ import annotations

from ..contracts.enums import ValuationMethod
from ..contracts.model import SectorModel

#: Everything the residual-income model consumes, in the order the driver chain
#: uses them. Every one is defined in Stage 1's canonical metric registry; none
#: is collected by any enabled provider today.
BANK_REQUIRED_METRICS = (
    # equity side — the residual-income base and its roll-forward
    "equity_attributable_to_parent",
    "net_profit_attributable_to_parent",
    "dividends_paid",
    "shares_outstanding",
    # net interest income
    "earning_assets",
    "interest_income",
    "interest_expense",
    # funding mix
    "deposits",
    "casa_deposits",
    # pre-provision operating profit
    "fee_income",
    "operating_expense",
    # credit
    "loans",
    "provision_expense",
    "non_performing_loans",
    "loan_loss_allowance",
    # capital
    "tier1_capital",
    "risk_weighted_assets",
)


class BankModel(SectorModel):
    family = "BANK"

    #: No valuation mathematics in this slice.
    implemented = False

    required_metrics = BANK_REQUIRED_METRICS

    permitted_methods = (
        ValuationMethod.RESIDUAL_INCOME,    # primary
        ValuationMethod.JUSTIFIED_PB,       # cross-check
        ValuationMethod.DIVIDEND_DISCOUNT,  # where payout is stable
    )

    #: Enterprise-value methods treat debt as financing. For a bank, deposits
    #: and borrowings are the raw material of the business, so enterprise value
    #: is not a meaningful quantity and these produce confident nonsense.
    forbidden_methods = (
        ValuationMethod.ENTERPRISE_DCF,
        ValuationMethod.EV_EBITDA,
        ValuationMethod.FCF_YIELD,
    )

    #: Stage 1's handoff is explicit: net_debt for a bank must be null with
    #: NOT_APPLICABLE_TO_MODEL, never 0.
    not_applicable_metrics = ("net_debt", "interest_bearing_debt")

    #: Three years is the minimum that distinguishes a trend from a level.
    min_annual_periods = 3


__all__ = ["BankModel", "BANK_REQUIRED_METRICS"]
