"""Macro-series providers (OJK, Bank Indonesia, BPS).

Only series the model registry actually needs are collected. Each observation
keeps three dates apart — the period it describes, when the agency published it,
and when we retrieved it — plus a release vintage, so a later revision of the
same period is a new row rather than an overwrite. Without the vintage you can
silently backtest on numbers that did not exist at the time.
"""

from __future__ import annotations

import json
from typing import Optional

from ..contracts.enums import MissingReason, Outcome, Severity
from ..contracts.provider import ProviderContext
from ..contracts.records import (
    DiscoveredItem,
    MacroObservation,
    Measure,
    RawPayload,
    ValidationIssue,
    ValidationReport,
)
from ..parsers.guards import assert_is_data
from .base import FixtureProvider, HttpProvider

#: Series the Stage 2 model registry is expected to consume. A series not in
#: this set is not collected, however easy it would be to grab.
REGISTERED_SERIES = {
    "BI_7DRR": {"provider": "bank-indonesia", "unit": "PERCENT",
                "label": "BI 7-day reverse repo rate"},
    "BPS_CPI_YOY": {"provider": "bps", "unit": "PERCENT",
                    "label": "CPI inflation, year on year"},
    "OJK_BANK_NPL_GROSS": {"provider": "ojk", "unit": "PERCENT",
                           "label": "Banking system gross NPL ratio"},
}


class MacroFixtureProvider(FixtureProvider):
    provider_id = "fixture_macro"
    data_types = ("macro_series",)

    def discover(self, context: ProviderContext) -> list:
        self.ensure_runnable()
        return [
            DiscoveredItem(
                item_id=f"macro:{self.fixture_path.name}",
                provider_id=self.provider_id,
                data_type="macro_series",
                hint={"fixture_path": str(self.fixture_path), "expect": "json"},
            )
        ]

    def parse(self, payload: RawPayload) -> list:
        assert_is_data(payload.content, expect="json", source=payload.item.item_id)
        document = json.loads(payload.content)

        observations = []
        for row in document.get("observations", []):
            series_id = row["seriesId"]
            if series_id not in REGISTERED_SERIES:
                continue  # not in the model registry: not our business

            unit = row.get("unit") or REGISTERED_SERIES[series_id]["unit"]
            value = row.get("value")
            if value is None:
                measure = Measure.missing(
                    MissingReason(row.get("missingReason", "NOT_REPORTED")), unit=unit
                )
            else:
                measure = Measure.of(float(value), unit=unit)

            observations.append(
                MacroObservation(
                    series_id=series_id,
                    observation_period=row["observationPeriod"],
                    measure=measure,
                    retrieved_at=payload.retrieved_at,
                    provider_id=self.provider_id,
                    rights_status=self.rights_status,
                    published_at=row.get("publishedAt"),
                    release_vintage=row.get("releaseVintage"),
                )
            )
        return observations

    def validate(self, records: list) -> ValidationReport:
        report = ValidationReport()

        keys = [r.primary_key for r in records]
        duplicates = sorted({k for k in keys if keys.count(k) > 1})
        report.add(
            ValidationIssue(
                check_id="macro.no_duplicates",
                severity=Severity.CRITICAL,
                outcome=Outcome.FAIL if duplicates else Outcome.PASS,
                message=f"duplicate (series, period, vintage): {duplicates[:3]}"
                if duplicates else f"{len(records)} observations with unique keys",
            )
        )

        unregistered = sorted({r.series_id for r in records if r.series_id not in REGISTERED_SERIES})
        report.add(
            ValidationIssue(
                check_id="macro.registered_only",
                severity=Severity.CRITICAL,
                outcome=Outcome.FAIL if unregistered else Outcome.PASS,
                message=f"unregistered series collected: {unregistered}" if unregistered
                else "only registered model series were collected",
            )
        )

        # A published observation without a publication date cannot be used
        # point-in-time, so flag it rather than let it look usable.
        undated = [
            f"{r.series_id}@{r.observation_period}"
            for r in records
            if not r.measure.is_missing and not r.published_at
        ]
        report.add(
            ValidationIssue(
                check_id="macro.publication_date",
                severity=Severity.WARNING,
                outcome=Outcome.FAIL if undated else Outcome.PASS,
                message=f"observations with a value but no publication date: {undated[:5]}"
                if undated else "every published observation carries a publication date",
            )
        )
        return report


class MacroLiveProvider(HttpProvider):
    """Live BI / BPS / OJK adapter. Disabled: hosts unreachable, rights unreviewed."""

    provider_id = "bank_indonesia"
    data_types = ("macro_series",)

    def discover(self, context: ProviderContext) -> list:
        self.ensure_runnable()
        return []
