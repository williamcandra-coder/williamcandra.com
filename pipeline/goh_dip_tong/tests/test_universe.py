"""Stage 1 tests: IDX30 config schema, uniqueness, effective dates,
model-family mapping, deterministic ordering, UI ticker-config compatibility.
"""

from __future__ import annotations

import json

import pytest
from jsonschema import Draft202012Validator

from pipeline.goh_dip_tong.contracts.enums import CoverageStatus
from pipeline.goh_dip_tong.contracts.records import ContractError
from pipeline.goh_dip_tong.publishing import registry_config
from pipeline.goh_dip_tong.validation import quality
from pipeline.goh_dip_tong.validation.schema import (
    SCHEMA_FILES,
    validate_document,
    validate_all_schemas,
)


# --- schemas ---------------------------------------------------------------


def test_every_declared_schema_exists_and_is_valid(real_settings):
    report = validate_all_schemas(real_settings)
    assert report.ok, [i.message for i in report.critical_failures]
    assert len(SCHEMA_FILES) == 8


def test_committed_idx30_config_matches_schema(real_settings):
    document = json.loads(real_settings.idx30_current.read_text(encoding="utf-8"))
    report = validate_document("idx30", document, settings=real_settings)
    assert report.ok, [i.message for i in report.critical_failures]


def test_committed_companies_config_matches_schema(real_settings):
    document = json.loads(real_settings.companies_file.read_text(encoding="utf-8"))
    report = validate_document("company", document, settings=real_settings)
    assert report.ok, [i.message for i in report.critical_failures]


# --- universe integrity ----------------------------------------------------


@pytest.fixture
def committed(real_settings):
    return json.loads(real_settings.idx30_current.read_text(encoding="utf-8"))


def test_universe_uniqueness(committed):
    tickers = [c["ticker"] for c in committed["constituents"]]
    assert len(tickers) == len(set(tickers))
    report = quality.check_ticker_uniqueness(committed["constituents"])
    assert report.ok


def test_duplicate_ticker_is_a_critical_failure():
    rows = [{"ticker": "BBCA", "active": True}, {"ticker": "BBCA", "active": True}]
    report = quality.check_ticker_uniqueness(rows)
    assert not report.ok
    assert "BBCA" in report.critical_failures[0].message


def test_membership_effective_dates_are_coherent(committed):
    report = quality.check_effective_dates(committed)
    assert report.ok, [i.message for i in report.critical_failures]
    assert committed["effectiveFrom"] <= (committed["effectiveTo"] or "9999-12-31")


def test_effective_range_inversion_is_caught():
    document = {"effectiveFrom": "2026-08-01", "effectiveTo": "2026-02-01", "constituents": []}
    assert not quality.check_effective_dates(document).ok


def test_entry_date_after_period_end_is_caught():
    document = {
        "effectiveFrom": "2026-01-01",
        "effectiveTo": "2026-06-30",
        "constituents": [{"ticker": "BBCA", "enteredAt": "2026-09-01"}],
    }
    assert not quality.check_effective_dates(document).ok


def test_universe_count_is_checked_against_the_source_not_a_hard_coded_30():
    """A pipeline that hard-codes 30 fails on exactly the day it matters."""
    twenty_nine = [{"ticker": f"AA{i:02d}", "active": True} for i in range(29)]

    # Matching a source that declared 29 is a PASS, even though 29 != 30.
    matching = quality.check_universe_count(twenty_nine, source_declared=29)
    assert matching.ok
    # ...but it still raises a WARNING so a human looks at it.
    assert any(i.check_id == "universe.count_conventional" for i in matching.warnings)

    # Disagreeing with the source is a CRITICAL failure regardless of the number.
    mismatched = quality.check_universe_count(twenty_nine, source_declared=30)
    assert not mismatched.ok


# --- model mapping and the onboarding rule ---------------------------------


def test_model_mapping_resolves_industry_before_sector(real_settings):
    models = real_settings.models()
    # BANKS industry wins over the FINANCIALS sector default (both give BANK here,
    # but INDUSTRIAL_CONGLOMERATES under INDUSTRIALS proves precedence).
    assert registry_config.resolve_model_family("FINANCIALS", "BANKS", models) == "BANK"
    assert registry_config.resolve_model_family(
        "INDUSTRIALS", "INDUSTRIAL_CONGLOMERATES", models
    ) == "CONGLOMERATE"


def test_unmapped_classification_becomes_onboarding_never_a_generic_model(real_settings):
    """The rule that stops a bank being valued with a generic FCFF model."""
    models = real_settings.models()
    family = registry_config.resolve_model_family("TRANSPORTATION_AND_LOGISTICS",
                                                  "SHIPPING", models)
    assert family is None
    coverage = registry_config.resolve_coverage_status("SMDR", family, models)
    assert coverage == CoverageStatus.ONBOARDING


def test_declared_but_unsupported_family_also_becomes_onboarding(real_settings):
    """TECH is declared in models.yml with supported: false."""
    models = real_settings.models()
    assert registry_config.resolve_model_family("TECHNOLOGY", "SOFTWARE_AND_IT_SERVICES",
                                                models) == "TECH"
    assert registry_config.resolve_coverage_status("GOTO", "TECH", models) == \
        CoverageStatus.ONBOARDING


