"""Data-quality checks and the quality report.

These are the checks listed in spec section 1.8 for `gdt-data-quality.yml`,
plus the per-dataset checks the collectors run before promotion.

A note on counting constituents: the spec is explicit that the active IDX30
count must be verified *against the authoritative effective list*, not against a
hard-coded 30. An index is 30 members by convention, not by law — mid-period
suspensions and corporate actions do produce off-count periods, and a pipeline
that treats 29 as an error will fail on exactly the day it matters most. So the
count is compared to what the source declared, and a bare deviation from 30 is a
warning that asks a human to look, never a hard failure.
"""

from __future__ import annotations

import json

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..contracts.enums import Outcome, QualityStatus, Severity, WriteMode
from ..contracts.records import ValidationIssue, ValidationReport
from ..publishing.writers import (
    VOLATILE_FIELDS,
    canonical_json,
    read_json,
    write_document_if_changed,
    write_json_if_changed,
)
from ..settings import Settings, get_settings, utc_now_iso

#: Index size by convention. Used only to phrase a warning, never to fail.
CONVENTIONAL_INDEX_SIZE = 30


def _issue(check_id, outcome, message, severity=Severity.CRITICAL, subject=None,
           observed=None, expected=None) -> ValidationIssue:
    return ValidationIssue(
        check_id=check_id, severity=severity, outcome=outcome, message=message,
        subject=subject, observed=observed, expected=expected,
    )


# ---------------------------------------------------------------------------
# Universe checks
# ---------------------------------------------------------------------------


def check_ticker_uniqueness(constituents: list) -> ValidationReport:
    report = ValidationReport()
    tickers = [c.get("ticker") for c in constituents]
    duplicates = sorted({t for t, n in Counter(tickers).items() if n > 1})
    report.add(
        _issue(
            "universe.ticker_unique",
            Outcome.FAIL if duplicates else Outcome.PASS,
            f"duplicate tickers: {duplicates}" if duplicates else
            f"all {len(tickers)} tickers are unique",
            severity=Severity.CRITICAL if duplicates else Severity.INFO,
            observed=duplicates or len(tickers),
        )
    )
    return report


def check_universe_count(constituents: list, source_declared: Optional[int] = None) -> ValidationReport:
    report = ValidationReport()
    active = [c for c in constituents if c.get("active")]
    count = len(active)

    if source_declared is not None:
        matches = count == source_declared
        report.add(
            _issue(
                "universe.count_matches_source",
                Outcome.PASS if matches else Outcome.FAIL,
                f"active constituents ({count}) "
                + ("matches" if matches else "does NOT match")
                + f" the count declared by the source ({source_declared})",
                severity=Severity.CRITICAL,
                observed=count,
                expected=source_declared,
            )
        )
    else:
        report.add(
            _issue(
                "universe.count_matches_source",
                Outcome.SKIP,
                "source did not declare a constituent count; cannot cross-check",
                severity=Severity.WARNING,
                observed=count,
            )
        )

    if count != CONVENTIONAL_INDEX_SIZE:
        report.add(
            _issue(
                "universe.count_conventional",
                Outcome.FAIL,
                f"active count is {count}, not the conventional {CONVENTIONAL_INDEX_SIZE} — "
                f"legitimate mid-period (suspension, corporate action), but review it",
                severity=Severity.WARNING,
                observed=count,
                expected=CONVENTIONAL_INDEX_SIZE,
            )
        )
    else:
        report.add(
            _issue(
                "universe.count_conventional", Outcome.PASS,
                f"active count is {count}", severity=Severity.INFO, observed=count,
            )
        )
    return report


def check_effective_dates(document: dict) -> ValidationReport:
    report = ValidationReport()
    effective_from = document.get("effectiveFrom")
    effective_to = document.get("effectiveTo")

    if effective_from and effective_to and effective_to < effective_from:
        report.add(
            _issue(
                "universe.effective_range", Outcome.FAIL,
                f"effectiveTo ({effective_to}) precedes effectiveFrom ({effective_from})",
            )
        )
    else:
        report.add(
            _issue(
                "universe.effective_range", Outcome.PASS,
                f"effective range {effective_from} → {effective_to or 'current'}",
                severity=Severity.INFO,
            )
        )

    bad_entries = [
        c["ticker"] for c in document.get("constituents", [])
        if c.get("enteredAt") and effective_to and c["enteredAt"] > effective_to
    ]
    report.add(
        _issue(
            "universe.entered_within_range",
            Outcome.FAIL if bad_entries else Outcome.PASS,
            f"constituents entered after the period ended: {bad_entries}" if bad_entries
            else "all enteredAt dates fall within the effective period",
            severity=Severity.CRITICAL if bad_entries else Severity.INFO,
        )
    )
    return report


