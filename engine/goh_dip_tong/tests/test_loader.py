"""Reading Stage 1's output, including the parts of it that are ambiguous.

The segment correction is exercised here because it was a real defect: before
it, one issuer's snapshot carried two indistinguishable ``revenue FY2025`` rows
— one consolidated with a value, one segment-level and null — and reported
revenue as a missing critical metric while consolidated revenue sat two lines
above it.
"""

from __future__ import annotations

import json

import pytest

from engine.goh_dip_tong import MODEL_VERSION
from engine.goh_dip_tong.inputs import loader

SEGMENTED = "BBCA"


def _load(settings, ticker=SEGMENTED, as_of="2026-07-31"):
    return loader.load(settings, ticker, as_of=as_of,
                       model_version=MODEL_VERSION,
                       calculated_at="2026-07-31T00:00:00Z")


# --- refusing to guess -----------------------------------------------------


def test_an_absent_snapshot_raises_rather_than_inventing_one(sandbox):
    with pytest.raises(loader.SnapshotMissing, match="will not"):
        _load(sandbox, ticker="ZZZZ")


def test_a_snapshot_failing_its_schema_is_refused(sandbox):
    path = sandbox.input_snapshots / f"{SEGMENTED}.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["facts"][0]["basis"] = "GUESSWORK"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(loader.InputError, match="failed schema validation"):
        _load(sandbox)


def test_a_null_fact_without_a_reason_is_treated_as_corrupt():
    """Stage 1 guarantees every null carries a reason. If one arrives without,
    the input is broken and continuing would mean inventing the reason."""
    from engine.goh_dip_tong.contracts.calculated import from_fact
    from pipeline.goh_dip_tong.contracts.records import ContractError

    with pytest.raises(ContractError, match="without"):
        from_fact(
            {"metric": "revenue", "periodType": "FY", "periodEnd": "2025-12-31",
             "basis": "REPORTED", "value": None, "missingReason": None,
             "unit": "IDR", "qualityStatus": "VALID"},
            model_version=MODEL_VERSION, calculated_at="x", ticker="TEST",
        )


# --- segments --------------------------------------------------------------


def test_the_segment_field_survives_into_the_engine(sandbox):
    facts = _load(sandbox).facts
    revenue = [c for c in facts if c.metric_id == "revenue"]
    segments = {c.segment for c in revenue}
    assert None in segments, "the consolidated row is missing"
    assert "WHOLESALE_BANKING" in segments, "the segment row lost its label"


def test_consolidated_and_segment_facts_are_distinguishable(sandbox):
    """The defect this fixes: without segment they are the same row twice, and
    an engine cannot tell which one to value from."""
    engine_input = _load(sandbox)
    fy_revenue = [
        c for c in engine_input.facts
        if c.metric_id == "revenue" and str(c.period.period_type) == "FY"
    ]
    assert len(fy_revenue) == 2
    consolidated = [c for c in fy_revenue if c.segment is None]
    assert len(consolidated) == 1
    assert consolidated[0].value == 112_500_000_000_000.0


def test_metrics_present_counts_consolidated_facts_only(sandbox):
    """A segment-level null must not make a present consolidated metric look
    absent — which is exactly what it used to do."""
    engine_input = _load(sandbox)
    assert "revenue" in engine_input.metrics_present()


def test_segment_facts_are_excluded_from_the_consolidated_view(sandbox):
    engine_input = _load(sandbox)
    assert all(c.segment is None for c in engine_input.consolidated)
    assert len(engine_input.consolidated) < len(engine_input.facts)


def test_no_ambiguity_is_reported_for_well_formed_inputs(sandbox):
    assert _load(sandbox).ambiguous == []


def test_two_facts_that_cannot_be_told_apart_are_reported_as_ambiguous(sandbox):
    """Choosing between them would be a silent guess that changes a number."""
    path = sandbox.facts_annual / f"{SEGMENTED}.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    twin = dict(rows[0])
    twin["factKey"] = twin["factKey"] + "|TWIN"
    twin["value"] = (twin["value"] or 0) + 1
    path.write_text(
        "".join(json.dumps(r) + "\n" for r in rows + [twin]), encoding="utf-8"
    )
    assert _load(sandbox).ambiguous, "a duplicate metric/period/segment went unreported"


# --- source selection ------------------------------------------------------


def test_the_fact_store_is_preferred_when_it_exists(sandbox):
    """Only the fact store carries revisions, and a cutoff has to choose
    between them."""
    assert _load(sandbox).fact_source == "FACT_STORE"


def test_the_snapshot_is_used_when_no_fact_store_exists(sandbox):
    for directory in (sandbox.facts_annual, sandbox.facts_quarterly):
        for path in directory.glob(f"{SEGMENTED}.jsonl"):
            path.unlink()
    engine_input = _load(sandbox)
    assert engine_input.fact_source == "INPUT_SNAPSHOT"
    assert engine_input.facts, "falling back must still produce facts"


def test_which_source_was_used_is_recorded_in_the_audit(sandbox):
    assert _load(sandbox).to_audit_json()["factSource"] in (
        "FACT_STORE", "INPUT_SNAPSHOT")


# --- inventory -------------------------------------------------------------


def test_available_tickers_are_exactly_the_snapshots_on_disk(sandbox):
    assert loader.available_tickers(sandbox) == ["ASII", "BBCA", "TLKM"]


def test_available_tickers_is_deterministically_ordered(sandbox):
    assert loader.available_tickers(sandbox) == sorted(loader.available_tickers(sandbox))


def test_annual_periods_reflect_what_is_actually_present(sandbox):
    """One annual period is a level, not a trend — which is why the history
    gate fails for every real issuer."""
    assert _load(sandbox).annual_periods() == ["2025-12-31"]


def test_the_synthetic_bank_fixture_has_enough_history_to_model(synthetic_bank):
    engine_input = _load(synthetic_bank, ticker="SYNB")
    assert len(engine_input.annual_periods()) == 5
    assert engine_input.metrics_present() >= {
        "earning_assets", "loans", "deposits", "shares_outstanding",
        "equity_attributable_to_parent", "tier1_capital",
    }
