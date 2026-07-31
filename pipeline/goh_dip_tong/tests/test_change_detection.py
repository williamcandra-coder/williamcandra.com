"""Stage 1 tests: change detection, sector/category changes, and the
append-only membership history.
"""

from __future__ import annotations

from pipeline.goh_dip_tong.contracts.enums import ChangeType, CoverageStatus
from pipeline.goh_dip_tong.publishing import history, registry_config
from pipeline.goh_dip_tong.publishing.change_detection import (
    detect_changes,
    has_material_change,
    summarise_changes,
)

OBSERVED = "2026-08-04T00:00:00Z"


def types_of(changes):
    return sorted(str(c.change_type) for c in changes)


# --- the four change types -------------------------------------------------


def test_added_is_detected(constituent_factory):
    previous = [constituent_factory(ticker="BBCA")]
    current = previous + [constituent_factory(ticker="TLKM", name="Telkom Indonesia Tbk")]
    changes = detect_changes(previous, current, OBSERVED)
    assert types_of(changes) == ["ADDED"]
    assert changes[0].ticker == "TLKM"
    assert changes[0].before is None and changes[0].after is not None


def test_removed_is_detected_and_never_deletes_the_record(constituent_factory):
    previous = [constituent_factory(ticker="BBCA"), constituent_factory(ticker="ESSA",
                                                                        name="Essa Tbk")]
    current = [constituent_factory(ticker="BBCA")]
    changes = detect_changes(previous, current, OBSERVED)
    assert types_of(changes) == ["REMOVED"]
    # The removal event carries the full prior snapshot, so nothing is lost.
    assert changes[0].before["name"] == "Essa Tbk"
    assert "retained" in changes[0].detail


def test_renamed_is_detected(constituent_factory):
    previous = [constituent_factory(ticker="ADRO", name="Alamtri Resources Indonesia Tbk")]
    current = [constituent_factory(ticker="ADRO", name="Alamtri Resources Tbk")]
    changes = detect_changes(previous, current, OBSERVED)
    assert types_of(changes) == ["RENAMED"]
    assert changes[0].before["name"] != changes[0].after["name"]


def test_reclassified_is_detected(constituent_factory):
    previous = [constituent_factory(ticker="BRPT", sector="BASIC_MATERIALS",
                                    industry="CHEMICALS", model="CHEMICALS")]
    current = [constituent_factory(ticker="BRPT", sector="INDUSTRIALS",
                                   industry="INDUSTRIAL_CONGLOMERATES",
                                   model="CONGLOMERATE")]
    changes = detect_changes(previous, current, OBSERVED)
    assert types_of(changes) == ["RECLASSIFIED"]
    assert "sector BASIC_MATERIALS → INDUSTRIALS" in changes[0].detail
    assert "industry CHEMICALS → INDUSTRIAL_CONGLOMERATES" in changes[0].detail


def test_coverage_status_change_is_a_reclassification(constituent_factory):
    previous = [constituent_factory(ticker="GOTO", model=None,
                                    coverage=CoverageStatus.ONBOARDING)]
    current = [constituent_factory(ticker="GOTO", model="TECH",
                                   coverage=CoverageStatus.FINANCIALS)]
    changes = detect_changes(previous, current, OBSERVED)
    assert types_of(changes) == ["RECLASSIFIED"]
    assert "coverage ONBOARDING → FINANCIALS" in changes[0].detail


def test_rename_and_reclassify_together_produce_two_distinct_events(constituent_factory):
    """They are separate facts; collapsing them would lose information."""
    previous = [constituent_factory(ticker="BRPT", name="Old Name Tbk",
                                    sector="BASIC_MATERIALS", industry="CHEMICALS",
                                    model="CHEMICALS")]
    current = [constituent_factory(ticker="BRPT", name="New Name Tbk",
                                   sector="INDUSTRIALS",
                                   industry="INDUSTRIAL_CONGLOMERATES",
                                   model="CONGLOMERATE")]
    changes = detect_changes(previous, current, OBSERVED)
    assert types_of(changes) == ["RECLASSIFIED", "RENAMED"]