def check_model_mapping(constituents: list, models_config: dict) -> ValidationReport:
    """Every constituent maps to a supported family, or is ONBOARDING."""
    report = ValidationReport()
    families = models_config.get("model_families", {}) or {}
    problems = []

    for c in constituents:
        family = c.get("modelFamily")
        coverage = c.get("coverageStatus")
        ticker = c.get("ticker")

        if family is None:
            if coverage != "ONBOARDING":
                problems.append(f"{ticker}: no model family but coverageStatus={coverage}")
            continue
        if family not in families:
            problems.append(f"{ticker}: model family {family!r} is not declared in models.yml")
        elif not families[family].get("supported", False) and coverage != "ONBOARDING":
            problems.append(
                f"{ticker}: family {family!r} is declared but unsupported, so "
                f"coverageStatus must be ONBOARDING (got {coverage})"
            )

    for problem in problems:
        report.add(_issue("universe.model_mapping", Outcome.FAIL, problem, subject=problem.split(":")[0]))
    if not problems:
        report.add(
            _issue(
                "universe.model_mapping", Outcome.PASS,
                f"all {len(constituents)} constituents have a coherent model/coverage pairing",
                severity=Severity.INFO,
            )
        )
    return report


def check_category_coverage(constituents: list) -> ValidationReport:
    report = ValidationReport()
    onboarding = sorted(c["ticker"] for c in constituents if c.get("coverageStatus") == "ONBOARDING")
    report.add(
        _issue(
            "universe.onboarding", Outcome.PASS,
            f"{len(onboarding)} constituents awaiting a model: {onboarding}" if onboarding
            else "no constituents are awaiting a model",
            severity=Severity.WARNING if onboarding else Severity.INFO,
            observed=onboarding,
        )
    )
    return report


# ---------------------------------------------------------------------------
# Dataset checks
# ---------------------------------------------------------------------------


def check_missing_vs_zero(records: list, value_field: str = "value",
                          reason_field: str = "missingReason") -> ValidationReport:
    """The central control, applied to a whole dataset.

    Two ways to fail: a null with no reason, or a reason attached to a value
    that is actually present.
    """
    report = ValidationReport()
    unexplained = []
    contradictory = []

    for record in records:
        value = record.get(value_field, "__absent__")
        reason = record.get(reason_field)
        if value is None and not reason:
            unexplained.append(record.get("ticker") or record.get("factKey") or "?")
        elif value is not None and value != "__absent__" and reason:
            contradictory.append(record.get("ticker") or record.get("factKey") or "?")

    for subject in unexplained[:20]:
        report.add(
            _issue(
                "data.missing_has_reason", Outcome.FAIL,
                "null value with no missingReason — a missing value must always say why",
                subject=subject,
            )
        )
    for subject in contradictory[:20]:
        report.add(
            _issue(
                "data.value_not_also_missing", Outcome.FAIL,
                "record has both a value and a missingReason",
                subject=subject,
            )
        )
    if not unexplained and not contradictory:
        report.add(
            _issue(
                "data.missing_vs_zero", Outcome.PASS,
                f"{len(records)} records: every null carries a reason and no value "
                f"contradicts one",
                severity=Severity.INFO,
            )
        )
    return report


def check_duplicates(records: list, key_fields: tuple) -> ValidationReport:
    report = ValidationReport()
    keys = [tuple(r.get(f) for f in key_fields) for r in records]
    duplicates = sorted({k for k, n in Counter(keys).items() if n > 1})
    report.add(
        _issue(
            "data.no_duplicates",
            Outcome.FAIL if duplicates else Outcome.PASS,
            f"{len(duplicates)} duplicate keys on {key_fields}: {duplicates[:5]}"
            if duplicates else f"no duplicate keys across {len(records)} records on {key_fields}",
            severity=Severity.CRITICAL if duplicates else Severity.INFO,
            observed=len(duplicates),
            expected=0,
        )
    )
    return report


