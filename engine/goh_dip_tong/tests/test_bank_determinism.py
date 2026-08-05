"""The valued path is deterministic, and its output never reaches `data/`.

Slice 1 proved this for refusals. A valuation has far more moving parts — three
scenarios, five years each, a solver — so it gets the same treatment: identical
inputs must give identical bytes, on any date and in any process.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys

import pytest

from engine.goh_dip_tong.models.bank import BankModel

from .conftest_bank import AS_OF, context, evaluate, load

LATER_DATES = ["2026-08-01", "2026-12-31", "2027-03-14"]


def _payload(result) -> str:
    return json.dumps(result.to_json(), sort_keys=True)


# --- determinism -----------------------------------------------------------


def test_two_valuations_of_the_same_inputs_are_identical(synthetic_bank):
    assert _payload(evaluate(synthetic_bank)) == _payload(evaluate(synthetic_bank))


def test_the_projection_is_identical_across_runs(synthetic_bank):
    first = evaluate(synthetic_bank).projections["BASE"].to_json()
    second = evaluate(synthetic_bank).projections["BASE"].to_json()
    assert first == second


@pytest.mark.parametrize("as_of", LATER_DATES)
def test_the_valuation_does_not_move_with_the_calendar(synthetic_bank, as_of):
    """Nothing new was published, so the research is unchanged. A valuation
    that drifts with the clock would republish itself every morning."""
    baseline = _payload(evaluate(synthetic_bank))
    later = BankModel().evaluate(load(synthetic_bank, as_of=as_of),
                                 context(synthetic_bank))
    assert _payload(later) == baseline


def test_the_valuation_is_reproducible_in_a_separate_process(repo_root):
    """Run with differing hash seeds. A dict iteration order leaking into the
    scenario loop or the present-value sum would show up here and nowhere else."""
    script = (
        "import sys, json, shutil, tempfile, pathlib; sys.path.insert(0, '.');"
        "from engine.goh_dip_tong import MODEL_VERSION;"
        "from engine.goh_dip_tong.contracts.model import ModelContext;"
        "from engine.goh_dip_tong.inputs import loader;"
        "from engine.goh_dip_tong.models.bank import BankModel;"
        "from engine.goh_dip_tong.settings import EngineSettings;"
        "from engine.goh_dip_tong.valuation.guards import load_guards;"
        "from pipeline.goh_dip_tong.settings import Settings, find_repo_root;"
        "R = find_repo_root();"
        "t = pathlib.Path(tempfile.mkdtemp())/'repo';"
        "shutil.copytree(R/'config'/'goh-dip-tong', t/'config'/'goh-dip-tong');"
        "shutil.copytree(R/'schemas'/'goh-dip-tong', t/'schemas'/'goh-dip-tong');"
        "d = t/'data'/'goh-dip-tong'/'research-snapshots'/'sample'; d.mkdir(parents=True);"
        "shutil.copy2(R/'engine/goh_dip_tong/fixtures/synthetic-bank/SYNB.json', d);"
        "st = EngineSettings(pipeline=Settings(repo_root=t));"
        "cfg = st.engine_config();"
        "ctx = ModelContext(models_config=st.pipeline.models(),"
        " allow_synthetic_cost_of_equity=True,"
        " cost_of_capital_config=st.cost_of_capital(),"
        " scenario_config=st.scenarios(), persistence=0.6,"
        " guards=load_guards(cfg), model_version=MODEL_VERSION, calculated_at='x');"
        "ei = loader.load(st, 'SYNB', as_of='2026-07-31',"
        " model_version=MODEL_VERSION, calculated_at='x');"
        "r = BankModel().evaluate(ei, ctx);"
        "print(json.dumps(r.to_json(), sort_keys=True))"
    )
    digests = []
    for seed in ("0", "1", "12345"):
        result = subprocess.run(
            [sys.executable, "-c", script], cwd=repo_root, capture_output=True,
            text=True, env={"PATH": "/usr/bin:/bin", "PYTHONHASHSEED": seed})
        assert result.returncode == 0, result.stderr[-2000:]
        digests.append(hashlib.sha256(result.stdout.encode()).hexdigest())
    assert len(set(digests)) == 1, digests


def test_the_present_value_sum_runs_in_year_order(synthetic_bank):
    """Float addition is not associative, so the order is the calculation."""
    result = evaluate(synthetic_bank)
    years = [r.period.fiscal_year for r in result.base.residual_income]
    assert years == sorted(years)


# --- synthetic data stays out of the published tree ------------------------


def test_valuing_the_synthetic_bank_writes_nothing_to_the_real_tree(
    synthetic_bank, repo_root
):
    def digest(root):
        return {hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(root.rglob("*")) if p.is_file()}

    before = digest(repo_root / "data/goh-dip-tong")
    evaluate(synthetic_bank)
    assert digest(repo_root / "data/goh-dip-tong") == before


def test_no_synthetic_valuation_figure_appears_under_data(synthetic_bank, repo_root):
    """The strongest form: take the numbers the synthetic bank produced and
    look for them in the published tree."""
    result = evaluate(synthetic_bank)
    values = {round(result.scenarios[s].primary.equity_value.value)
              for s in result.scenario_order}
    published = " ".join(
        p.read_text(encoding="utf-8")
        for p in sorted((repo_root / "data/goh-dip-tong").rglob("*.json")))
    for value in values:
        assert str(value) not in published


def test_the_synthetic_rate_never_appears_under_data(repo_root):
    published = " ".join(
        p.read_text(encoding="utf-8")
        for p in sorted((repo_root / "data/goh-dip-tong").rglob("*")) if p.is_file())
    assert "SYNTHETIC" not in published
