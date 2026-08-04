"""Arithmetic that cannot conceal a failure.

Stage 1's rule was *missing must never become zero*. Its derived-metric
counterpart is *a division that cannot be performed must not return a number* —
not ``inf``, not ``nan``, not a zero from a swallowed exception. Both are the
same failure wearing different clothes: a value that looks computed and is not.

Every helper here returns a :class:`Measure`, so the only way to express "this
could not be computed" is with a stated reason.

Note on determinism: sums iterate over an explicitly ordered sequence and never
over a set or a dict's insertion order. Floating-point addition is not
associative, so an unordered sum is a value that depends on how the collection
happened to be built.
"""

from __future__ import annotations

import math
from typing import Optional, Sequence

from pipeline.goh_dip_tong.contracts.enums import (
    MissingReason,
    QualityStatus,
    ValueBasis,
)
from pipeline.goh_dip_tong.contracts.records import Measure
from pipeline.goh_dip_tong.normalization.units import assert_same_currency

from ..contracts.registry import REGISTRY


def _derived(
    value: float,
    unit: str,
    currency: Optional[str] = None,
    quality: QualityStatus = QualityStatus.UNVALIDATED,
) -> Measure:
    """A present, derived value.

    ``inf`` and ``nan`` are rejected here rather than downstream: JSON cannot
    represent them (Stage 1's writers pass ``allow_nan=False``), so a NaN that
    escaped this far would fail at serialisation with no indication of which
    calculation produced it.
    """
    if not math.isfinite(value):
        return Measure.missing(
            MissingReason.UNDEFINED_DENOMINATOR, unit=unit, currency=currency,
            basis=ValueBasis.DERIVED,
        )
    return Measure(
        value=float(value),
        unit=unit,
        currency=currency,
        basis=ValueBasis.DERIVED,
        quality_status=quality,
    )


def _worst_quality(*measures: Measure) -> QualityStatus:
    """Quality propagates downward: a derived value is never sounder than its
    weakest input. Ordered worst-first so the first hit wins."""
    order = (
        QualityStatus.INVALID,
        QualityStatus.SUSPECT,
        QualityStatus.UNVALIDATED,
        QualityStatus.VALID,
    )
    for status in order:
        if any(m.quality_status == status for m in measures):
            return status
    return QualityStatus.UNVALIDATED


# ---------------------------------------------------------------------------
# primitives
# ---------------------------------------------------------------------------


def safe_div(
    numerator: Measure,
    denominator: Measure,
    unit: str = "RATIO",
    allow_negative_denominator: bool = False,
) -> Measure:
    """Divide, or state why not.

    A zero denominator is the obvious case. A *negative* one is the subtle case
    and is refused by default: a "return on equity" computed on negative book
    value is arithmetically fine and financially meaningless, and it produces a
    plausible-looking positive number when both terms are negative. Models that
    genuinely want a signed denominator must say so.
    """
    if numerator.is_missing:
        return Measure.missing(
            numerator.missing_reason, unit=unit, basis=ValueBasis.DERIVED
        )
    if denominator.is_missing:
        return Measure.missing(
            denominator.missing_reason, unit=unit, basis=ValueBasis.DERIVED
        )

    if denominator.value == 0:
        return Measure.missing(
            MissingReason.UNDEFINED_DENOMINATOR, unit=unit, basis=ValueBasis.DERIVED
        )
    if denominator.value < 0 and not allow_negative_denominator:
        return Measure.missing(
            MissingReason.UNDEFINED_DENOMINATOR, unit=unit, basis=ValueBasis.DERIVED
        )

    return _derived(
        numerator.value / denominator.value,
        unit=unit,
        currency=None if unit == "RATIO" else numerator.currency,
        quality=_worst_quality(numerator, denominator),
    )


