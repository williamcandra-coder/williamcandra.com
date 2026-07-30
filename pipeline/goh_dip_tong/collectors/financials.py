"""Financial-fact providers.

The fixture is shaped like an XBRL fact table — concept id, context period,
unit, scale, sign — so swapping in a real XBRL adapter later means writing a
different `parse`, not redesigning the contract.

Restatement handling is the interesting part. A restated figure does not
overwrite the original: it lands as a new revision sharing the same `factKey`,
and the prior revision stays in the store marked SUPERSEDED. That is what makes
"what did we believe in July" answerable later.
"""

from __future__ import annotations

import json
from typing import Optional

from ..contracts.enums import (
    MissingReason,
    Outcome,
    PeriodType,
    QualityStatus,
    Severity,
    ValueBasis,
)
from ..contracts.provider import ProviderContext
from ..contracts.records import (
    DiscoveredItem,
    FinancialFact,
    Measure,
    RawPayload,
    SourceRef,
    ValidationIssue,
    ValidationReport,
)
from ..normalization.periods import normalize_period
from ..normalization.units import parse_currency, parse_scale, to_base_units
from ..normalization.values import coerce, is_null_token
from ..parsers.guards import assert_is_data
from .base import FixtureProvider, HttpProvider


class FinancialFixtureProvider(FixtureProvider):
    provider_id = "fixture_financials"
    data_types = ("financial_facts", "financial_statements", "restatements")

    def discover(self, context: ProviderContext) -> list:
        self.ensure_runnable()
        return [
            DiscoveredItem(
                item_id=f"facts:{self.fixture_path.name}",
                provider_id=self.provider_id,
                data_type="financial_facts",
                hint={"fixture_path": str(self.fixture_path), "expect": "json"},
            )
        ]

    def parse(self, payload: RawPayload) -> list:
        assert_is_data(payload.content, expect="json", source=payload.item.item_id)
        document = json.loads(payload.content)
        taxonomy = document.get("taxonomy")
        parser_version = document.get("parserVersion", "1.0.0")

        facts = []
        for row in document.get("facts", []):
            period = normalize_period(row["periodRef"])
            currency = parse_currency(row.get("currency"))
            unit = row.get("unit") or currency or "IDR"
            scale = parse_scale(row.get("scale"))
            revision = int(row.get("revision", 1))
            basis = ValueBasis.RESTATED if revision > 1 else ValueBasis.REPORTED

            raw = row.get("rawValue")
            measure = coerce(raw, unit=unit, currency=currency, basis=basis)
            if not measure.is_missing:
                # Normalize the reported scale out to base units while keeping
                # a record of what the filing actually said.
                measure = Measure(
                    value=to_base_units(measure.value, scale),
                    unit=unit,
                    currency=currency,
                    scale=scale,
                    basis=basis,
                    quality_status=QualityStatus.UNVALIDATED,
                )

            facts.append(
                FinancialFact(
                    ticker=row["ticker"],
                    metric=row["metric"],
                    period_type=PeriodType(period["periodType"]),
                    period_start=period["periodStart"],
                    period_end=period["periodEnd"],
                    fiscal_year=period["fiscalYear"],
                    measure=measure,
                    source=SourceRef(
                        provider_id=self.provider_id,
                        retrieved_at=payload.retrieved_at,
                        rights_status=self.rights_status,
                        document_ref=row.get("documentRef"),
                        document_url=None,
                        published_at=row.get("publishedAt"),
                    ),
                    revision=revision,
                    supersedes=revision - 1 if revision > 1 else None,
                    restatement_of=row.get("restatementOf"),
                    concept_id=row.get("conceptId"),
                    taxonomy=taxonomy,
                    parser_version=parser_version,
                    statement=row.get("statement"),
                    segment=row.get("segment"),
                )
            )
        return facts

    def validate(self, records: list) -> ValidationReport:
        report = ValidationReport()

        keys = [r.primary_key for r in records]
        duplicates = sorted({k for k in keys if keys.count(k) > 1})
        report.add(
            ValidationIssue(
                check_id="facts.no_duplicates",
                severity=Severity.CRITICAL,
                outcome=Outcome.FAIL if duplicates else Outcome.PASS,
                message=f"duplicate (factKey, revision): {duplicates[:3]}" if duplicates
                else f"{len(records)} facts with unique (factKey, revision)",
            )
        )

        # The control this whole design exists for.
        zero_from_nothing = [
            r.fact_key for r in records if r.measure.value == 0 and not r.measure.is_missing
        ]
        report.add(
            ValidationIssue(
                check_id="facts.zero_is_real",
                severity=Severity.WARNING,
                outcome=Outcome.FAIL if zero_from_nothing else Outcome.PASS,
                message=f"facts with a value of exactly 0 — confirm each is a reported "
                        f"zero, not a failed extraction: {zero_from_nothing[:5]}"
                if zero_from_nothing else "no zero-valued facts to disambiguate",
            )
        )

        unexplained = [
            r.fact_key for r in records
            if r.measure.is_missing and r.measure.missing_reason is None
        ]
        report.add(
            ValidationIssue(
                check_id="facts.missing_has_reason",
                severity=Severity.CRITICAL,
                outcome=Outcome.FAIL if unexplained else Outcome.PASS,
                message=f"missing facts with no reason: {unexplained[:5]}" if unexplained
                else "every missing fact carries a reason",
            )
        )

        # Accounting identity, checked only where both sides are actually present.
        report.extend(self._check_balance_sheet(records))
        return report

    def _check_balance_sheet(self, records: list) -> ValidationReport:
        """assets = liabilities + equity, within a rounding tolerance."""
        report = ValidationReport()
        by_period: dict = {}
        for record in records:
            if record.metric in ("total_assets", "total_liabilities", "total_equity"):
                key = (record.ticker, record.period_end, record.revision)
                by_period.setdefault(key, {})[record.metric] = record.measure.value

        problems = []
        checked = 0
        for (ticker, period_end, _), values in sorted(by_period.items()):
            assets = values.get("total_assets")
            liabilities = values.get("total_liabilities")
            equity = values.get("total_equity")
            if None in (assets, liabilities, equity):
                continue  # incomplete is not wrong
            checked += 1
            gap = abs(assets - (liabilities + equity))
            if gap > max(abs(assets) * 0.005, 1.0):
                problems.append(
                    f"{ticker}@{period_end}: assets {assets:,.0f} != liabilities+equity "
                    f"{liabilities + equity:,.0f} (gap {gap:,.0f})"
                )

        for message in problems:
            report.add(
                ValidationIssue(
                    check_id="facts.balance_sheet_identity",
                    severity=Severity.CRITICAL,
                    outcome=Outcome.FAIL,
                    message=message,
                )
            )
        if not problems:
            report.add(
                ValidationIssue(
                    check_id="facts.balance_sheet_identity",
                    severity=Severity.INFO,
                    outcome=Outcome.PASS,
                    message=f"balance-sheet identity holds for {checked} complete periods",
                )
            )
        return report


