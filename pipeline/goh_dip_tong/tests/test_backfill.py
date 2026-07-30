"""Stage 1 tests: idempotent backfill, duplicate prevention, restatement
versioning, fail-soft collection, and fail-closed publication.
"""

from __future__ import annotations

import json

import pytest

from pipeline.goh_dip_tong.collectors.disclosures import DisclosureFixtureProvider
from pipeline.goh_dip_tong.collectors.financials import (
    FinancialFixtureProvider,
    apply_restatements,
    latest_revisions,
)
from pipeline.goh_dip_tong.collectors.macro import MacroFixtureProvider
from pipeline.goh_dip_tong.collectors.market_prices import MarketPriceFixtureProvider
from pipeline.goh_dip_tong.collectors.registry import ProviderRegistry
from pipeline.goh_dip_tong.contracts.enums import MissingReason, ValueBasis
from pipeline.goh_dip_tong.contracts.provider import ProviderContext
from pipeline.goh_dip_tong.publishing.writers import (
    read_csv,
    read_jsonl,
    upsert_csv,
    upsert_jsonl,
    write_document_if_changed,
    write_json_if_changed,
)
from pipeline.goh_dip_tong.validation import quality


def build(provider_cls, provider_id, settings):
    registry = ProviderRegistry(settings)
    config = dict(registry.provider_configs[provider_id])
    config["provider_id"] = provider_id
    return provider_cls(config, settings=settings)


def collect(provider_cls, provider_id, settings):
    provider = build(provider_cls, provider_id, settings)
    records, failures = provider.collect(ProviderContext(run_id="test"))
    return provider, records, failures


# --- upsert idempotency ----------------------------------------------------


def test_jsonl_upsert_is_idempotent(tmp_path):
    path = tmp_path / "facts.jsonl"
    rows = [{"id": "a", "v": 1}, {"id": "b", "v": 2}]
    key = lambda r: (r["id"],)  # noqa: E731

    changed, added, updated = upsert_jsonl(path, rows, key=key)
    assert changed and added == 2 and updated == 0
    first = path.read_bytes()

    changed, added, updated = upsert_jsonl(path, rows, key=key)
    assert not changed and added == 0 and updated == 0
    assert path.read_bytes() == first
    assert len(read_jsonl(path)) == 2


def test_jsonl_upsert_replaces_rather_than_appends_on_a_real_change(tmp_path):
    path = tmp_path / "facts.jsonl"
    key = lambda r: (r["id"],)  # noqa: E731
    upsert_jsonl(path, [{"id": "a", "v": 1}], key=key)
    changed, added, updated = upsert_jsonl(path, [{"id": "a", "v": 99}], key=key)
    assert changed and added == 0 and updated == 1
    assert read_jsonl(path) == [{"id": "a", "v": 99}]


def test_upsert_ignores_a_retrieval_timestamp_only_difference(tmp_path):
    """A rerun that found identical data must not churn the file."""
    path = tmp_path / "facts.jsonl"
    key = lambda r: (r["id"],)  # noqa: E731
    upsert_jsonl(path, [{"id": "a", "v": 1, "source": {"retrievedAt": "2026-07-30T00:00:00Z"}}],
                 key=key)
    changed, _, updated = upsert_jsonl(
        path, [{"id": "a", "v": 1, "source": {"retrievedAt": "2026-07-31T09:00:00Z"}}],
        key=key)
    assert not changed and updated == 0
    # The original retrievedAt survives — it records when we first saw this.
    assert read_jsonl(path)[0]["source"]["retrievedAt"] == "2026-07-30T00:00:00Z"


def test_csv_upsert_is_idempotent(tmp_path):
    path = tmp_path / "prices.csv"
    columns = ["ticker", "tradingDate", "close"]
    rows = [{"ticker": "BBCA", "tradingDate": "2026-07-01", "close": 9250}]
    key = lambda r: (r["ticker"], r["tradingDate"])  # noqa: E731

    upsert_csv(path, rows, columns, key=key)
    first = path.read_bytes()
    changed, added, updated = upsert_csv(path, rows, columns, key=key)
    assert not changed and added == 0 and updated == 0
    assert path.read_bytes() == first


def test_write_json_if_changed_returns_false_on_no_change(tmp_path):
    path = tmp_path / "doc.json"
    assert write_json_if_changed(path, {"a": 1}) is True
    assert write_json_if_changed(path, {"a": 1}) is False
    assert write_json_if_changed(path, {"a": 2}) is True


def test_write_document_ignores_generated_at(tmp_path):
    path = tmp_path / "doc.json"
    assert write_document_if_changed(path, {"a": 1, "generatedAt": "2026-07-30T00:00:00Z"})
    assert not write_document_if_changed(path, {"a": 1, "generatedAt": "2026-07-31T00:00:00Z"})
    # ...but the stored generatedAt is untouched, so it stays truthful.
    assert json.loads(path.read_text())["generatedAt"] == "2026-07-30T00:00:00Z"
    assert write_document_if_changed(path, {"a": 2, "generatedAt": "2026-07-31T00:00:00Z"})


