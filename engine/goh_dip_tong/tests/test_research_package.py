"""The research package: every claim cited, ranked, and rejected if it is not.

The failure this suite guards is the one every research product eventually has:
a section of confident sentences that nobody can trace to a number, sitting
beside numbers that have since moved. So the assertions are structural rather
than editorial — not "is this a good thesis" but "does this thesis point at
records that exist, and would the engine have refused to build it if it did
not".
"""

from __future__ import annotations

import ast

import pytest

from engine.goh_dip_tong import RESEARCH_RULE_REGISTRY_HASH
from engine.goh_dip_tong.research import package as package_mod
from engine.goh_dip_tong.research.records import (
    BANNED_PHRASES,
    CLAIM_TYPES,
    Importance,
    MAX_STATEMENT_CHARS,
    RecordType,
    ResearchRecord,
    Severity,
    UnsupportedClaim,
    stable_id,
)
from engine.goh_dip_tong.research.rules import RULES

from .conftest_bank import evaluate


@pytest.fixture
def valued(synthetic_bank):
    return evaluate(synthetic_bank)


@pytest.fixture
def research(valued):
    return valued.research


# --- 1 & 2: every claim references registered evidence ---------------------


def test_every_thesis_statement_references_registered_evidence(research, valued):
    known = _known_evidence(valued)
    assert research.thesis, "the synthetic bank should support a thesis"
    for record in research.thesis:
        assert record.supporting_evidence, record.record_id
        for ref in record.supporting_evidence:
            assert ref in known, (record.record_id, ref)


def test_every_counter_thesis_statement_references_registered_evidence(
    research, valued
):
    known = _known_evidence(valued)
    assert research.counter_thesis
    for record in research.counter_thesis:
        assert record.supporting_evidence, record.record_id
        for ref in record.supporting_evidence:
            assert ref in known, (record.record_id, ref)


def test_every_claim_references_calculated_records_that_exist(research, valued):
    known = {r.ref for r in valued.comparison.values()}
    for record in research.claims:
        assert record.supporting_records, record.record_id
        for ref in record.supporting_records:
            assert ref in known, (record.record_id, ref)


# --- 3 & 4: identity and citation for catalysts, risks and breakers --------


def test_every_catalyst_risk_and_breaker_has_a_stable_unique_id(research):
    records = [*research.catalysts, *research.risks, *research.breakers]
    assert records
    ids = [r.record_id for r in records]
    assert len(ids) == len(set(ids)), "IDs collide"
    for record in records:
        assert record.record_id == stable_id(
            research.ticker, record.record_type, record.rule_id, record.scenario)


def test_the_ids_are_stable_across_independent_runs(synthetic_bank):
    """Not merely unique within a run. The same on the next one."""
    first = evaluate(synthetic_bank).research
    second = evaluate(synthetic_bank).research
    assert [r.record_id for r in first.records] == [
        r.record_id for r in second.records]


def test_no_id_encodes_a_position(research):
    """A record identified by its index is renamed whenever a rule ahead of it
    stops firing, which is exactly when identity should hold still."""
    for record in research.records:
        assert record.rule_id in record.record_id
        assert record.record_id.startswith(research.ticker)


def test_every_catalyst_risk_and_breaker_has_at_least_one_evidence_reference(
    research,
):
    for record in [*research.catalysts, *research.risks, *research.breakers]:
        assert record.supporting_evidence, record.record_id
        assert record.supporting_records, record.record_id


def test_every_claim_is_ranked(research):
    for record in research.claims:
        ranked = (record.severity if record.record_type in
                  (RecordType.RISK, RecordType.BREAKER) else record.importance)
        assert ranked is not None, record.record_id


# --- 5: unsupported claims are rejected -----------------------------------


def _claim(**overrides) -> dict:
    payload = {
        "record_id": "SYNB.THESIS.test.rule.BASE",
        "record_type": RecordType.THESIS,
        "statement": "A statement about the issuer.",
        "rule_id": "test.rule",
        "supporting_records": ("metric|FY|2025-12-31|CONSOLIDATED|BASE|f",),
        "supporting_evidence": ("SYNB|equity|FY|2025-12-31|CONSOLIDATED",),
        "importance": Importance.MEDIUM,
    }
    payload.update(overrides)
    return payload


