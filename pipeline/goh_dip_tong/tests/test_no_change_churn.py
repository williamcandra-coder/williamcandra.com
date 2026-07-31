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
