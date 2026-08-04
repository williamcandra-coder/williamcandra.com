"""As-of selection, and the leak it exists to prevent.

The fixtures contain a real instance of the problem. One issuer's FY2025 net
profit was reported as 54.80T on 2026-07-24 and restated to 53.95T on
2026-07-28. A cutoff before the restatement must return the original — not
because the original is better, but because it is what was knowable, and a
backtest that knows the revision is measuring hindsight.
"""

from __future__ import annotations

import pytest

from engine.goh_dip_tong import MODEL_VERSION
from engine.goh_dip_tong.inputs import loader
from engine.goh_dip_tong.inputs import point_in_time as pit

BEFORE_RESTATEMENT = "2026-07-25"
AFTER_RESTATEMENT = "2026-07-29"
RESTATED_TICKER = "BBCA"


def _net_profit(engine_input):
    for calculated in engine_input.facts:
        if (calculated.metric_id == "net_profit"
                and str(calculated.period.period_type) == "FY"):
            return calculated
    raise AssertionError("the restated FY net_profit is missing from the fixtures")


def _load(settings, ticker=RESTATED_TICKER, as_of=None):
    return loader.load(settings, ticker, as_of=as_of,
                       model_version=MODEL_VERSION,
                       calculated_at="2026-07-31T00:00:00Z")


# --- the restatement -------------------------------------------------------


def test_a_cutoff_before_the_restatement_returns_the_original(sandbox):
    fact = _net_profit(_load(sandbox, as_of=BEFORE_RESTATEMENT))
    assert fact.value == 54_800_000_000_000.0
    assert str(fact.basis) == "REPORTED"


def test_a_cutoff_after_the_restatement_returns_the_revision(sandbox):
    fact = _net_profit(_load(sandbox, as_of=AFTER_RESTATEMENT))
    assert fact.value == 53_950_000_000_000.0
    assert str(fact.basis) == "RESTATED"


def test_the_restatement_is_excluded_by_publication_date_not_period_end(sandbox):
    """Both revisions describe FY2025. Only the cutoff distinguishes them, and
    filtering on period end would keep both."""
    before = _load(sandbox, as_of=BEFORE_RESTATEMENT)
    after = _load(sandbox, as_of=AFTER_RESTATEMENT)
    assert before.selection.excluded_future == 1
    assert after.selection.excluded_future == 0
    assert _net_profit(before).period.period_end == _net_profit(after).period.period_end


# --- no leakage ------------------------------------------------------------


def test_a_fact_published_after_the_cutoff_changes_nothing(sandbox):
    """The no-leakage assertion, made as a byte comparison rather than a
    spot-check: adding a later-published fact must leave the selection
    identical, not merely similar."""
    baseline = _load(sandbox, as_of="2026-07-20")

    path = sandbox.facts_annual / f"{RESTATED_TICKER}.jsonl"
    injected = path.read_text(encoding="utf-8") + (
        '{"ticker":"%s","metric":"revenue","periodType":"FY","periodEnd":'
        '"2025-12-31","periodStart":"2025-01-01","fiscalYear":2025,"basis":'
        '"RESTATED","value":999000000000000.0,"missingReason":null,"unit":"IDR",'
        '"currency":"IDR","revision":9,"qualityStatus":"VALID","segment":null,'
        '"factKey":"%s|revenue|FY|2025-12-31|CONSOLIDATED","source":'
        '{"documentRef":"LATER","publishedAt":"2026-09-01T00:00:00Z",'
        '"retrievedAt":"2026-09-01T00:00:00Z"}}\n'
    ) % (RESTATED_TICKER, RESTATED_TICKER)
    path.write_text(injected, encoding="utf-8")

    after = _load(sandbox, as_of="2026-07-20")
    assert [c.to_json() for c in after.facts] == [c.to_json() for c in baseline.facts]


def test_selection_raises_if_a_future_row_survives_the_filter():
    """A belt-and-braces check on the filter itself. If it ever regresses, the
    numbers downstream are wrong and silence would be the worst outcome."""
    rows = [{"factKey": "X", "revision": 1,
             "source": {"publishedAt": "2030-01-01T00:00:00Z"}}]
    selection = pit.select_facts(rows, "2026-07-31")
    assert selection.rows == []
    assert selection.excluded_future == 1


def test_an_undated_record_is_never_treated_as_known():
    """Admitting it would mean assuming a publication date, which is precisely
    what a cutoff exists to stop doing."""
    rows = [{"factKey": "X", "revision": 1, "value": 1, "source": {}}]
    selection = pit.select_facts(rows, "2026-07-31")
    assert selection.rows == []
    assert selection.excluded_undated == 1


def test_is_known_by_reads_both_flat_and_nested_publication_dates():
    assert pit.is_known_by({"publishedAt": "2026-01-01T00:00:00Z"}, "2026-07-31")
    assert pit.is_known_by({"source": {"publishedAt": "2026-01-01"}}, "2026-07-31")
    assert not pit.is_known_by({"publishedAt": "2026-12-01"}, "2026-07-31")


def test_the_cutoff_day_itself_is_inclusive():
    assert pit.is_known_by({"publishedAt": "2026-07-31T23:00:00Z"}, "2026-07-31")


# --- macro vintages --------------------------------------------------------


def test_a_revised_macro_print_is_only_used_once_its_vintage_has_passed(sandbox):
    """BPS_CPI_YOY 2026-05 exists twice: 2.41 released 2026-06-02, revised to
    2.38 on 2026-07-01. The cutoff must choose between them, not take the
    newest regardless."""
    early = _load(sandbox, as_of="2026-06-15")
    late = _load(sandbox, as_of="2026-07-25")

    def cpi(engine_input):
        rows = [r for r in engine_input.macro
                if r["seriesId"] == "BPS_CPI_YOY"
                and r["observationPeriod"] == "2026-05"]
        assert len(rows) == 1, "one observation must survive, not both vintages"
        return rows[0]

    assert cpi(early)["value"] == 2.41
    assert cpi(early)["releaseVintage"] == "2026-06-02"
    assert cpi(late)["value"] == 2.38
    assert cpi(late)["releaseVintage"] == "2026-07-01"


def test_an_undated_macro_observation_is_excluded(sandbox):
    """OJK_BANK_NPL_GROSS has no publication date in the fixtures."""
    engine_input = _load(sandbox, as_of="2026-07-31")
    assert engine_input.macro_selection.excluded_undated >= 1
    assert not [r for r in engine_input.macro
                if r["seriesId"] == "OJK_BANK_NPL_GROSS"]


# --- determinism -----------------------------------------------------------


@pytest.mark.parametrize("as_of", ["2026-07-20", BEFORE_RESTATEMENT, AFTER_RESTATEMENT])
def test_the_same_cutoff_always_produces_the_same_selection(sandbox, as_of):
    first = [c.to_json() for c in _load(sandbox, as_of=as_of).facts]
    second = [c.to_json() for c in _load(sandbox, as_of=as_of).facts]
    assert first == second


def test_facts_are_ordered_deterministically(sandbox):
    facts = _load(sandbox, as_of=AFTER_RESTATEMENT).facts
    keys = [(c.period.period_end, c.metric_id, c.segment or "") for c in facts]
    assert keys == sorted(keys)
