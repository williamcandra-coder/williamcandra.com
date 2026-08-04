"""The output contract: schema, determinism, and no churn on a later date.

The date sweep here is the direct descendant of Stage 1's membership-heartbeat
defect. Everything looked idempotent there because every run happened on the
date the fixtures were generated. A test that only observes one date cannot see
that class of bug, so these deliberately move the calendar.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from engine.goh_dip_tong import ENGINE_VERSION, FORMULA_REGISTRY_HASH, MODEL_VERSION
from engine.goh_dip_tong.contracts.model import ModelContext
from engine.goh_dip_tong.inputs import loader
from engine.goh_dip_tong.models.registry import model_for
from engine.goh_dip_tong.publishing import snapshot as snapshot_mod
from pipeline.goh_dip_tong.publishing.writers import read_json

#: Later cutoffs at which nothing new was published, so the research is
#: unchanged. They stop short of the staleness threshold on purpose: going
#: stale is a genuine change in what the document says, and is asserted
#: separately below.
LATER_DATES = ["2026-08-01", "2026-12-31", "2027-03-14", "2027-07-31"]

#: Far enough past the newest input (2026-07-28) to exceed the 400-day
#: staleness limit in engine.yml.
STALE_DATE = "2031-06-30"


def _build(settings, ticker="BBCA", as_of="2026-07-31",
           calculated_at="2026-07-31T00:00:00Z"):
    engine_input = loader.load(settings, ticker, as_of=as_of,
                               model_version=MODEL_VERSION,
                               calculated_at=calculated_at)
    model = model_for(settings.pipeline.models(),
                      engine_input.identity.get("modelFamily"))
    context = ModelContext(models_config=settings.pipeline.models())
    return snapshot_mod.build(settings, engine_input, model, context, calculated_at)


def _tree(settings):
    root = settings.output_root
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*.json")) if "sample" not in p.parts
    }


# --- schema ----------------------------------------------------------------


@pytest.mark.parametrize("ticker", ["BBCA", "TLKM", "ASII"])
def test_output_validates_against_the_research_snapshot_schema(sandbox, ticker):
    document = _build(sandbox, ticker)
    report = snapshot_mod.validate(sandbox, document)
    assert report.ok, [i.message for i in report.critical_failures]


def test_the_output_schema_is_distinct_from_the_input_schema(real_engine):
    """Conflating them is how a derived figure eventually gets read back as a
    reported one."""
    assert real_engine.output_schema_file.exists()
    assert real_engine.output_schema_file.name != "research-input.schema.json"


def test_a_document_without_a_mode_fails_validation(sandbox):
    document = _build(sandbox)
    del document["mode"]
    assert not snapshot_mod.validate(sandbox, document).ok


def test_a_document_with_an_invented_mode_fails_validation(sandbox):
    document = _build(sandbox)
    document["mode"] = "LIVE"
    assert not snapshot_mod.validate(sandbox, document).ok


def test_a_null_value_without_a_reason_fails_validation(sandbox):
    """The missing-versus-zero rule, enforced at the schema boundary."""
    document = _build(sandbox, "TLKM")
    nulls = [v for v in document["reported"]["values"] if v["value"] is None]
    assert nulls, "TLKM's treasury_shares should be null in the fixtures"
    nulls[0]["missingReason"] = None
    assert not snapshot_mod.validate(sandbox, document).ok


def test_a_value_without_a_formula_id_fails_validation(sandbox):
    document = _build(sandbox)
    document["reported"]["values"][0]["formulaId"] = ""
    assert not snapshot_mod.validate(sandbox, document).ok


# --- the document's shape --------------------------------------------------


def test_every_section_the_spec_requires_is_present(sandbox):
    document = _build(sandbox)
    for key in ("company", "coverage", "freshness", "quality", "reported",
                "normalized", "derivedMetrics", "drivers", "forecast",
                "valuation", "marketImplied", "thesis", "counterThesis",
                "catalysts", "risks", "breakers", "evidence", "uncleView",
                "analystView", "modelAudit"):
        assert key in document, key


def test_unbuilt_sections_say_so_rather_than_being_empty(sandbox):
    """An empty object leaves a reader guessing whether the engine tried."""
    document = _build(sandbox)
    for key in ("forecast", "drivers", "uncleView", "analystView"):
        assert document[key]["status"] == "NOT_PRODUCED"
        assert document[key]["reason"]


def test_market_implied_is_unavailable_for_a_rights_reason(sandbox):
    """Spec section 2.7 is blocked by the rights gate, not by an unimplemented
    feature, and the output should say which."""
    market = _build(sandbox)["marketImplied"]
    assert market["available"] is False
    assert "rights" in market["reason"].lower()


def test_research_status_is_model_under_validation(sandbox):
    assert _build(sandbox)["researchStatus"] == "MODEL_UNDER_VALIDATION"


def test_stage_1_coverage_status_is_carried_through_unchanged(sandbox):
    """Two vocabularies, one owner each. The engine reads coverageStatus and
    never writes it."""
    document = _build(sandbox)
    snapshot = read_json(sandbox.input_snapshots / "BBCA.json")
    assert document["coverage"]["coverageStatus"] == snapshot["identity"]["coverageStatus"]


def test_output_completeness_measures_what_the_model_needs(sandbox):
    """Not what the issuer happened to report. This issuer's reported facts are
    all present and it is still missing fifteen of seventeen required metrics."""
    document = _build(sandbox)
    assert document["quality"]["completeness"] == pytest.approx(2 / 17, abs=1e-4)
    assert len(document["quality"]["missingCriticalMetrics"]) == 15


def test_the_audit_records_the_registry_hash_and_version(sandbox):
    audit = _build(sandbox)["modelAudit"]
    assert audit["formulaRegistryHash"] == FORMULA_REGISTRY_HASH
    assert audit["modelVersion"] == MODEL_VERSION
    assert audit["engineVersion"] == ENGINE_VERSION


def test_evidence_points_back_at_source_records(sandbox):
    evidence = _build(sandbox)["evidence"]
    assert evidence
    assert any(e["ref"].startswith("BBCA|") for e in evidence)
    assert any(e["kind"] == "MACRO" for e in evidence)


def test_macro_context_is_marked_as_not_used_in_any_calculation(sandbox):
    """BI_7DRR is context. Nothing discounts with it."""
    macro = _build(sandbox)["modelAudit"]["macroContext"]
    assert macro
    assert all(row["usedInCalculation"] is False for row in macro)


# --- determinism -----------------------------------------------------------


def test_two_builds_of_the_same_inputs_are_identical(sandbox):
    first = _build(sandbox, calculated_at="2026-07-31T01:00:00Z")
    second = _build(sandbox, calculated_at="2026-07-31T23:59:00Z")
    assert first["contentHash"] == second["contentHash"]


def test_the_content_hash_ignores_the_run_timestamp(sandbox):
    """calculatedAt records when we ran, not what we found."""
    first = _build(sandbox, calculated_at="2020-01-01T00:00:00Z")
    second = _build(sandbox, calculated_at="2031-01-01T00:00:00Z")
    assert first["contentHash"] == second["contentHash"]


@pytest.mark.parametrize("as_of", LATER_DATES)
def test_the_content_hash_does_not_move_with_the_calendar(sandbox, as_of):
    """The date sweep. Identical evidence on a later cutoff is the same
    research, and must not present itself as new."""
    baseline = _build(sandbox, as_of="2026-07-31")
    assert _build(sandbox, as_of=as_of)["contentHash"] == baseline["contentHash"]


def test_inputs_going_stale_is_a_real_change_and_does_move_the_hash(sandbox):
    """The counterpart to the date sweep. Time passing changes nothing — until
    it crosses the staleness threshold, at which point the document genuinely
    says something different and must not pretend otherwise."""
    fresh = _build(sandbox, as_of="2026-07-31")
    stale = _build(sandbox, as_of=STALE_DATE)
    assert fresh["freshness"]["stale"] is False
    assert stale["freshness"]["stale"] is True
    assert stale["researchStatus"] == "STALE"
    assert stale["contentHash"] != fresh["contentHash"]


def test_the_content_hash_does_move_when_the_evidence_changes(sandbox):
    """The other half: a cutoff that genuinely changes what was knowable must
    produce different research."""
    before = _build(sandbox, as_of="2026-07-25")
    after = _build(sandbox, as_of="2026-07-29")
    assert before["contentHash"] != after["contentHash"]


def test_the_build_is_reproducible_in_a_separate_process(repo_root):
    """Run three times with different hash seeds. A dict iteration order
    leaking into output would show up here and nowhere else."""
    script = (
        "import sys; sys.path.insert(0, '.');"
        "from engine.goh_dip_tong.contracts.model import ModelContext;"
        "from engine.goh_dip_tong.inputs import loader;"
        "from engine.goh_dip_tong.models.registry import model_for;"
        "from engine.goh_dip_tong.publishing import snapshot as s;"
        "from engine.goh_dip_tong.settings import get_engine_settings;"
        "st = get_engine_settings();"
        "ei = loader.load(st, 'BBCA', as_of='2026-07-31',"
        " model_version='0.1.0', calculated_at='x');"
        "m = model_for(st.pipeline.models(), ei.identity.get('modelFamily'));"
        "d = s.build(st, ei, m, ModelContext(models_config=st.pipeline.models()), 'x');"
        "print(d['contentHash'])"
    )
    hashes = []
    for seed in ("0", "1", "12345"):
        result = subprocess.run(
            [sys.executable, "-c", script], cwd=repo_root, capture_output=True,
            text=True, env={"PATH": "/usr/bin:/bin", "PYTHONHASHSEED": seed},
        )
        assert result.returncode == 0, result.stderr
        hashes.append(result.stdout.strip())
    assert len(set(hashes)) == 1, hashes


# --- writing ---------------------------------------------------------------


def test_a_first_build_writes_a_dated_snapshot_and_a_pointer(sandbox):
    document = _build(sandbox)
    path, pointer, unchanged = snapshot_mod.write(sandbox, document)
    assert not unchanged
    assert path.exists() and pointer.exists()
    assert path.name == f"{MODEL_VERSION}.json"
    assert path.parent.name == document["asOf"]
    assert path.parent.parent.name == "BBCA"


def test_rebuilding_identical_content_writes_nothing(sandbox):
    snapshot_mod.write(sandbox, _build(sandbox))
    before = _tree(sandbox)
    _, _, unchanged = snapshot_mod.write(sandbox, _build(sandbox))
    assert unchanged
    assert _tree(sandbox) == before


@pytest.mark.parametrize("as_of", LATER_DATES)
def test_rebuilding_on_a_later_date_deposits_nothing(sandbox, as_of):
    """Without this, a daily rebuild leaves an identical document under a new
    date every day and the repository grows with no information in it."""
    snapshot_mod.write(sandbox, _build(sandbox, as_of="2026-07-31"))
    before = _tree(sandbox)
    _, _, unchanged = snapshot_mod.write(sandbox, _build(sandbox, as_of=as_of))
    assert unchanged
    assert _tree(sandbox) == before


def test_the_pointer_carries_the_snapshot_s_date_not_today_s(sandbox):
    snapshot_mod.write(sandbox, _build(sandbox, as_of="2026-07-31"))
    pointer = read_json(sandbox.output_current / "BBCA.json")
    assert pointer["asOf"] == "2026-07-31"
    snapshot_mod.write(sandbox, _build(sandbox, as_of="2027-08-31"))
    assert read_json(sandbox.output_current / "BBCA.json")["asOf"] == "2026-07-31"


def test_a_genuine_change_does_produce_a_new_snapshot(sandbox):
    """The fix must not have bought quiet by suppressing real changes."""
    snapshot_mod.write(sandbox, _build(sandbox, as_of="2026-07-25"))
    before = _tree(sandbox)
    _, _, unchanged = snapshot_mod.write(sandbox, _build(sandbox, as_of="2026-07-29"))
    assert not unchanged
    assert _tree(sandbox) != before
    assert len(snapshot_mod.stored_snapshots(sandbox, "BBCA")) == 2


def test_written_bytes_are_stable_across_repeated_writes(sandbox):
    snapshot_mod.write(sandbox, _build(sandbox))
    first = _tree(sandbox)
    for _ in range(3):
        snapshot_mod.write(sandbox, _build(sandbox))
    assert _tree(sandbox) == first


def test_written_json_is_canonical_and_newline_terminated(sandbox):
    path, _, _ = snapshot_mod.write(sandbox, _build(sandbox))
    text = path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert json.loads(text)["ticker"] == "BBCA"
    assert "\r\n" not in text


# --- the CLI ---------------------------------------------------------------


def test_the_cli_builds_every_available_issuer_without_writing(
    sandbox, monkeypatch, capsys
):
    from engine.goh_dip_tong import cli

    monkeypatch.setattr(cli, "get_engine_settings", lambda: sandbox)
    assert cli.main(["research-build", "--all"]) == 0
    out = capsys.readouterr().out
    for ticker in ("BBCA", "TLKM", "ASII"):
        assert ticker in out
    assert "valuation=REFUSED" in out
    assert _tree(sandbox) == {}, "validate_only must write nothing"


def test_the_cli_writes_only_in_commit_mode(sandbox, monkeypatch):
    from engine.goh_dip_tong import cli

    monkeypatch.setattr(cli, "get_engine_settings", lambda: sandbox)
    assert cli.main(["research-build", "--ticker", "BBCA",
                     "--write-mode", "commit"]) == 0
    assert _tree(sandbox)


def test_the_cli_skips_a_ticker_with_no_input_snapshot(sandbox, monkeypatch, capsys):
    from engine.goh_dip_tong import cli

    monkeypatch.setattr(cli, "get_engine_settings", lambda: sandbox)
    assert cli.main(["research-build", "--ticker", "ZZZZ"]) == 0
    assert "SKIP ZZZZ" in capsys.readouterr().out


def test_the_cli_requires_a_target(sandbox, monkeypatch):
    from engine.goh_dip_tong import cli

    monkeypatch.setattr(cli, "get_engine_settings", lambda: sandbox)
    assert cli.main(["research-build"]) == 2
