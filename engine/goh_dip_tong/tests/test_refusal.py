"""Refusal as a result: gates, precedence, and the methods a family may not use.

The instruction these tests hold to is explicit: every real Stage 1 fixture
issuer must return a refused valuation until a validated risk-free input, the
required bank facts, a share count and market data all exist. None of those
exists, so all four gates fail — and the refusal has to say so specifically
enough that a reader knows which one to fix first.
"""

from __future__ import annotations

import pytest

from engine.goh_dip_tong import MODEL_VERSION
from engine.goh_dip_tong.contracts.enums import GateId, RefusalReason, ValuationMethod
from engine.goh_dip_tong.contracts.model import ModelContext
from engine.goh_dip_tong.contracts.refusal import (
    GateReport,
    MethodNotPermitted,
    ValuationRefusal,
)
from engine.goh_dip_tong.inputs import loader
from engine.goh_dip_tong.models.bank import BANK_REQUIRED_METRICS, BankModel
from engine.goh_dip_tong.models.registry import NoModel, build_registry, model_for
from pipeline.goh_dip_tong.contracts.records import ContractError

BANK_TICKER = "BBCA"


def _context(settings) -> ModelContext:
    return ModelContext(models_config=settings.pipeline.models())


def _evaluate(settings, ticker=BANK_TICKER):
    engine_input = loader.load(settings, ticker, as_of="2026-07-31",
                               model_version=MODEL_VERSION, calculated_at="x")
    model = model_for(settings.pipeline.models(),
                      engine_input.identity.get("modelFamily"))
    return engine_input, model, model.evaluate(engine_input, _context(settings))


# --- the bank issuer, the case the instruction names ----------------------


def test_the_bank_issuer_valuation_is_refused(sandbox):
    _, _, result = _evaluate(sandbox)
    assert isinstance(result, ValuationRefusal)
    assert result.to_json()["status"] == "REFUSED"


def test_the_refusal_names_insufficient_inputs_as_the_headline(sandbox):
    """Not "model not implemented": implementing the mathematics would not
    produce a number, so that would point at the wrong problem."""
    _, _, result = _evaluate(sandbox)
    assert result.reason == RefusalReason.INSUFFICIENT_INPUTS


def test_the_refusal_lists_every_gate_that_failed(sandbox):
    """MODEL_IMPLEMENTED is deliberately absent: the BANK mathematics exists
    now, and the refusal is entirely about the data."""
    _, _, result = _evaluate(sandbox)
    assert set(result.failed_gates) >= {
        GateId.REQUIRED_INPUTS_PRESENT,
        GateId.PER_SHARE_INPUTS,
        GateId.MIN_HISTORY_PERIODS,
        GateId.VALIDATED_RISK_FREE_RATE,
        GateId.MARKET_DATA_AVAILABLE,
    }
    assert GateId.MODEL_IMPLEMENTED not in set(result.failed_gates)


def test_the_refusal_names_the_missing_metrics(sandbox):
    _, _, result = _evaluate(sandbox)
    missing = set(result.missing_inputs)
    assert {"shares_outstanding", "equity_attributable_to_parent", "loans",
            "deposits", "tier1_capital"} <= missing
    # The two this issuer does report must not appear as missing.
    assert "interest_income" not in missing
    assert "net_profit_attributable_to_parent" not in missing


def test_the_refusal_carries_a_note_a_reader_can_act_on(sandbox):
    _, _, result = _evaluate(sandbox)
    assert BANK_TICKER in result.note
    assert "No valuation is produced" in result.note


@pytest.mark.parametrize("ticker", ["BBCA", "TLKM", "ASII"])
def test_every_real_fixture_issuer_is_refused(sandbox, ticker):
    _, _, result = _evaluate(sandbox, ticker)
    assert isinstance(result, ValuationRefusal)


@pytest.mark.parametrize("ticker", ["BBCA", "TLKM", "ASII"])
def test_no_real_issuer_passes_the_risk_free_gate(sandbox, ticker):
    """BI_7DRR is a policy rate, not a risk-free yield, and nothing else exists."""
    engine_input, model, _ = _evaluate(sandbox, ticker)
    report = model.gates(engine_input, _context(sandbox))
    gate = [g for g in report.gates if g.gate_id == GateId.VALIDATED_RISK_FREE_RATE][0]
    assert not gate.passed
    assert "BI_7DRR" in gate.detail