def check_trading_dates(records: list) -> ValidationReport:
    """Weekend dates and future dates are both signs of a bad parse."""
    report = ValidationReport()
    today = datetime.now(timezone.utc).date().isoformat()
    weekend, future = [], []

    for record in records:
        raw = record.get("tradingDate")
        if not raw:
            continue
        try:
            day = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            report.add(
                _issue("data.trading_date_format", Outcome.FAIL,
                       f"unparseable trading date: {raw!r}", subject=record.get("ticker"))
            )
            continue
        if day.weekday() >= 5:
            weekend.append(f"{record.get('ticker')}@{raw}")
        if raw > today:
            future.append(f"{record.get('ticker')}@{raw}")

    for subject in weekend[:10]:
        report.add(
            _issue("data.trading_date_weekend", Outcome.FAIL,
                   f"{subject}: trading date falls on a weekend", severity=Severity.WARNING)
        )
    for subject in future[:10]:
        report.add(
            _issue("data.trading_date_future", Outcome.FAIL,
                   f"{subject}: trading date is in the future", severity=Severity.CRITICAL)
        )
    if not weekend and not future:
        report.add(
            _issue("data.trading_dates", Outcome.PASS,
                   f"{len(records)} trading dates are plausible", severity=Severity.INFO)
        )
    return report


def check_price_jumps(records: list, threshold: float = 0.35) -> ValidationReport:
    """Flag day-on-day moves large enough to be an unadjusted corporate action.

    A warning, not a failure: real 35% days happen. But an unflagged one next to
    a split is usually a missing adjustment.
    """
    report = ValidationReport()
    by_ticker: dict = {}
    for record in records:
        by_ticker.setdefault(record.get("ticker"), []).append(record)

    jumps = []
    for ticker, rows in by_ticker.items():
        rows = sorted(rows, key=lambda r: r.get("tradingDate") or "")
        previous = None
        for row in rows:
            close = row.get("close")
            if close is None or previous is None or previous == 0:
                previous = close if close else previous
                continue
            change = abs(close - previous) / previous
            if change > threshold and row.get("corporateActionFlag", "NONE") == "NONE":
                jumps.append(f"{ticker}@{row.get('tradingDate')} {change:+.1%}")
            previous = close

    for jump in jumps[:15]:
        report.add(
            _issue("data.price_jump", Outcome.FAIL,
                   f"{jump}: move over {threshold:.0%} with no corporate-action flag",
                   severity=Severity.WARNING)
        )
    if not jumps:
        report.add(
            _issue("data.price_jump", Outcome.PASS,
                   "no unexplained large price moves", severity=Severity.INFO)
        )
    return report


def check_source_staleness(sources_config: dict, last_success: dict,
                           max_age_days: float = 14.0,
                           untrackable: Optional[set] = None) -> ValidationReport:
    """Flag enabled sources whose newest committed record is too old.

    ``last_success`` comes from :func:`derive_last_success`, which reads the
    data itself rather than a side-car timestamp file. A source whose rights
    forbid committing leaves no trace in the repository, so it is reported as
    untrackable rather than stale — claiming a provider is stale when policy is
    the reason nothing was committed would be misleading.
    """
    report = ValidationReport()
    now = datetime.now(timezone.utc)
    untrackable = untrackable or set()
    stale = []

    for provider_id, config in sorted((sources_config.get("providers") or {}).items()):
        if not config.get("enabled"):
            continue
        if provider_id in untrackable:
            report.add(
                _issue("sources.staleness", Outcome.SKIP,
                       f"{provider_id}: output is not committed (rights do not permit "
                       f"it), so freshness cannot be derived from the repository",
                       severity=Severity.INFO, subject=provider_id)
            )
            continue
        stamp = last_success.get(provider_id)
        if not stamp:
            stale.append((provider_id, None))
            continue
        try:
            age = (now - datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc)).total_seconds() / 86400
        except ValueError:
            stale.append((provider_id, None))
            continue
        if age > max_age_days:
            stale.append((provider_id, round(age, 1)))

    for provider_id, age in stale:
        report.add(
            _issue("sources.staleness", Outcome.FAIL,
                   f"{provider_id}: no committed record carries a retrieval timestamp"
                   if age is None
                   else f"{provider_id}: newest committed record is {age} days old "
                        f"(limit {max_age_days})",
                   severity=Severity.WARNING, subject=provider_id, observed=age,
                   expected=max_age_days)
        )
    if not stale:
        report.add(
            _issue("sources.staleness", Outcome.PASS,
                   "every trackable enabled source has recent committed data",
                   severity=Severity.INFO)
        )
    return report


# ---------------------------------------------------------------------------
# Quality report
# ---------------------------------------------------------------------------


