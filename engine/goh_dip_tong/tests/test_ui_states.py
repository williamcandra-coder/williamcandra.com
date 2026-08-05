"""The six UI-state fixtures Stage 3 builds against.

These are the contract between Stage 2 and a UI that does not exist yet, which
makes them the easiest thing in the repository to get quietly wrong: nobody is
rendering them, so nothing complains when one drifts. Hence the strongest
assertion here is not about any one fixture's content but about regeneration —
every fixture is rebuilt from the engine and compared byte for byte, so a
fixture that stopped describing real engine output fails immediately.

The second concern is containment. A fixture is synthetic output, and synthetic
output has exactly one way to cause harm: reaching the published tree and being
read as research. So every ticker is checked against the universe and against
``data/``, and no fixture that carries a valuation may name a real issuer.
"""

from __future__ import annotations

import json

import pytest

from engine.goh_dip_tong.contracts.enums import ResearchStatus, UiState
from engine.goh_dip_tong.publishing import ui_states
from pipeline.goh_dip_tong.publishing.writers import read_json
from pipeline.goh_dip_tong.validation.schema import validate_document

ALL_STATES = tuple(str(case.state) for case in ui_states.UI_STATE_CASES)


@pytest.fixture(scope="module")
def fixture_documents(repo_root) -> dict:
    directory = repo_root / "engine/goh_dip_tong/fixtures/ui_states"
    return {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    }


# --- 9 to 14: every fixture validates -------------------------------------


@pytest.mark.parametrize("state", ALL_STATES)
def test_the_fixture_validates_against_the_output_schema(
    state, fixture_documents, real_engine
):
    document = fixture_documents[state]
    report = validate_document("research-snapshot", document,
                               subject=document["ticker"],
                               settings=real_engine.pipeline)
    assert report.ok, [i.message for i in report.critical_failures[:5]]


def test_exactly_six_fixtures_exist(fixture_documents):
    assert sorted(fixture_documents) == sorted(ALL_STATES)
    assert len(fixture_documents) == 6


@pytest.mark.parametrize("state", ALL_STATES)
def test_the_fixture_carries_the_state_it_is_named_for(state, fixture_documents):
    assert fixture_documents[state]["uiState"] == state


# --- 15: labelling ---------------------------------------------------------


@pytest.mark.parametrize("state", ALL_STATES)
def test_every_fixture_is_fixture_test_only(state, fixture_documents):
    document = fixture_documents[state]
    assert document["mode"] == "FIXTURE_TEST_ONLY"
    assert "FIXTURE_TEST_ONLY" in document["quality"]["flags"]
    assert document["modelAudit"]["inputProvenance"]["mode"] == "FIXTURE_TEST_ONLY"


@pytest.mark.parametrize("state", ALL_STATES)
def test_every_fixture_carries_a_visible_disclaimer(state, fixture_documents):
    disclaimers = fixture_documents[state]["disclaimers"]
    assert disclaimers
    assert disclaimers[0].startswith("FIXTURE_TEST_ONLY")
    assert "not live, current or authoritative" in disclaimers[0]


#: Phrases that can only appear in an affirmative claim. Deliberately not
#: "authoritative" or "live" on their own: the mode disclaimer denies both by
#: name, and a test that flagged the denial would push someone to weaken the
#: denial rather than the claim.
AFFIRMATIVE_CLAIMS = (
    "production-ready",
    "production ready",
    "real-time",
    "live market",
    "current market price",
    "as reported today",
)


@pytest.mark.parametrize("state", ALL_STATES)
def test_no_fixture_claims_to_be_live_or_production(state, fixture_documents):
    """Checked against the serialised document, so a claim added anywhere in
    it — a note, a statement, a section — is caught rather than only the fields
    somebody remembered to assert on."""
    document = fixture_documents[state]
    text = json.dumps(document).lower()
    for phrase in AFFIRMATIVE_CLAIMS:
        assert phrase not in text, phrase
    assert '"mode": "production"' not in text
    assert '"uistate": "production"' not in text
    # And the denial is present, so the absence above is not vacuous.
    assert any("not live, current or authoritative" in d
               for d in document["disclaimers"])