def test_no_change_produces_nothing(constituent_factory):
    universe = [constituent_factory(ticker="BBCA")]
    assert detect_changes(universe, universe, OBSERVED) == []


def test_no_change_produces_nothing_on_any_date(constituent_factory):
    """The regression this fixes was invisible on the seed date.

    An UNCHANGED row keyed on the observation date meant the first run of every
    new calendar day appended one, so the history churned and a no-change run
    opened an empty pull request. Because every run happened on the date the
    fixtures were generated, the row always deduplicated and nothing looked
    wrong. Sweeping the date is what makes the assertion mean anything.
    """
    universe = [constituent_factory(ticker="BBCA")]
    for observed in ("2026-01-01", "2026-07-30", "2026-07-31", "2027-03-14",
                     "2031-12-31"):
        assert detect_changes(universe, universe, observed) == [], observed


def test_detect_changes_has_no_unchanged_switch(constituent_factory):
    """No caller can opt the heartbeat back in."""
    import inspect

    assert "emit_unchanged" not in inspect.signature(detect_changes).parameters


def test_legacy_unchanged_rows_are_still_treated_as_immaterial():
    """Rows written before the fix stay in the committed history.

    They are never rewritten — the file is append-only — so every consumer has
    to keep tolerating them rather than assuming they cannot occur.
    """
    from pipeline.goh_dip_tong.contracts.enums import ChangeType
    from pipeline.goh_dip_tong.contracts.records import MembershipChange

    legacy = MembershipChange(
        change_type=ChangeType.UNCHANGED, ticker="*", observed_at="2026-07-30",
        effective_from=None, before=None, after={"constituentCount": 30},
        detail="universe verified unchanged (30 constituents)", source_ref=None,
    )
    assert not has_material_change([legacy])


def test_first_run_reports_every_constituent_as_added(idx30_h1, real_settings):
    current = _constituents_from(idx30_h1, real_settings)
    changes = detect_changes([], current, OBSERVED)
    assert len(changes) == len(current) == 30
    assert set(types_of(changes)) == {"ADDED"}


def test_full_period_transition_h1_to_h2(idx30_h1, idx30_h2, real_settings):
    """The two fixtures differ by one add, one removal, one rename and one
    reclassification — every change type in a single realistic diff."""
    previous = _constituents_from(idx30_h1, real_settings)
    current = _constituents_from(idx30_h2, real_settings)
    changes = detect_changes(previous, current, OBSERVED, effective_from="2026-08-04")

    by_type = {}
    for change in changes:
        by_type.setdefault(str(change.change_type), []).append(change.ticker)

    assert by_type["ADDED"] == ["GOTO"]
    assert by_type["REMOVED"] == ["ESSA"]
    assert by_type["RENAMED"] == ["ADRO"]
    assert by_type["RECLASSIFIED"] == ["BRPT"]
    assert has_material_change(changes)


def _constituents_from(document, settings):
    from pipeline.goh_dip_tong.contracts.records import Constituent

    raw = [
        Constituent(
            ticker=r["ticker"], name=r["name"], sector_code=r["sectorCode"],
            sector_name=r["sectorName"], industry_code=r["industryCode"],
            industry_name=r["industryName"], model_family=None,
            coverage_status=CoverageStatus.ONBOARDING,
            entered_at=r["enteredAt"], source_ref=r["sourceRef"],
        )
        for r in document["constituents"]
    ]
    return registry_config.apply_model_mapping(raw, settings.models())


# --- diff summary ----------------------------------------------------------


def test_summary_is_human_readable(constituent_factory):
    previous = [constituent_factory(ticker="BBCA")]
    current = [constituent_factory(ticker="TLKM", name="Telkom Indonesia Tbk")]
    text = summarise_changes(detect_changes(previous, current, OBSERVED))
    assert "### ADDED (1)" in text and "### REMOVED (1)" in text
    assert "**TLKM**" in text and "**BBCA**" in text