def build_quality_report(
    run_id: str,
    workflow: str,
    report: ValidationReport,
    counts: Optional[dict] = None,
    failed_tickers: Optional[list] = None,
    sources: Optional[list] = None,
    write_mode: WriteMode = WriteMode.VALIDATE_ONLY,
    promoted: bool = False,
    not_promoted_reason: Optional[str] = None,
) -> dict:
    counts = counts or {}
    return {
        "schemaVersion": "1.0.0",
        "runId": run_id,
        "workflow": workflow,
        "generatedAt": utc_now_iso(),
        "writeMode": str(write_mode),
        "status": report.status,
        "promoted": promoted,
        "notPromotedReason": not_promoted_reason,
        "checks": report.to_json(),
        "counts": {
            "recordsIn": counts.get("recordsIn", 0),
            "recordsValid": counts.get("recordsValid", 0),
            "recordsInvalid": counts.get("recordsInvalid", 0),
            "recordsMissing": counts.get("recordsMissing", 0),
            "recordsWritten": counts.get("recordsWritten", 0),
            "filesChanged": counts.get("filesChanged", 0),
            "tickersSucceeded": counts.get("tickersSucceeded", 0),
            "tickersFailed": counts.get("tickersFailed", 0),
        },
        "failedTickers": failed_tickers or [],
        "sources": sources or [],
    }


def write_quality_report(document: dict, workflow: str,
                         settings: Optional[Settings] = None) -> tuple:
    """Write the latest report and append an immutable copy to history."""
    settings = settings or get_settings()
    latest = settings.quality_latest / f"{workflow}.json"
    # runId and generatedAt differ on every run by construction; a report is
    # only worth rewriting when the checks, counts or status actually moved.
    changed = write_document_if_changed(
        latest, document, volatile_fields=(*VOLATILE_FIELDS, "runId")
    )

    # History is appended only when something changed, so the archive records
    # transitions rather than accumulating one identical file per scheduled run.
    if changed:
        stamp = document["generatedAt"].replace(":", "").replace("-", "")
        history = settings.quality_history / f"{workflow}-{stamp}.json"
        if not history.exists():
            history.parent.mkdir(parents=True, exist_ok=True)
            history.write_text(canonical_json(document), encoding="utf-8")
    return changed, latest


def derive_last_success(settings: Optional[Settings] = None) -> dict:
    """Newest ``retrievedAt`` per provider, read from the committed datasets.

    An earlier design wrote a `last-success.json` side-car on every successful
    run. That file's whole content is timestamps, so it changed on every run and
    would have produced a commit on every scheduled run even when no data
    changed — exactly what the no-change/no-commit policy forbids.

    Deriving the same signal from data we already commit costs nothing extra,
    cannot churn, and is a more honest answer: it reports when the freshest
    record we actually hold was retrieved, rather than when a process last
    finished. The private tree is excluded because nothing there is committed.
    """
    settings = settings or get_settings()
    newest: dict = {}

    def note(provider_id, stamp):
        if not provider_id or not stamp:
            return
        if provider_id not in newest or stamp > newest[provider_id]:
            newest[provider_id] = stamp

    def scan(record):
        if not isinstance(record, dict):
            return
        note(record.get("providerId"), record.get("retrievedAt"))
        source = record.get("source")
        if isinstance(source, dict):
            note(source.get("providerId"), source.get("retrievedAt"))

    private = settings.private_dir.resolve()
    roots = [settings.data_dir, settings.config_dir]
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix not in (".json", ".jsonl"):
                continue
            try:
                path.resolve().relative_to(private)
                continue  # inside the git-ignored tree
            except ValueError:
                pass
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if path.suffix == ".jsonl":
                for line in text.splitlines():
                    if line.strip():
                        try:
                            scan(json.loads(line))
                        except json.JSONDecodeError:
                            break
            else:
                try:
                    document = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if isinstance(document, dict):
                    scan(document)
                    for value in document.values():
                        if isinstance(value, list):
                            for item in value:
                                scan(item)
    return newest


def untrackable_providers(sources_config: dict) -> set:
    """Enabled providers whose rights forbid committing, so they leave no
    trace in the repository for :func:`derive_last_success` to find."""
    from .rights import RightsGate

    gate = RightsGate(sources_config)
    return {
        pid for pid, cfg in (sources_config.get("providers") or {}).items()
        if cfg.get("enabled") and not gate.may(pid, "commit_to_repo")
    }