@pytest.mark.parametrize("state", ALL_STATES)
def test_every_fixture_carries_freshness_quality_evidence_and_audit(
    state, fixture_documents
):
    document = fixture_documents[state]
    assert set(document["freshness"]) >= {"asOf", "newestPublishedAt",
                                          "ageDays", "stale"}
    assert set(document["quality"]) >= {"status", "completeness", "flags"}
    assert document["evidence"], "a fixture with no evidence cites nothing"
    assert document["researchRefs"]["status"] == "PRODUCED"
    audit = document["modelAudit"]
    assert audit["formulaRegistryHash"]
    assert audit["ruleRegistryHash"]
    assert audit["inputProvenance"]["mode"]


# --- 16: no real issuer, and only SYNB is valued --------------------------


def test_only_the_synthetic_bank_carries_a_valuation(fixture_documents):
    valued = {
        state: doc["ticker"] for state, doc in fixture_documents.items()
        if doc["valuation"]["status"] == "VALUED"
    }
    assert valued == {"FULL_RESEARCH": "SYNB"}


def test_no_fixture_uses_a_real_issuer(fixture_documents, real_engine):
    universe = read_json(real_engine.pipeline.idx30_current)
    real = {c["ticker"] for c in universe["constituents"]}
    for state, document in fixture_documents.items():
        assert document["ticker"] not in real, (state, document["ticker"])
        assert document["ticker"] in ui_states.FIXTURE_TICKERS


def test_every_fixture_ticker_is_synthetic(fixture_documents):
    for document in fixture_documents.values():
        assert document["ticker"].startswith("SYN")


# --- 17: nothing synthetic under data/ ------------------------------------


def test_no_ui_state_fixture_exists_under_data(repo_root):
    data = repo_root / "data" / "goh-dip-tong"
    offenders = [
        str(path.relative_to(repo_root))
        for path in sorted(data.rglob("*"))
        if path.is_file() and (
            "ui_states" in path.parts
            or path.stem in ui_states.FIXTURE_TICKERS)
    ]
    assert offenders == []


def test_no_synthetic_ticker_appears_in_any_published_document(repo_root):
    data = repo_root / "data" / "goh-dip-tong"
    offenders = []
    for path in sorted(data.rglob("*.json")):
        text = path.read_text(encoding="utf-8")
        for ticker in ui_states.FIXTURE_TICKERS:
            if ticker in text:
                offenders.append((str(path.relative_to(repo_root)), ticker))
    assert offenders == []


def test_no_fixture_shares_a_hash_with_a_published_file(repo_root):
    import hashlib

    def digests(root):
        return {
            hashlib.sha256(p.read_bytes()).hexdigest(): str(p)
            for p in sorted(root.rglob("*")) if p.is_file()
        }

    fixtures = digests(repo_root / "engine/goh_dip_tong/fixtures")
    published = digests(repo_root / "data/goh-dip-tong")
    assert set(fixtures) & set(published) == set()


def test_no_synthetic_ticker_is_in_the_idx30_universe(real_engine):
    universe = read_json(real_engine.pipeline.idx30_current)
    tickers = {c["ticker"] for c in universe["constituents"]}
    assert set(ui_states.FIXTURE_TICKERS) & tickers == set()


# --- regeneration: the assertion that keeps the rest honest ---------------


def test_regenerating_every_fixture_reproduces_it_byte_for_byte(
    repo_root, tmp_path
):
    """The fixtures are engine output, not hand-written JSON. If this fails,
    either a fixture was edited by hand or the engine changed — and the second
    is the case worth catching, because a fixture that no longer describes real
    output is worse than no fixture at all."""
    sandbox = ui_states.prepare_sandbox(tmp_path / "sandbox", repo_root)
    source = ui_states.source_document(
        ui_states.EngineSettings(
            pipeline=type(sandbox.pipeline)(repo_root=repo_root)))

    directory = repo_root / "engine/goh_dip_tong/fixtures/ui_states"
    for case in ui_states.UI_STATE_CASES:
        rebuilt = ui_states.serialise(
            ui_states.build_case(sandbox, case, source))
        stored = (directory / case.filename).read_text(encoding="utf-8")
        assert rebuilt == stored, case.filename