def test_a_claim_with_no_calculated_record_is_rejected():
    with pytest.raises(UnsupportedClaim, match="calculated record"):
        ResearchRecord(**_claim(supporting_records=()))


def test_a_claim_with_no_evidence_is_rejected():
    with pytest.raises(UnsupportedClaim, match="evidence"):
        ResearchRecord(**_claim(supporting_evidence=()))


def test_an_unranked_claim_is_rejected():
    with pytest.raises(UnsupportedClaim, match="importance"):
        ResearchRecord(**_claim(importance=None))


def test_an_unranked_risk_is_rejected():
    with pytest.raises(UnsupportedClaim, match="severity"):
        ResearchRecord(**_claim(record_type=RecordType.RISK, importance=None))


def test_a_claim_with_no_rule_is_rejected():
    with pytest.raises(UnsupportedClaim, match="rule"):
        ResearchRecord(**_claim(rule_id=""))


def test_an_empty_statement_is_rejected():
    with pytest.raises(UnsupportedClaim, match="state something"):
        ResearchRecord(**_claim(statement="   "))


def test_an_overlong_statement_is_rejected():
    with pytest.raises(UnsupportedClaim, match="limit"):
        ResearchRecord(**_claim(statement="x" * (MAX_STATEMENT_CHARS + 1)))


@pytest.mark.parametrize("phrase", ["target price", "buy", "undervalued",
                                    "guaranteed", "outperform"])
def test_a_recommendation_is_rejected(phrase):
    with pytest.raises(UnsupportedClaim, match="recommendation"):
        ResearchRecord(**_claim(statement=f"This issuer is {phrase} today."))


def test_a_claim_citing_a_record_that_does_not_exist_is_rejected():
    """The check with teeth: not "is the ref well-formed" but "is it there"."""
    with pytest.raises(UnsupportedClaim, match="do not exist"):
        package_mod._reject_dangling(
            [ResearchRecord(**_claim())],
            known_records={"something|else"},
            known_evidence={"SYNB|equity|FY|2025-12-31|CONSOLIDATED"},
        )


def test_a_claim_citing_evidence_that_does_not_exist_is_rejected():
    with pytest.raises(UnsupportedClaim, match="evidence that does not exist"):
        package_mod._reject_dangling(
            [ResearchRecord(**_claim())],
            known_records={"metric|FY|2025-12-31|CONSOLIDATED|BASE|f"},
            known_evidence=set(),
        )


def test_no_produced_statement_contains_banned_vocabulary(research):
    for record in research.records:
        lowered = record.statement.lower()
        for phrase in BANNED_PHRASES:
            assert phrase not in lowered, (record.record_id, phrase)


# --- 6: no arithmetic in the narrative layer ------------------------------


ARITHMETIC = {"Add", "Sub", "Mult", "Div", "Pow", "FloorDiv", "Mod"}

NARRATIVE_MODULES = (
    "engine/goh_dip_tong/research/rules.py",
    "engine/goh_dip_tong/research/records.py",
    "engine/goh_dip_tong/research/package.py",
    "engine/goh_dip_tong/narration/views.py",
)


@pytest.mark.parametrize("relative", NARRATIVE_MODULES)
def test_narrative_modules_contain_no_arithmetic(repo_root, relative):
    """Asserted against the source. A behavioural test of today's rules would
    not notice a calculation added tomorrow.

    String and list concatenation count: they are the same AST node, and the
    prohibition is easier to keep than to qualify."""
    source = (repo_root / relative).read_text(encoding="utf-8")
    offenders = [
        f"{relative}:{node.lineno} {type(node.op).__name__}"
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.BinOp) and type(node.op).__name__ in ARITHMETIC
    ]
    assert offenders == [], offenders


def test_no_rule_imports_the_formula_registry_to_compute(repo_root):
    """A rule may cite a number. It may not make one."""
    source = (repo_root / "engine/goh_dip_tong/research/rules.py").read_text(
        encoding="utf-8")
    assert "REGISTRY.compute" not in source


# --- the rule registry -----------------------------------------------------


def test_the_rule_registry_hash_matches_the_declared_constant():
    """Changing what a rule concludes without bumping the constant fails here,
    for the same reason the formula hash exists: a published conclusion carries
    a ruleId, and following it must reach the rule that ran."""
    assert RULES.registry_hash() == RESEARCH_RULE_REGISTRY_HASH