def test_onboarding_constituent_carries_no_model_family(real_settings, idx30_h2):
    """End to end: the H2 fixture adds GOTO, whose sector has no supported model."""
    models = real_settings.models()
    from pipeline.goh_dip_tong.contracts.records import Constituent

    raw = [
        Constituent(
            ticker=r["ticker"], name=r["name"],
            sector_code=r["sectorCode"], sector_name=r["sectorName"],
            industry_code=r["industryCode"], industry_name=r["industryName"],
            model_family=None, coverage_status=CoverageStatus.ONBOARDING,
            entered_at=r["enteredAt"], source_ref=r["sourceRef"],
        )
        for r in idx30_h2["constituents"]
    ]
    mapped = {c.ticker: c for c in registry_config.apply_model_mapping(raw, models)}

    assert mapped["GOTO"].model_family is None
    assert mapped["GOTO"].coverage_status == CoverageStatus.ONBOARDING
    assert mapped["BBCA"].model_family == "BANK"
    assert mapped["BBCA"].coverage_status == CoverageStatus.FINANCIALS


def test_constituent_type_rejects_null_model_with_non_onboarding_coverage():
    """The invariant is enforced at construction, not only by the schema."""
    with pytest.raises(ContractError, match="ONBOARDING"):
        from pipeline.goh_dip_tong.contracts.records import Constituent

        Constituent(
            ticker="GOTO", name="GoTo", sector_code="TECHNOLOGY", sector_name="Technology",
            industry_code="SOFTWARE_AND_IT_SERVICES", industry_name="Software",
            model_family=None, coverage_status=CoverageStatus.FINANCIALS,
        )


def test_committed_universe_model_mapping_is_coherent(real_settings, committed):
    report = quality.check_model_mapping(committed["constituents"], real_settings.models())
    assert report.ok, [i.message for i in report.critical_failures]


def test_invalid_ticker_is_rejected():
    from pipeline.goh_dip_tong.contracts.records import Constituent

    with pytest.raises(ContractError, match="invalid IDX ticker"):
        Constituent(
            ticker="bbca", name="x", sector_code="F", sector_name="F",
            industry_code="B", industry_name="B", model_family="BANK",
            coverage_status=CoverageStatus.FINANCIALS,
        )


# --- deterministic output ordering -----------------------------------------


def test_constituents_are_sorted_by_ticker(committed):
    tickers = [c["ticker"] for c in committed["constituents"]]
    assert tickers == sorted(tickers)


def test_generation_is_byte_stable_across_runs(real_settings, constituent_factory):
    """Same content in, same bytes out — including the contentHash."""
    from pipeline.goh_dip_tong.publishing.writers import canonical_json

    constituents = [
        constituent_factory(ticker=t) for t in ("TLKM", "ASII", "BBCA")
    ]
    source = {"name": "test", "url": None, "providerId": "test",
              "publishedAt": None, "retrievedAt": "2026-07-30T00:00:00Z",
              "rightsStatus": "PUBLIC_METADATA_ONLY"}

    first = registry_config.build_idx30_document(constituents, "2026-02-02", source)
    second = registry_config.build_idx30_document(list(reversed(constituents)),
                                                  "2026-02-02", source)

    assert first["contentHash"] == second["contentHash"]
    assert canonical_json({k: v for k, v in first.items() if k != "generatedAt"}) == \
           canonical_json({k: v for k, v in second.items() if k != "generatedAt"})


def test_content_hash_ignores_retrieval_time_but_not_content(constituent_factory):
    """A hash that moved with the clock would be useless as a change signal."""
    constituents = [constituent_factory()]

    def build(retrieved_at, name="Bank Central Asia Tbk"):
        return registry_config.build_idx30_document(
            [constituent_factory(name=name)], "2026-02-02",
            {"name": "t", "url": None, "providerId": "t", "publishedAt": None,
             "retrievedAt": retrieved_at, "rightsStatus": "PUBLIC_METADATA_ONLY"},
        )

    assert build("2026-07-30T00:00:00Z")["contentHash"] == \
           build("2026-07-31T23:59:59Z")["contentHash"]
    assert build("2026-07-30T00:00:00Z")["contentHash"] != \
           build("2026-07-30T00:00:00Z", name="Renamed Tbk")["contentHash"]


# --- Stage 3 UI contract ---------------------------------------------------


UI_REQUIRED_FIELDS = ("ticker", "name", "sectorCode", "sectorName",
                      "industryCode", "coverageStatus", "active", "modelFamily")


def test_ui_ticker_config_compatibility(committed):
    """The Stage 3 company picker reads this file directly. It must be able to
    render a labelled, grouped, filterable list from it alone."""
    assert committed["indexCode"] == "IDX30"
    assert committed["constituents"], "the UI cannot render an empty universe"

    for row in committed["constituents"]:
        for field in UI_REQUIRED_FIELDS:
            assert field in row, f"{row.get('ticker')} is missing {field}"
        assert row["coverageStatus"] in {
            "FULL_RESEARCH", "FINANCIALS", "ONBOARDING", "SUSPENDED"
        }

    # The picker must be able to tell the user this is not live index data.
    assert committed["authoritative"] is False
    assert committed["provenance"] == "FIXTURE"


def test_ui_can_group_by_sector_from_categories_alone(real_settings, committed):
    categories = json.loads(real_settings.categories_file.read_text(encoding="utf-8"))
    sector_codes = {s["sectorCode"] for s in categories["sectors"]}
    assert {c["sectorCode"] for c in committed["constituents"]} == sector_codes

    counted = sum(s["constituentCount"] for s in categories["sectors"])
    assert counted == len(committed["constituents"])
