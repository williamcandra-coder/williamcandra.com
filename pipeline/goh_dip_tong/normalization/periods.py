"""Fiscal-period normalization.

Indonesian interim filings are cumulative: the "Q3" report contains nine months,
not three. Treating a year-to-date figure as a standalone quarter is one of the
easiest ways to be confidently wrong, so YTD and standalone periods are distinct
types here and conversion between them is explicit.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Optional, Tuple

from ..contracts.enums import PeriodType

_QUARTER_END = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
_QUARTER_START = {1: (1, 1), 2: (4, 1), 3: (7, 1), 4: (10, 1)}

YTD_TO_QUARTER = {
    PeriodType.YTD_Q1: 1,
    PeriodType.YTD_Q2: 2,
    PeriodType.YTD_Q3: 3,
}
QUARTER_TO_YTD = {v: k for k, v in YTD_TO_QUARTER.items()}

_PATTERNS = (
    (re.compile(r"^FY[-_ ]?(\d{4})$", re.I), lambda m: (PeriodType.FY, int(m.group(1)), None)),
    (re.compile(r"^(\d{4})[-_ ]?FY$", re.I), lambda m: (PeriodType.FY, int(m.group(1)), None)),
    (re.compile(r"^Q([1-4])[-_ ](\d{4})$", re.I), lambda m: (PeriodType(f"Q{m.group(1)}"), int(m.group(2)), int(m.group(1)))),
    (re.compile(r"^(\d{4})[-_ ]?Q([1-4])$", re.I), lambda m: (PeriodType(f"Q{m.group(2)}"), int(m.group(1)), int(m.group(2)))),
    (re.compile(r"^YTD[-_ ]?Q([1-3])[-_ ](\d{4})$", re.I), lambda m: (PeriodType(f"YTD_Q{m.group(1)}"), int(m.group(2)), int(m.group(1)))),
    (re.compile(r"^(\d{4})[-_ ]?YTD[-_ ]?Q([1-3])$", re.I), lambda m: (PeriodType(f"YTD_Q{m.group(2)}"), int(m.group(1)), int(m.group(2)))),
    (re.compile(r"^H([12])[-_ ](\d{4})$", re.I), lambda m: (PeriodType(f"H{m.group(1)}"), int(m.group(2)), None)),
    (re.compile(r"^TTM[-_ ](\d{4})[-_ ]?Q?([1-4])?$", re.I), lambda m: (PeriodType.TTM, int(m.group(1)), None)),
)


class PeriodError(ValueError):
    """An unparseable or self-contradictory period reference."""


def parse_period_ref(ref: str) -> Tuple[PeriodType, int, Optional[int]]:
    """``"Q3-2025"`` -> ``(PeriodType.Q3, 2025, 3)``.

    Raises rather than guessing. A period we cannot read is a data problem to
    surface, not one to paper over with a default.
    """
    if not ref or not isinstance(ref, str):
        raise PeriodError(f"empty period reference: {ref!r}")
    text = ref.strip()
    for pattern, build in _PATTERNS:
        match = pattern.match(text)
        if match:
            return build(match)
    raise PeriodError(f"unrecognised period reference: {ref!r}")


def period_bounds(
    period_type: PeriodType, fiscal_year: int, quarter: Optional[int] = None
) -> Tuple[Optional[str], str]:
    """Return ``(period_start, period_end)`` as ISO dates.

    ``period_start`` is None for instants, which is exactly what the
    financial-fact schema requires.
    """
    period_type = PeriodType(period_type)

    if period_type == PeriodType.POINT_IN_TIME:
        return None, f"{fiscal_year}-12-31"

    if period_type == PeriodType.FY:
        return f"{fiscal_year}-01-01", f"{fiscal_year}-12-31"

    if period_type == PeriodType.TTM:
        if not quarter:
            return f"{fiscal_year}-01-01", f"{fiscal_year}-12-31"
        # The window is the four standalone quarters ending at (fiscal_year,
        # quarter); its start is the start of the first of those quarters.
        first_year, first_quarter = ttm_window(fiscal_year, quarter)[0]
        sm, sd = _QUARTER_START[first_quarter]
        em, ed = _QUARTER_END[quarter]
        return (
            date(first_year, sm, sd).isoformat(),
            date(fiscal_year, em, ed).isoformat(),
        )

    if period_type in (PeriodType.H1, PeriodType.H2):
        if period_type == PeriodType.H1:
            return f"{fiscal_year}-01-01", f"{fiscal_year}-06-30"
        return f"{fiscal_year}-07-01", f"{fiscal_year}-12-31"

    if period_type in YTD_TO_QUARTER:
        q = YTD_TO_QUARTER[period_type]
        m, d = _QUARTER_END[q]
        return f"{fiscal_year}-01-01", f"{fiscal_year}-{m:02d}-{d:02d}"

    q = int(str(period_type)[-1])
    sm, sd = _QUARTER_START[q]
    em, ed = _QUARTER_END[q]
    return f"{fiscal_year}-{sm:02d}-{sd:02d}", f"{fiscal_year}-{em:02d}-{ed:02d}"


def normalize_period(ref: str) -> dict:
    """One call from a raw period string to the fields a fact record needs."""
    period_type, fiscal_year, quarter = parse_period_ref(ref)
    start, end = period_bounds(period_type, fiscal_year, quarter)
    return {
        "periodType": str(period_type),
        "periodStart": start,
        "periodEnd": end,
        "fiscalYear": fiscal_year,
    }


def is_cumulative(period_type: PeriodType) -> bool:
    """Whether the period is year-to-date rather than standalone."""
    return PeriodType(period_type) in YTD_TO_QUARTER


def standalone_from_ytd(
    current_ytd: Optional[float], prior_ytd: Optional[float]
) -> Optional[float]:
    """Derive a standalone quarter by differencing cumulative figures.

    Returns None if either input is missing. It deliberately does NOT treat a
    missing prior period as zero — that would silently report the full
    year-to-date figure as a single quarter.
    """
    if current_ytd is None or prior_ytd is None:
        return None
    return current_ytd - prior_ytd


def ttm_window(fiscal_year: int, quarter: int) -> list:
    """The four standalone quarters that make up a TTM ending at this quarter."""
    out = []
    y, q = fiscal_year, quarter
    for _ in range(4):
        out.append((y, q))
        q -= 1
        if q == 0:
            q = 4
            y -= 1
    return list(reversed(out))
