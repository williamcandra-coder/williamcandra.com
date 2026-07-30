"""Disclosure-metadata providers.

Metadata only, by design and by rights status. A disclosure document that is
large or restricted becomes a manifest row — official URL, size, media type,
retrieval outcome — and never a committed file.
"""

from __future__ import annotations

import json
from typing import Optional

from ..contracts.enums import EventStatus, Outcome, Severity
from ..contracts.provider import ProviderContext
from ..contracts.records import (
    DisclosureRecord,
    DiscoveredItem,
    RawPayload,
    SourceRef,
    ValidationIssue,
    ValidationReport,
)
from ..parsers.guards import assert_is_data
from .base import FixtureProvider, HttpProvider

#: Disclosure types that should wake the financial-update workflow.
FINANCIAL_TYPES = frozenset(
    {"FINANCIAL_REPORT", "ANNUAL_REPORT", "RESTATEMENT", "CORRECTION"}
)

#: Above this, a document is manifest-only regardless of rights.
MANIFEST_SIZE_THRESHOLD = 1_048_576  # 1 MiB


class DisclosureFixtureProvider(FixtureProvider):
    provider_id = "fixture_disclosures"
    data_types = ("disclosure_metadata", "events")

    def discover(self, context: ProviderContext) -> list:
        self.ensure_runnable()
        return [
            DiscoveredItem(
                item_id=f"disclosures:{self.fixture_path.name}",
                provider_id=self.provider_id,
                data_type="disclosure_metadata",
                hint={"fixture_path": str(self.fixture_path), "expect": "json"},
            )
        ]

    def parse(self, payload: RawPayload) -> list:
        assert_is_data(payload.content, expect="json", source=payload.item.item_id)
        document = json.loads(payload.content)
        source = SourceRef(
            provider_id=self.provider_id,
            retrieved_at=payload.retrieved_at,
            rights_status=self.rights_status,
        )

        records = []
        for row in document.get("disclosures", []):
            manifest = row.get("manifest")
            size = (manifest or {}).get("byteSize") or 0
            if manifest is None and size > MANIFEST_SIZE_THRESHOLD:
                manifest = {
                    "storedInRepo": False,
                    "byteSize": size,
                    "mediaType": None,
                    "retrievalOutcome": "NOT_ATTEMPTED",
                    "objectStoreKey": None,
                }

            status = row.get("eventStatus")
            records.append(
                DisclosureRecord(
                    disclosure_id=row["disclosureId"],
                    ticker=row["ticker"],
                    disclosure_type=row["disclosureType"],
                    title=row["title"],
                    published_at=row["publishedAt"],
                    official_url=row["officialUrl"],
                    source=source,
                    # No summary is synthesised: copying source prose would be
                    # exactly the redistribution the rights status forbids.
                    summary=None,
                    language=row.get("language"),
                    period_ref=row.get("periodRef"),
                    content_hash=row.get("contentHash"),
                    flagged_for_financial_update=row["disclosureType"] in FINANCIAL_TYPES,
                    manifest=manifest,
                    event_status=EventStatus(status) if status else None,
                )
            )
        return records

    def validate(self, records: list) -> ValidationReport:
        report = ValidationReport()

        ids = [r.disclosure_id for r in records]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        report.add(
            ValidationIssue(
                check_id="disclosures.stable_id_unique",
                severity=Severity.CRITICAL,
                outcome=Outcome.FAIL if duplicates else Outcome.PASS,
                message=f"duplicate disclosure ids: {duplicates}" if duplicates
                else f"{len(ids)} unique disclosure ids",
            )
        )

        # A stored document would be a rights breach; the schema forbids it and
        # so does this check.
        stored = [r.disclosure_id for r in records
                  if r.manifest and r.manifest.get("storedInRepo")]
        report.add(
            ValidationIssue(
                check_id="disclosures.no_stored_documents",
                severity=Severity.CRITICAL,
                outcome=Outcome.FAIL if stored else Outcome.PASS,
                message=f"disclosures claiming a stored document: {stored}" if stored
                else "no disclosure stores its source document in the repository",
            )
        )

        missing_url = [r.disclosure_id for r in records if not r.official_url]
        report.add(
            ValidationIssue(
                check_id="disclosures.official_url",
                severity=Severity.CRITICAL,
                outcome=Outcome.FAIL if missing_url else Outcome.PASS,
                message=f"disclosures with no official URL: {missing_url}" if missing_url
                else "every disclosure links to its official source",
            )
        )

        # Rumour and media report are not facts; surface them so nothing
        # downstream treats them as confirmed.
        unconfirmed = [
            r.disclosure_id for r in records
            if r.event_status in (EventStatus.RUMOR, EventStatus.MEDIA_REPORT)
        ]
        report.add(
            ValidationIssue(
                check_id="disclosures.unconfirmed_events",
                severity=Severity.WARNING if unconfirmed else Severity.INFO,
                outcome=Outcome.FAIL if unconfirmed else Outcome.PASS,
                message=f"{len(unconfirmed)} disclosures are below OFFICIAL_DECISION and "
                        f"must not be rendered as fact: {unconfirmed}" if unconfirmed
                else "no unconfirmed events in this batch",
            )
        )
        return report


class DisclosureLiveProvider(HttpProvider):
    """Live disclosure adapter. Disabled: host unreachable, rights unreviewed."""

    provider_id = "idx_disclosures"
    data_types = ("disclosure_metadata", "events")

    def discover(self, context: ProviderContext) -> list:
        self.ensure_runnable()
        return []
