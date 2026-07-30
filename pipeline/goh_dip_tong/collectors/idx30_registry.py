"""IDX30 universe providers."""

from __future__ import annotations

import json
from typing import Optional

from ..contracts.enums import CoverageStatus, Outcome, Severity
from ..contracts.provider import ProviderContext
from ..contracts.records import (
    Constituent,
    DiscoveredItem,
    RawPayload,
    ValidationIssue,
    ValidationReport,
)
from ..parsers.guards import assert_is_data
from .base import FixtureProvider, HttpProvider


class Idx30FixtureProvider(FixtureProvider):
    """Reads a committed IDX30 universe fixture.

    The output is deliberately marked non-authoritative all the way through, so
    nothing downstream can present it as live index membership.
    """

    provider_id = "fixture_idx30_registry"
    data_types = ("index_membership", "company_identity", "sector_classification")

    def discover(self, context: ProviderContext) -> list:
        self.ensure_runnable()
        path = self.fixture_path
        if context and getattr(context, "settings", None) is None:
            pass
        return [
            DiscoveredItem(
                item_id=f"idx30:{path.name}",
                provider_id=self.provider_id,
                data_type="index_membership",
                url=None,
                hint={"fixture_path": str(path), "expect": "json",
                      "media_type": "application/json"},
            )
        ]

    def parse(self, payload: RawPayload) -> list:
        assert_is_data(payload.content, expect="json", source=payload.item.item_id)
        document = json.loads(payload.content)
        self._last_document = document

        constituents = []
        for row in document.get("constituents", []):
            constituents.append(
                Constituent(
                    ticker=row["ticker"],
                    name=row["name"],
                    sector_code=row["sectorCode"],
                    sector_name=row["sectorName"],
                    industry_code=row["industryCode"],
                    industry_name=row["industryName"],
                    # Model family and coverage are resolved later, from
                    # models.yml. A source never gets to declare which valuation
                    # model applies to a company.
                    model_family=None,
                    coverage_status=CoverageStatus.ONBOARDING,
                    active=True,
                    entered_at=row.get("enteredAt"),
                    source_ref=row.get("sourceRef", f"{self.provider_id}:{row['ticker']}"),
                )
            )
        return constituents

    def validate(self, records: list) -> ValidationReport:
        report = ValidationReport()

        tickers = [c.ticker for c in records]
        duplicates = sorted({t for t in tickers if tickers.count(t) > 1})
        report.add(
            ValidationIssue(
                check_id="registry.ticker_unique",
                severity=Severity.CRITICAL,
                outcome=Outcome.FAIL if duplicates else Outcome.PASS,
                message=f"duplicate tickers: {duplicates}" if duplicates
                else f"{len(tickers)} unique tickers",
            )
        )

        empty = [c.ticker for c in records if not c.name.strip()]
        report.add(
            ValidationIssue(
                check_id="registry.name_present",
                severity=Severity.CRITICAL,
                outcome=Outcome.FAIL if empty else Outcome.PASS,
                message=f"constituents with an empty name: {empty}" if empty
                else "every constituent has a name",
            )
        )

        report.add(
            ValidationIssue(
                check_id="registry.nonempty",
                severity=Severity.CRITICAL,
                outcome=Outcome.FAIL if not records else Outcome.PASS,
                message="source returned no constituents — refusing to replace the "
                        "committed universe with an empty one"
                if not records else f"source returned {len(records)} constituents",
            )
        )
        return report

    # -- source metadata used to stamp the generated config ----------------

    def source_block(self, retrieved_at: str) -> dict:
        document = getattr(self, "_last_document", {}) or {}
        return {
            "name": document.get("sourceName", "Committed development fixture"),
            "url": document.get("sourceUrl"),
            "providerId": self.provider_id,
            "publishedAt": document.get("publishedAt"),
            "retrievedAt": retrieved_at,
            "rightsStatus": str(self.rights_status),
        }

    def effective_from(self) -> Optional[str]:
        return (getattr(self, "_last_document", {}) or {}).get("effectiveFrom")

    def declared_count(self) -> Optional[int]:
        return (getattr(self, "_last_document", {}) or {}).get("declaredConstituentCount")


class Idx30LiveProvider(HttpProvider):
    """Live IDX index-constituent adapter.

    Disabled. The host is unreachable from this environment (the egress policy
    answers 403 to CONNECT) and IDX's terms have not been reviewed. `parse` is
    intentionally left unimplemented: a parser written against a response nobody
    has seen is untested code that merely looks complete, and the spec is
    explicit that a provider may be configured but disabled.
    """

    provider_id = "idx_index_constituents"
    data_types = ("index_membership", "company_identity", "sector_classification")

    def discover(self, context: ProviderContext) -> list:
        self.ensure_runnable()
        return [
            DiscoveredItem(
                item_id="idx30:constituents",
                provider_id=self.provider_id,
                data_type="index_membership",
                url=self.config.get("official_url"),
                hint={"expect": "json"},
            )
        ]
