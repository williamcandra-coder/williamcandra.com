"""Market-price providers.

Rights, not code, are the constraint here. The fixture provider is enabled but
carries PRIVATE_RESEARCH_ONLY, so the rights gate routes its output to the
git-ignored private tree. That keeps the daily-update path genuinely exercised
end to end while making it impossible to commit a price series before market
data rights are documented.
"""

from __future__ import annotations

from typing import Optional

from ..contracts.enums import (
    CorporateActionFlag,
    MissingReason,
    Outcome,
    QualityStatus,
    Severity,
)
from ..contracts.provider import ProviderContext
from ..contracts.records import (
    DiscoveredItem,
    MarketPriceRecord,
    RawPayload,
    SourceRef,
    ValidationIssue,
    ValidationReport,
)
from ..normalization.values import coerce
from ..parsers.guards import parse_numeric
from .base import FixtureProvider, HttpProvider

PRICE_COLUMNS = ("open", "high", "low", "close")


class MarketPriceFixtureProvider(FixtureProvider):
    provider_id = "fixture_market_prices"
    data_types = ("market_prices_daily", "corporate_actions")

    def discover(self, context: ProviderContext) -> list:
        self.ensure_runnable()
        return [
            DiscoveredItem(
                item_id=f"prices:{self.fixture_path.name}",
                provider_id=self.provider_id,
                data_type="market_prices_daily",
                hint={"fixture_path": str(self.fixture_path), "media_type": "text/csv"},
            )
        ]

    def parse(self, payload: RawPayload) -> list:
        import csv
        import io

        reader = csv.DictReader(io.StringIO(payload.content))
        source = SourceRef(
            provider_id=self.provider_id,
            retrieved_at=payload.retrieved_at,
            rights_status=self.rights_status,
        )

        records = []
        for row in reader:
            ticker = (row.get("ticker") or "").strip().upper()
            if not ticker:
                continue

            # A blank price cell is a null token: it becomes a missing Measure
            # with a reason, never 0. A suspended day has no price but a real
            # volume of 0, and the two must not look alike.
            flag = CorporateActionFlag(row.get("corporateActionFlag") or "NONE")
            reason = (
                MissingReason.TRADING_HALTED
                if flag == CorporateActionFlag.SUSPENSION
                else MissingReason.NOT_REPORTED
            )
            measures = {}
            for column in PRICE_COLUMNS:
                measure = coerce(row.get(column), unit="IDR", currency="IDR")
                if measure.is_missing and reason == MissingReason.TRADING_HALTED:
                    from ..contracts.records import Measure

                    measure = Measure.missing(reason, unit="IDR", currency="IDR")
                measures[column] = measure

            volume_raw = row.get("volume")
            volume = parse_numeric(volume_raw)

            records.append(
                MarketPriceRecord(
                    ticker=ticker,
                    trading_date=(row.get("tradingDate") or "").strip(),
                    open=measures["open"],
                    high=measures["high"],
                    low=measures["low"],
                    close=measures["close"],
                    volume=int(volume) if volume is not None else None,
                    currency=(row.get("currency") or "IDR").strip().upper(),
                    source=source,
                    corporate_action_flag=flag,
                    # Never fabricated: an adjusted close requires a documented
                    # methodology, which no Stage 1 source has.
                    adjusted_close=None,
                    adjustment_methodology=None,
                    quality_status=QualityStatus.UNVALIDATED,
                )
            )
        return records

    def validate(self, records: list) -> ValidationReport:
        report = ValidationReport()

        keys = [r.primary_key for r in records]
        duplicates = sorted({k for k in keys if keys.count(k) > 1})
        report.add(
            ValidationIssue(
                check_id="prices.no_duplicates",
                severity=Severity.CRITICAL,
                outcome=Outcome.FAIL if duplicates else Outcome.PASS,
                message=f"duplicate (ticker, date) rows: {duplicates[:5]}" if duplicates
                else f"{len(records)} rows with unique (ticker, date)",
            )
        )

        # A high below a low, or a close outside the day's range, is a parse bug.
        inconsistent = []
        for record in records:
            values = {c: getattr(record, c).value for c in PRICE_COLUMNS}
            if any(v is None for v in values.values()):
                continue
            if values["high"] < values["low"]:
                inconsistent.append(f"{record.ticker}@{record.trading_date}: high < low")
            elif not (values["low"] <= values["close"] <= values["high"]):
                inconsistent.append(f"{record.ticker}@{record.trading_date}: close outside range")
        for message in inconsistent[:10]:
            report.add(
                ValidationIssue(
                    check_id="prices.ohlc_consistent",
                    severity=Severity.CRITICAL,
                    outcome=Outcome.FAIL,
                    message=message,
                )
            )
        if not inconsistent:
            report.add(
                ValidationIssue(
                    check_id="prices.ohlc_consistent",
                    severity=Severity.INFO,
                    outcome=Outcome.PASS,
                    message="all priced rows are internally consistent",
                )
            )

        # A missing price with no reason would be exactly the bug the whole
        # Measure type exists to prevent, so assert it rather than assume it.
        unexplained = [
            f"{r.ticker}@{r.trading_date}"
            for r in records
            if r.close.is_missing and r.close.missing_reason is None
        ]
        report.add(
            ValidationIssue(
                check_id="prices.missing_has_reason",
                severity=Severity.CRITICAL,
                outcome=Outcome.FAIL if unexplained else Outcome.PASS,
                message=f"missing close with no reason: {unexplained[:5]}" if unexplained
                else "every missing price carries a reason",
            )
        )
        return report


class MarketPriceLiveProvider(HttpProvider):
    """Live market-data adapter. Disabled: host unreachable and redistribution
    rights undocumented. Must first run at PRIVATE_RESEARCH_ONLY even once
    reachable."""

    provider_id = "idx_market_prices"
    data_types = ("market_prices_daily", "corporate_actions")

    def discover(self, context: ProviderContext) -> list:
        self.ensure_runnable()
        return [
            DiscoveredItem(
                item_id=f"prices:{ticker}",
                provider_id=self.provider_id,
                data_type="market_prices_daily",
                ticker=ticker,
                url=self.config.get("official_url"),
            )
            for ticker in (context.tickers or [])
        ]
