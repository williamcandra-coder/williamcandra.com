"""A no-change run must be inert, on every calendar date — not just today.

These tests exist because the Stage 1 suite was date-blind. Every check ran on
the date the fixtures were generated, and two separate per-day stamps
(`UNCHANGED` history rows and `companies.json`'s `lastSeenAt`) therefore always
matched what was already committed. The pipeline looked idempotent and was not:
on the first run of any later day it rewrote the history file and all thirty
constituent rows, which under the scheduled workflows means a pull request
containing no facts.

Everything here sweeps the clock deliberately. A test that can only observe one
date cannot see this class of defect.
"""

from __future__ import annotations

import json

import pytest

from ._clock import install as freeze_clock


LATER_DATES = ["2026-08-01", "2026-12-31", "2027-03-14", "2031-06-30"]


def _run(settings, date_iso, monkeypatch):
    """One registry-update in ``settings``' tree, as if it were ``date_iso``."""
    import pipeline.goh_dip_tong.cli as cli

    monkeypatch.setattr(cli, "get_settings", lambda: settings, raising=False)
    monkeypatch.chdir(settings.repo_root)
    freeze_clock(date_iso)
    return cli.main(["registry-update", "--write-mode", "commit"])


def _tree(settings):
    """Content of every committed config/data file, keyed by relative path."""
    out = {}
    for base in (settings.repo_root / "config" / "goh-dip-tong",
                 settings.repo_root / "data" / "goh-dip-tong"):
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            # The per-run audit report is a record of the run, not of the data.
            if not path.is_file() or "quality" in path.parts:
                continue
            out[str(path.relative_to(settings.repo_root))] = path.read_bytes()
    return out


@pytest.fixture
def warm(sandbox, monkeypatch):
    """A sandbox already at steady state, so later runs measure only drift."""
    for _ in range(3):
        _run(sandbox, "2026-07-31", monkeypatch)
    return sandbox


def test_no_change_run_on_a_later_date_changes_nothing(warm, monkeypatch):
    before = _tree(warm)
    for date_iso in LATER_DATES:
        _run(warm, date_iso, monkeypatch)
        assert _tree(warm) == before, f"tree drifted on {date_iso}"


def test_history_gains_no_rows_as_the_calendar_advances(warm, monkeypatch):
    path = warm.repo_root / "config" / "goh-dip-tong" / "idx30.history.jsonl"
    before = path.read_bytes()
    for date_iso in LATER_DATES:
        _run(warm, date_iso, monkeypatch)
    assert path.read_bytes() == before


