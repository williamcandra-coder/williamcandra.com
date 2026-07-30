"""Repository-data guard (spec section 1.2).

Runs before any generated data is committed. If it fails, the workflow does not
commit. The point is that a repository storing generated data degrades slowly
and invisibly — one oversized file, one duplicated backfill, one saved error
page at a time — so the checks are mechanical and the thresholds live in
config/goh-dip-tong/guard.yml where raising one is a visible diff.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from ..contracts.enums import Outcome, Severity
from ..contracts.records import ValidationIssue, ValidationReport
from ..settings import Settings, get_settings


class RepoGuard:
    def __init__(self, settings: Optional[Settings] = None, config: Optional[dict] = None):
        self.settings = settings or get_settings()
        self.config = config if config is not None else self.settings.guard()
        self.limits = self.config.get("limits", {})
        self._secret_patterns = [
            (p["name"], re.compile(p["pattern"]))
            for p in self.config.get("secret_patterns", [])
        ]

    # -- helpers -----------------------------------------------------------

    def guarded_files(self) -> list:
        """Every file under a guarded path, excluding the private (git-ignored)
        tree — the guard's job is to protect the repository, and nothing under
        _private/ enters it."""
        files = []
        private = self.settings.private_dir.resolve()
        for rel in self.config.get("guarded_paths", []):
            root = self.settings.repo_root / rel
            if not root.exists():
                continue
            for path in sorted(root.rglob("*")):
                if not path.is_file():
                    continue
                try:
                    path.resolve().relative_to(private)
                    continue  # inside _private/
                except ValueError:
                    pass
                files.append(path)
        return files

    def _issue(self, check_id, outcome, message, severity=Severity.CRITICAL, subject=None,
               observed=None, expected=None) -> ValidationIssue:
        return ValidationIssue(
            check_id=check_id,
            severity=severity,
            outcome=outcome,
            message=message,
            subject=subject,
            observed=observed,
            expected=expected,
        )

    # -- individual checks -------------------------------------------------

    def check_file_sizes(self, files: list) -> ValidationReport:
        report = ValidationReport()
        limit = int(self.limits.get("max_file_bytes", 2 * 1024 * 1024))
        oversized = [(f, f.stat().st_size) for f in files if f.stat().st_size > limit]
        for path, size in oversized:
            report.add(
                self._issue(
                    "guard.file_size",
                    Outcome.FAIL,
                    f"{self.settings.rel(path)} is {size} bytes, over the {limit}-byte limit",
                    subject=self.settings.rel(path),
                    observed=size,
                    expected=limit,
                )
            )
        if not oversized:
            report.add(
                self._issue(
                    "guard.file_size",
                    Outcome.PASS,
                    f"all {len(files)} generated files are within {limit} bytes",
                    severity=Severity.INFO,
                )
            )
        return report

    def check_total_size(self, files: list) -> ValidationReport:
        report = ValidationReport()
        limit = int(self.limits.get("max_total_change_bytes", 20 * 1024 * 1024))
        total = sum(f.stat().st_size for f in files)
        report.add(
            self._issue(
                "guard.total_size",
                Outcome.FAIL if total > limit else Outcome.PASS,
                f"guarded paths hold {total} bytes (limit {limit})",
                severity=Severity.CRITICAL if total > limit else Severity.INFO,
                observed=total,
                expected=limit,
            )
        )
        return report

    def check_file_count(self, files: list) -> ValidationReport:
        report = ValidationReport()
        limit = int(self.limits.get("max_changed_files", 500))
        report.add(
            self._issue(
                "guard.file_count",
                Outcome.FAIL if len(files) > limit else Outcome.PASS,
                f"{len(files)} files under guarded paths (limit {limit})",
                severity=Severity.WARNING if len(files) > limit else Severity.INFO,
                observed=len(files),
                expected=limit,
            )
        )
        return report

    def check_extensions(self, files: list) -> ValidationReport:
        report = ValidationReport()
        forbidden = {e.lower() for e in self.config.get("forbidden_extensions", [])}
        allowed = {e.lower() for e in self.config.get("allowed_extensions", [])}
        parquet_ok = bool((self.config.get("parquet") or {}).get("allowed", False))
        if parquet_ok:
            allowed.add(".parquet")

        bad = []
        for path in files:
            suffix = path.suffix.lower() or ("." + path.name.lstrip(".") if path.name.startswith(".") else "")
            if path.name == ".gitkeep":
                continue
            if suffix in forbidden:
                bad.append((path, suffix, "forbidden"))
            elif allowed and suffix not in allowed:
                bad.append((path, suffix, "not allow-listed"))

        for path, suffix, why in bad:
            report.add(
                self._issue(
                    "guard.extension",
                    Outcome.FAIL,
                    f"{self.settings.rel(path)}: extension {suffix!r} is {why}; "
                    f"large or binary documents belong behind a manifest, not in git",
                    subject=self.settings.rel(path),
                    observed=suffix,
                )
            )
        if not bad:
            report.add(
                self._issue(
                    "guard.extension",
                    Outcome.PASS,
                    "no forbidden or unexpected file types under guarded paths",
                    severity=Severity.INFO,
                )
            )
        return report

    def check_binaries(self, files: list) -> ValidationReport:
        """A NUL byte in the first 8 KiB means it is not text."""
        report = ValidationReport()
        binaries = []
        for path in files:
            try:
                if b"\x00" in path.read_bytes()[:8192]:
                    binaries.append(path)
            except OSError:
                continue
        for path in binaries:
            report.add(
                self._issue(
                    "guard.binary",
                    Outcome.FAIL,
                    f"{self.settings.rel(path)} contains NUL bytes — binary content "
                    f"must not be committed under guarded paths",
                    subject=self.settings.rel(path),
                )
            )
        if not binaries:
            report.add(
                self._issue(
                    "guard.binary", Outcome.PASS, "no accidental binaries found",
                    severity=Severity.INFO,
                )
            )
        return report

    def check_secrets(self, files: list) -> ValidationReport:
        """No threshold, no allowlist. One hit fails the guard."""
        report = ValidationReport()
        hits = []
        for path in files:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for name, pattern in self._secret_patterns:
                match = pattern.search(text)
                if match:
                    line = text[: match.start()].count("\n") + 1
                    hits.append((path, name, line))
        for path, name, line in hits:
            report.add(
                self._issue(
                    "guard.secret",
                    Outcome.FAIL,
                    f"{self.settings.rel(path)}:{line} matches secret pattern {name!r}",
                    subject=self.settings.rel(path),
                    observed=name,
                )
            )
        if not hits:
            report.add(
                self._issue(
                    "guard.secret", Outcome.PASS,
                    f"no secret-shaped strings in {len(files)} files",
                    severity=Severity.INFO,
                )
            )
        return report

    def check_html_error_pages(self, files: list) -> ValidationReport:
        """Catch a saved error page that was committed as data."""
        report = ValidationReport()
        markers = [m.lower() for m in self.config.get("html_error_page_markers", [])]
        hits = []
        for path in files:
            if path.suffix.lower() not in (".json", ".jsonl", ".csv", ".txt"):
                continue
            try:
                head = path.read_text(encoding="utf-8", errors="ignore")[:2048].lower()
            except OSError:
                continue
            for marker in markers:
                if marker in head:
                    hits.append((path, marker))
                    break
        for path, marker in hits:
            report.add(
                self._issue(
                    "guard.html_as_data",
                    Outcome.FAIL,
                    f"{self.settings.rel(path)} looks like a saved HTML/error page "
                    f"(matched {marker!r}), not data",
                    subject=self.settings.rel(path),
                )
            )
        if not hits:
            report.add(
                self._issue(
                    "guard.html_as_data", Outcome.PASS,
                    "no HTML or error pages stored as data", severity=Severity.INFO,
                )
            )
        return report

    def check_duplicate_rows(self, files: list) -> ValidationReport:
        report = ValidationReport()
        max_ratio = float(self.limits.get("max_duplicate_row_ratio", 0.02))
        max_rows = int(self.limits.get("max_rows_per_file", 250000))
        flagged = False

        for path in files:
            if path.suffix.lower() not in (".jsonl", ".csv"):
                continue
            try:
                lines = [
                    ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()
                ]
            except (OSError, UnicodeDecodeError):
                continue
            if path.suffix.lower() == ".csv" and lines:
                lines = lines[1:]  # drop header
            if not lines:
                continue

            if len(lines) > max_rows:
                flagged = True
                report.add(
                    self._issue(
                        "guard.row_count",
                        Outcome.FAIL,
                        f"{self.settings.rel(path)} has {len(lines)} rows (limit {max_rows}); "
                        f"partition this dataset instead",
                        subject=self.settings.rel(path),
                        observed=len(lines),
                        expected=max_rows,
                    )
                )

            duplicates = len(lines) - len(set(lines))
            ratio = duplicates / len(lines)
            if ratio > max_ratio:
                flagged = True
                report.add(
                    self._issue(
                        "guard.duplicate_rows",
                        Outcome.FAIL,
                        f"{self.settings.rel(path)}: {duplicates}/{len(lines)} rows are "
                        f"exact duplicates ({ratio:.1%} > {max_ratio:.1%}) — likely a "
                        f"non-idempotent backfill",
                        subject=self.settings.rel(path),
                        observed=round(ratio, 4),
                        expected=max_ratio,
                    )
                )

        if not flagged:
            report.add(
                self._issue(
                    "guard.duplicate_rows", Outcome.PASS,
                    "row duplication within limits", severity=Severity.INFO,
                )
            )
        return report

    def check_schema_growth(self, files: list) -> ValidationReport:
        """Flag a dataset that suddenly sprouts many new fields."""
        report = ValidationReport()
        limit = int(self.limits.get("max_new_fields_per_dataset", 12))
        flagged = False

        for path in files:
            if path.suffix.lower() != ".jsonl":
                continue
            try:
                lines = [
                    ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()
                ]
            except (OSError, UnicodeDecodeError):
                continue
            if len(lines) < 2:
                continue
            try:
                first = set(json.loads(lines[0]).keys())
                last = set(json.loads(lines[-1]).keys())
            except (json.JSONDecodeError, AttributeError):
                continue
            new_fields = last - first
            if len(new_fields) > limit:
                flagged = True
                report.add(
                    self._issue(
                        "guard.schema_growth",
                        Outcome.FAIL,
                        f"{self.settings.rel(path)}: {len(new_fields)} new fields appeared "
                        f"within one file (limit {limit}): {sorted(new_fields)[:10]}",
                        subject=self.settings.rel(path),
                        observed=len(new_fields),
                        expected=limit,
                    )
                )

        if not flagged:
            report.add(
                self._issue(
                    "guard.schema_growth", Outcome.PASS,
                    "no unexpected schema growth", severity=Severity.INFO,
                )
            )
        return report

    def check_sentinels(self, files: list) -> ValidationReport:
        """Sentinel numbers are a failed extraction wearing a number's clothes."""
        report = ValidationReport()
        sentinels = [str(s) for s in self.config.get("suspicious_numeric_sentinels", [])]
        hits = []
        for path in files:
            if path.suffix.lower() not in (".jsonl", ".csv", ".json"):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for sentinel in sentinels:
                if sentinel in text:
                    hits.append((path, sentinel))
        for path, sentinel in hits:
            report.add(
                self._issue(
                    "guard.sentinel_value",
                    Outcome.FAIL,
                    f"{self.settings.rel(path)} contains sentinel value {sentinel} — "
                    f"a failed extraction must be null with a reason, not a magic number",
                    subject=self.settings.rel(path),
                    observed=sentinel,
                    severity=Severity.WARNING,
                )
            )
        if not hits:
            report.add(
                self._issue(
                    "guard.sentinel_value", Outcome.PASS,
                    "no suspicious sentinel values", severity=Severity.INFO,
                )
            )
        return report

    # -- entry point -------------------------------------------------------

    def run(self) -> ValidationReport:
        files = self.guarded_files()
        report = ValidationReport()
        report.extend(self.check_file_sizes(files))
        report.extend(self.check_total_size(files))
        report.extend(self.check_file_count(files))
        report.extend(self.check_extensions(files))
        report.extend(self.check_binaries(files))
        report.extend(self.check_secrets(files))
        report.extend(self.check_html_error_pages(files))
        report.extend(self.check_duplicate_rows(files))
        report.extend(self.check_schema_growth(files))
        report.extend(self.check_sentinels(files))
        return report


def run_guard(settings: Optional[Settings] = None) -> ValidationReport:
    return RepoGuard(settings).run()