def test_generation_writes_nothing_to_the_repository(repo_root, tmp_path):
    import hashlib

    def digest(root):
        return hashlib.sha256(
            b"".join(sorted(p.read_bytes() for p in root.rglob("*")
                            if p.is_file()))).hexdigest()

    before = digest(repo_root / "data" / "goh-dip-tong")
    sandbox = ui_states.prepare_sandbox(tmp_path / "sandbox", repo_root)
    source = ui_states.source_document(
        ui_states.EngineSettings(
            pipeline=type(sandbox.pipeline)(repo_root=repo_root)))
    # The valued case is the one that could deposit something worth worrying
    # about, so it is the one this asserts on.
    ui_states.build_case(sandbox, ui_states.UI_STATE_CASES[0], source)
    assert digest(repo_root / "data" / "goh-dip-tong") == before


# --- the derivation itself -------------------------------------------------


def test_suspension_outranks_everything():
    """A suspended issuer must never render as current research, whatever the
    mathematics managed to produce."""
    assert ui_states.derive("SUSPENDED", str(ResearchStatus.FULL_RESEARCH),
                            "BANK", "VALUED") == UiState.SUSPENDED


def test_staleness_outranks_a_produced_valuation():
    assert ui_states.derive("FINANCIALS", str(ResearchStatus.STALE),
                            "BANK", "VALUED") == UiState.STALE


def test_no_model_family_is_onboarding():
    assert ui_states.derive("FINANCIALS",
                            str(ResearchStatus.FINANCIALS_VALIDATED),
                            None, "REFUSED") == UiState.ONBOARDING


def test_a_data_shortfall_is_partial_not_model_under_validation():
    """The distinction a reader cares about: waiting on collection, or waiting
    on methodology."""
    assert ui_states.derive(
        "FINANCIALS", str(ResearchStatus.MODEL_UNDER_VALIDATION), "BANK",
        "REFUSED", "INSUFFICIENT_INPUTS") == UiState.PARTIAL
    assert ui_states.derive(
        "FINANCIALS", str(ResearchStatus.MODEL_UNDER_VALIDATION), "BANK",
        "REFUSED", "NO_VALIDATED_RISK_FREE_RATE") == UiState.MODEL_UNDER_VALIDATION


def test_every_state_is_reachable():
    """A state in the enum that no input produces is documentation pretending
    to be code."""
    produced = {ui_states.derive_for(doc) for doc in _all_built()}
    assert produced == set(UiState)


def _all_built():
    directory = (__import__("pathlib").Path(__file__).resolve().parents[1]
                 / "fixtures" / "ui_states")
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(directory.glob("*.json"))]


def test_the_derivation_is_total(fixture_documents):
    for document in fixture_documents.values():
        assert ui_states.derive_for(document) == UiState(document["uiState"])


# --- real issuers reach the same states -----------------------------------


@pytest.mark.parametrize("ticker", ["BBCA", "TLKM", "ASII"])
def test_real_issuers_land_in_partial(sandbox, ticker):
    """The state the fixtures exist to demonstrate is the one real issuers are
    actually in — otherwise the fixture set describes a repository that does
    not exist."""
    from engine.goh_dip_tong import MODEL_VERSION
    from engine.goh_dip_tong.contracts.model import ModelContext
    from engine.goh_dip_tong.inputs import loader
    from engine.goh_dip_tong.models.registry import model_for
    from engine.goh_dip_tong.publishing import snapshot as snapshot_mod

    engine_input = loader.load(sandbox, ticker, as_of="2026-07-31",
                               model_version=MODEL_VERSION, calculated_at="x")
    model = model_for(sandbox.pipeline.models(),
                      engine_input.identity.get("modelFamily"))
    document = snapshot_mod.build(
        sandbox, engine_input, model,
        ModelContext(models_config=sandbox.pipeline.models()), "x")
    assert document["uiState"] == str(UiState.PARTIAL)