def apply_restatements(facts: list) -> list:
    """Mark superseded revisions and promote the latest one.

    Input is every revision ever seen; output is the same set with prior
    revisions flagged SUPERSEDED. Nothing is dropped — the earlier number
    remains available, which is the whole point of correction-awareness.
    """
    latest: dict = {}
    for fact in facts:
        key = fact.fact_key
        if key not in latest or fact.revision > latest[key].revision:
            latest[key] = fact

    out = []
    for fact in facts:
        winner = latest[fact.fact_key]
        if fact.revision < winner.revision and not fact.measure.is_missing:
            out.append(
                FinancialFact(
                    ticker=fact.ticker,
                    metric=fact.metric,
                    period_type=fact.period_type,
                    period_start=fact.period_start,
                    period_end=fact.period_end,
                    fiscal_year=fact.fiscal_year,
                    measure=Measure(
                        value=fact.measure.value,
                        unit=fact.measure.unit,
                        currency=fact.measure.currency,
                        scale=fact.measure.scale,
                        basis=fact.measure.basis,
                        quality_status=fact.measure.quality_status,
                    ),
                    source=fact.source,
                    revision=fact.revision,
                    supersedes=fact.supersedes,
                    restatement_of=fact.restatement_of,
                    concept_id=fact.concept_id,
                    taxonomy=fact.taxonomy,
                    parser_version=fact.parser_version,
                    statement=fact.statement,
                    segment=fact.segment,
                    quality_flags=tuple(fact.quality_flags) + ("SUPERSEDED",),
                )
            )
        else:
            out.append(fact)
    return out


def latest_revisions(facts: list) -> list:
    """The current view: one fact per factKey, highest revision wins."""
    best: dict = {}
    for fact in facts:
        key = fact.fact_key
        if key not in best or fact.revision > best[key].revision:
            best[key] = fact
    return [best[k] for k in sorted(best)]


class FinancialLiveProvider(HttpProvider):
    """Live XBRL/filing adapter. Disabled: host unreachable, rights unreviewed."""

    provider_id = "idx_financials"
    data_types = ("financial_facts", "financial_statements")

    def discover(self, context: ProviderContext) -> list:
        self.ensure_runnable()
        return []
