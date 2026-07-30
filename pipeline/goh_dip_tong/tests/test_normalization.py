"""Stage 1 tests: period normalization, unit/currency normalization, and the
missing-versus-zero control.
"""

from __future__ import annotations

import pytest

from pipeline.goh_dip_tong.contracts.enums import (
    MissingReason,
    PeriodType,
    Scale,
    ValueBasis,
)
from pipeline.goh_dip_tong.contracts.records import ContractError, Measure
from pipeline.goh_dip_tong.normalization import periods, units, values
from pipeline.goh_dip_tong.validation import quality


# --- period normalization --------------------------------------------------


@pytest.mark.parametrize(
    "ref,expected_type,expected_year",
    [
        ("FY2025", PeriodType.FY, 2025),
        ("FY-2025", PeriodType.FY, 2025),
        ("Q3-2025", PeriodType.Q3, 2025),
        ("2025-Q3", PeriodType.Q3, 2025),
        ("YTD_Q2-2026", PeriodType.YTD_Q2, 2026),
        ("H1-2026", PeriodType.H1, 2026),
    ],
)
def test_period_references_parse(ref, expected_type, expected_year):
    period_type, year, _ = periods.parse_period_ref(ref)
    assert period_type == expected_type
    assert year == expected_year


def test_unparseable_period_raises_rather_than_guessing():
    with pytest.raises(periods.PeriodError):
        periods.parse_period_ref("sometime in 2025")
    with pytest.raises(periods.PeriodError):
        periods.parse_period_ref("")


def test_period_bounds_for_a_standalone_quarter():
    assert periods.period_bounds(PeriodType.Q3, 2025) == ("2025-07-01", "2025-09-30")


def test_ytd_period_starts_at_the_year_start_not_the_quarter_start():
    """Indonesian interim filings are cumulative; treating Q3 as three months is
    a classic way to be confidently wrong."""
    assert periods.period_bounds(PeriodType.YTD_Q3, 2025) == ("2025-01-01", "2025-09-30")
    assert periods.is_cumulative(PeriodType.YTD_Q3)
    assert not periods.is_cumulative(PeriodType.Q3)


def test_instant_periods_have_no_start_date():
    start, end = periods.period_bounds(PeriodType.POINT_IN_TIME, 2025)
    assert start is None and end == "2025-12-31"


def test_ttm_window_spans_four_quarters_across_a_year_boundary():
    assert periods.ttm_window(2026, 2) == [(2025, 3), (2025, 4), (2026, 1), (2026, 2)]
    assert periods.period_bounds(PeriodType.TTM, 2026, 2) == ("2025-07-01", "2026-06-30")


def test_standalone_derived_from_ytd():
    assert periods.standalone_from_ytd(900, 600) == 300


def test_missing_prior_period_does_not_become_zero():
    """Treating a missing prior YTD as 0 would report nine months as one quarter."""
    assert periods.standalone_from_ytd(900, None) is None
    assert periods.standalone_from_ytd(None, 600) is None


def test_normalize_period_produces_the_fact_record_fields():
    out = periods.normalize_period("YTD_Q2-2026")
    assert out == {
        "periodType": "YTD_Q2", "periodStart": "2026-01-01",
        "periodEnd": "2026-06-30", "fiscalYear": 2026,
    }


# --- unit, scale and currency ----------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [("millions", Scale.MILLIONS), ("juta", Scale.MILLIONS), ("miliar", Scale.BILLIONS),
     ("TRILLIONS", Scale.TRILLIONS), ("ribu", Scale.THOUSANDS), (None, Scale.UNITS),
     (1_000_000, Scale.MILLIONS)],
)
def test_scale_aliases(raw, expected):
    assert units.parse_scale(raw) == expected


def test_unknown_scale_raises():
    with pytest.raises(units.UnitError):
        units.parse_scale("gazillions")


@pytest.mark.parametrize("raw,expected",
                         [("Rp", "IDR"), ("IDR", "IDR"), ("US$", "USD"), ("usd", "USD"),
                          (None, None), ("", None)])
def test_currency_aliases(raw, expected):
    assert units.parse_currency(raw) == expected


def test_unsupported_currency_raises():
    with pytest.raises(units.UnitError):
        units.parse_currency("SGD")


def test_scale_is_multiplied_out_to_base_units():
    measure = units.normalize_measure(112_500, unit="IDR", currency="Rp", scale="millions")
    assert measure.value == 112_500_000_000
    # The scale as reported is preserved so the filing can be reconstructed.
    assert measure.scale == Scale.MILLIONS


