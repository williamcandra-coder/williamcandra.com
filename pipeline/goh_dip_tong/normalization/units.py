"""Unit, scale and currency normalization.

Indonesian filings routinely report in millions or billions of rupiah, and some
IDX30 issuers report in USD. Every value is normalized to base units on ingest
while the scale as reported is retained on the record, so a reader can always
reconstruct what the filing literally said.

There is deliberately no FX conversion here. Converting USD reporters into IDR
requires a rate, a rate date and a documented source, none of which Stage 1 has.
A currency mismatch is surfaced as a fact for the engine to handle, not silently
converted.
"""

from __future__ import annotations

from typing import Optional

from ..contracts.enums import SCALE_FACTORS, MissingReason, Scale
from ..contracts.records import Measure

CURRENCIES = ("IDR", "USD")

_SCALE_ALIASES = {
    "": Scale.UNITS,
    "1": Scale.UNITS,
    "unit": Scale.UNITS,
    "units": Scale.UNITS,
    "full": Scale.UNITS,
    "rupiah": Scale.UNITS,
    "thousand": Scale.THOUSANDS,
    "thousands": Scale.THOUSANDS,
    "ribu": Scale.THOUSANDS,
    "000": Scale.THOUSANDS,
    "million": Scale.MILLIONS,
    "millions": Scale.MILLIONS,
    "juta": Scale.MILLIONS,
    "mn": Scale.MILLIONS,
    "billion": Scale.BILLIONS,
    "billions": Scale.BILLIONS,
    "miliar": Scale.BILLIONS,
    "milyar": Scale.BILLIONS,
    "bn": Scale.BILLIONS,
    "trillion": Scale.TRILLIONS,
    "trillions": Scale.TRILLIONS,
    "triliun": Scale.TRILLIONS,
    "tn": Scale.TRILLIONS,
}


class UnitError(ValueError):
    """An unrecognised unit, scale or currency."""


def parse_scale(raw: Optional[str]) -> Scale:
    if raw is None:
        return Scale.UNITS
    if isinstance(raw, Scale):
        return raw
    if isinstance(raw, (int, float)):
        for scale, factor in SCALE_FACTORS.items():
            if factor == int(raw):
                return scale
        raise UnitError(f"unrecognised numeric scale: {raw!r}")
    key = str(raw).strip().lower()
    try:
        return Scale(key.upper())
    except ValueError:
        pass
    if key in _SCALE_ALIASES:
        return _SCALE_ALIASES[key]
    raise UnitError(f"unrecognised scale: {raw!r}")


def parse_currency(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    code = str(raw).strip().upper()
    if code in ("RP", "IDR", "RUPIAH"):
        return "IDR"
    if code in ("USD", "US$", "$", "DOLLAR"):
        return "USD"
    if code == "":
        return None
    raise UnitError(f"unsupported currency: {raw!r}")


def to_base_units(value: Optional[float], scale: Scale) -> Optional[float]:
    """Multiply out the reporting scale.

    A None value stays None. Scaling a missing value would be how a missing
    figure quietly becomes 0.0 * factor.
    """
    if value is None:
        return None
    return float(value) * SCALE_FACTORS[Scale(scale)]


def normalize_measure(
    raw_value: Optional[float],
    unit: str,
    currency: Optional[str] = None,
    scale: Optional[str] = None,
    missing_reason: Optional[MissingReason] = None,
    basis=None,
) -> Measure:
    """Build a Measure with the value already in base units.

    When ``raw_value`` is None a reason is required; the caller must have one,
    because "we don't know why it's missing" is itself a data-quality finding.
    """
    parsed_scale = parse_scale(scale)
    parsed_currency = parse_currency(currency)

    kwargs = {} if basis is None else {"basis": basis}

    if raw_value is None:
        return Measure.missing(
            missing_reason or MissingReason.NOT_REPORTED,
            unit=unit,
            currency=parsed_currency,
            **kwargs,
        )

    return Measure(
        value=to_base_units(raw_value, parsed_scale),
        unit=unit,
        currency=parsed_currency,
        scale=parsed_scale,
        **kwargs,
    )


def percent_to_ratio(value: Optional[float]) -> Optional[float]:
    return None if value is None else value / 100.0


def ratio_to_percent(value: Optional[float]) -> Optional[float]:
    return None if value is None else value * 100.0


def assert_same_currency(measures: list) -> Optional[str]:
    """Return the shared currency, or raise if the inputs disagree.

    Arithmetic across currencies without an explicit, dated FX rate is a bug.
    """
    currencies = {m.currency for m in measures if m.currency is not None}
    if len(currencies) > 1:
        raise UnitError(
            f"cannot combine measures across currencies: {sorted(currencies)}; "
            f"an explicit, dated FX rate is required and Stage 1 has no rate source"
        )
    return next(iter(currencies), None)
