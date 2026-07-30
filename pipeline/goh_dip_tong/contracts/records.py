"""Canonical record types.

Everything a provider returns is one of these. They are plain dataclasses with
an explicit ``to_json`` so serialisation stays deterministic and reviewable
rather than depending on field-declaration order at some later date.

The central type is :class:`Measure`. It makes "missing" a first-class value
that cannot be confused with zero: you cannot construct a missing Measure
without stating why, and you cannot construct a present Measure that also
claims to be missing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from .enums import (
    CorporateActionFlag,
    CoverageStatus,
    EventStatus,
    MissingReason,
    PeriodType,
    QualityStatus,
    RightsStatus,
    Scale,
    ValueBasis,
)

TICKER_RE = re.compile(r"^[A-Z]{4}$")


class ContractError(ValueError):
    """Raised when a record violates its own contract at construction time."""


# ---------------------------------------------------------------------------
# Measure: the missing-versus-zero control
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Measure:
    """A number that might not exist, and knows why if it doesn't.

    Construct via :meth:`of` or :meth:`missing` rather than directly, so the
    invariants below are always enforced:

    * ``value is None``  =>  ``missing_reason`` must be set
    * ``value is not None`` => ``missing_reason`` must be None

    A parser that cannot read a figure returns ``Measure.missing(
    MissingReason.EXTRACTION_FAILED)``. There is deliberately no code path that
    turns a parse failure into ``0.0``.
    """

    value: Optional[float]
    unit: str
    currency: Optional[str] = None
    scale: Scale = Scale.UNITS
    missing_reason: Optional[MissingReason] = None
    basis: ValueBasis = ValueBasis.REPORTED
    quality_status: QualityStatus = QualityStatus.UNVALIDATED

    def __post_init__(self) -> None:
        if self.value is None and self.missing_reason is None:
            raise ContractError(
                "a missing Measure must carry a MissingReason; "
                "silently dropping the reason is how missing becomes zero"
            )
        if self.value is not None and self.missing_reason is not None:
            raise ContractError(
                f"Measure has a value ({self.value!r}) and also claims to be "
                f"missing ({self.missing_reason})"
            )

    @classmethod
    def of(
        cls,
        value: float,
        unit: str,
        currency: Optional[str] = None,
        scale: Scale = Scale.UNITS,
        basis: ValueBasis = ValueBasis.REPORTED,
    ) -> "Measure":
        if value is None:
            raise ContractError("Measure.of() requires a value; use Measure.missing()")
        return cls(
            value=float(value),
            unit=unit,
            currency=currency,
            scale=scale,
            basis=basis,
        )

    @classmethod
    def missing(
        cls,
        reason: MissingReason,
        unit: str = "IDR",
        currency: Optional[str] = None,
        basis: ValueBasis = ValueBasis.REPORTED,
    ) -> "Measure":
        return cls(
            value=None,
            unit=unit,
            currency=currency,
            missing_reason=reason,
            basis=basis,
            quality_status=QualityStatus.VALID,
        )

    @property
    def is_missing(self) -> bool:
        return self.value is None


# ---------------------------------------------------------------------------
# Provider plumbing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiscoveredItem:
    """Something a provider found and could fetch. Discovery is separate from
    fetching so a DISCOVERY_ONLY source can list without downloading."""

    item_id: str
    provider_id: str
    data_type: str
    ticker: Optional[str] = None
    url: Optional[str] = None
    period_ref: Optional[str] = None
    published_at: Optional[str] = None
    hint: dict = field(default_factory=dict)


@dataclass(frozen=True)
class RawPayload:
    """Bytes (or decoded text) as returned by a source, plus enough metadata to
    decide whether they are data at all."""

    item: DiscoveredItem
    content: Any
    media_type: str
    retrieved_at: str
    byte_size: int = 0
    http_status: Optional[int] = None
    from_fixture: bool = False


@dataclass(frozen=True)
class ValidationIssue:
    check_id: str
    severity: str
    outcome: str
    message: str
    subject: Optional[str] = None
    observed: Any = None
    expected: Any = None

    def to_json(self) -> dict:
        return {
            "id": self.check_id,
            "severity": str(self.severity),
            "outcome": str(self.outcome),
            "message": self.message,
            "subject": self.subject,
            "observed": self.observed,
            "expected": self.expected,
        }


@dataclass
class ValidationReport:
    """Accumulates check outcomes. ``ok`` is false as soon as one CRITICAL check
    fails, which is what makes publication fail closed."""

    issues: list = field(default_factory=list)

    def add(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)

    def extend(self, other: "ValidationReport") -> None:
        self.issues.extend(other.issues)

    @property
    def critical_failures(self) -> list:
        return [
            i for i in self.issues if i.severity == "CRITICAL" and i.outcome == "FAIL"
        ]

    @property
    def warnings(self) -> list:
        return [
            i for i in self.issues if i.severity == "WARNING" and i.outcome == "FAIL"
        ]

    @property
    def ok(self) -> bool:
        return not self.critical_failures

    @property
    def status(self) -> str:
        if self.critical_failures:
            return "FAIL"
        if self.warnings:
            return "PASS_WITH_WARNINGS"
        return "PASS"

    def to_json(self) -> list:
        return [i.to_json() for i in self.issues]


# ---------------------------------------------------------------------------
# Canonical domain records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceRef:
    provider_id: str
    retrieved_at: str
    rights_status: RightsStatus
    document_ref: Optional[str] = None
    document_url: Optional[str] = None
    published_at: Optional[str] = None

    def to_json(self, include_document: bool = True) -> dict:
        out = {
            "providerId": self.provider_id,
            "retrievedAt": self.retrieved_at,
            "rightsStatus": str(self.rights_status),
        }
        if include_document:
            out["documentRef"] = self.document_ref
            out["documentUrl"] = self.document_url
            out["publishedAt"] = self.published_at
        return out


@dataclass(frozen=True)
class Constituent:
    """One row of the IDX30 universe."""

    ticker: str
    name: str
    sector_code: str
    sector_name: str
    industry_code: str
    industry_name: str
    model_family: Optional[str]
    coverage_status: CoverageStatus
    active: bool = True
    entered_at: Optional[str] = None
    source_ref: str = "unknown"

    def __post_init__(self) -> None:
        if not TICKER_RE.match(self.ticker):
            raise ContractError(f"invalid IDX ticker: {self.ticker!r}")
        # The onboarding rule, enforced at the type level rather than only in
        # the schema: an unmapped classification can never carry a real model.
        if self.model_family is None and self.coverage_status != CoverageStatus.ONBOARDING:
            raise ContractError(
                f"{self.ticker}: modelFamily is null so coverageStatus must be "
                f"ONBOARDING, got {self.coverage_status}"
            )

    def to_json(self) -> dict:
        return {
            "ticker": self.ticker,
            "name": self.name,
            "sectorCode": self.sector_code,
            "sectorName": self.sector_name,
            "industryCode": self.industry_code,
            "industryName": self.industry_name,
            "modelFamily": self.model_family,
            "coverageStatus": str(self.coverage_status),
            "active": self.active,
            "enteredAt": self.entered_at,
            "sourceRef": self.source_ref,
        }

    @property
    def identity_fingerprint(self) -> tuple:
        """Fields whose change is a RENAMED or RECLASSIFIED event."""
        return (self.name, self.sector_code, self.industry_code)


@dataclass(frozen=True)
class MarketPriceRecord:
    ticker: str
    trading_date: str
    open: Measure
    high: Measure
    low: Measure
    close: Measure
    volume: Optional[int]
    currency: str
    source: SourceRef
    corporate_action_flag: CorporateActionFlag = CorporateActionFlag.NONE
    adjusted_close: Optional[float] = None
    adjustment_methodology: Optional[str] = None
    quality_status: QualityStatus = QualityStatus.UNVALIDATED
    quality_flags: tuple = ()

    @property
    def primary_key(self) -> tuple:
        return (self.ticker, self.trading_date)

    def to_json(self) -> dict:
        missing = next(
            (
                str(m.missing_reason)
                for m in (self.close, self.open, self.high, self.low)
                if m.is_missing
            ),
            None,
        )
        return {
            "ticker": self.ticker,
            "tradingDate": self.trading_date,
            "open": self.open.value,
            "high": self.high.value,
            "low": self.low.value,
            "close": self.close.value,
            "adjustedClose": self.adjusted_close,
            "adjustmentMethodology": self.adjustment_methodology,
            "volume": self.volume,
            "currency": self.currency,
            "missingReason": missing,
            "corporateActionFlag": str(self.corporate_action_flag),
            "qualityStatus": str(self.quality_status),
            "qualityFlags": list(self.quality_flags),
            "source": self.source.to_json(include_document=False),
        }


@dataclass(frozen=True)
class FinancialFact:
    ticker: str
    metric: str
    period_type: PeriodType
    period_start: Optional[str]
    period_end: str
    fiscal_year: int
    measure: Measure
    source: SourceRef
    revision: int = 1
    supersedes: Optional[int] = None
    restatement_of: Optional[str] = None
    concept_id: Optional[str] = None
    taxonomy: Optional[str] = None
    parser_version: str = "1.0.0"
    statement: Optional[str] = None
    segment: Optional[str] = None
    quality_flags: tuple = ()

    @property
    def fact_key(self) -> str:
        """Identity of the underlying economic fact, excluding revision.

        Deliberately does NOT include ``basis``. A restatement is the same fact
        observed again: revision 1 carries basis REPORTED, revision 2 carries
        RESTATED, and they share a factKey so the supersession chain links up.
        Putting basis in the key would split every restatement into two
        unrelated lineages and silently break correction tracking.

        It DOES include ``segment``, because segment revenue and consolidated
        revenue for the same period are different facts, not revisions of one.
        """
        return "|".join(
            [
                self.ticker,
                self.metric,
                str(self.period_type),
                self.period_end,
                self.segment or "CONSOLIDATED",
            ]
        )

    @property
    def primary_key(self) -> tuple:
        return (self.fact_key, self.revision)

    def to_json(self) -> dict:
        return {
            "factKey": self.fact_key,
            "ticker": self.ticker,
            "metric": self.metric,
            "periodType": str(self.period_type),
            "periodStart": self.period_start,
            "periodEnd": self.period_end,
            "fiscalYear": self.fiscal_year,
            "basis": str(self.measure.basis),
            "value": self.measure.value,
            "missingReason": (
                str(self.measure.missing_reason) if self.measure.missing_reason else None
            ),
            "unit": self.measure.unit,
            "currency": self.measure.currency,
            "scale": str(self.measure.scale),
            "revision": self.revision,
            "supersedes": self.supersedes,
            "restatementOf": self.restatement_of,
            "qualityStatus": str(self.measure.quality_status),
            "qualityFlags": list(self.quality_flags),
            "conceptId": self.concept_id,
            "taxonomy": self.taxonomy,
            "parserVersion": self.parser_version,
            "statement": self.statement,
            "segment": self.segment,
            "source": self.source.to_json(),
        }


@dataclass(frozen=True)
class DisclosureRecord:
    disclosure_id: str
    ticker: str
    disclosure_type: str
    title: str
    published_at: str
    official_url: str
    source: SourceRef
    summary: Optional[str] = None
    language: Optional[str] = None
    period_ref: Optional[str] = None
    content_hash: Optional[str] = None
    flagged_for_financial_update: bool = False
    processed_by_financial_update: bool = False
    manifest: Optional[dict] = None
    event_status: Optional[EventStatus] = None

    @property
    def primary_key(self) -> tuple:
        return (self.disclosure_id,)

    def to_json(self) -> dict:
        return {
            "disclosureId": self.disclosure_id,
            "ticker": self.ticker,
            "disclosureType": self.disclosure_type,
            "title": self.title,
            "summary": self.summary,
            "language": self.language,
            "publishedAt": self.published_at,
            "periodRef": self.period_ref,
            "officialUrl": self.official_url,
            "contentHash": self.content_hash,
            "flaggedForFinancialUpdate": self.flagged_for_financial_update,
            "processedByFinancialUpdate": self.processed_by_financial_update,
            "manifest": self.manifest,
            "eventStatus": str(self.event_status) if self.event_status else None,
            "source": self.source.to_json(include_document=False),
        }


@dataclass(frozen=True)
class MacroObservation:
    """A macro series point.

    Three timestamps are kept strictly apart: the period the number describes,
    when the agency published it, and when we fetched it. Collapsing these is a
    classic way to accidentally backtest with data that did not exist yet.
    """

    series_id: str
    observation_period: str
    measure: Measure
    retrieved_at: str
    provider_id: str
    rights_status: RightsStatus
    published_at: Optional[str] = None
    release_vintage: Optional[str] = None

    @property
    def primary_key(self) -> tuple:
        return (self.series_id, self.observation_period, self.release_vintage or "")

    def to_json(self) -> dict:
        return {
            "seriesId": self.series_id,
            "observationPeriod": self.observation_period,
            "value": self.measure.value,
            "missingReason": (
                str(self.measure.missing_reason) if self.measure.missing_reason else None
            ),
            "unit": self.measure.unit,
            "releaseVintage": self.release_vintage,
            "publishedAt": self.published_at,
            "retrievedAt": self.retrieved_at,
            "providerId": self.provider_id,
            "rightsStatus": str(self.rights_status),
        }


@dataclass(frozen=True)
class MembershipChange:
    """One append-only row of idx30.history.jsonl."""

    change_type: str
    ticker: str
    observed_at: str
    effective_from: Optional[str] = None
    before: Optional[dict] = None
    after: Optional[dict] = None
    detail: Optional[str] = None
    source_ref: Optional[str] = None

    @property
    def primary_key(self) -> tuple:
        return (self.observed_at, self.ticker, self.change_type, self.detail or "")

    def to_json(self) -> dict:
        return {
            "changeType": str(self.change_type),
            "ticker": self.ticker,
            "observedAt": self.observed_at,
            "effectiveFrom": self.effective_from,
            "before": self.before,
            "after": self.after,
            "detail": self.detail,
            "sourceRef": self.source_ref,
        }