def test_even_the_synthetic_bank_is_refused_without_explicit_permission(synthetic_bank):
    """Complete data is not enough. The synthetic discount rate has to be asked
    for by name, which the CLI never does."""
    _, _, result = _evaluate(synthetic_bank, "SYNB")
    assert isinstance(result, ValuationRefusal)
    assert result.reason == RefusalReason.NO_VALIDATED_RISK_FREE_RATE


def test_the_synthetic_bank_clears_the_data_gates(synthetic_bank):
    """Which is what makes it useful: the only gates left are the ones about
    assumptions and unimplemented mathematics, not about missing facts."""
    engine_input = loader.load(synthetic_bank, "SYNB", as_of="2026-07-31",
                               model_version=MODEL_VERSION, calculated_at="x")
    report = BankModel().gates(engine_input, _context(synthetic_bank))
    failed = {g.gate_id for g in report.failed}
    assert GateId.REQUIRED_INPUTS_PRESENT not in failed
    assert GateId.PER_SHARE_INPUTS not in failed
    assert GateId.MIN_HISTORY_PERIODS not in failed


# --- method policy ---------------------------------------------------------


@pytest.mark.parametrize("method", [
    ValuationMethod.EV_EBITDA,
    ValuationMethod.ENTERPRISE_DCF,
    ValuationMethod.FCF_YIELD,
])
def test_enterprise_methods_raise_for_a_bank(method):
    """models.yml states the rule: for a bank, debt is raw material, not
    financing. A rule enforced only by not calling something survives exactly
    until someone calls it."""
    with pytest.raises(MethodNotPermitted):
        BankModel().assert_method_permitted(method)


@pytest.mark.parametrize("method", [
    ValuationMethod.RESIDUAL_INCOME,
    ValuationMethod.JUSTIFIED_PB,
    ValuationMethod.DIVIDEND_DISCOUNT,
])
def test_equity_side_methods_are_permitted_for_a_bank(method):
    BankModel().assert_method_permitted(method)


def test_a_method_outside_the_permitted_set_also_raises():
    with pytest.raises(MethodNotPermitted):
        BankModel().assert_method_permitted(ValuationMethod.SUM_OF_THE_PARTS)


def test_net_debt_is_declared_not_applicable_to_a_bank():
    """Stage 1's handoff is explicit that this must be null with
    NOT_APPLICABLE_TO_MODEL, never 0."""
    assert "net_debt" in BankModel().not_applicable_metrics


def test_metrics_yml_agrees_that_net_debt_does_not_apply_to_banks(real_engine):
    net_debt = real_engine.pipeline.metrics()["metrics"]["net_debt"]
    assert "BANK" in net_debt["not_applicable_to_model_families"]


# --- the model registry ----------------------------------------------------


def test_every_declared_family_is_registered(real_engine):
    """An unregistered family falls through to whatever the caller does next,
    and that is how a generic model ends up valuing a bank."""
    models_config = real_engine.pipeline.models()
    registry = build_registry(models_config)
    assert set(registry) == set(models_config["model_families"])


def test_only_the_bank_family_implements_valuation_mathematics(real_engine):
    """Slice 2 built BANK and nothing else. A second family appearing here
    without its own tests would be a family valuing issuers on borrowed
    assumptions."""
    registry = build_registry(real_engine.pipeline.models())
    assert sorted(f for f, m in registry.items() if m.implemented) == ["BANK"]


def test_an_unmapped_classification_gets_no_model_rather_than_a_default():
    assert isinstance(model_for({}, None), NoModel)


def test_a_family_absent_from_models_yml_still_gets_a_registered_model():
    """It refuses with a specific reason instead of failing with a KeyError
    halfway through a build."""
    model = model_for({"model_families": {}}, "SOMETHING_NEW")
    assert model.family == "SOMETHING_NEW"
    assert not model.implemented


