"""Engine-owned controlled vocabularies.

These are deliberately separate from Stage 1's enums. The engine extends the
pipeline's vocabulary; it never redefines it. Where Stage 1 already owns a
concept — ``ValueBasis``, ``MissingReason``, ``QualityStatus``, ``PeriodType``
— the engine imports it rather than declaring a parallel copy that could drift.
"""

from __future__ import annotations

from pipeline.goh_dip_tong.contracts.enums import StrEnum


class EngineMode(StrEnum):
    """Whether output describes real data or development fixtures.

    This is never set by hand. :mod:`engine.goh_dip_tong.inputs.provenance`
    derives it from the inputs' own provenance, so it flips to ``PRODUCTION``
    automatically when the inputs become authoritative and cannot be forgotten
    when they are not.
    """

    #: At least one input is fixture-backed or non-authoritative. Nothing in
    #: the output may be presented as live, current or real analysis.
    FIXTURE_TEST_ONLY = "FIXTURE_TEST_ONLY"
    #: Every input is authoritative and rights-cleared. Unreachable today.
    PRODUCTION = "PRODUCTION"


class ResearchStatus(StrEnum):
    """Spec section 2.8. Distinct from Stage 1's ``CoverageStatus``.

    ``CoverageStatus`` is the *universe registry's* view of a company and is
    owned by Stage 1 — the engine reads it and never writes it. This is the
    *engine's* view of how far research has actually got. They overlap but are
    not the same ladder, and collapsing them would let the engine silently
    promote a company Stage 1 has not.
    """

    #: Identity known; no validated financial facts.
    DISCOVERY = "DISCOVERY"
    #: Facts present and schema-valid; no model has been applied.
    FINANCIALS_VALIDATED = "FINANCIALS_VALIDATED"
    #: A model family is mapped but cannot produce a validated valuation —
    #: unsupported, not yet implemented, or short of required inputs.
    MODEL_UNDER_VALIDATION = "MODEL_UNDER_VALIDATION"
    #: Every gate in spec section 2.8 passes.
    FULL_RESEARCH = "FULL_RESEARCH"
    #: The issuer is halted, delisted or otherwise withdrawn from coverage.
    MODEL_SUSPENDED = "MODEL_SUSPENDED"
    #: Inputs are older than the configured staleness threshold.
    STALE = "STALE"


class ScenarioName(StrEnum):
    BEAR = "BEAR"
    BASE = "BASE"
    BULL = "BULL"
    #: Values that are not scenario-dependent: reported facts, historical
    #: derived metrics. Using BASE for these would imply a forecast where
    #: there is none.
    ACTUAL = "ACTUAL"


class ValuationMethod(StrEnum):
    RESIDUAL_INCOME = "RESIDUAL_INCOME"
    DIVIDEND_DISCOUNT = "DIVIDEND_DISCOUNT"
    JUSTIFIED_PB = "JUSTIFIED_PB"
    ENTERPRISE_DCF = "ENTERPRISE_DCF"
    EV_EBITDA = "EV_EBITDA"
    PE_MULTIPLE = "PE_MULTIPLE"
    FCF_YIELD = "FCF_YIELD"
    SUM_OF_THE_PARTS = "SUM_OF_THE_PARTS"
    NAV = "NAV"
    RNAV = "RNAV"


class ValuationOutcome(StrEnum):
    VALUED = "VALUED"
    REFUSED = "REFUSED"


class RefusalReason(StrEnum):
    """Why no valuation was produced.

    Every one of these names a specific, checkable condition. There is no
    generic "could not value" — a refusal a reader cannot act on is only
    marginally better than a wrong number.
    """

    #: The classification maps to no model family at all (Stage 1's ONBOARDING).
    NO_MODEL_FAMILY = "NO_MODEL_FAMILY"
    #: models.yml declares the family with ``supported: false``.
    MODEL_FAMILY_UNSUPPORTED = "MODEL_FAMILY_UNSUPPORTED"
    #: The family is supported and registered, but its mathematics is not built
    #: yet. True of every family in this slice.
    MODEL_NOT_IMPLEMENTED = "MODEL_NOT_IMPLEMENTED"
    #: Required metrics are absent from the inputs.
    INSUFFICIENT_INPUTS = "INSUFFICIENT_INPUTS"
    #: Fewer historical periods than the model needs to anchor a forecast.
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    #: No price is available, so a price-dependent output cannot be produced.
    NO_MARKET_DATA = "NO_MARKET_DATA"
    #: No validated risk-free input, so no defensible cost of equity.
    NO_VALIDATED_RISK_FREE_RATE = "NO_VALIDATED_RISK_FREE_RATE"
    #: A terminal assumption is outside its admissible range (r <= g, fade >= 1).
    TERMINAL_ASSUMPTION_INVALID = "TERMINAL_ASSUMPTION_INVALID"
    #: The method requested is invalid for this model family.
    METHOD_NOT_PERMITTED_FOR_FAMILY = "METHOD_NOT_PERMITTED_FOR_FAMILY"
    #: Two facts describe the same metric, period and basis and cannot be told
    #: apart. Picking one arbitrarily would be a silent guess.
    AMBIGUOUS_FACTS = "AMBIGUOUS_FACTS"
    #: The issuer is not covered.
    COVERAGE_SUSPENDED = "COVERAGE_SUSPENDED"
    #: Inputs are stale beyond the configured threshold.
    INPUTS_STALE = "INPUTS_STALE"


class GateId(StrEnum):
    """Named preconditions a model checks before it will value anything.

    A refusal lists the gates that failed, so "why is there no number" always
    has a specific answer rather than a shrug.
    """

    MODEL_REGISTERED = "MODEL_REGISTERED"
    MODEL_IMPLEMENTED = "MODEL_IMPLEMENTED"
    MODEL_FAMILY_SUPPORTED = "MODEL_FAMILY_SUPPORTED"
    REQUIRED_INPUTS_PRESENT = "REQUIRED_INPUTS_PRESENT"
    PER_SHARE_INPUTS = "PER_SHARE_INPUTS"
    MIN_HISTORY_PERIODS = "MIN_HISTORY_PERIODS"
    VALIDATED_RISK_FREE_RATE = "VALIDATED_RISK_FREE_RATE"
    MARKET_DATA_AVAILABLE = "MARKET_DATA_AVAILABLE"
    FACTS_UNAMBIGUOUS = "FACTS_UNAMBIGUOUS"
    COVERAGE_ACTIVE = "COVERAGE_ACTIVE"
    INPUTS_FRESH = "INPUTS_FRESH"


__all__ = [
    "EngineMode",
    "ResearchStatus",
    "ScenarioName",
    "ValuationMethod",
    "ValuationOutcome",
    "RefusalReason",
    "GateId",
]
