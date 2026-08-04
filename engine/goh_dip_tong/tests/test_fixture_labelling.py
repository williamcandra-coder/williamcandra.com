"""Provenance labelling, and the two leaks it has to prevent.

The first leak is a claim: development data presented as real analysis. The
label that prevents it is derived from the inputs rather than set by hand, so
it cannot be forgotten, and ``PRODUCTION`` is unreachable while any input is a
fixture.

The second leak is physical: the synthetic bank's invented figures reaching the
published data tree. That one is checked by hashing every fixture file and
looking for it in the published tree.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from engine.goh_dip_tong import MODEL_VERSION
from engine.goh_dip_tong.contracts.enums import EngineMode
from engine.goh_dip_tong.contracts.model import ModelContext
from engine.goh_dip_tong.inputs import loader
from engine.goh_dip_tong.inputs.provenance import (
    PUBLISHABLE_RIGHTS,
    Provenance,
    assess,
    disclaimers_for,
)
from engine.goh_dip_tong.models.registry import model_for
from engine.goh_dip_tong.publishing import snapshot as snapshot_mod
from pipeline.goh_dip_tong.publishing.writers import read_json


def _build(settings, ticker="BBCA", as_of="2026-07-31"):
    engine_input = loader.load(settings, ticker, as_of=as_of,
                               model_version=MODEL_VERSION, calculated_at="x")
    model = model_for(settings.pipeline.models(),
                      engine_input.identity.get("modelFamily"))
    context = ModelContext(models_config=settings.pipeline.models())
    return snapshot_mod.build(settings, engine_input, model, context, "x")


# --- the label -------------------------------------------------------------


@pytest.mark.parametrize("ticker", ["BBCA", "TLKM", "ASII"])
def test_every_output_is_labelled_fixture_test_only(sandbox, ticker):
    assert _build(sandbox, ticker)["mode"] == "FIXTURE_TEST_ONLY"


def test_the_label_appears_in_four_independent_places(sandbox):
    document = _build(sandbox)
    assert document["mode"] == "FIXTURE_TEST_ONLY"
    assert "FIXTURE_TEST_ONLY" in document["quality"]["flags"]
    assert document["disclaimers"][0].startswith("FIXTURE_TEST_ONLY")
    assert document["modelAudit"]["inputProvenance"]["mode"] == "FIXTURE_TEST_ONLY"


def test_the_mode_disclaimer_comes_first(sandbox):
    """A reader who stops after one line should have read the one that says
    this is not real analysis."""
    document = _build(sandbox)
    assert "not live, current or authoritative" in document["disclaimers"][0]


def test_stage_1_disclaimers_are_carried_through_not_replaced(sandbox):
    document = _build(sandbox)
    joined = " ".join(document["disclaimers"])
    assert "Not investment advice" in joined
    assert "must never be rendered as zero" in joined


def test_the_label_states_its_reasons(sandbox):
    reasons = _build(sandbox)["modelAudit"]["inputProvenance"]["reasons"]
    assert any("authoritative=false" in r for r in reasons)
    assert any("fixture-backed" in r for r in reasons)


# --- PRODUCTION is unreachable --------------------------------------------


def test_production_mode_is_unreachable_from_the_real_repository(real_engine):
    """The universe declares authoritative=false and every enabled provider is
    a fixture. No issuer can be assessed as production."""
    universe = read_json(real_engine.pipeline.idx30_current)
    for ticker in loader.available_tickers(real_engine):
        snapshot = read_json(real_engine.input_snapshots / f"{ticker}.json")
        assert assess(real_engine, universe, snapshot).mode == (
            EngineMode.FIXTURE_TEST_ONLY)


def test_an_authoritative_universe_alone_does_not_reach_production(sandbox):
    """Each condition is independently sufficient to hold the label. Flipping
    one flag must not be enough."""
    universe = {"authoritative": True, "provenance": "LIVE",
                "source": {"providerId": "fixture_idx30_registry"}}
    snapshot = {"quality": {"flags": []}}
    assert assess(sandbox, universe, snapshot).mode == EngineMode.FIXTURE_TEST_ONLY


def test_clearing_the_fixture_flag_alone_does_not_reach_production(sandbox):
    universe = read_json(sandbox.pipeline.idx30_current)
    assert assess(sandbox, universe, {"quality": {"flags": []}}).mode == (
        EngineMode.FIXTURE_TEST_ONLY
    )


def test_no_enabled_provider_currently_holds_publishable_rights(real_engine):
    """The structural reason production is unreachable: not one provider's
    rights permit publishing derived output."""
    providers = real_engine.pipeline.sources()["providers"]
    publishable = [
        pid for pid, entry in providers.items()
        if entry.get("enabled") and entry.get("rights_status") in PUBLISHABLE_RIGHTS
        and entry.get("authoritative") and entry.get("kind") != "fixture"
    ]
    assert publishable == []


def test_production_requires_every_condition_at_once(sandbox):
    """Constructed rather than found: this is what it would take, and it
    demonstrates the label is derived logic and not a constant."""
    universe = {"authoritative": True, "provenance": "LIVE", "source": {}}
    provenance = assess(sandbox, universe, {"quality": {"flags": []}})
    # The sandbox still has fixture providers supplying financial facts.
    assert provenance.mode == EngineMode.FIXTURE_TEST_ONLY
    assert provenance.reasons


def test_the_mode_is_never_written_by_hand(repo_root):
    """Only provenance.assess may decide it. Anything else assigning
    EngineMode.PRODUCTION would be a hand-set label."""
    offenders = []
    for path in sorted((repo_root / "engine").rglob("*.py")):
        if path.name in ("provenance.py", "enums.py") or "tests" in path.parts:
            continue
        if "EngineMode.PRODUCTION" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(repo_root)))
    assert offenders == []


def test_disclaimers_for_production_would_read_differently():
    production = Provenance(mode=EngineMode.PRODUCTION)
    assert not disclaimers_for(production, [])[0].startswith("FIXTURE_TEST_ONLY")


# --- synthetic data never enters the published tree -----------------------


def _hashes(root, pattern="*"):
    return {
        hashlib.sha256(p.read_bytes()).hexdigest(): str(p)
        for p in sorted(root.rglob(pattern)) if p.is_file()
    }


def test_no_published_file_shares_a_hash_with_an_engine_fixture(repo_root):
    """The physical leak check. Copying a fixture into the data tree — by hand,
    by script, or by a build that read the wrong directory — fails here."""
    fixtures = _hashes(repo_root / "engine/goh_dip_tong/fixtures")
    published = _hashes(repo_root / "data/goh-dip-tong")
    overlap = set(fixtures) & set(published)
    assert overlap == set(), [
        (fixtures[h], published[h]) for h in sorted(overlap)
    ]


def test_the_synthetic_ticker_appears_nowhere_under_data(repo_root):
    data = repo_root / "data" / "goh-dip-tong"
    offenders = [
        str(p.relative_to(repo_root))
        for p in sorted(data.rglob("*"))
        if p.is_file() and (p.stem == "SYNB" or "SYNB" in p.parts)
    ]
    assert offenders == []


def test_no_published_document_carries_the_synthetic_flag(repo_root):
    data = repo_root / "data" / "goh-dip-tong"
    offenders = [
        str(path.relative_to(repo_root))
        for path in sorted(data.rglob("*.json"))
        if "SYNTHETIC" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_the_synthetic_fixture_declares_itself_loudly(repo_root):
    document = json.loads(
        (repo_root / "engine/goh_dip_tong/fixtures/synthetic-bank/SYNB.json")
        .read_text(encoding="utf-8")
    )
    assert "SYNTHETIC" in document["quality"]["flags"]
    assert "FIXTURE_TEST_ONLY" in document["quality"]["flags"]
    assert document["disclaimers"][0].startswith("SYNTHETIC")
    assert "never be copied into the published data tree" in " ".join(
        document["disclaimers"])


def test_the_synthetic_ticker_is_not_in_the_idx30_universe(real_engine):
    """So a build over the live universe can never pick it up."""
    universe = read_json(real_engine.pipeline.idx30_current)
    assert "SYNB" not in {c["ticker"] for c in universe["constituents"]}


def test_building_the_synthetic_bank_writes_nothing_to_the_real_tree(
    synthetic_bank, repo_root
):
    before = _hashes(repo_root / "data/goh-dip-tong")
    document = _build(synthetic_bank, "SYNB")
    snapshot_mod.write(synthetic_bank, document)
    assert _hashes(repo_root / "data/goh-dip-tong") == before
