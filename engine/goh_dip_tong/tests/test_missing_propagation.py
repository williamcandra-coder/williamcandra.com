"""Missing never becomes zero, and a division that cannot be done returns nothing.

Stage 1 established the first rule. These tests establish its derived-metric
counterpart, which is the same failure wearing different clothes: a ratio whose
denominator is zero must not come back as ``inf``, as ``nan``, or as a zero
from a swallowed exception. All three look like computed values and none is one.
"""

from __future__ import annotations

import json
import math

import pytest

from engine.goh_dip_tong.common.arithmetic import safe_add, safe_div, safe_mean, safe_sub
from pipeline.goh_dip_tong.contracts.enums import (
    MissingReason,
    QualityStatus,
    ValueBasis,
)
from pipeline.goh_dip_tong.contracts.records import ContractError, Measure
from pipeline.goh_dip_tong.normalization.units import UnitError


def m(x, unit="IDR", currency="IDR", quality=QualityStatus.VALID):
    return Measure(value=float(x), unit=unit, currency=currency, quality_status=quality)


def gone(reason=MissingReason.NOT_REPORTED, unit="IDR"):
    return Measure.missing(reason, unit=unit, currency="IDR")


# --- division --------------------------------------------------------------


def test_a_zero_denominator_is_undefined_not_infinite():
    result = safe_div(m(10), m(0))
    assert result.is_missing
    assert result.missing_reason == MissingReason.UNDEFINED_DENOMINATOR


def test_a_zero_denominator_never_returns_zero():
    result = safe_div(m(10), m(0))
    assert result.value is None and result.value != 0


def test_a_negative_denominator_is_refused_by_default():
    """ROE on negative book value is arithmetically fine and financially
    meaningless — and with a negative numerator it returns a plausible positive."""
    result = safe_div(m(-5), m(-20))
    assert result.is_missing
    assert result.missing_reason == MissingReason.UNDEFINED_DENOMINATOR


def test_a_negative_denominator_is_allowed_when_a_model_asks_for_it():
    result = safe_div(m(-5), m(-20), allow_negative_denominator=True)
    assert result.value == 0.25


def test_a_zero_numerator_over_a_real_denominator_is_a_real_zero():
    """A reported zero is data. Refusing it would be the opposite error."""
    result = safe_div(m(0), m(20))
    assert not result.is_missing
    assert result.value == 0.0


def test_division_propagates_a_missing_numerator_with_its_reason():
    result = safe_div(gone(MissingReason.EXTRACTION_FAILED), m(20))
    assert result.missing_reason == MissingReason.EXTRACTION_FAILED


def test_division_propagates_a_missing_denominator_with_its_reason():
    result = safe_div(m(20), gone(MissingReason.RIGHTS_WITHHELD))
    assert result.missing_reason == MissingReason.RIGHTS_WITHHELD


def test_a_ratio_result_carries_no_currency():
    result = safe_div(m(10, currency="IDR"), m(20, currency="IDR"))
    assert result.unit == "RATIO"
    assert result.currency is None


# --- non-finite results ----------------------------------------------------


def test_an_overflowing_result_is_missing_not_infinite():
    result = safe_div(m(1e308), m(1e-308))
    assert result.is_missing or math.isfinite(result.value)
    if result.is_missing:
        assert result.missing_reason == MissingReason.UNDEFINED_DENOMINATOR


def test_no_derived_value_can_serialise_as_nan_or_infinity():
    """Stage 1's writers pass allow_nan=False, so a non-finite value that
    escaped this far would fail at serialisation with no clue which
    calculation produced it."""
    for result in (safe_div(m(1e308), m(1e-308)), safe_div(m(1), m(0))):
        json.dumps(result.value, allow_nan=False)


# --- addition and subtraction ---------------------------------------------


def test_subtraction_propagates_missing_from_either_side():
    assert safe_sub(gone(), m(3)).is_missing
    assert safe_sub(m(3), gone()).is_missing


def test_addition_propagates_missing_from_either_side():
    assert safe_add(gone(), m(3)).is_missing
    assert safe_add(m(3), gone()).is_missing


def test_arithmetic_across_currencies_raises_rather_than_converting():
    """Stage 1 has no FX rate source, and an implicit conversion would be a
    silent one."""
    with pytest.raises(UnitError):
        safe_sub(m(10, currency="IDR"), m(2, currency="USD"))


def test_arithmetic_results_are_labelled_derived():
    assert safe_sub(m(10), m(4)).basis == ValueBasis.DERIVED
    assert safe_add(m(10), m(4)).basis == ValueBasis.DERIVED


# --- averaging -------------------------------------------------------------


def test_the_mean_of_nothing_is_missing_not_zero():
    result = safe_mean([])
    assert result.is_missing
    assert result.missing_reason == MissingReason.INSUFFICIENT_PERIODS


def test_one_missing_member_makes_the_whole_average_missing():
    """Averaging the rest would silently change the denominator."""
    result = safe_mean([m(10), gone(), m(30)])
    assert result.is_missing


def test_the_mean_of_present_values_is_exact():
    assert safe_mean([m(10), m(20)]).value == 15.0


def test_averaging_across_currencies_raises():
    with pytest.raises(UnitError):
        safe_mean([m(10, currency="IDR"), m(20, currency="USD")])


# --- quality propagation ---------------------------------------------------


def test_a_derived_value_is_never_sounder_than_its_weakest_input():
    result = safe_div(
        m(10, quality=QualityStatus.VALID),
        m(20, quality=QualityStatus.SUSPECT),
    )
    assert result.quality_status == QualityStatus.SUSPECT


def test_invalid_beats_suspect_when_propagating():
    result = safe_add(
        m(10, quality=QualityStatus.INVALID),
        m(20, quality=QualityStatus.SUSPECT),
    )
    assert result.quality_status == QualityStatus.INVALID


# --- the type-level guarantee ---------------------------------------------


def test_a_missing_measure_cannot_be_built_without_a_reason():
    with pytest.raises(ContractError):
        Measure(value=None, unit="IDR")


def test_undefined_denominator_is_a_declared_reason_in_metrics_yml(real_engine):
    """The engine must not invent vocabulary the canonical registry lacks."""
    reasons = real_engine.pipeline.metrics()["missing_reasons"]
    assert "UNDEFINED_DENOMINATOR" in reasons
    assert MissingReason.UNDEFINED_DENOMINATOR in set(MissingReason)