def test_summary_of_no_changes_says_so():
    assert "No IDX30 membership" in summarise_changes([])


# --- append-only history ---------------------------------------------------


def test_history_is_append_only_and_idempotent(sandbox, constituent_factory):
    previous = [constituent_factory(ticker="BBCA")]
    current = previous + [constituent_factory(ticker="TLKM", name="Telkom Indonesia Tbk")]
    changes = detect_changes(previous, current, OBSERVED)

    changed, appended = history.append_changes(changes, sandbox)
    assert changed and appended == 1
    first = sandbox.idx30_history.read_text(encoding="utf-8")

    # Re-appending the identical change must be a no-op.
    changed, appended = history.append_changes(changes, sandbox)
    assert not changed and appended == 0
    assert sandbox.idx30_history.read_text(encoding="utf-8") == first


def test_repeated_unchanged_runs_on_one_day_append_nothing(sandbox,
                                                           constituent_factory):
    """A four-times-daily workflow must not append anything at all."""
    universe = [constituent_factory(ticker="BBCA")]
    for _ in range(4):
        changes = detect_changes(universe, universe, "2026-08-04T09:17:00Z")
        history.append_changes(changes, sandbox)
    assert history.load_history(sandbox) == []


def test_later_days_still_append_nothing(sandbox, constituent_factory):
    """The inverted assertion.

    This test previously required a new row on each new day, which is the
    defect written down as a requirement: the history grew by one row per day
    forever while the index stood still. Crossing a day boundary is not an
    event.
    """
    universe = [constituent_factory(ticker="BBCA")]
    for day in ("2026-08-04T09:00:00Z", "2026-08-05T09:00:00Z",
                "2027-01-01T09:00:00Z", "2031-06-30T09:00:00Z"):
        history.append_changes(detect_changes(universe, universe, day), sandbox)
    assert history.load_history(sandbox) == []


def test_a_real_change_on_a_later_day_does_append(sandbox, constituent_factory):
    """The counterpart: silence on no-change must not mean silence on change."""
    before = [constituent_factory(ticker="BBCA")]
    after = [constituent_factory(ticker="BBCA"), constituent_factory(ticker="BBRI")]

    history.append_changes(detect_changes(before, before, "2026-08-04T09:00:00Z"),
                           sandbox)
    assert history.load_history(sandbox) == []

    history.append_changes(detect_changes(before, after, "2027-01-01T09:00:00Z"),
                           sandbox)
    rows = history.load_history(sandbox)
    assert [r["changeType"] for r in rows] == ["ADDED"]
    assert rows[0]["ticker"] == "BBRI"
    assert rows[0]["observedAt"] == "2027-01-01"


def test_existing_history_rows_are_never_rewritten(sandbox, constituent_factory):
    history.append_changes(
        detect_changes([], [constituent_factory(ticker="BBCA")], "2026-02-02T00:00:00Z"),
        sandbox,
    )
    original_first_line = sandbox.idx30_history.read_text(encoding="utf-8").splitlines()[0]

    history.append_changes(
        detect_changes([constituent_factory(ticker="BBCA")],
                       [constituent_factory(ticker="BBCA"),
                        constituent_factory(ticker="TLKM", name="Telkom Indonesia Tbk")],
                       "2026-08-04T00:00:00Z"),
        sandbox,
    )
    lines = sandbox.idx30_history.read_text(encoding="utf-8").splitlines()
    assert lines[0] == original_first_line
    assert len(lines) == 2


