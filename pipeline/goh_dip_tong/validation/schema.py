"""JSON Schema validation against schemas/goh-dip-tong/."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Optional

from jsonschema import Draft202012Validator

from ..contracts.enums import Outcome, Severity
from ..contracts.records import ValidationIssue, ValidationReport
from ..settings import Settings, get_settings

SCHEMA_FILES = {
    "idx30": "idx30.schema.json",
    "company": "company.schema.json",
    "financial-fact": "financial-fact.schema.json",
    "market-price": "market-price.schema.json",
    "disclosure": "disclosure.schema.json",
    "event": "event.schema.json",
    "quality-report": "quality-report.schema.json",
    "research-input": "research-input.schema.json",
    # Stage 2 engine output. Registered here so it is covered by the same
    # "every declared schema is a legal Draft 2020-12 document" audit as the
    # rest, rather than living in a second, unaudited place.
    "research-snapshot": "research-snapshot.schema.json",
}


@lru_cache(maxsize=32)
def _load_validator(schema_path: str) -> Draft202012Validator:
    with open(schema_path, "r", encoding="utf-8") as fh:
        schema = json.load(fh)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def get_validator(name: str, settings: Optional[Settings] = None) -> Draft202012Validator:
    settings = settings or get_settings()
    if name not in SCHEMA_FILES:
        raise KeyError(f"unknown schema {name!r}; known: {sorted(SCHEMA_FILES)}")
    path = settings.schema_dir / SCHEMA_FILES[name]
    if not path.exists():
        raise FileNotFoundError(f"schema not found: {path}")
    return _load_validator(str(path))


def _describe(error) -> str:
    location = "/".join(str(p) for p in error.absolute_path) or "<root>"
    return f"{location}: {error.message}"


def validate_document(
    name: str,
    document: Any,
    subject: str = "",
    settings: Optional[Settings] = None,
    severity: Severity = Severity.CRITICAL,
) -> ValidationReport:
    """Validate one document. All errors are reported, not just the first."""
    report = ValidationReport()
    validator = get_validator(name, settings)
    errors = sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))

    if not errors:
        report.add(
            ValidationIssue(
                check_id=f"schema.{name}",
                severity=Severity.CRITICAL,
                outcome=Outcome.PASS,
                message=f"document conforms to {name}.schema.json",
                subject=subject or None,
            )
        )
        return report

    for error in errors:
        report.add(
            ValidationIssue(
                check_id=f"schema.{name}",
                severity=severity,
                outcome=Outcome.FAIL,
                message=_describe(error),
                subject=subject or None,
                observed=_safe(error.instance),
            )
        )
    return report


def validate_records(
    name: str,
    records: Iterable[dict],
    subject_key: str = "ticker",
    settings: Optional[Settings] = None,
    max_reported: int = 25,
) -> ValidationReport:
    """Validate a collection of records.

    Caps the number of reported failures so one systemic problem produces a
    readable report instead of thousands of identical lines — but the count is
    always stated in full.
    """
    report = ValidationReport()
    validator = get_validator(name, settings)
    total = failed = 0

    for record in records:
        total += 1
        errors = sorted(validator.iter_errors(record), key=lambda e: list(e.absolute_path))
        if not errors:
            continue
        failed += 1
        if failed <= max_reported:
            subject = str(record.get(subject_key, "?")) if isinstance(record, dict) else "?"
            for error in errors[:5]:
                report.add(
                    ValidationIssue(
                        check_id=f"schema.{name}",
                        severity=Severity.CRITICAL,
                        outcome=Outcome.FAIL,
                        message=_describe(error),
                        subject=subject,
                        observed=_safe(error.instance),
                    )
                )

    if failed > max_reported:
        report.add(
            ValidationIssue(
                check_id=f"schema.{name}.truncated",
                severity=Severity.INFO,
                outcome=Outcome.PASS,
                message=f"{failed - max_reported} further invalid records not listed",
            )
        )

    report.add(
        ValidationIssue(
            check_id=f"schema.{name}.summary",
            severity=Severity.CRITICAL if failed else Severity.INFO,
            outcome=Outcome.FAIL if failed else Outcome.PASS,
            message=f"{total - failed}/{total} records conform to {name}.schema.json",
            observed=failed,
            expected=0,
        )
    )
    return report


def _safe(value: Any, limit: int = 200) -> Any:
    """Keep report payloads small and JSON-serialisable."""
    try:
        text = json.dumps(value, default=str)
    except (TypeError, ValueError):
        text = str(value)
    return text if len(text) <= limit else text[:limit] + "…"


def validate_all_schemas(settings: Optional[Settings] = None) -> ValidationReport:
    """Check that every declared schema file exists and is itself legal."""
    settings = settings or get_settings()
    report = ValidationReport()
    for name, filename in sorted(SCHEMA_FILES.items()):
        path = settings.schema_dir / filename
        if not path.exists():
            report.add(
                ValidationIssue(
                    check_id="schema.present",
                    severity=Severity.CRITICAL,
                    outcome=Outcome.FAIL,
                    message=f"missing schema file: {settings.rel(path)}",
                    subject=name,
                )
            )
            continue
        try:
            Draft202012Validator.check_schema(json.loads(path.read_text(encoding="utf-8")))
        except Exception as exc:  # noqa: BLE001 - report, do not crash the run
            report.add(
                ValidationIssue(
                    check_id="schema.wellformed",
                    severity=Severity.CRITICAL,
                    outcome=Outcome.FAIL,
                    message=f"{settings.rel(path)}: {type(exc).__name__}: {exc}",
                    subject=name,
                )
            )
        else:
            report.add(
                ValidationIssue(
                    check_id="schema.wellformed",
                    severity=Severity.INFO,
                    outcome=Outcome.PASS,
                    message=f"{settings.rel(path)} is a valid Draft 2020-12 schema",
                    subject=name,
                )
            )
    return report
