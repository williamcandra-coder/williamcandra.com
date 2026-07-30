"""Source connectivity smoke test — a diagnostic, not a collector.

Answers exactly one question: *can a GitHub Actions runner reach the official
URL of each configured source?* The build sandbox could not (HTTP 403 on
`CONNECT` to every host), and whether a hosted runner can is unknown. Guessing
is how a project ends up with an adapter that "should work".

WHAT THIS IS NOT
It is not collection, and a successful probe grants nothing. A source is
enabled only by a human editing `sources.yml` **and** recording a dated rights
review in `SOURCE_REGISTER.md`. Every record this module emits carries
``enablesProvider: false`` and a status of ``REACHABLE_UNVALIDATED`` at best —
"the socket opened", not "we may use this".

CONSERVATIVE BY CONSTRUCTION
* one request per provider, never a crawl;
* `HEAD` first, falling back to `GET` only when the server rejects the method;
* redirects are *not* followed — the target is recorded and the probe stops;
* no retries, so a refusal is never re-attempted;
* a pause between providers;
* an identifying User-Agent;
* **no response body is ever read, stored or printed.** Size comes from the
  `Content-Length` header. Nothing else about the payload is retained.

Nothing here bypasses authentication, rate limiting or bot protection. A 401 or
403 is recorded as a finding and the probe moves on — that is the answer, not an
obstacle.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

from ..settings import Settings, get_settings, utc_now_iso

#: The complete outcome vocabulary. Anything outside this set is a bug.
OUTCOMES = (
    "REACHABLE_UNVALIDATED",           # responded; says nothing about rights
    "UNREACHABLE_FROM_GITHUB_ACTIONS",  # could not establish a connection
    "AUTHENTICATION_REQUIRED",          # 401, or an auth challenge
    "ACCESS_CONTROLLED",                # 403 / 429 / bot or geo gate
    "CONTENT_TYPE_UNEXPECTED",          # responded, but not with data
    "NETWORK_ERROR",                    # TLS, DNS or protocol failure
    "NOT_TESTED",                       # no URL, or probing was skipped
)

#: Content types a data source might plausibly return. A landing page returning
#: text/html is not an error — it is a finding worth recording.
DATA_CONTENT_TYPES = (
    "application/json",
    "application/x-ndjson",
    "text/csv",
    "application/xml",
    "text/xml",
    "application/xbrl+xml",
    "text/plain",
)

DEFAULT_TIMEOUT = 15.0
DEFAULT_DELAY = 2.0
USER_AGENT = "goh-dip-tong-connectivity-smoke/1.0 (+https://williamcandra.com)"


class ProbeResponse:
    """The only things we keep from a response. Deliberately not the body."""

    def __init__(self, status: int, headers: Optional[dict] = None):
        self.status = status
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}


def _classify(response: ProbeResponse) -> tuple:
    """Map a response to an outcome. Returns ``(outcome, detail)``."""
    status = response.status
    content_type = (response.headers.get("content-type") or "").split(";")[0].strip().lower()

    if status == 401:
        return "AUTHENTICATION_REQUIRED", "server requires authentication"
    if status in (403, 429, 451):
        return "ACCESS_CONTROLLED", f"server returned {status}"
    if 500 <= status <= 599:
        return "NETWORK_ERROR", f"server error {status}"
    if 300 <= status <= 399:
        # Not followed on purpose: the redirect target is the useful finding.
        return "REACHABLE_UNVALIDATED", f"redirect {status}, target recorded"
    if 200 <= status <= 299:
        if content_type and content_type not in DATA_CONTENT_TYPES:
            return ("CONTENT_TYPE_UNEXPECTED",
                    f"responded {status} with {content_type!r}, not a data type")
        return "REACHABLE_UNVALIDATED", f"responded {status}"
    return "NETWORK_ERROR", f"unexpected status {status}"


def _requests_transport(url: str, timeout: float) -> ProbeResponse:
    """Real network transport. HEAD first; GET without reading the body if the
    server rejects HEAD."""
    import requests

    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    response = requests.head(url, timeout=timeout, allow_redirects=False, headers=headers)
    if response.status_code in (405, 501):
        # Some servers refuse HEAD. Stream the GET and close it without ever
        # reading the body.
        with requests.get(url, timeout=timeout, allow_redirects=False,
                          headers=headers, stream=True) as streamed:
            return ProbeResponse(streamed.status_code, dict(streamed.headers))
    return ProbeResponse(response.status_code, dict(response.headers))


def probe_url(
    provider_id: str,
    url: Optional[str],
    transport: Optional[Callable] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict:
    """Probe one URL. Never raises — a failure is a recorded outcome."""
    record = {
        "providerId": provider_id,
        "url": url,
        "checkedAt": utc_now_iso(),
        "httpStatus": None,
        "redirectTarget": None,
        "contentType": None,
        "responseBytes": None,
        "outcome": "NOT_TESTED",
        "detail": None,
        # Restated on every single record so it cannot be read out of context.
        "enablesProvider": False,
    }

    if not url:
        record["detail"] = "no official_url configured"
        return record

    transport = transport or _requests_transport

    try:
        response = transport(url, timeout)
    except Exception as exc:  # noqa: BLE001 - every failure is a finding
        name = type(exc).__name__
        connection_failures = (
            "ConnectionError", "ConnectTimeout", "ReadTimeout", "Timeout",
            "ProxyError", "NewConnectionError", "MaxRetryError", "socket.timeout",
        )
        if name in connection_failures:
            record["outcome"] = "UNREACHABLE_FROM_GITHUB_ACTIONS"
            record["detail"] = f"{name}: connection could not be established"
        elif name == "ImportError" or name == "ModuleNotFoundError":
            record["outcome"] = "NOT_TESTED"
            record["detail"] = "requests is not installed"
        else:
            record["outcome"] = "NETWORK_ERROR"
            record["detail"] = f"{name}"
        return record

    record["httpStatus"] = response.status
    record["contentType"] = response.headers.get("content-type")
    record["redirectTarget"] = response.headers.get("location")

    length = response.headers.get("content-length")
    if length is not None:
        try:
            record["responseBytes"] = int(length)
        except (TypeError, ValueError):
            record["responseBytes"] = None

    outcome, detail = _classify(response)
    record["outcome"] = outcome
    record["detail"] = detail
    return record


def probe_sources(
    settings: Optional[Settings] = None,
    transport: Optional[Callable] = None,
    delay_seconds: float = DEFAULT_DELAY,
    timeout: float = DEFAULT_TIMEOUT,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """Probe every provider in sources.yml that declares an official URL."""
    settings = settings or get_settings()
    sources = settings.sources()
    providers = sources.get("providers", {}) or {}

    results = []
    for index, provider_id in enumerate(sorted(providers)):
        config = providers[provider_id] or {}
        url = config.get("official_url")

        if config.get("kind") == "fixture":
            results.append({
                "providerId": provider_id, "url": None, "checkedAt": utc_now_iso(),
                "httpStatus": None, "redirectTarget": None, "contentType": None,
                "responseBytes": None, "outcome": "NOT_TESTED",
                "detail": "local fixture; nothing to reach", "enablesProvider": False,
            })
            continue

        if index and delay_seconds:
            sleep(delay_seconds)   # one request at a time, never a burst
        results.append(probe_url(provider_id, url, transport=transport, timeout=timeout))

    reachable = [r for r in results if r["outcome"] == "REACHABLE_UNVALIDATED"]

    return {
        "schemaVersion": "1.0.0",
        "report": "source-connectivity-smoke",
        "generatedAt": utc_now_iso(),
        "notice": (
            "DIAGNOSTIC ONLY. Reachability is not permission. No provider is "
            "enabled by this report — enabling one requires editing "
            "config/goh-dip-tong/sources.yml AND recording a dated rights review "
            "in docs/goh-dip-tong/SOURCE_REGISTER.md. HTTP 200 means a socket "
            "opened, nothing more."
        ),
        "bodiesRetained": False,
        "providersEnabledByThisRun": 0,
        "counts": {
            "probed": len([r for r in results if r["outcome"] != "NOT_TESTED"]),
            "notTested": len([r for r in results if r["outcome"] == "NOT_TESTED"]),
            "reachableUnvalidated": len(reachable),
        },
        "results": sorted(results, key=lambda r: r["providerId"]),
    }


def format_table(report: dict) -> str:
    """Human-readable summary. Contains no response content by construction."""
    lines = [
        f"{'provider':<26} {'status':>6}  {'bytes':>9}  {'content-type':<26} outcome",
        "-" * 110,
    ]
    for row in report["results"]:
        lines.append(
            f"{row['providerId']:<26} "
            f"{str(row['httpStatus'] or '-'):>6}  "
            f"{str(row['responseBytes'] if row['responseBytes'] is not None else '-'):>9}  "
            f"{str((row['contentType'] or '-')[:26]):<26} "
            f"{row['outcome']}"
        )
        if row["redirectTarget"]:
            lines.append(f"{'':<26} → redirect: {row['redirectTarget'][:70]}")
        if row["detail"]:
            lines.append(f"{'':<26}   {row['detail']}")
    return "\n".join(lines)