def test_membership_can_be_reconstructed_at_a_past_date(sandbox, constituent_factory):
    """History is only worth keeping if a past universe can be rebuilt from it."""
    history.append_changes(
        detect_changes([], [constituent_factory(ticker="BBCA"),
                            constituent_factory(ticker="ESSA", name="Essa Tbk")],
                       "2026-02-02T00:00:00Z"),
        sandbox,
    )
    history.append_changes(
        detect_changes([constituent_factory(ticker="BBCA"),
                        constituent_factory(ticker="ESSA", name="Essa Tbk")],
                       [constituent_factory(ticker="BBCA"),
                        # entered_at must be the date GOTO actually joined, or an
                        # effective-basis replay would place it in the index from
                        # the start of the year.
                        constituent_factory(ticker="GOTO", name="GoTo Tbk",
                                            sector="TECHNOLOGY",
                                            industry="SOFTWARE_AND_IT_SERVICES",
                                            model=None,
                                            coverage=CoverageStatus.ONBOARDING,
                                            entered_at="2026-08-04")],
                       "2026-08-04T00:00:00Z",
                       effective_from="2026-08-04"),
        sandbox,
    )

    assert history.membership_at("2026-03-01", sandbox) == {"BBCA", "ESSA"}
    assert history.membership_at("2026-09-01", sandbox) == {"BBCA", "GOTO"}
    # The observed-basis replay agrees here because collection was same-day.
    assert history.membership_at("2026-09-01", sandbox, basis="observed") == \
        {"BBCA", "GOTO"}


def test_former_members_are_retained_in_companies_json(constituent_factory):
    """A company leaving the index must not vanish from the master."""
    first = registry_config.build_companies_document(
        [constituent_factory(ticker="BBCA"),
         constituent_factory(ticker="ESSA", name="Essa Tbk")],
        observed_at="2026-02-02T00:00:00Z",
    )
    second = registry_config.build_companies_document(
        [constituent_factory(ticker="BBCA")],
        previous=first, observed_at="2026-08-04T00:00:00Z",
    )

    by_ticker = {c["ticker"]: c for c in second["companies"]}
    assert set(by_ticker) == {"BBCA", "ESSA"}
    assert by_ticker["BBCA"]["inIdx30"] is True
    assert by_ticker["ESSA"]["inIdx30"] is False
    assert by_ticker["ESSA"]["lastSeenAt"] == "2026-02-02"


def test_name_and_classification_history_accumulate(constituent_factory):
    first = registry_config.build_companies_document(
        [constituent_factory(ticker="ADRO", name="Alamtri Resources Indonesia Tbk",
                             sector="ENERGY", industry="COAL", model="ENERGY_COAL")],
        observed_at="2026-02-02T00:00:00Z",
    )
    second = registry_config.build_companies_document(
        [constituent_factory(ticker="ADRO", name="Alamtri Resources Tbk",
                             sector="ENERGY", industry="COAL", model="ENERGY_COAL")],
        previous=first, observed_at="2026-08-04T00:00:00Z",
    )
    company = second["companies"][0]
    assert [n["name"] for n in company["nameHistory"]] == [
        "Alamtri Resources Indonesia Tbk", "Alamtri Resources Tbk"
    ]
    # Classification did not change, so it must not gain a duplicate entry.
    assert len(company["classificationHistory"]) == 1
    assert company["firstSeenAt"] == "2026-02-02"


def test_membership_replay_distinguishes_effective_from_observed(sandbox,
                                                                 constituent_factory):
    """An index review is published before it takes effect, so 'what the index
    was' and 'what we knew' are different questions with different answers."""
    history.append_changes(
        detect_changes([], [constituent_factory(ticker="BBCA")],
                       observed_at="2026-01-05T00:00:00Z",
                       effective_from="2026-02-02"),
        sandbox,
    )

    # Observed in January, effective in February.
    assert history.membership_at("2026-01-10", sandbox, basis="observed") == {"BBCA"}
    assert history.membership_at("2026-01-10", sandbox, basis="effective") == set()
    assert history.membership_at("2026-02-15", sandbox, basis="effective") == {"BBCA"}


def test_membership_replay_rejects_an_unknown_basis(sandbox):
    import pytest as _pytest

    with _pytest.raises(ValueError, match="basis must be"):
        history.membership_at("2026-01-01", sandbox, basis="whenever")
