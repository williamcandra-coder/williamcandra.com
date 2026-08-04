"""Controlled vocabularies shared by every layer of the pipeline.

These are `str` enums so a value serialises to plain JSON without a custom
encoder, and so a hand-written string in a fixture still compares equal to the
enum member.
"""

from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    """`str` subclass enum. Python 3.11's own StrEnum is fine but this keeps the
    module importable on 3.9/3.10 runners too."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return str(self.value)


class RightsStatus(StrEnum):
    """What a source permits. Ordered loosely from most to least permissive."""

    PUBLIC_RAW_DATA_APPROVED = "PUBLIC_RAW_DATA_APPROVED"
    PUBLIC_DERIVED_OUTPUT_APPROVED = "PUBLIC_DERIVED_OUTPUT_APPROVED"
    PUBLIC_METADATA_ONLY = "PUBLIC_METADATA_ONLY"
    PRIVATE_RESEARCH_ONLY = "PRIVATE_RESEARCH_ONLY"
    DISCOVERY_ONLY = "DISCOVERY_ONLY"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    DISABLED = "DISABLED"


#: Statuses that may never run, regardless of the `enabled` flag in sources.yml.
#: This is the second of the two independent locks on live providers.
NON_RUNNABLE_RIGHTS = frozenset(
    {RightsStatus.MANUAL_REVIEW_REQUIRED, RightsStatus.DISABLED}
)


class CoverageStatus(StrEnum):
    FULL_RESEARCH = "FULL_RESEARCH"
    FINANCIALS = "FINANCIALS"
    ONBOARDING = "ONBOARDING"
    SUSPENDED = "SUSPENDED"


class ChangeType(StrEnum):
    """Membership-history event types (spec section 1.4)."""

    ADDED = "ADDED"
    REMOVED = "REMOVED"
    RENAMED = "RENAMED"
    RECLASSIFIED = "RECLASSIFIED"
    UNCHANGED = "UNCHANGED"


class EventStatus(StrEnum):
    """Certainty ladder. Anything below OFFICIAL_DECISION is not a fact."""

    RUMOR = "RUMOR"
    MEDIA_REPORT = "MEDIA_REPORT"
    PROPOSAL = "PROPOSAL"
    OFFICIAL_DECISION = "OFFICIAL_DECISION"
    IMPLEMENTED = "IMPLEMENTED"
    COMPANY_IMPACT_CONFIRMED = "COMPANY_IMPACT_CONFIRMED"


#: Rank used to decide whether a new observation advances an event's certainty.
EVENT_STATUS_RANK = {
    EventStatus.RUMOR: 0,
    EventStatus.MEDIA_REPORT: 1,
    EventStatus.PROPOSAL: 2,
    EventStatus.OFFICIAL_DECISION: 3,
    EventStatus.IMPLEMENTED: 4,
    EventStatus.COMPANY_IMPACT_CONFIRMED: 5,
}


class ValueBasis(StrEnum):
    """The disclosure class the public product must keep visually separate."""

    REPORTED = "REPORTED"
    RESTATED = "RESTATED"
    NORMALIZED = "NORMALIZED"
    DERIVED = "DERIVED"
    FORECAST = "FORECAST"
    MARKET_IMPLIED = "MARKET_IMPLIED"


class QualityStatus(StrEnum):
    VALID = "VALID"
    SUSPECT = "SUSPECT"
    INVALID = "INVALID"
    UNVALIDATED = "UNVALIDATED"


class MissingReason(StrEnum):
    """Why a value is null.

    Every null carries one of these. The pipeline's central rule is that a
    failed extraction becomes ``value=None`` with ``EXTRACTION_FAILED`` and
    never ``value=0``.
    """

    NOT_REPORTED = "NOT_REPORTED"
    NOT_APPLICABLE_TO_MODEL = "NOT_APPLICABLE_TO_MODEL"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    RIGHTS_WITHHELD = "RIGHTS_WITHHELD"
    INSUFFICIENT_PERIODS = "INSUFFICIENT_PERIODS"
    #: A ratio whose denominator was zero, missing or wrongly signed. Stage 2
    #: added this so a division can fail visibly rather than returning inf/nan
    #: or being swallowed into a zero.
    UNDEFINED_DENOMINATOR = "UNDEFINED_DENOMINATOR"
    PENDING_REVIEW = "PENDING_REVIEW"
    SUPERSEDED = "SUPERSEDED"
    TRADING_HALTED = "TRADING_HALTED"


class PeriodType(StrEnum):
    FY = "FY"
    Q1 = "Q1"
    Q2 = "Q2"
    Q3 = "Q3"
    Q4 = "Q4"
    H1 = "H1"
    H2 = "H2"
    YTD_Q1 = "YTD_Q1"
    YTD_Q2 = "YTD_Q2"
    YTD_Q3 = "YTD_Q3"
    TTM = "TTM"
    POINT_IN_TIME = "POINT_IN_TIME"


DURATION_PERIODS = frozenset(
    {
        PeriodType.FY,
        PeriodType.Q1,
        PeriodType.Q2,
        PeriodType.Q3,
        PeriodType.Q4,
        PeriodType.H1,
        PeriodType.H2,
        PeriodType.YTD_Q1,
        PeriodType.YTD_Q2,
        PeriodType.YTD_Q3,
        PeriodType.TTM,
    }
)


class Scale(StrEnum):
    UNITS = "UNITS"
    THOUSANDS = "THOUSANDS"
    MILLIONS = "MILLIONS"
    BILLIONS = "BILLIONS"
    TRILLIONS = "TRILLIONS"


SCALE_FACTORS = {
    Scale.UNITS: 1,
    Scale.THOUSANDS: 1_000,
    Scale.MILLIONS: 1_000_000,
    Scale.BILLIONS: 1_000_000_000,
    Scale.TRILLIONS: 1_000_000_000_000,
}


class WriteMode(StrEnum):
    """`validate_only` collects and validates but promotes nothing."""

    VALIDATE_ONLY = "validate_only"
    COMMIT = "commit"


class Severity(StrEnum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class Outcome(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"


class CorporateActionFlag(StrEnum):
    NONE = "NONE"
    DIVIDEND = "DIVIDEND"
    SPLIT = "SPLIT"
    REVERSE_SPLIT = "REVERSE_SPLIT"
    RIGHTS_ISSUE = "RIGHTS_ISSUE"
    BONUS_ISSUE = "BONUS_ISSUE"
    SUSPENSION = "SUSPENSION"
    MULTIPLE = "MULTIPLE"