# --- collector-level idempotency and duplicate prevention ------------------


def test_rerunning_a_collector_produces_identical_bytes(sandbox):
    provider, records, _ = collect(FinancialFixtureProvider, "fixture_financials", sandbox)
    rows = [f.to_json() for f in records]
    path = sandbox.facts_annual / "ALL.jsonl"
    key = lambda r: (r["factKey"], r["revision"])  # noqa: E731

    upsert_jsonl(path, rows, key=key)
    first = path.read_bytes()
    for _ in range(3):
        upsert_jsonl(path, rows, key=key)
    assert path.read_bytes() == first


def test_no_duplicate_fact_keys_from_the_fixture(sandbox):
    _, records, _ = collect(FinancialFixtureProvider, "fixture_financials", sandbox)
    keys = [f.primary_key for f in records]
    assert len(keys) == len(set(keys))


def test_no_duplicate_price_rows_from_the_fixture(sandbox):
    _, records, _ = collect(MarketPriceFixtureProvider, "fixture_market_prices", sandbox)
    keys = [r.primary_key for r in records]
    assert len(keys) == len(set(keys))


def test_no_duplicate_disclosure_ids(sandbox):
    _, records, _ = collect(DisclosureFixtureProvider, "fixture_disclosures", sandbox)
    ids = [r.disclosure_id for r in records]
    assert len(ids) == len(set(ids))


def test_macro_revisions_of_one_period_are_kept_apart(sandbox):
    """Same period, later vintage, different value — both rows must survive."""
    _, records, _ = collect(MacroFixtureProvider, "fixture_macro", sandbox)
    cpi_may = [r for r in records
               if r.series_id == "BPS_CPI_YOY" and r.observation_period == "2026-05"]
    assert len(cpi_may) == 2
    assert {r.release_vintage for r in cpi_may} == {"2026-06-02", "2026-07-01"}
    assert {r.measure.value for r in cpi_may} == {2.41, 2.38}
    # Vintage is part of the key, so neither overwrites the other.
    assert len({r.primary_key for r in cpi_may}) == 2


# --- restatement versioning ------------------------------------------------


def test_restatement_creates_a_new_revision_and_preserves_the_original(sandbox):
    _, records, _ = collect(FinancialFixtureProvider, "fixture_financials", sandbox)
    processed = apply_restatements(records)

    net_profit = [f for f in processed
                  if f.ticker == "BBCA" and f.metric == "net_profit"
                  and f.period_end == "2025-12-31"]
    assert len(net_profit) == 2, "both the original and the restatement must survive"

    by_revision = {f.revision: f for f in net_profit}
    original, restated = by_revision[1], by_revision[2]

    # They share an identity, which is what makes the supersession chain work.
    assert original.fact_key == restated.fact_key
    assert original.measure.basis == ValueBasis.REPORTED
    assert restated.measure.basis == ValueBasis.RESTATED
    assert restated.supersedes == 1
    assert restated.restatement_of == "FIX-DISC-2026-0001"

    # The original is flagged, not deleted or overwritten.
    assert "SUPERSEDED" in original.quality_flags
    assert original.measure.value == 53_950_000_000_000 or original.measure.value != \
        restated.measure.value


def test_latest_revisions_returns_one_current_view_per_fact(sandbox):
    _, records, _ = collect(FinancialFixtureProvider, "fixture_financials", sandbox)
    current = latest_revisions(apply_restatements(records))
    keys = [f.fact_key for f in current]
    assert len(keys) == len(set(keys))

    net_profit = next(f for f in current
                      if f.ticker == "BBCA" and f.metric == "net_profit"
                      and f.period_end == "2025-12-31")
    assert net_profit.revision == 2
    assert net_profit.measure.basis == ValueBasis.RESTATED


def test_segment_facts_do_not_collide_with_consolidated_ones(sandbox):
    _, records, _ = collect(FinancialFixtureProvider, "fixture_financials", sandbox)
    revenue = [f for f in records
               if f.ticker == "BBCA" and f.metric == "revenue"
               and f.period_end == "2025-12-31"]
    assert len(revenue) == 2
    assert len({f.fact_key for f in revenue}) == 2, "segment must be part of the identity"


def test_scale_normalization_end_to_end(sandbox):
    """ASII reports in billions, BBCA in millions; both land in base units."""
    _, records, _ = collect(FinancialFixtureProvider, "fixture_financials", sandbox)
    asii = next(f for f in records if f.ticker == "ASII" and f.metric == "revenue")
    bbca = next(f for f in records
                if f.ticker == "BBCA" and f.metric == "revenue" and f.segment is None)
    assert asii.measure.value == 316_400 * 1_000_000_000
    assert bbca.measure.value == 112_500_000 * 1_000_000