def test_an_unsupported_family_refuses_with_model_family_unsupported(sandbox):
    """models.yml marks TECH supported: false."""
    engine_input = loader.load(sandbox, BANK_TICKER, as_of="2026-07-31",
                               model_version=MODEL_VERSION, calculated_at="x")
    engine_input.identity["modelFamily"] = "TECH"
    model = model_for(sandbox.pipeline.models(), "TECH")
    result = model.evaluate(engine_input, _context(sandbox))
    assert result.reason == RefusalReason.MODEL_FAMILY_UNSUPPORTED


def test_an_onboarding_issuer_refuses_with_no_model_family(sandbox):
    engine_input = loader.load(sandbox, BANK_TICKER, as_of="2026-07-31",
                               model_version=MODEL_VERSION, calculated_at="x")
    engine_input.identity["modelFamily"] = None
    result = model_for(sandbox.pipeline.models(), None).evaluate(
        engine_input, _context(sandbox))
    assert result.reason == RefusalReason.NO_MODEL_FAMILY


def test_a_suspended_issuer_refuses_before_anything_else_is_considered(sandbox):
    engine_input = loader.load(sandbox, BANK_TICKER, as_of="2026-07-31",
                               model_version=MODEL_VERSION, calculated_at="x")
    engine_input.identity["coverageStatus"] = "SUSPENDED"
    result = BankModel().evaluate(engine_input, _context(sandbox))
    assert result.reason == RefusalReason.COVERAGE_SUSPENDED


# --- the bank declaration --------------------------------------------------


def test_every_bank_metric_is_defined_in_the_canonical_registry(real_engine):
    """metrics.yml states that a metric not defined there must not be
    published. The model must not require vocabulary the registry lacks."""
    defined = set(real_engine.pipeline.metrics()["metrics"])
    assert set(BANK_REQUIRED_METRICS) <= defined


def test_the_bank_model_requires_seventeen_metrics():
    assert len(BANK_REQUIRED_METRICS) == 17
    assert len(set(BANK_REQUIRED_METRICS)) == 17


# --- the gate report itself ------------------------------------------------


def test_a_gate_report_collects_every_failure_not_just_the_first():
    """Stopping at the first would turn diagnosis into a dozen round trips."""
    report = GateReport()
    report.check(GateId.MODEL_IMPLEMENTED, False, "a")
    report.check(GateId.MIN_HISTORY_PERIODS, False, "b")
    report.check(GateId.COVERAGE_ACTIVE, True, "c")
    assert len(report.failed) == 2
    assert not report.passed


def test_a_refusal_must_explain_itself():
    with pytest.raises(ContractError):
        ValuationRefusal(reason=RefusalReason.INSUFFICIENT_INPUTS, note="")


def test_refusal_json_is_sorted_so_output_is_stable():
    report = GateReport()
    report.require_inputs(GateId.REQUIRED_INPUTS_PRESENT, ["zeta", "alpha", "alpha"])
    refusal = report.refusal(RefusalReason.INSUFFICIENT_INPUTS, "note")
    assert refusal.to_json()["missingInputs"] == ["alpha", "zeta"]


# --- the synthetic switch --------------------------------------------------


def test_the_cli_never_permits_a_synthetic_cost_of_equity(repo_root):
    """The boundary that keeps invented assumptions out of published output.

    Asserted against the CLI's parsed source rather than its behaviour, because
    the failure mode is someone adding a flag later — and a behavioural test of
    today's CLI would not notice.
    """
    import ast

    text = (repo_root / "engine/goh_dip_tong/cli.py").read_text(encoding="utf-8")
    enabled = [
        node for node in ast.walk(ast.parse(text))
        if isinstance(node, ast.keyword)
        and node.arg == "allow_synthetic_cost_of_equity"
        and isinstance(node.value, ast.Constant)
        and node.value.value is True
    ]
    assert enabled == [], "the CLI enables the synthetic cost of equity"
    assert "allow_synthetic_cost_of_equity" in text, (
        "the CLI should mention the switch in prose explaining why it is never "
        "set, so a future reader knows the omission is deliberate"
    )


def test_the_synthetic_permission_defaults_to_off():
    assert ModelContext().allow_synthetic_cost_of_equity is False


def test_cost_of_capital_config_marks_the_risk_free_rate_unvalidated(real_engine):
    coc = real_engine.cost_of_capital()
    assert coc["risk_free"]["validated"] is False
    assert coc["synthetic"]["usable_in_production"] is False
    rejected = {r["id"] for r in coc["risk_free"]["rejected_substitutes"]}
    assert "BI_7DRR" in rejected