def safe_sub(left: Measure, right: Measure) -> Measure:
    """Subtract, refusing to combine currencies without a dated rate."""
    if left.is_missing:
        return Measure.missing(left.missing_reason, unit=left.unit,
                               currency=left.currency, basis=ValueBasis.DERIVED)
    if right.is_missing:
        return Measure.missing(right.missing_reason, unit=left.unit,
                               currency=left.currency, basis=ValueBasis.DERIVED)
    currency = assert_same_currency([left, right])
    return _derived(left.value - right.value, unit=left.unit, currency=currency,
                    quality=_worst_quality(left, right))


def safe_add(left: Measure, right: Measure) -> Measure:
    if left.is_missing:
        return Measure.missing(left.missing_reason, unit=left.unit,
                               currency=left.currency, basis=ValueBasis.DERIVED)
    if right.is_missing:
        return Measure.missing(right.missing_reason, unit=left.unit,
                               currency=left.currency, basis=ValueBasis.DERIVED)
    currency = assert_same_currency([left, right])
    return _derived(left.value + right.value, unit=left.unit, currency=currency,
                    quality=_worst_quality(left, right))


def safe_mean(measures: Sequence[Measure]) -> Measure:
    """Arithmetic mean over an ordered sequence.

    An empty sequence is ``INSUFFICIENT_PERIODS``, not zero — averaging nothing
    is the "missing becomes zero" bug in aggregate form. Any missing member
    makes the whole average missing rather than quietly averaging the rest,
    which would silently change the denominator.
    """
    measures = list(measures)
    if not measures:
        return Measure.missing(
            MissingReason.INSUFFICIENT_PERIODS, unit="IDR", basis=ValueBasis.DERIVED
        )
    for measure in measures:
        if measure.is_missing:
            return Measure.missing(
                measure.missing_reason, unit=measure.unit,
                currency=measure.currency, basis=ValueBasis.DERIVED,
            )
    currency = assert_same_currency(measures)
    total = 0.0
    for measure in measures:  # ordered: float addition is not associative
        total += measure.value
    return _derived(total / len(measures), unit=measures[0].unit, currency=currency,
                    quality=_worst_quality(*measures))


# ---------------------------------------------------------------------------
# registered formulas
#
# Generic primitives only. Model-specific derivations and all valuation
# mathematics belong to later slices; registering them here early would create
# formula IDs whose behaviour is not yet tested.
# ---------------------------------------------------------------------------


@REGISTRY.formula("core.ratio", inputs=("numerator", "denominator"),
                  output_metric="ratio")
def formula_ratio(numerator: Measure, denominator: Measure) -> Measure:
    """Dimensionless ratio of two measures. Undefined denominator refuses."""
    return safe_div(numerator, denominator, unit="RATIO")


@REGISTRY.formula("core.difference", inputs=("left", "right"),
                  output_metric="difference")
def formula_difference(left: Measure, right: Measure) -> Measure:
    """left - right, in left's unit."""
    return safe_sub(left, right)


@REGISTRY.formula("core.sum", inputs=("left", "right"), output_metric="sum")
def formula_sum(left: Measure, right: Measure) -> Measure:
    """left + right, in left's unit."""
    return safe_add(left, right)


@REGISTRY.formula("core.mean2", inputs=("opening", "closing"),
                  output_metric="average")
def formula_mean2(opening: Measure, closing: Measure) -> Measure:
    """Average of an opening and closing balance.

    Balance-sheet stocks averaged against income-statement flows: using the
    closing balance alone overstates the denominator of a growing bank's ROE.
    """
    return safe_mean([opening, closing])


@REGISTRY.formula("core.per_share", inputs=("total", "shares"),
                  output_metric="per_share")
def formula_per_share(total: Measure, shares: Measure) -> Measure:
    """A currency total divided by a share count.

    A zero or negative share count is refused rather than producing a
    per-share figure of infinity.
    """
    result = safe_div(total, shares, unit=total.unit)
    if result.is_missing:
        return result
    return _derived(result.value, unit=total.unit, currency=total.currency,
                    quality=result.quality_status)


__all__ = [
    "safe_div",
    "safe_sub",
    "safe_add",
    "safe_mean",
]
