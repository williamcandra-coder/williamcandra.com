"""Goh Dip Tong pipeline CLI.

    python3 -m pipeline.goh_dip_tong.cli <command> [options]

Every collecting command shares the same shape:

    discover -> fetch -> parse -> validate -> (promote | refuse)

`--write-mode validate_only` (the default) runs everything and promotes
nothing. `--write-mode commit` promotes only if no CRITICAL check failed, so
invalid data can never replace the last validated data.

Exit codes:
    0  ran, validation passed (whether or not anything changed)
    1  validation failed, nothing was promoted
    2  usage or configuration error
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

from .collectors.financials import apply_restatements, latest_revisions
from .collectors.registry import ProviderRegistry
from .contracts.enums import (
    Outcome,
    PeriodType,
    Severity,
    WriteMode,
)
from .contracts.provider import (
    ProviderContext,
    ProviderDisabledError,
    RightsViolationError,
)
from .contracts.records import ValidationIssue, ValidationReport
from .publishing import change_detection, history, registry_config
from .publishing.writers import (
    canonical_json,
    content_hash,
    read_json,
    upsert_csv,
    upsert_jsonl,
    write_document_if_changed,
    write_json_if_changed,
    write_text_if_changed,
)
from .settings import get_settings, utc_now_iso
from .validation import connectivity as connectivity_mod
from .validation import quality as quality_mod
from .validation.repo_guard import RepoGuard
from .validation.rights import RightsGate
from .validation.schema import validate_all_schemas, validate_document, validate_records

EXIT_OK, EXIT_VALIDATION_FAILED, EXIT_USAGE = 0, 1, 2


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def _run_id(workflow: str) -> str:
    return f"{workflow}-{utc_now_iso().replace(':', '').replace('-', '')}"


def _emit_github_output(**values) -> None:
    """Expose results to the workflow without parsing stdout."""
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        for key, value in values.items():
            fh.write(f"{key}={value}\n")


def _print_report(report: ValidationReport, verbose: bool = False) -> None:
    for issue in report.issues:
        if issue.outcome == Outcome.PASS and not verbose and issue.severity == Severity.INFO:
            continue
        marker = {"PASS": "  ok", "FAIL": "FAIL", "SKIP": "skip"}[str(issue.outcome)]
        subject = f" [{issue.subject}]" if issue.subject else ""
        print(f"  {marker} {issue.check_id}{subject}: {issue.message}")


def _finish(workflow, report, counts, settings, write_mode, promoted,
            not_promoted_reason=None, failed_tickers=None, sources=None,
            changed_files=0, verbose=False) -> int:
    document = quality_mod.build_quality_report(
        run_id=_run_id(workflow),
        workflow=workflow,
        report=report,
        counts={**counts, "filesChanged": changed_files},
        failed_tickers=failed_tickers,
        sources=sources,
        write_mode=write_mode,
        promoted=promoted,
        not_promoted_reason=not_promoted_reason,
    )
    schema_report = validate_document("quality-report", document, subject=workflow, settings=settings)
    if not schema_report.ok:  # pragma: no cover - would be a bug in our own writer
        print("  FAIL the quality report itself does not match its schema:")
        _print_report(schema_report, verbose=True)

    quality_mod.write_quality_report(document, workflow, settings)

    print()
    print(f"  status={report.status} promoted={promoted} filesChanged={changed_files}")
    if not_promoted_reason:
        print(f"  not promoted: {not_promoted_reason}")
    print(f"  quality report: {settings.rel(settings.quality_latest / (workflow + '.json'))}")

    _emit_github_output(
        status=report.status,
        promoted=str(promoted).lower(),
        files_changed=changed_files,
        has_changes=str(changed_files > 0).lower(),
    )
    return EXIT_OK if report.ok else EXIT_VALIDATION_FAILED


def _write_run_manifest(workflow, settings, payload) -> None:
    """Record what the run did. Ignores runId/generatedAt so an unchanged run
    does not produce a diff."""
    path = settings.pipeline_runs / f"{workflow}.json"
    write_document_if_changed(path, payload, volatile_fields=("generatedAt", "runId"))


def _source_rows(registry: ProviderRegistry) -> list:
    """Source state for the quality report.

    `lastSuccessAt` is derived from the newest retrieval timestamp in the
    committed data, not from a side-car file — see quality.derive_last_success.
    """
    last_success = quality_mod.derive_last_success()
    return [
        {
            "providerId": row["providerId"],
            "enabled": row["enabled"],
            "rightsStatus": row["rightsStatus"],
            "lastSuccessAt": last_success.get(row["providerId"]),
            "staleDays": None,
        }
        for row in registry.status_table()
    ]


# ---------------------------------------------------------------------------
# registry-update
# ---------------------------------------------------------------------------


def cmd_registry_update(args) -> int:
    settings = get_settings()
    registry = ProviderRegistry(settings)
    workflow = "gdt-registry-update"
    write_mode = WriteMode(args.write_mode)
    report = ValidationReport()

    print(f"[{workflow}] write_mode={write_mode}")

    try:
        provider = registry.resolve("index_membership", preferred=args.provider)
    except ProviderDisabledError as exc:
        print(f"  FAIL {exc}")
        report.add(ValidationIssue("registry.provider", Severity.CRITICAL, Outcome.FAIL, str(exc)))
        return _finish(workflow, report, {}, settings, write_mode, promoted=False,
                       not_promoted_reason="no runnable index-membership provider")

    print(f"  provider: {provider.provider_id} (rights={provider.rights_status})")

    collected, failures = provider.collect(ProviderContext(run_id=_run_id(workflow)))
    report.extend(provider.validate(collected))

    if not report.ok:
        _print_report(report, args.verbose)
        return _finish(workflow, report, {"recordsIn": len(collected)}, settings, write_mode,
                       promoted=False, not_promoted_reason="source validation failed",
                       failed_tickers=failures, sources=_source_rows(registry))

    # Resolve models only after the source is known good.
    models = settings.models()
    constituents = registry_config.apply_model_mapping(collected, models)
    previous = registry_config.load_current_constituents(settings)

    observed_at = utc_now_iso()
    effective_from = getattr(provider, "effective_from", lambda: None)() or observed_at[:10]
    source_block = provider.source_block(observed_at)

    changes = change_detection.detect_changes(
        previous=previous,
        current=constituents,
        observed_at=observed_at,
        effective_from=effective_from,
    )
    material = change_detection.has_material_change(changes)
    print(f"  constituents: {len(constituents)} | previous: {len(previous)} | "
          f"changes: {len(changes)} (material={material})")

    idx30 = registry_config.build_idx30_document(
        constituents=constituents,
        effective_from=effective_from,
        source=source_block,
        provenance="FIXTURE" if provider.provider_id.startswith("fixture_") else "LIVE",
        authoritative=bool(getattr(provider, "authoritative", False)),
    )

    report.extend(validate_document("idx30", idx30, subject="idx30.current.json", settings=settings))
    report.extend(quality_mod.check_ticker_uniqueness(idx30["constituents"]))
    report.extend(quality_mod.check_universe_count(
        idx30["constituents"],
        source_declared=getattr(provider, "declared_count", lambda: None)(),
    ))
    report.extend(quality_mod.check_effective_dates(idx30))
    report.extend(quality_mod.check_model_mapping(idx30["constituents"], models))
    report.extend(quality_mod.check_category_coverage(idx30["constituents"]))

    _print_report(report, args.verbose)

    # Fail-closed: an invalid universe never replaces the committed one.
    if not report.ok:
        return _finish(workflow, report, {"recordsIn": len(constituents)}, settings, write_mode,
                       promoted=False,
                       not_promoted_reason="validation failed; committed config left untouched",
                       failed_tickers=failures, sources=_source_rows(registry))

    diff_summary = change_detection.summarise_changes(changes)
    diff_path = settings.registry_history / "latest-diff.md"
    changed_files = 0

    if write_mode == WriteMode.COMMIT:
        companies = registry_config.build_companies_document(
            constituents, previous=read_json(settings.companies_file), observed_at=observed_at
        )
        categories = registry_config.build_categories_document(constituents, models)

        report.extend(validate_document("company", companies, subject="companies.json",
                                        settings=settings))
        if not report.ok:
            _print_report(report, args.verbose)
            return _finish(workflow, report, {"recordsIn": len(constituents)}, settings,
                           write_mode, promoted=False,
                           not_promoted_reason="companies.json failed schema validation",
                           failed_tickers=failures, sources=_source_rows(registry))

        written = registry_config.write_configs(idx30, companies, categories, settings)
        changed_files = sum(1 for v in written.values() if v)

        history_changed, appended = history.append_changes(changes, settings)
        if history_changed:
            changed_files += 1
        if write_text_if_changed(diff_path, diff_summary):
            changed_files += 1

        snapshot = settings.registry_current / "idx30.json"
        if write_document_if_changed(snapshot, idx30):
            changed_files += 1

        print(f"  wrote: {[k for k, v in written.items() if v]} | "
              f"history rows appended: {appended}")
    else:
        print("  validate_only: nothing promoted")
        print()
        print(diff_summary)

    _write_run_manifest(workflow, settings, {
        "workflow": workflow, "runId": _run_id(workflow), "generatedAt": observed_at,
        "provider": provider.provider_id, "writeMode": str(write_mode),
        "constituentCount": len(constituents), "materialChange": material,
        "changeCounts": {t: sum(1 for c in changes if str(c.change_type) == t)
                         for t in sorted({str(c.change_type) for c in changes})},
    })

    return _finish(workflow, report,
                   {"recordsIn": len(collected), "recordsValid": len(constituents),
                    "recordsWritten": len(constituents) if write_mode == WriteMode.COMMIT else 0,
                    "tickersSucceeded": len(constituents), "tickersFailed": len(failures)},
                   settings, write_mode,
                   promoted=(write_mode == WriteMode.COMMIT), failed_tickers=failures,
                   sources=_source_rows(registry), changed_files=changed_files,
                   verbose=args.verbose)


# ---------------------------------------------------------------------------
# daily-update (market prices)
# ---------------------------------------------------------------------------

PRICE_COLUMNS = [
    "ticker", "tradingDate", "open", "high", "low", "close", "adjustedClose",
    "adjustmentMethodology", "volume", "currency", "missingReason",
    "corporateActionFlag", "qualityStatus",
]


def cmd_daily_update(args) -> int:
    settings = get_settings()
    registry = ProviderRegistry(settings)
    gate = RightsGate(registry.sources)
    workflow = "gdt-daily-update"
    write_mode = WriteMode(args.write_mode)
    report = ValidationReport()

    print(f"[{workflow}] write_mode={write_mode}")

    active = [c.ticker for c in registry_config.load_current_constituents(settings) if c.active]
    if not active:
        message = ("no active IDX30 universe found — run registry-update first; "
                   "refusing to guess a ticker list")
        print(f"  FAIL {message}")
        report.add(ValidationIssue("daily.universe", Severity.CRITICAL, Outcome.FAIL, message))
        return _finish(workflow, report, {}, settings, write_mode, promoted=False,
                       not_promoted_reason=message)
    print(f"  active universe: {len(active)} tickers")

    try:
        provider = registry.resolve("market_prices_daily", preferred=args.provider)
    except ProviderDisabledError as exc:
        print(f"  skip {exc}")
        report.add(ValidationIssue("daily.provider", Severity.WARNING, Outcome.FAIL, str(exc)))
        return _finish(workflow, report, {}, settings, write_mode, promoted=False,
                       not_promoted_reason="no runnable market-price provider",
                       sources=_source_rows(registry))

    print(f"  provider: {provider.provider_id} (rights={provider.rights_status})")

    records, failures = provider.collect(
        ProviderContext(run_id=_run_id(workflow), tickers=active)
    )
    # Only tickers in the active universe are updated.
    records = [r for r in records if r.ticker in set(active)]
    rows = [r.to_json() for r in records]

    report.extend(provider.validate(records))
    report.extend(validate_records("market-price", rows, settings=settings))
    report.extend(quality_mod.check_trading_dates(rows))
    report.extend(quality_mod.check_duplicates(rows, ("ticker", "tradingDate")))
    report.extend(quality_mod.check_missing_vs_zero(rows, value_field="close"))
    report.extend(quality_mod.check_price_jumps(rows))
    _print_report(report, args.verbose)

    # Rights routing: PRIVATE_RESEARCH_ONLY output goes to the git-ignored tree.
    public_root = settings.market_prices_daily
    private_root = settings.private_dir / "market-prices" / "daily"
    destination_root = gate.destination_for(provider.provider_id, public_root, private_root)
    is_private = gate.is_private_path(destination_root, settings.private_dir)
    print(f"  destination: {settings.rel(destination_root)}"
          + ("  (git-ignored: rights do not permit committing price data)" if is_private else ""))

    changed_files = 0
    if write_mode == WriteMode.COMMIT and report.ok:
        by_partition: dict = {}
        for row in rows:
            by_partition.setdefault(
                (row["ticker"], row["tradingDate"][:4]), []
            ).append(row)

        for (ticker, year), partition_rows in sorted(by_partition.items()):
            path = destination_root / ticker / f"{year}.csv"
            gate.assert_write_allowed(provider.provider_id, path, settings.private_dir,
                                      subject=f"{ticker} {year} prices")
            changed, added, updated = upsert_csv(
                path, partition_rows, PRICE_COLUMNS,
                key=lambda r: (r["ticker"], r["tradingDate"]),
            )
            if changed:
                changed_files += 1
        print(f"  partitions written: {changed_files} changed of {len(by_partition)}")
    elif write_mode == WriteMode.COMMIT:
        print("  validation failed: nothing promoted, last validated data stands")
    else:
        print("  validate_only: nothing promoted")

    _write_run_manifest(workflow, settings, {
        "workflow": workflow, "runId": _run_id(workflow), "generatedAt": utc_now_iso(),
        "provider": provider.provider_id, "writeMode": str(write_mode),
        "activeTickers": len(active), "rowsCollected": len(rows),
        "destination": settings.rel(destination_root), "committable": not is_private,
    })

    missing = sum(1 for r in rows if r["close"] is None)
    return _finish(workflow, report,
                   {"recordsIn": len(rows), "recordsValid": len(rows) - missing,
                    "recordsMissing": missing,
                    "recordsWritten": len(rows) if (write_mode == WriteMode.COMMIT and report.ok) else 0,
                    "tickersSucceeded": len({r["ticker"] for r in rows}),
                    "tickersFailed": len(failures)},
                   settings, write_mode,
                   promoted=(write_mode == WriteMode.COMMIT and report.ok),
                   not_promoted_reason=None if report.ok else "validation failed",
                   failed_tickers=failures, sources=_source_rows(registry),
                   changed_files=changed_files, verbose=args.verbose)


# ---------------------------------------------------------------------------
# disclosure-watch
# ---------------------------------------------------------------------------


def cmd_disclosure_watch(args) -> int:
    settings = get_settings()
    registry = ProviderRegistry(settings)
    gate = RightsGate(registry.sources)
    workflow = "gdt-disclosure-watch"
    write_mode = WriteMode(args.write_mode)
    report = ValidationReport()

    print(f"[{workflow}] write_mode={write_mode}")

    try:
        provider = registry.resolve("disclosure_metadata", preferred=args.provider)
    except ProviderDisabledError as exc:
        print(f"  skip {exc}")
        report.add(ValidationIssue("disclosures.provider", Severity.WARNING, Outcome.FAIL, str(exc)))
        return _finish(workflow, report, {}, settings, write_mode, promoted=False,
                       not_promoted_reason=str(exc), sources=_source_rows(registry))

    print(f"  provider: {provider.provider_id} (rights={provider.rights_status})")
    records, failures = provider.collect(ProviderContext(run_id=_run_id(workflow)))
    rows = [r.to_json() for r in records]

    report.extend(provider.validate(records))
    report.extend(validate_records("disclosure", rows, settings=settings))
    report.extend(quality_mod.check_duplicates(rows, ("disclosureId",)))
    _print_report(report, args.verbose)

    flagged = [r for r in rows if r["flaggedForFinancialUpdate"]]
    manifests = [r for r in rows if r.get("manifest")]
    print(f"  disclosures: {len(rows)} | flagged for financial update: {len(flagged)} "
          f"| manifest-only documents: {len(manifests)}")

    changed_files = 0
    if write_mode == WriteMode.COMMIT and report.ok:
        gate.assert_may(provider.provider_id, "commit_to_repo", "disclosure metadata")
        by_month: dict = {}
        for row in rows:
            by_month.setdefault(row["publishedAt"][:7], []).append(row)
        for month, month_rows in sorted(by_month.items()):
            path = settings.disclosures_metadata / f"{month}.jsonl"
            changed, _, _ = upsert_jsonl(
                path, month_rows, key=lambda r: (r["disclosureId"],),
                sort_key=lambda r: (r["publishedAt"], r["disclosureId"]),
            )
            if changed:
                changed_files += 1

        if manifests:
            path = settings.disclosures_manifests / "documents.jsonl"
            manifest_rows = [
                {"disclosureId": r["disclosureId"], "ticker": r["ticker"],
                 "officialUrl": r["officialUrl"], "publishedAt": r["publishedAt"],
                 "contentHash": r["contentHash"], **r["manifest"]}
                for r in manifests
            ]
            changed, _, _ = upsert_jsonl(path, manifest_rows,
                                         key=lambda r: (r["disclosureId"],))
            if changed:
                changed_files += 1

        # Hand-off queue for gdt-financial-update.
        queue = settings.disclosures_metadata / "pending-financial.json"
        if write_document_if_changed(queue, {
            "generatedAt": utc_now_iso(),
            "disclosureIds": sorted(r["disclosureId"] for r in flagged),
        }):
            changed_files += 1

    elif write_mode == WriteMode.COMMIT:
        print("  validation failed: nothing promoted")
    else:
        print("  validate_only: nothing promoted")

    _write_run_manifest(workflow, settings, {
        "workflow": workflow, "runId": _run_id(workflow), "generatedAt": utc_now_iso(),
        "provider": provider.provider_id, "writeMode": str(write_mode),
        "disclosures": len(rows), "flaggedForFinancialUpdate": len(flagged),
    })

    return _finish(workflow, report,
                   {"recordsIn": len(rows), "recordsValid": len(rows),
                    "recordsWritten": len(rows) if (write_mode == WriteMode.COMMIT and report.ok) else 0},
                   settings, write_mode,
                   promoted=(write_mode == WriteMode.COMMIT and report.ok),
                   not_promoted_reason=None if report.ok else "validation failed",
                   failed_tickers=failures, sources=_source_rows(registry),
                   changed_files=changed_files, verbose=args.verbose)


# ---------------------------------------------------------------------------
# financial-update
# ---------------------------------------------------------------------------

def cmd_financial_update(args) -> int:
    settings = get_settings()
    registry = ProviderRegistry(settings)
    gate = RightsGate(registry.sources)
    workflow = "gdt-financial-update"
    write_mode = WriteMode(args.write_mode)
    report = ValidationReport()

    print(f"[{workflow}] write_mode={write_mode}")

    try:
        provider = registry.resolve("financial_facts", preferred=args.provider)
    except ProviderDisabledError as exc:
        print(f"  skip {exc}")
        report.add(ValidationIssue("facts.provider", Severity.WARNING, Outcome.FAIL, str(exc)))
        return _finish(workflow, report, {}, settings, write_mode, promoted=False,
                       not_promoted_reason=str(exc), sources=_source_rows(registry))

    print(f"  provider: {provider.provider_id} (rights={provider.rights_status})")
    facts, failures = provider.collect(ProviderContext(run_id=_run_id(workflow)))

    facts = apply_restatements(facts)
    current = latest_revisions(facts)
    restated = [f for f in facts if "SUPERSEDED" in f.quality_flags]
    print(f"  facts: {len(facts)} | current revisions: {len(current)} | superseded: {len(restated)}")

    rows = [f.to_json() for f in facts]
    report.extend(provider.validate(facts))
    report.extend(validate_records("financial-fact", rows, settings=settings))
    report.extend(quality_mod.check_missing_vs_zero(rows))
    report.extend(quality_mod.check_duplicates(rows, ("factKey", "revision")))
    _print_report(report, args.verbose)

    changed_files = 0
    if write_mode == WriteMode.COMMIT and report.ok:
        gate.assert_may(provider.provider_id, "commit_to_repo", "financial facts")

        annual = [r for r in rows if r["periodType"] == str(PeriodType.FY)]
        quarterly = [r for r in rows if r["periodType"] != str(PeriodType.FY)]

        for bucket, target in ((annual, settings.facts_annual),
                               (quarterly, settings.facts_quarterly)):
            by_ticker: dict = {}
            for row in bucket:
                by_ticker.setdefault(row["ticker"], []).append(row)
            for ticker, ticker_rows in sorted(by_ticker.items()):
                path = target / f"{ticker}.jsonl"
                changed, _, _ = upsert_jsonl(
                    path, ticker_rows,
                    key=lambda r: (r["factKey"], r["revision"]),
                    sort_key=lambda r: (r["periodEnd"], r["metric"], r["revision"]),
                )
                if changed:
                    changed_files += 1

        # Restatement trail, separate from the reported statements.
        if restated:
            path = settings.statements_restated / "restatements.jsonl"
            changed, _, _ = upsert_jsonl(
                path, [f.to_json() for f in restated],
                key=lambda r: (r["factKey"], r["revision"]),
            )
            if changed:
                changed_files += 1

        # Normalized current view: what the engine reads.
        path = settings.statements_normalized / "current-facts.jsonl"
        changed, _, _ = upsert_jsonl(
            path, [f.to_json() for f in current],
            key=lambda r: (r["factKey"],),
            sort_key=lambda r: (r["ticker"], r["periodEnd"], r["metric"]),
        )
        if changed:
            changed_files += 1

    elif write_mode == WriteMode.COMMIT:
        print("  validation failed: nothing promoted")
    else:
        print("  validate_only: nothing promoted")

    _write_run_manifest(workflow, settings, {
        "workflow": workflow, "runId": _run_id(workflow), "generatedAt": utc_now_iso(),
        "provider": provider.provider_id, "writeMode": str(write_mode),
        "factsTotal": len(facts), "currentRevisions": len(current),
        "supersededRevisions": len(restated),
    })

    missing = sum(1 for r in rows if r["value"] is None)
    return _finish(workflow, report,
                   {"recordsIn": len(rows), "recordsValid": len(rows) - missing,
                    "recordsMissing": missing,
                    "recordsWritten": len(rows) if (write_mode == WriteMode.COMMIT and report.ok) else 0,
                    "tickersSucceeded": len({r["ticker"] for r in rows}),
                    "tickersFailed": len(failures)},
                   settings, write_mode,
                   promoted=(write_mode == WriteMode.COMMIT and report.ok),
                   not_promoted_reason=None if report.ok else "validation failed",
                   failed_tickers=failures, sources=_source_rows(registry),
                   changed_files=changed_files, verbose=args.verbose)


# ---------------------------------------------------------------------------
# macro-update
# ---------------------------------------------------------------------------


def cmd_macro_update(args) -> int:
    settings = get_settings()
    registry = ProviderRegistry(settings)
    gate = RightsGate(registry.sources)
    workflow = "gdt-macro-update"
    write_mode = WriteMode(args.write_mode)
    report = ValidationReport()

    print(f"[{workflow}] write_mode={write_mode}")

    try:
        provider = registry.resolve("macro_series", preferred=args.provider)
    except ProviderDisabledError as exc:
        print(f"  skip {exc}")
        report.add(ValidationIssue("macro.provider", Severity.WARNING, Outcome.FAIL, str(exc)))
        return _finish(workflow, report, {}, settings, write_mode, promoted=False,
                       not_promoted_reason=str(exc), sources=_source_rows(registry))

    print(f"  provider: {provider.provider_id} (rights={provider.rights_status})")
    observations, failures = provider.collect(ProviderContext(run_id=_run_id(workflow)))
    rows = [o.to_json() for o in observations]

    report.extend(provider.validate(observations))
    report.extend(quality_mod.check_missing_vs_zero(rows))
    _print_report(report, args.verbose)

    from .collectors.macro import REGISTERED_SERIES

    changed_files = 0
    if write_mode == WriteMode.COMMIT and report.ok:
        gate.assert_may(provider.provider_id, "commit_to_repo", "macro series")
        by_agency: dict = {}
        for row in rows:
            agency = REGISTERED_SERIES[row["seriesId"]]["provider"]
            by_agency.setdefault((agency, row["seriesId"]), []).append(row)

        for (agency, series_id), series_rows in sorted(by_agency.items()):
            path = settings.macro_dir / agency / f"{series_id}.jsonl"
            # Vintage is part of the key, so a revised observation is a new row
            # rather than an overwrite of what we previously believed.
            changed, _, _ = upsert_jsonl(
                path, series_rows,
                key=lambda r: (r["seriesId"], r["observationPeriod"], r["releaseVintage"] or ""),
                sort_key=lambda r: (r["observationPeriod"], r["releaseVintage"] or ""),
            )
            if changed:
                changed_files += 1
    elif write_mode == WriteMode.COMMIT:
        print("  validation failed: nothing promoted")
    else:
        print("  validate_only: nothing promoted")

    _write_run_manifest(workflow, settings, {
        "workflow": workflow, "runId": _run_id(workflow), "generatedAt": utc_now_iso(),
        "provider": provider.provider_id, "writeMode": str(write_mode),
        "observations": len(rows),
        "series": sorted({r["seriesId"] for r in rows}),
    })

    missing = sum(1 for r in rows if r["value"] is None)
    return _finish(workflow, report,
                   {"recordsIn": len(rows), "recordsValid": len(rows) - missing,
                    "recordsMissing": missing,
                    "recordsWritten": len(rows) if (write_mode == WriteMode.COMMIT and report.ok) else 0},
                   settings, write_mode,
                   promoted=(write_mode == WriteMode.COMMIT and report.ok),
                   not_promoted_reason=None if report.ok else "validation failed",
                   failed_tickers=failures, sources=_source_rows(registry),
                   changed_files=changed_files, verbose=args.verbose)


# ---------------------------------------------------------------------------
# backfill
# ---------------------------------------------------------------------------


def cmd_backfill(args) -> int:
    """Historical backfill across scope / ticker / data type.

    Idempotent by construction: every dataset is written through an upsert keyed
    on the record's primary key, so rerunning the same range produces the same
    bytes and therefore no commit.
    """
    settings = get_settings()
    workflow = "gdt-historical-backfill"
    write_mode = WriteMode(args.write_mode)
    report = ValidationReport()

    print(f"[{workflow}] scope={args.scope} write_mode={write_mode} "
          f"years={args.start_year or '-'}..{args.end_year or '-'}")

    data_types = (
        [args.data_type] if args.scope == "data_type" and args.data_type
        else ["market_prices_daily", "disclosure_metadata", "financial_facts", "macro_series"]
    )

    handlers = {
        "market_prices_daily": cmd_daily_update,
        "disclosure_metadata": cmd_disclosure_watch,
        "financial_facts": cmd_financial_update,
        "macro_series": cmd_macro_update,
    }

    worst = EXIT_OK
    for data_type in data_types:
        handler = handlers.get(data_type)
        if handler is None:
            print(f"  skip unknown data type: {data_type}")
            continue
        print()
        print(f"--- backfill: {data_type} ---")
        sub = argparse.Namespace(
            write_mode=args.write_mode, provider=args.provider, verbose=args.verbose
        )
        # Fail-soft across data types: one failing dataset must not abandon the rest.
        try:
            code = handler(sub)
        except Exception as exc:  # noqa: BLE001 - deliberate fail-soft boundary
            print(f"  FAIL {data_type}: {type(exc).__name__}: {exc}")
            report.add(ValidationIssue(f"backfill.{data_type}", Severity.CRITICAL,
                                       Outcome.FAIL, f"{type(exc).__name__}: {exc}"))
            worst = EXIT_VALIDATION_FAILED
            continue
        worst = max(worst, code)

    report.add(ValidationIssue(
        "backfill.completed",
        Severity.INFO if worst == EXIT_OK else Severity.CRITICAL,
        Outcome.PASS if worst == EXIT_OK else Outcome.FAIL,
        f"backfilled {len(data_types)} data types: {data_types}",
    ))

    _write_run_manifest(workflow, settings, {
        "workflow": workflow, "runId": _run_id(workflow), "generatedAt": utc_now_iso(),
        "scope": args.scope, "dataTypes": data_types, "writeMode": str(write_mode),
        "startYear": args.start_year, "endYear": args.end_year,
    })

    print()
    return _finish(workflow, report, {}, settings, write_mode,
                   promoted=(write_mode == WriteMode.COMMIT and worst == EXIT_OK),
                   verbose=args.verbose)


# ---------------------------------------------------------------------------
# research snapshot (Stage 2 contract sample)
# ---------------------------------------------------------------------------

DISCLAIMERS = [
    "Development data. Generated from committed fixtures, not from a live or "
    "authoritative market data source.",
    "Not investment advice. No buy or sell recommendation, no guaranteed return, "
    "and no personalised investment recommendation is expressed or implied.",
    "Values are labelled by basis (reported, restated, normalized, derived, "
    "forecast, market-implied) and must be displayed with that label.",
    "Missing values are null with a stated reason and must never be rendered as zero.",
]


def cmd_research_snapshot(args) -> int:
    """Emit the Stage 2 hand-off contract for one ticker."""
    settings = get_settings()
    workflow = "gdt-research-snapshot"
    report = ValidationReport()
    ticker = args.ticker.upper()

    constituents = {c.ticker: c for c in registry_config.load_current_constituents(settings)}
    if ticker not in constituents:
        print(f"  FAIL {ticker} is not in the current IDX30 universe")
        return EXIT_USAGE
    constituent = constituents[ticker]

    from .publishing.writers import read_jsonl

    facts = [
        row for row in read_jsonl(settings.statements_normalized / "current-facts.jsonl")
        if row["ticker"] == ticker
    ]

    snapshot_facts = sorted(
        (
            {
                "metric": f["metric"], "periodType": f["periodType"],
                "periodStart": f["periodStart"], "periodEnd": f["periodEnd"],
                "fiscalYear": f["fiscalYear"], "basis": f["basis"], "value": f["value"],
                "missingReason": f["missingReason"], "unit": f["unit"],
                "currency": f["currency"], "revision": f["revision"],
                "qualityStatus": f["qualityStatus"],
                "sourceRef": (f.get("source") or {}).get("documentRef"),
                "publishedAt": (f.get("source") or {}).get("publishedAt"),
                "retrievedAt": (f.get("source") or {}).get("retrievedAt"),
            }
            for f in facts
        ),
        key=lambda r: (r["periodEnd"], r["metric"]),
    )

    present = sum(1 for f in snapshot_facts if f["value"] is not None)
    payload = {
        "schemaVersion": "1.0.0",
        "ticker": ticker,
        "snapshotAt": utc_now_iso(),
        "identity": {
            "name": constituent.name,
            "sectorCode": constituent.sector_code,
            "sectorName": constituent.sector_name,
            "industryCode": constituent.industry_code,
            "industryName": constituent.industry_name,
            "modelFamily": constituent.model_family,
            "coverageStatus": str(constituent.coverage_status),
            "inIdx30": constituent.active,
            "reportingCurrency": "IDR",
        },
        "facts": snapshot_facts,
        # Explicitly unavailable rather than absent, so the engine has to handle
        # the no-price case instead of assuming one exists.
        "marketContext": {
            "available": False,
            "reason": "Market-data redistribution rights are not documented; the "
                      "price provider is PRIVATE_RESEARCH_ONLY.",
            "asOfDate": None, "close": None, "currency": None,
            "rightsStatus": "PRIVATE_RESEARCH_ONLY",
        },
        "macroContext": [],
        "recentEvents": [],
        "quality": {
            "status": "UNVALIDATED",
            "completeness": round(present / len(snapshot_facts), 4) if snapshot_facts else 0.0,
            "missingCriticalMetrics": sorted(
                {f["metric"] for f in snapshot_facts if f["value"] is None}
            ),
            "flags": ["FIXTURE_DATA"],
        },
        "disclaimers": DISCLAIMERS,
    }
    payload["contentHash"] = content_hash(
        {k: v for k, v in payload.items() if k != "snapshotAt"}
    )

    report.extend(validate_document("research-input", payload, subject=ticker, settings=settings))
    _print_report(report, args.verbose)

    if report.ok:
        path = settings.research_snapshots / "sample" / f"{ticker}.json"
        changed = write_document_if_changed(path, payload)
        print(f"  {'wrote' if changed else 'unchanged'}: {settings.rel(path)} "
              f"({len(snapshot_facts)} facts)")
        return EXIT_OK
    return EXIT_VALIDATION_FAILED


# ---------------------------------------------------------------------------
# audit commands
# ---------------------------------------------------------------------------


def cmd_repo_guard(args) -> int:
    settings = get_settings()
    print("[repo-guard]")
    report = RepoGuard(settings).run()
    _print_report(report, args.verbose)
    print()
    print(f"  status={report.status} critical_failures={len(report.critical_failures)}")
    _emit_github_output(guard_status=report.status)
    return EXIT_OK if report.ok else EXIT_VALIDATION_FAILED


def cmd_sources(args) -> int:
    settings = get_settings()
    registry = ProviderRegistry(settings)
    gate = RightsGate(registry.sources)

    print(f"{'provider':<28} {'kind':<8} {'enabled':<8} {'runnable':<9} rights")
    print("-" * 100)
    for row in registry.status_table():
        print(f"{row['providerId']:<28} {row['kind']:<8} "
              f"{str(row['enabled']).lower():<8} {str(row['runnable']).lower():<9} "
              f"{row['rightsStatus']}")
        if row["blockedReason"]:
            print(f"{'':<28} blocked: {row['blockedReason']}")

    print()
    print(f"runnable: {gate.runnable_providers()}")
    print(f"blocked:  {gate.blocked_providers()}")

    register = settings.docs_dir / "SOURCE_REGISTER.md"
    problems = gate.cross_check_register(
        register.read_text(encoding="utf-8") if register.exists() else None
    )
    if problems:
        print()
        print("rights/register inconsistencies:")
        for problem in problems:
            print(f"  FAIL {problem}")
        return EXIT_VALIDATION_FAILED
    print("rights and SOURCE_REGISTER.md are consistent")
    return EXIT_OK


def cmd_quality(args) -> int:
    """The gdt-data-quality audit over everything already committed."""
    settings = get_settings()
    registry = ProviderRegistry(settings)
    gate = RightsGate(registry.sources)
    workflow = "gdt-data-quality"
    report = ValidationReport()

    print(f"[{workflow}]")
    report.extend(validate_all_schemas(settings))

    idx30 = read_json(settings.idx30_current)
    if not idx30:
        report.add(ValidationIssue("quality.idx30_present", Severity.CRITICAL, Outcome.FAIL,
                                   "config/goh-dip-tong/idx30.current.json does not exist"))
    else:
        models = settings.models()
        report.extend(validate_document("idx30", idx30, subject="idx30.current.json",
                                        settings=settings))
        report.extend(quality_mod.check_ticker_uniqueness(idx30["constituents"]))
        report.extend(quality_mod.check_universe_count(idx30["constituents"]))
        report.extend(quality_mod.check_effective_dates(idx30))
        report.extend(quality_mod.check_model_mapping(idx30["constituents"], models))
        report.extend(quality_mod.check_category_coverage(idx30["constituents"]))

        # The Stage 3 contract: the UI reads this file, so it must stay readable.
        missing_fields = [
            c["ticker"] for c in idx30["constituents"]
            if not all(k in c for k in ("ticker", "name", "sectorCode", "coverageStatus"))
        ]
        report.add(ValidationIssue(
            "quality.ui_contract", Severity.CRITICAL,
            Outcome.FAIL if missing_fields else Outcome.PASS,
            f"constituents missing UI-required fields: {missing_fields}" if missing_fields
            else "every constituent carries the fields the Stage 3 picker needs",
        ))

    companies = read_json(settings.companies_file)
    if companies:
        report.extend(validate_document("company", companies, subject="companies.json",
                                        settings=settings))

    report.extend(quality_mod.check_source_staleness(
        registry.sources,
        quality_mod.derive_last_success(settings),
        untrackable=quality_mod.untrackable_providers(registry.sources),
    ))

    register = settings.docs_dir / "SOURCE_REGISTER.md"
    problems = gate.cross_check_register(
        register.read_text(encoding="utf-8") if register.exists() else None
    )
    report.add(ValidationIssue(
        "quality.rights_register", Severity.CRITICAL,
        Outcome.FAIL if problems else Outcome.PASS,
        "; ".join(problems) if problems
        else "declared rights match docs/goh-dip-tong/SOURCE_REGISTER.md",
    ))

    report.extend(RepoGuard(settings).run())
    _print_report(report, args.verbose)

    return _finish(workflow, report,
                   {"recordsIn": len((idx30 or {}).get("constituents", []))},
                   settings, WriteMode.VALIDATE_ONLY, promoted=False,
                   sources=_source_rows(registry), verbose=args.verbose)


def cmd_connectivity_smoke(args) -> int:
    """Diagnostic probe of configured official source URLs.

    Enables nothing. Collects nothing. Writes a metadata-only report and always
    exits 0 when the probe itself ran — an unreachable source is a finding to
    record, not a build failure.
    """
    settings = get_settings()
    print("[gdt-source-connectivity-smoke]")
    print("  DIAGNOSTIC ONLY — reachability is not permission.")
    print("  No provider is enabled by this run, whatever the results say.")
    print()

    report = connectivity_mod.probe_sources(
        settings,
        delay_seconds=args.delay,
        timeout=args.timeout,
    )

    print(connectivity_mod.format_table(report))
    print()
    counts = report["counts"]
    print(f"  probed={counts['probed']} not_tested={counts['notTested']} "
          f"reachable_unvalidated={counts['reachableUnvalidated']}")
    print(f"  providers enabled by this run: {report['providersEnabledByThisRun']}")
    print(f"  response bodies retained: {report['bodiesRetained']}")

    # Deliberately outside data/ and config/: this is a diagnostic artifact, not
    # a dataset, and it must never appear in a generated-data commit.
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(canonical_json(report), encoding="utf-8")
    print(f"  report written: {out}")

    _emit_github_output(
        reachable=counts["reachableUnvalidated"],
        probed=counts["probed"],
        providers_enabled=0,
    )
    return EXIT_OK


# ---------------------------------------------------------------------------
# argument parsing
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m pipeline.goh_dip_tong.cli",
        description="Goh Dip Tong IDX30 data-collection pipeline (Stage 1)",
    )
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="show passing INFO checks too")
    sub = parser.add_subparsers(dest="command", required=True)

    # `--verbose` is accepted both before and after the subcommand, because both
    # read naturally and getting it wrong is a usage error at the worst possible
    # moment (inside a workflow step).
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--verbose", "-v", action="store_true",
                        help="show passing INFO checks too")

    def add_write_mode(p):
        p.add_argument("--write-mode", choices=["validate_only", "commit"],
                       default="validate_only",
                       help="validate_only (default) collects and validates but promotes nothing")
        p.add_argument("--provider", default=None,
                       help="force a specific provider id from sources.yml")
        return p

    add_write_mode(sub.add_parser("registry-update", parents=[common], help="refresh the IDX30 universe")).set_defaults(func=cmd_registry_update)
    add_write_mode(sub.add_parser("daily-update", parents=[common], help="collect permitted market data")).set_defaults(func=cmd_daily_update)
    add_write_mode(sub.add_parser("disclosure-watch", parents=[common], help="collect disclosure metadata")).set_defaults(func=cmd_disclosure_watch)
    add_write_mode(sub.add_parser("financial-update", parents=[common], help="parse filings into normalized facts")).set_defaults(func=cmd_financial_update)
    add_write_mode(sub.add_parser("macro-update", parents=[common], help="collect registered macro series")).set_defaults(func=cmd_macro_update)

    backfill = add_write_mode(sub.add_parser("backfill", parents=[common], help="historical backfill"))
    backfill.add_argument("--scope", choices=["all", "ticker", "data_type"], default="all")
    backfill.add_argument("--ticker", default=None)
    backfill.add_argument("--data-type", default=None)
    backfill.add_argument("--start-year", type=int, default=None)
    backfill.add_argument("--end-year", type=int, default=None)
    backfill.set_defaults(func=cmd_backfill)

    snapshot = sub.add_parser("research-snapshot", parents=[common], help="emit the Stage 2 contract for one ticker")
    snapshot.add_argument("--ticker", required=True)
    snapshot.set_defaults(func=cmd_research_snapshot)

    smoke = sub.add_parser("connectivity-smoke", parents=[common],
                           help="diagnostic probe of configured source URLs (enables nothing)")
    smoke.add_argument("--output", default="connectivity-report.json",
                       help="where to write the metadata-only report")
    smoke.add_argument("--timeout", type=float,
                       default=connectivity_mod.DEFAULT_TIMEOUT)
    smoke.add_argument("--delay", type=float, default=connectivity_mod.DEFAULT_DELAY,
                       help="seconds between providers; keep this conservative")
    smoke.set_defaults(func=cmd_connectivity_smoke)

    sub.add_parser("repo-guard", parents=[common], help="run the repository-data guard").set_defaults(func=cmd_repo_guard)
    sub.add_parser("sources", parents=[common], help="show source status and rights").set_defaults(func=cmd_sources)
    sub.add_parser("quality", parents=[common], help="run the full data-quality audit").set_defaults(func=cmd_quality)

    return parser


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except RightsViolationError as exc:
        print(f"RIGHTS VIOLATION: {exc}", file=sys.stderr)
        return EXIT_VALIDATION_FAILED
    except ProviderDisabledError as exc:
        print(f"PROVIDER DISABLED: {exc}", file=sys.stderr)
        return EXIT_VALIDATION_FAILED
    except FileNotFoundError as exc:
        print(f"MISSING FILE: {exc}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
