"""The formula registry: identity, propagation and reproducibility.

The registry is where three separate guarantees are enforced at once, so it
gets the closest scrutiny: no number without a named formula, no hand-written
input reference, and no formula that ever sees a missing value.
"""

from __future__ import annotations

import sys

import pytest

from engine.goh_dip_tong import FORMULA_REGISTRY_HASH, MODEL_VERSION
from engine.goh_dip_tong.common import arithmetic  # noqa: F401  (registers formulas)
from engine.goh_dip_tong.contracts.calculated import Calculated, InputRef, Period
from engine.goh_dip_tong.contracts.registry import (
    REGISTRY,
    FormulaError,
    FormulaRegistry,
)
from pipeline.goh_dip_tong.contracts.enums import MissingReason, PeriodType, ValueBasis
from pipeline.goh_dip_tong.contracts.records import ContractError, Measure

FY25 = Period(PeriodType.FY, "2025-12-31", "2025-01-01", 2025)


def _value(x, unit="IDR", currency="IDR", metric="m"):
    return Calculated(
        metric_id=metric,
        measure=Measure.of(x, unit=unit, currency=currency),
        period=FY25, formula_id="source.fact",
        model_version=MODEL_VERSION, calculated_at="2026-07-31T00:00:00Z",
        input_refs=(InputRef(ref=f"REF|{metric}"),),
    )


def _missing(reason, unit="IDR", metric="m"):
    return Calculated(
        metric_id=metric,
        measure=Measure.missing(reason, unit=unit, currency="IDR"),
        period=FY25, formula_id="source.fact",
        model_version=MODEL_VERSION, calculated_at="2026-07-31T00:00:00Z",
        input_refs=(InputRef(ref=f"REF|{metric}"),),
    )


def _compute(formula_id, **inputs):
    return REGISTRY.compute(
        formula_id, FY25, inputs,
        model_version=MODEL_VERSION, calculated_at="2026-07-31T00:00:00Z",
    )


# --- identity --------------------------------------------------------------


def test_a_calculated_cannot_exist_without_a_formula_id():
    with pytest.raises(ContractError):
        Calculated(
            metric_id="roe", measure=Measure.of(1.0, unit="RATIO"), period=FY25,
            formula_id="", model_version=MODEL_VERSION, calculated_at="x",
        )


def test_a_calculated_cannot_exist_without_a_metric():
    with pytest.raises(ContractError):
        Calculated(
            metric_id="", measure=Measure.of(1.0, unit="RATIO"), period=FY25,
            formula_id="core.ratio", model_version=MODEL_VERSION, calculated_at="x",
        )


def test_every_registered_formula_declares_inputs_matching_its_signature():
    """Enforced at registration, so a mismatch cannot reach a snapshot."""
    registry = FormulaRegistry()
    with pytest.raises(FormulaError, match="do not match the function signature"):
        @registry.formula("bad", inputs=("a", "b"), output_metric="x")
        def bad(a):  # noqa: ARG001 - the mismatch is the point
            return a

    assert len(registry) == 0, "a rejected formula must not remain registered"


def test_registering_the_same_id_twice_is_rejected():
    registry = FormulaRegistry()

    @registry.formula("dup", inputs=("a",), output_metric="x")
    def first(a):
        return a

    with pytest.raises(FormulaError, match="already registered"):
        @registry.formula("dup", inputs=("a",), output_metric="x")
        def second(a):
            return a


def test_an_unknown_formula_names_what_is_registered():
    with pytest.raises(FormulaError, match="unknown formula"):
        _compute("core.nonexistent")


def test_supplying_the_wrong_inputs_is_rejected():
    with pytest.raises(FormulaError, match="expected inputs"):
        _compute("core.ratio", numerator=_value(1.0))


def test_a_formula_returning_a_bare_float_is_rejected():
    """A float cannot carry a missing reason, so returning one would reopen
    exactly the hole the Measure type closes."""
    registry = FormulaRegistry()

    @registry.formula("naked", inputs=("a",), output_metric="x")
    def naked(a):
        return 1.0

    with pytest.raises(FormulaError, match="must return a Measure"):
        registry.compute("naked", FY25, {"a": _value(2.0)},
                         model_version=MODEL_VERSION, calculated_at="x")


# --- propagation -----------------------------------------------------------


def test_a_missing_input_short_circuits_before_the_formula_runs():
    """The strongest form of the missing-versus-zero rule: no formula body ever
    sees a missing value, so none can treat one as zero."""
    seen = []
    registry = FormulaRegistry()

    @registry.formula("watch", inputs=("a", "b"), output_metric="x")
    def watch(a, b):
        seen.append((a, b))
        return Measure.of(0.0, unit="RATIO")

    result = registry.compute(
        "watch", FY25,
        {"a": _missing(MissingReason.NOT_REPORTED), "b": _value(2.0)},
        model_version=MODEL_VERSION, calculated_at="x",
    )
    assert seen == [], "the formula was invoked with a missing input"
    assert result.is_missing
    assert result.missing_reason == MissingReason.NOT_REPORTED


