"""Payload guards: is this actually data?

The single most common silent-corruption mode for a scraped source is that the
server returns HTTP 200 with an error page, a login wall, or a bot-check
interstitial, and the pipeline happily saves it as "data". Every payload passes
through here before a parser ever sees it.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

#: Markers that mean "this is a web page, not a dataset". Kept in code as well
#: as guard.yml because parsers must be able to reject a payload even when no
#: config has been loaded.
HTML_MARKERS = (
    "<!doctype html",
    "<html",
    "<head>",
    "<body",
    "<?xml-stylesheet",
)

BLOCK_PAGE_MARKERS = (
    "access denied",
    "403 forbidden",
    "404 not found",
    "just a moment",
    "enable javascript and cookies to continue",
    "are you a robot",
    "rate limit exceeded",
    "service unavailable",
    "please verify you are a human",
)

DATA_MEDIA_TYPES = (
    "application/json",
    "application/x-ndjson",
    "text/csv",
    "text/plain",
    "application/xml",
    "text/xml",
    "application/xbrl+xml",
)


class PayloadRejected(ValueError):
    """The payload is not data. Never downgrade this to a warning: a saved
    error page is worse than no data because it looks like a successful run."""


def _as_text(content: Any, limit: int = 4096) -> str:
    if isinstance(content, bytes):
        return content[:limit].decode("utf-8", errors="replace")
    if isinstance(content, str):
        return content[:limit]
    return ""


def looks_like_html(content: Any) -> bool:
    head = _as_text(content).lstrip().lower()
    return any(head.startswith(m) or m in head[:512] for m in HTML_MARKERS)


def looks_like_block_page(content: Any) -> bool:
    text = _as_text(content).lower()
    return any(m in text for m in BLOCK_PAGE_MARKERS)


def assert_is_data(
    content: Any,
    media_type: Optional[str] = None,
    expect: Optional[str] = None,
    source: str = "<payload>",
) -> None:
    """Raise :class:`PayloadRejected` unless this payload can plausibly be data.

    ``expect`` is one of ``json``, ``csv``, ``xml`` when the caller knows what
    it asked for.
    """
    if content is None:
        raise PayloadRejected(f"{source}: empty payload (None)")

    if isinstance(content, (bytes, str)) and len(content) == 0:
        raise PayloadRejected(f"{source}: empty payload (zero length)")

    # An HTML payload is only acceptable when HTML was explicitly expected,
    # which no Stage 1 provider does.
    if expect != "html" and looks_like_html(content):
        raise PayloadRejected(
            f"{source}: response is an HTML document, not data — this is "
            f"almost always an error page, login wall or bot check saved as data"
        )

    if looks_like_block_page(content):
        raise PayloadRejected(
            f"{source}: response body matches a known block/error page pattern"
        )

    if media_type:
        base = media_type.split(";")[0].strip().lower()
        if base and base not in DATA_MEDIA_TYPES:
            raise PayloadRejected(
                f"{source}: unexpected content type {base!r}; "
                f"expected one of {', '.join(DATA_MEDIA_TYPES)}"
            )

    if expect == "json":
        text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else content
        if isinstance(text, str):
            stripped = text.lstrip()
            if stripped and stripped[0] not in "[{":
                raise PayloadRejected(
                    f"{source}: expected JSON but body starts with {stripped[:40]!r}"
                )
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                raise PayloadRejected(f"{source}: expected JSON, parse failed: {exc}") from exc


_NUMERIC_RE = re.compile(r"^-?\d+(\.\d+)?([eE][+-]?\d+)?$")


def is_numeric_text(text: Any) -> bool:
    """Whether a raw cell is a number.

    Anything that is not — an empty string, ``-``, ``n/a``, a footnote marker —
    is treated as missing by the caller, never coerced to 0.
    """
    if text is None:
        return False
    if isinstance(text, (int, float)) and not isinstance(text, bool):
        return True
    if not isinstance(text, str):
        return False
    cleaned = text.strip().replace(",", "").replace(" ", "")
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    return bool(_NUMERIC_RE.match(cleaned))


def parse_numeric(text: Any) -> Optional[float]:
    """Return a float, or None when the cell is not a number.

    Handles thousands separators and accounting-style parentheses for
    negatives. Returning None rather than 0.0 for unparseable input is the
    whole point of this function.
    """
    if not is_numeric_text(text):
        return None
    if isinstance(text, (int, float)):
        return float(text)
    cleaned = text.strip().replace(",", "").replace(" ", "")
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    try:
        return float(cleaned)
    except ValueError:  # pragma: no cover - guarded by is_numeric_text
        return None