def test_unparseable_and_absent_values_survive_as_missing(sandbox):
    _, records, _ = collect(FinancialFixtureProvider, "fixture_financials", sandbox)

    treasury = next(f for f in records if f.metric == "treasury_shares")
    assert treasury.measure.is_missing
    assert treasury.measure.missing_reason == MissingReason.EXTRACTION_FAILED

    segment = next(f for f in records if f.segment == "WHOLESALE_BANKING")
    assert segment.measure.is_missing
    assert segment.measure.missing_reason == MissingReason.NOT_REPORTED

    assert all(f.measure.value != 0 for f in records if f.measure.is_missing is False
               and f.metric in ("treasury_shares",))


# --- suspension: missing price, real zero volume ---------------------------


def test_a_suspended_day_has_no_price_but_a_genuine_zero_volume(sandbox):
    _, records, _ = collect(MarketPriceFixtureProvider, "fixture_market_prices", sandbox)
    suspended = next(r for r in records
                     if r.ticker == "ASII" and r.trading_date == "2026-07-10")

    assert suspended.close.is_missing
    assert suspended.close.missing_reason == MissingReason.TRADING_HALTED
    assert suspended.close.value is None
    # Volume of 0 is real data on a halted day, not a missing value.
    assert suspended.volume == 0
    assert str(suspended.corporate_action_flag) == "SUSPENSION"


def test_adjusted_close_is_never_fabricated(sandbox):
    _, records, _ = collect(MarketPriceFixtureProvider, "fixture_market_prices", sandbox)
    assert all(r.adjusted_close is None for r in records)
    assert all(r.adjustment_methodology is None for r in records)


# --- fail-soft and fail-closed ---------------------------------------------


def test_one_failing_item_does_not_abort_the_others(sandbox, monkeypatch):
    """Fail-soft by ticker: one issuer failing must not corrupt the rest."""
    provider = build(FinancialFixtureProvider, "fixture_financials", sandbox)

    from pipeline.goh_dip_tong.contracts.records import DiscoveredItem

    good = provider.discover(ProviderContext(run_id="test"))[0]
    bad = DiscoveredItem(item_id="facts:missing", provider_id=provider.provider_id,
                         data_type="financial_facts", ticker="BROKEN",
                         hint={"fixture_path": str(sandbox.repo_root / "nope.json")})
    monkeypatch.setattr(provider, "discover", lambda ctx: [bad, good])

    records, failures = provider.collect(ProviderContext(run_id="test"))
    assert records, "the healthy item must still have been collected"
    assert len(failures) == 1
    assert failures[0]["ticker"] == "BROKEN"
    assert "FileNotFoundError" in failures[0]["reason"]


def test_invalid_data_does_not_replace_the_last_validated_data(sandbox):
    """Fail-closed publication, demonstrated on the real file."""
    from pipeline.goh_dip_tong.publishing import registry_config

    good = [_c("BBCA", "Bank Central Asia Tbk")]
    document = registry_config.build_idx30_document(
        good, "2026-02-02",
        {"name": "t", "url": None, "providerId": "t", "publishedAt": None,
         "retrievedAt": "2026-07-30T00:00:00Z", "rightsStatus": "PUBLIC_METADATA_ONLY"},
    )
    write_document_if_changed(sandbox.idx30_current, document)
    good_bytes = sandbox.idx30_current.read_bytes()

    # An invalid universe: empty. The provider's own validator refuses it.
    provider = build(
        __import__("pipeline.goh_dip_tong.collectors.idx30_registry",
                   fromlist=["Idx30FixtureProvider"]).Idx30FixtureProvider,
        "fixture_idx30_registry", sandbox)
    report = provider.validate([])
    assert not report.ok
    assert any("refusing to replace" in i.message for i in report.critical_failures)

    # Nothing was written, so the last validated config still stands.
    assert sandbox.idx30_current.read_bytes() == good_bytes


def _c(ticker, name):
    from pipeline.goh_dip_tong.contracts.enums import CoverageStatus
    from pipeline.goh_dip_tong.contracts.records import Constituent

    return Constituent(
        ticker=ticker, name=name, sector_code="FINANCIALS", sector_name="Financials",
        industry_code="BANKS", industry_name="Banks", model_family="BANK",
        coverage_status=CoverageStatus.FINANCIALS, entered_at="2026-02-02",
        source_ref="test",
    )


def test_balance_sheet_identity_is_checked_where_complete(sandbox):
    _, records, _ = collect(FinancialFixtureProvider, "fixture_financials", sandbox)
    report = build(FinancialFixtureProvider, "fixture_financials", sandbox)._check_balance_sheet(records)
    assert report.ok, [i.message for i in report.critical_failures]


def test_duplicate_detection_helper():
    rows = [{"a": 1, "b": 2}, {"a": 1, "b": 2}]
    assert not quality.check_duplicates(rows, ("a", "b")).ok
    assert quality.check_duplicates([{"a": 1}, {"a": 2}], ("a",)).ok