# --- what a refused issuer must NOT contain -------------------------------
#
# The gates above establish that no valuation is produced. These establish the
# consequences a reader would actually notice if the refusal leaked: a price to
# anchor on, a claim to repeat, or a market-implied case solved from a price
# nobody is licensed to publish.


def _document(settings, ticker, as_of="2026-07-31"):
    from engine.goh_dip_tong.models.registry import model_for as _model_for
    from engine.goh_dip_tong.publishing import snapshot as snapshot_mod

    engine_input = loader.load(settings, ticker, as_of=as_of,
                               model_version=MODEL_VERSION, calculated_at="x")
    model = _model_for(settings.pipeline.models(),
                       engine_input.identity.get("modelFamily"))
    return snapshot_mod.build(
        settings, engine_input, model,
        ModelContext(models_config=settings.pipeline.models()), "x")


@pytest.mark.parametrize("ticker", ["BBCA", "TLKM", "ASII"])
def test_a_real_issuer_snapshot_still_refuses(sandbox, ticker):
    document = _document(sandbox, ticker)
    assert document["mode"] == "FIXTURE_TEST_ONLY"
    assert document["valuation"]["status"] == "REFUSED"
    assert document["valuation"]["failedGates"]
    assert document["valuation"]["missingInputs"]
    assert document["valuation"]["note"]


@pytest.mark.parametrize("ticker", ["BBCA", "TLKM", "ASII"])
def test_a_real_issuer_has_no_target_price(sandbox, ticker):
    """No per-share figure of any kind. Checked over the serialised document
    rather than a field list, because the way a target price reaches a reader
    is by appearing somewhere nobody thought to look."""
    import json as _json

    document = _document(sandbox, ticker)
    text = _json.dumps(document)
    for token in ("valuePerShare", "targetPrice", "fairValue",
                  "value_per_share"):
        assert token not in text, token
    assert document["forecast"]["status"] == "NOT_PRODUCED"
    assert document["drivers"]["status"] == "NOT_PRODUCED"


@pytest.mark.parametrize("ticker", ["BBCA", "TLKM", "ASII"])
def test_a_real_issuer_has_no_market_implied_result(sandbox, ticker):
    document = _document(sandbox, ticker)
    implied = document["marketImplied"]
    assert implied["available"] is False
    assert implied["cases"] == {}
    assert implied["reason"]


@pytest.mark.parametrize("ticker", ["BBCA", "TLKM", "ASII"])
def test_a_real_issuer_asserts_no_thesis(sandbox, ticker):
    document = _document(sandbox, ticker)
    assert document["thesis"]["status"] == "NOT_PRODUCED"
    assert document["counterThesis"]["status"] == "NOT_PRODUCED"
    assert document["methodComparison"]["status"] == "NOT_PRODUCED"
    assert document["catalysts"] == []
    assert document["risks"] == []
    assert document["breakers"] == []


@pytest.mark.parametrize("ticker", ["BBCA", "TLKM", "ASII"])
def test_a_real_issuer_still_gets_its_citation_index(sandbox, ticker):
    """The refusal suppresses claims, not sources. A reader who wants to know
    what the engine had should be able to see it."""
    document = _document(sandbox, ticker)
    assert document["researchRefs"]["status"] == "PRODUCED"
    assert document["researchRefs"]["evidence"]
    assert document["researchRefs"]["modelAudit"]
    assert document["evidence"]


def test_no_market_implied_case_exists_without_an_approved_price(sandbox):
    """The gate is rights, not arithmetic. The solver works; there is no price
    it is permitted to solve from."""
    document = _document(sandbox, "BBCA")
    market = document["marketImplied"]
    assert market["available"] is False
    assert market["cases"] == {}
    providers = sandbox.pipeline.sources()["providers"]
    price_rights = {
        pid: entry.get("rights_status") for pid, entry in providers.items()
        if "market_prices_daily" in (entry.get("data_types") or [])
        and entry.get("enabled")
    }
    assert price_rights, "no enabled price provider — the premise has moved"
    assert all(r == "PRIVATE_RESEARCH_ONLY" for r in price_rights.values())