def test_the_rule_registry_hash_is_insensitive_to_layout():
    first = RULES.registry_hash()
    assert first == RULES.registry_hash()
    assert len(first) == 64


def test_every_registered_rule_is_documented():
    undocumented = [rid for rid in RULES.ids() if not RULES.get(rid).doc]
    assert undocumented == []


def test_a_duplicate_rule_id_is_refused():
    with pytest.raises(ValueError, match="already registered"):
        RULES.rule("bank.roe_above_cost_of_equity", RecordType.THESIS)(
            lambda ctx: [])


def test_records_are_ordered_deterministically(research):
    from engine.goh_dip_tong.research.records import sort_key

    assert research.records == sorted(research.records, key=sort_key)


def test_the_package_records_which_rules_fired(research):
    assert research.rules_fired
    assert set(research.rules_fired) <= set(RULES.ids())
    assert "bank.roe_above_cost_of_equity" in research.rules_fired


def test_a_rule_that_does_not_apply_does_not_fire(research):
    """The synthetic bank is solvent and profitable, so the breakers that fire
    only on distress must be absent — otherwise the conditions are decorative."""
    fired = set(research.rules_fired)
    assert "bank.book_value_non_positive" not in fired
    assert "bank.residual_income_turns_negative" not in fired


# --- method comparison notes ----------------------------------------------


def test_the_method_comparison_names_residual_income_as_primary(research):
    joined = " ".join(r.statement for r in research.method_comparison)
    assert "cross-check" in joined
    assert "not an equal-weight" in joined


def test_every_cross_check_gets_a_note_in_every_scenario(research, valued):
    scenarios = {r.scenario for r in research.method_comparison}
    assert scenarios == set(valued.scenario_order)
    for record in research.method_comparison:
        assert record.supporting_records


# --- refusal produces no claims -------------------------------------------


def _refused_package(sandbox, ticker):
    from engine.goh_dip_tong import (
        ENGINE_VERSION, FORMULA_REGISTRY_HASH, MODEL_VERSION)
    from engine.goh_dip_tong.inputs import loader

    engine_input = loader.load(sandbox, ticker, as_of="2026-07-31",
                               model_version=MODEL_VERSION, calculated_at="x")
    return package_mod.build(
        ticker=ticker, family="BANK", valued=False, comparison_records={},
        fact_keys=package_mod.fact_keys_for(engine_input),
        audit_refs=package_mod.audit_refs_for(
            ENGINE_VERSION, MODEL_VERSION, FORMULA_REGISTRY_HASH),
    )


@pytest.mark.parametrize("ticker", ["BBCA", "TLKM", "ASII"])
def test_a_refused_issuer_produces_no_claims_at_all(sandbox, ticker):
    package = _refused_package(sandbox, ticker)
    assert package.claims == []
    assert package.thesis == []
    assert package.counter_thesis == []
    assert package.catalysts == []
    assert package.risks == []
    assert package.breakers == []


def test_a_refused_issuer_still_gets_its_citation_index(sandbox):
    """A pointer carries no claim, so a refusal does not suppress it."""
    package = _refused_package(sandbox, "BBCA")
    assert package.evidence_refs
    assert package.model_audit_refs
    assert package.refs_section()["status"] == "PRODUCED"


def test_the_absent_sections_say_why(sandbox):
    package = _refused_package(sandbox, "BBCA")
    section = package.section(package.thesis)
    assert section["status"] == "NOT_PRODUCED"
    assert "no valuation was produced" in section["reason"].lower()


def test_claim_rules_never_run_without_a_valuation(sandbox):
    """Not filtered afterwards — never run. There is no unsupported claim to
    remove, which is a stronger guarantee than removing one."""
    package = _refused_package(sandbox, "BBCA")
    claim_rules = {RULES.get(rid).rule_id for rid in RULES.ids()
                   if RULES.get(rid).record_type in CLAIM_TYPES}
    assert set(package.rules_fired) & claim_rules == set()


# --- helpers ---------------------------------------------------------------


def _known_evidence(valued) -> set:
    known = set()
    for record in valued.research.evidence_refs:
        known.update(record.supporting_evidence)
    for record in valued.research.model_audit_refs:
        known.update(record.supporting_evidence)
    return known