def test_the_propagated_reason_is_the_first_in_declared_order():
    """Declared order, not dict order, so the same missing combination always
    reports the same reason."""
    result = _compute(
        "core.ratio",
        numerator=_missing(MissingReason.EXTRACTION_FAILED),
        denominator=_missing(MissingReason.NOT_REPORTED),
    )
    assert result.missing_reason == MissingReason.EXTRACTION_FAILED


def test_a_propagated_missing_is_never_zero():
    result = _compute(
        "core.difference",
        left=_missing(MissingReason.SOURCE_UNAVAILABLE), right=_value(5.0),
    )
    assert result.value is None
    assert result.value != 0


# --- derivation trail ------------------------------------------------------


def test_input_refs_are_populated_by_the_registry():
    result = _compute("core.sum", left=_value(2.0, metric="a"),
                      right=_value(3.0, metric="b"))
    assert [r.ref for r in result.input_refs] == ["REF|a", "REF|b"]


def test_input_refs_follow_declared_order_not_call_order():
    forward = _compute("core.sum", left=_value(2.0, metric="a"),
                       right=_value(3.0, metric="b"))
    backward = REGISTRY.compute(
        "core.sum", FY25,
        {"right": _value(3.0, metric="b"), "left": _value(2.0, metric="a")},
        model_version=MODEL_VERSION, calculated_at="x",
    )
    assert [r.ref for r in forward.input_refs] == [r.ref for r in backward.input_refs]


def test_a_calculated_result_can_be_another_calculation_s_input_ref():
    inner = _compute("core.sum", left=_value(2.0), right=_value(3.0))
    outer = _compute("core.ratio", numerator=inner, denominator=_value(10.0))
    assert outer.input_refs[0].kind == "CALCULATED"
    assert outer.input_refs[0].ref == inner.ref


def test_results_carry_the_model_version_and_a_derived_basis():
    result = _compute("core.ratio", numerator=_value(1.0), denominator=_value(4.0))
    assert result.model_version == MODEL_VERSION
    assert result.basis == ValueBasis.DERIVED
    assert result.value == 0.25


# --- reproducibility -------------------------------------------------------


@pytest.mark.skipif(
    sys.version_info[:2] != (3, 11),
    reason="the fingerprint is an AST dump, whose shape varies between Python "
           "versions; CI pins 3.11, which is where this guard has to hold",
)
def test_the_registry_hash_matches_the_declared_constant():
    """Changing a formula without bumping MODEL_VERSION fails here.

    This is the mechanical half of point-in-time reproducibility: a snapshot
    records the hash it was produced under, so a later run that quietly
    computes something different cannot claim the same model version.
    """
    assert REGISTRY.registry_hash() == FORMULA_REGISTRY_HASH, (
        "the formula registry changed. Bump MODEL_VERSION and update "
        "FORMULA_REGISTRY_HASH in engine/goh_dip_tong/__init__.py "
        f"(now {REGISTRY.registry_hash()})."
    )


def test_the_registry_hash_is_stable_across_calls():
    assert REGISTRY.registry_hash() == REGISTRY.registry_hash()


def test_the_registry_hash_moves_when_a_formula_s_logic_changes():
    left = FormulaRegistry()
    right = FormulaRegistry()

    @left.formula("f", inputs=("a",), output_metric="x")
    def original(a):
        return Measure.of(a.value * 2, unit=a.unit)

    @right.formula("f", inputs=("a",), output_metric="x")
    def altered(a):
        return Measure.of(a.value * 3, unit=a.unit)

    assert left.registry_hash() != right.registry_hash()


def test_the_registry_hash_ignores_comments_and_layout():
    """Reformatting must not force a model-version bump; changing behaviour must."""
    left = FormulaRegistry()
    right = FormulaRegistry()

    @left.formula("f", inputs=("a",), output_metric="x")
    def plain(a):
        return Measure.of(a.value * 2, unit=a.unit)

    @right.formula("f", inputs=("a",), output_metric="x")
    def commented(a):
        # doubling, as above
        return Measure.of(
            a.value * 2,
            unit=a.unit,
        )

    assert left.registry_hash() == right.registry_hash()


def test_every_registered_formula_is_documented():
    """A formula ID appears in published output; an undocumented one leaves a
    reader with a name and nothing else."""
    undocumented = [fid for fid in REGISTRY.ids() if not REGISTRY.get(fid).doc]
    assert undocumented == []