def test_scaling_a_missing_value_keeps_it_missing():
    measure = units.normalize_measure(None, unit="IDR", scale="millions",
                                      missing_reason=MissingReason.NOT_REPORTED)
    assert measure.is_missing and measure.value is None
    assert units.to_base_units(None, Scale.BILLIONS) is None


def test_cross_currency_arithmetic_is_refused():
    idr = Measure.of(100, unit="IDR", currency="IDR")
    usd = Measure.of(100, unit="USD", currency="USD")
    assert units.assert_same_currency([idr, idr]) == "IDR"
    with pytest.raises(units.UnitError, match="FX rate"):
        units.assert_same_currency([idr, usd])


# --- missing versus zero ---------------------------------------------------


@pytest.mark.parametrize("token", ["", "-", "—", "n/a", "N.A.", "nil", "tidak ada", None])
def test_null_tokens_become_missing_not_zero(token):
    measure = values.coerce(token, unit="IDR")
    assert measure.is_missing
    assert measure.value is None
    assert measure.missing_reason == MissingReason.NOT_REPORTED


def test_a_reported_zero_stays_a_real_zero():
    """The one case that must NOT be treated as missing."""
    measure = values.coerce("0", unit="IDR")
    assert not measure.is_missing
    assert measure.value == 0.0


def test_unparseable_text_becomes_extraction_failed_not_zero():
    measure = values.coerce("see note 14", unit="IDR")
    assert measure.is_missing
    assert measure.missing_reason == MissingReason.EXTRACTION_FAILED
    assert measure.value is None


def test_accounting_negatives_and_thousands_separators():
    assert values.coerce("(1,234.5)", unit="IDR").value == -1234.5
    assert values.coerce("1,234,567", unit="IDR").value == 1234567.0


def test_sentinel_numbers_are_treated_as_failed_extraction():
    measure = values.coerce("-999999999", unit="IDR")
    assert measure.is_missing
    assert measure.missing_reason == MissingReason.EXTRACTION_FAILED


def test_measure_cannot_be_missing_without_a_reason():
    with pytest.raises(ContractError, match="MissingReason"):
        Measure(value=None, unit="IDR")


def test_measure_cannot_have_a_value_and_a_missing_reason():
    with pytest.raises(ContractError, match="claims to be"):
        Measure(value=1.0, unit="IDR", missing_reason=MissingReason.NOT_REPORTED)


def test_missing_zero_guard_fires_on_a_coerced_zero():
    bad = Measure.of(0.0, unit="IDR")
    with pytest.raises(values.MissingZeroViolation):
        values.assert_not_zero_from_missing("n/a", bad, subject="revenue")


def test_missing_zero_guard_is_silent_on_a_genuine_reported_zero():
    values.assert_not_zero_from_missing("0", Measure.of(0.0, unit="IDR"))


def test_rights_withheld_is_distinct_from_not_reported():
    """A licensing gap and a data gap are different problems."""
    assert values.missing_because_rights().missing_reason == MissingReason.RIGHTS_WITHHELD
    assert values.missing_because_source_down().missing_reason == \
        MissingReason.SOURCE_UNAVAILABLE


def test_dataset_level_missing_vs_zero_check():
    good = [{"ticker": "A", "value": None, "missingReason": "NOT_REPORTED"},
            {"ticker": "B", "value": 0, "missingReason": None}]
    assert quality.check_missing_vs_zero(good).ok

    unexplained = [{"ticker": "C", "value": None, "missingReason": None}]
    assert not quality.check_missing_vs_zero(unexplained).ok

    contradictory = [{"ticker": "D", "value": 12, "missingReason": "NOT_REPORTED"}]
    assert not quality.check_missing_vs_zero(contradictory).ok


# --- sign conventions ------------------------------------------------------


def test_sign_conventions():
    measure = Measure.of(-500, unit="IDR")
    assert values.apply_sign_convention(measure, "positive_magnitude").value == 500
    assert values.apply_sign_convention(Measure.of(500, unit="IDR"),
                                        "negative_outflow").value == -500
    assert values.apply_sign_convention(measure, "signed").value == -500


def test_sign_convention_leaves_missing_values_alone():
    missing = Measure.missing(MissingReason.NOT_REPORTED, unit="IDR")
    assert values.apply_sign_convention(missing, "positive_magnitude").is_missing


def test_unknown_sign_convention_raises():
    with pytest.raises(ContractError):
        values.apply_sign_convention(Measure.of(1, unit="IDR"), "wishful")


def test_completeness():
    present = Measure.of(1, unit="IDR")
    missing = Measure.missing(MissingReason.NOT_REPORTED, unit="IDR")
    assert values.completeness([present, present]) == 1.0
    assert values.completeness([present, missing]) == 0.5
    assert values.completeness([]) == 1.0