def test_no_unchanged_row_is_ever_written(warm, monkeypatch):
    path = warm.repo_root / "config" / "goh-dip-tong" / "idx30.history.jsonl"
    for date_iso in LATER_DATES:
        _run(warm, date_iso, monkeypatch)
    written = [json.loads(line) for line in
               path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert [r for r in written if r["changeType"] == "UNCHANGED"] == []


def test_last_seen_at_does_not_rewrite_companies(warm, monkeypatch):
    """The second per-day stamp, and the one that moved thirty rows at a time."""
    path = warm.repo_root / "config" / "goh-dip-tong" / "companies.json"
    before = path.read_bytes()
    for date_iso in LATER_DATES:
        _run(warm, date_iso, monkeypatch)
    assert path.read_bytes() == before


def test_repeated_runs_on_one_date_are_byte_identical(warm, monkeypatch):
    before = _tree(warm)
    for _ in range(3):
        _run(warm, "2027-03-14", monkeypatch)
        assert _tree(warm) == before


def test_a_real_change_is_still_recorded(sandbox, monkeypatch):
    """The fix must not have bought silence by suppressing genuine events."""
    import yaml

    for _ in range(2):
        _run(sandbox, "2026-07-31", monkeypatch)
    path = sandbox.repo_root / "config" / "goh-dip-tong" / "idx30.history.jsonl"
    before = len(path.read_text(encoding="utf-8").splitlines())

    sources = sandbox.repo_root / "config" / "goh-dip-tong" / "sources.yml"
    sources.write_text(
        sources.read_text(encoding="utf-8").replace(
            "fixtures/idx30/2026H1.json", "fixtures/idx30/2026H2.json"),
        encoding="utf-8",
    )
    _run(sandbox, "2027-03-14", monkeypatch)

    rows = [json.loads(line) for line in
            path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) > before, "a genuine membership change was not recorded"
    new = rows[before:]
    assert {r["changeType"] for r in new} <= {
        "ADDED", "REMOVED", "RENAMED", "RECLASSIFIED"}
    assert all(r["observedAt"] == "2027-03-14" for r in new)
    assert yaml.safe_load  # the import is load-bearing for the fixture swap


def test_a_recorded_change_converges_in_one_further_run(sandbox, monkeypatch):
    """After the event is written, the next run must append nothing.

    This is the assertion that failed on main: the change was recorded, then the
    following run added the day's UNCHANGED row on top of it.
    """
    for _ in range(2):
        _run(sandbox, "2026-07-31", monkeypatch)
    sources = sandbox.repo_root / "config" / "goh-dip-tong" / "sources.yml"
    sources.write_text(
        sources.read_text(encoding="utf-8").replace(
            "fixtures/idx30/2026H1.json", "fixtures/idx30/2026H2.json"),
        encoding="utf-8",
    )
    path = sandbox.repo_root / "config" / "goh-dip-tong" / "idx30.history.jsonl"

    _run(sandbox, "2027-03-14", monkeypatch)
    after_change = path.read_bytes()
    _run(sandbox, "2027-03-14", monkeypatch)
    assert path.read_bytes() == after_change, "same-day rerun appended"
    _run(sandbox, "2027-03-15", monkeypatch)
    assert path.read_bytes() == after_change, "next-day rerun appended"


def _reclassify_one_ticker(settings, ticker="BRPT", donor="ADRO"):
    """Fixture whose membership is identical but one ticker's category moved.

    Borrowing a donor's sector/industry rather than inventing one keeps the
    model mapping resolvable, so the test exercises reclassification instead of
    accidentally exercising the ONBOARDING path.
    """
    path = (settings.repo_root / "pipeline" / "goh_dip_tong" / "tests"
            / "fixtures" / "idx30" / "2026H1.json")
    doc = json.loads(path.read_text(encoding="utf-8"))
    by = {c["ticker"]: c for c in doc["constituents"]}
    for field in ("sectorCode", "sectorName", "industryCode", "industryName"):
        by[ticker][field] = by[donor][field]
    out = path.with_name("CATEGORY.json")
    out.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    sources = settings.repo_root / "config" / "goh-dip-tong" / "sources.yml"
    sources.write_text(
        sources.read_text(encoding="utf-8").replace(
            "fixtures/idx30/2026H1.json", "fixtures/idx30/CATEGORY.json"),
        encoding="utf-8",
    )


def test_a_genuine_category_change_is_recorded(sandbox, monkeypatch):
    """Requirement 4: silence on no-change must not silence reclassification.

    Category changes are the quiet ones — membership is unchanged, so a diff
    that only watched the ticker list would miss them entirely, and the Stage 2
    model mapping would silently keep using the old family.
    """
    for _ in range(2):
        _run(sandbox, "2026-07-31", monkeypatch)
    path = sandbox.repo_root / "config" / "goh-dip-tong" / "idx30.history.jsonl"
    before = len(path.read_text(encoding="utf-8").splitlines())

    _reclassify_one_ticker(sandbox)
    _run(sandbox, "2027-03-14", monkeypatch)

    rows = [json.loads(line) for line in
            path.read_text(encoding="utf-8").splitlines() if line.strip()]
    new = rows[before:]
    assert [r["changeType"] for r in new] == ["RECLASSIFIED"], new
    row = new[0]
    assert row["ticker"] == "BRPT"
    assert row["observedAt"] == "2027-03-14"
    assert row["before"]["sectorCode"] != row["after"]["sectorCode"]

    # The category master must follow, or Stage 3 groups by a stale sector.
    categories = json.loads(
        (sandbox.repo_root / "config" / "goh-dip-tong" / "categories.json")
        .read_text(encoding="utf-8"))
    energy = [s for s in categories["sectors"] if s["sectorCode"] == "ENERGY"]
    assert energy and "BRPT" in energy[0]["tickers"]


def test_a_category_change_converges_and_then_stays_quiet(sandbox, monkeypatch):
    """The reclassification is recorded once, not once per subsequent day."""
    for _ in range(2):
        _run(sandbox, "2026-07-31", monkeypatch)
    _reclassify_one_ticker(sandbox)
    path = sandbox.repo_root / "config" / "goh-dip-tong" / "idx30.history.jsonl"

    _run(sandbox, "2027-03-14", monkeypatch)
    settled = path.read_bytes()
    for date_iso in ("2027-03-14", "2027-03-15", "2028-01-01", "2031-06-30"):
        _run(sandbox, date_iso, monkeypatch)
        assert path.read_bytes() == settled, f"appended again on {date_iso}"


def test_no_change_run_creates_no_pr_eligible_diff(sandbox, monkeypatch):
    """Requirement 5, stated the way the workflow states it.

    ``filesChanged=0`` is the pipeline's own accounting. What actually decides
    whether a pull request gets opened is git, via the workflow's

        git add config/goh-dip-tong data/goh-dip-tong
        git diff --quiet

    so the assertion is made against git, not against our own counter. A
    discrepancy between the two would be the interesting failure.
    """
    import subprocess

    root = sandbox.repo_root

    def git(*args, **kwargs):
        return subprocess.run(("git", "-C", str(root)) + args,
                              capture_output=True, text=True, **kwargs)

    for _ in range(3):                       # reach steady state first
        _run(sandbox, "2026-07-31", monkeypatch)

    git("init", "-q")
    git("add", "-A")
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "baseline")
    assert git("status", "--porcelain").stdout == "", "baseline not clean"

    for date_iso in LATER_DATES:
        _run(sandbox, date_iso, monkeypatch)
        git("add", "config/goh-dip-tong", "data/goh-dip-tong")
        staged = git("diff", "--cached", "--stat").stdout.strip()
        assert staged == "", f"{date_iso} would open a pull request:\n{staged}"


