"""Missing-versus-zero controls and sign conventions.

This module exists because of one rule from the Stage 1 spec:

    Missing data is null plus a reason; extraction failure must never
    become zero.

Everything here is in service of making that rule mechanically enforceable
rather than a convention people remember most of the time.
"""

from __future__ import annotations

from typing import Any, Optional

from ..contracts.enums import MissingReason, ValueBasis
from ..contracts.records import ContractError, Measure

#: Raw cell values that mean "the issuer did not report this". None of them
#: mean zero. A literal "0" is NOT in this list — a reported zero is real data.
NULL_TOKENS = frozenset(
    {
        "",
        "-",
        "--",
        "—",
        "–",
        "n/a",
        "na",
        "n.a.",
        "nil",
        "none",
        "null",
        "tidak ada",
        "tad",
        "*",
        "n/m",
        "nm",
        "not reported",
        "not available",
    }
)

#: Values that are almost always a failed extraction coerced into a number.
SENTINELS = frozenset({-999999999.0, 999999999.0, -1e308, 1e308})


class MissingZeroViolation(AssertionError):
    """A value that should have been missing was recorded as zero."""


def is_null_token(raw: Any) -> bool:
    if raw is None:
        return True
    if isinstance(raw, str):
        return raw.strip().lower() in NULL_TOKENS
    return False


def coerce(
    raw: Any,
    unit: str,
    currency: Optional[str] = None,
    basis: ValueBasis = ValueBasis.REPORTED,
    on_unparseable: MissingReason = MissingReason.EXTRACTION_FAILED,
) -> Measure:
    """Turn one raw cell into a Measure.

    Three outcomes, and only three:

    * a recognised null token -> missing(NOT_REPORTED)
    * a parseable number      -> present value (including a genuine 0)
    * anything else           -> missing(EXTRACTION_FAILED)

    There is no branch that produces ``0.0`` from unparseable input.
    """
    from ..parsers.guards import parse_numeric

    if is_null_token(raw):
        return Measure.missing(MissingReason.NOT_REPORTED, unit=unit, currency=currency, basis=basis)

    value = parse_numeric(raw)
    if value is None:
        return Measure.missing(on_unparseable, unit=unit, currency=currency, basis=basis)

    if value in SENTINELS:
        return Measure.missing(
            MissingReason.EXTRACTION_FAILED, unit=unit, currency=currency, basis=basis
        )

    return Measure.of(value, unit=unit, currency=currency, basis=basis)


def assert_not_zero_from_missing(raw: Any, measure: Measure, subject: str = "") -> None:
    """Guard the specific bug this whole design is built to prevent.

    If the raw input was absent or unparseable but the resulting Measure is a
    present zero, something coerced missing into zero. Raise loudly.
    """
    if measure.value == 0 and not measure.is_missing and is_null_token(raw):
        raise MissingZeroViolation(
            f"{subject or 'value'}: raw input {raw!r} is a null token but was "
            f"recorded as 0 — missing must never become zero"
        )


def missing_because_rights(unit: str = "IDR", currency: Optional[str] = None) -> Measure:
    """A value that exists but may not be used. Distinguishing this from
    NOT_REPORTED matters: one is a data gap, the other is a licensing gap."""
    return Measure.missing(MissingReason.RIGHTS_WITHHELD, unit=unit, currency=currency)


def missing_because_source_down(unit: str = "IDR", currency: Optional[str] = None) -> Measure:
    return Measure.missing(MissingReason.SOURCE_UNAVAILABLE, unit=unit, currency=currency)


def apply_sign_convention(measure: Measure, convention: str) -> Measure:
    """Normalize a value's sign to the convention declared in metrics.yml.

    Signs are only ever changed through this function, so a sign flip is always
    traceable to a declared convention rather than an ad-hoc ``abs()`` or
    ``-x`` somewhere in a parser.
    """
    if measure.is_missing:
        return measure

    value = measure.value
    if convention == "positive_magnitude":
        value = abs(value)
    elif convention == "negative_outflow":
        value = -abs(value)
    elif convention in ("signed", "positive", ""):
        pass
    else:
        raise ContractError(f"unknown sign convention: {convention!r}")

    return Measure(
        value=value,
        unit=measure.unit,
        currency=measure.currency,
        scale=measure.scale,
        missing_reason=None,
        basis=measure.basis,
        quality_status=measure.quality_status,
    )


def completeness(measures: list) -> float:
    """Share of measures that carry a real value. 1.0 for an empty input, since
    "nothing was required" is not incompleteness."""
    if not measures:
        return 1.0
    present = sum(1 for m in measures if not m.is_missing)
    return present / len(measures)