def test_replay_still_works_after_the_change(sandbox, monkeypatch):
    """Both replay bases must survive; the fix removes noise, not history."""
    from pipeline.goh_dip_tong.publishing.history import membership_at

    for _ in range(2):
        _run(sandbox, "2026-07-31", monkeypatch)
    sources = sandbox.repo_root / "config" / "goh-dip-tong" / "sources.yml"
    sources.write_text(
        sources.read_text(encoding="utf-8").replace(
            "fixtures/idx30/2026H1.json", "fixtures/idx30/2026H2.json"),
        encoding="utf-8",
    )
    _run(sandbox, "2027-03-14", monkeypatch)

    # Before anything was observed, the universe is empty on both bases.
    assert membership_at("2020-01-01", sandbox, basis="observed") == set()
    assert membership_at("2020-01-01", sandbox, basis="effective") == set()

    observed_before = membership_at("2026-07-31", sandbox, basis="observed")
    observed_after = membership_at("2027-03-14", sandbox, basis="observed")
    assert observed_before, "replay lost the initial universe"
    assert observed_after != observed_before, "replay did not see the change"

    # Effective replay answers a different question and must remain available.
    assert membership_at("2027-03-14", sandbox, basis="effective")

    with pytest.raises(ValueError):
        membership_at("2027-03-14", sandbox, basis="nonsense")
