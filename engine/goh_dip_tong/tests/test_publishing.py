"""Publishing: byte stability, the pointer, and the write that must not happen.

The dated-snapshot path is covered in ``test_snapshot_output.py``. What this
module adds is the two properties that only matter once something is already
published: that the ``current/`` pointer moves for the same reasons the
snapshot does and for no others, and that an invalid document cannot replace a
valid one.

The second is the one worth having. A build that validates, then mutates, then
writes leaves the last good snapshot overwritten by something no reader can
trust, with the pointer aimed at it — and every downstream consumer follows the
pointer. Validating at the writer means the worst case is a stale-but-valid
snapshot, which is recoverable.
"""

from __future__ import annotations

import json

import pytest

from engine.goh_dip_tong import MODEL_VERSION
from engine.goh_dip_tong.contracts.model import ModelContext
from engine.goh_dip_tong.inputs import loader
from engine.goh_dip_tong.models.registry import model_for
from engine.goh_dip_tong.publishing import snapshot as snapshot_mod
from pipeline.goh_dip_tong.publishing.writers import read_json

from .conftest_bank import CALCULATED_AT, context as bank_context

LATER_DATES = ["2026-08-01", "2026-12-31", "2027-03-14", "2027-07-31"]


def _build(settings, ticker="BBCA", as_of="2026-07-31",
           calculated_at="2026-07-31T00:00:00Z", valued=False):
    engine_input = loader.load(settings, ticker, as_of=as_of,
                               model_version=MODEL_VERSION,
                               calculated_at=calculated_at)
    model = model_for(settings.pipeline.models(),
                      engine_input.identity.get("modelFamily"))
    ctx = (bank_context(settings) if valued
           else ModelContext(models_config=settings.pipeline.models()))
    return snapshot_mod.build(settings, engine_input, model, ctx, calculated_at)


def _pointer_path(settings, ticker):
    return settings.output_current / f"{ticker}.json"


# --- 21: the versioned snapshot is byte-stable ----------------------------


def test_the_versioned_snapshot_is_byte_stable_across_repeated_writes(sandbox):
    document = _build(sandbox)
    path, _, _ = snapshot_mod.write(sandbox, document)
    first = path.read_bytes()
    snapshot_mod.write(sandbox, _build(sandbox))
    assert path.read_bytes() == first


def test_a_valued_snapshot_is_byte_stable_too(synthetic_bank):
    """Asserted on the one issuer that actually produces numbers, because a
    forecast has far more places for float ordering to leak than a refusal."""
    document = _build(synthetic_bank, "SYNB", calculated_at=CALCULATED_AT,
                      valued=True)
    path, _, _ = snapshot_mod.write(synthetic_bank, document)
    first = path.read_bytes()
    rebuilt = _build(synthetic_bank, "SYNB", calculated_at=CALCULATED_AT,
                     valued=True)
    assert rebuilt["contentHash"] == document["contentHash"]
    snapshot_mod.write(synthetic_bank, rebuilt)
    assert path.read_bytes() == first


# --- 22: the pointer is byte-stable ---------------------------------------


def test_the_pointer_is_byte_stable_across_repeated_writes(sandbox):
    document = _build(sandbox)
    _, pointer, _ = snapshot_mod.write(sandbox, document)
    first = pointer.read_bytes()
    snapshot_mod.write(sandbox, _build(sandbox))
    assert pointer.read_bytes() == first


def test_the_pointer_updates_only_when_the_content_changes(sandbox):
    """The pointer's job is to name the newest *research*, not the newest run.
    A pointer that moved on every rebuild would be a timestamp with extra steps.
    """
    snapshot_mod.write(sandbox, _build(sandbox))
    pointer = _pointer_path(sandbox, "BBCA")
    unchanged = pointer.read_bytes()

    _, _, was_unchanged = snapshot_mod.write(sandbox, _build(sandbox))
    assert was_unchanged
    assert pointer.read_bytes() == unchanged

    changed = _build(sandbox, as_of="2026-07-31")
    changed["quality"]["completeness"] = 0.5
    changed["contentHash"] = "f" * 64
    snapshot_mod.write(sandbox, changed)
    assert pointer.read_bytes() != unchanged


def test_the_pointer_names_the_state_a_ui_would_render(sandbox):
    snapshot_mod.write(sandbox, _build(sandbox))
    pointer = read_json(_pointer_path(sandbox, "BBCA"))
    assert pointer["uiState"] == "PARTIAL"
    assert pointer["valuationStatus"] == "REFUSED"
    assert pointer["contentHash"]


# --- 23: a later calendar date alone changes nothing ----------------------


@pytest.mark.parametrize("as_of", LATER_DATES)
def test_a_later_date_alone_writes_nothing_new(sandbox, as_of):
    snapshot_mod.write(sandbox, _build(sandbox))
    before = _tree(sandbox)
    _, _, unchanged = snapshot_mod.write(sandbox, _build(sandbox, as_of=as_of))
    assert unchanged
    assert _tree(sandbox) == before


def test_a_later_run_timestamp_alone_writes_nothing_new(sandbox):
    snapshot_mod.write(sandbox, _build(sandbox))
    before = _tree(sandbox)
    later = _build(sandbox, calculated_at="2027-01-01T12:34:56Z")
    _, _, unchanged = snapshot_mod.write(sandbox, later)
    assert unchanged
    assert _tree(sandbox) == before


# --- 24: an invalid snapshot never replaces a valid one -------------------


def test_an_invalid_snapshot_is_refused_at_the_writer(sandbox):
    document = _build(sandbox)
    snapshot_mod.write(sandbox, document)

    corrupt = json.loads(json.dumps(document))
    corrupt["researchStatus"] = "NOT_A_STATUS"
    with pytest.raises(snapshot_mod.InvalidSnapshot):
        snapshot_mod.write(sandbox, corrupt)


def test_the_last_valid_snapshot_survives_an_invalid_build(sandbox):
    document = _build(sandbox)
    path, pointer, _ = snapshot_mod.write(sandbox, document)
    good_snapshot = path.read_bytes()
    good_pointer = pointer.read_bytes()

    corrupt = json.loads(json.dumps(document))
    corrupt["valuation"] = {"status": "VALUED"}          # missing everything
    corrupt["contentHash"] = "a" * 64                    # would force a write
    with pytest.raises(snapshot_mod.InvalidSnapshot):
        snapshot_mod.write(sandbox, corrupt)

    assert path.read_bytes() == good_snapshot
    assert pointer.read_bytes() == good_pointer


def test_an_invalid_first_build_writes_nothing_at_all(sandbox):
    """No prior snapshot to protect, and still nothing is written — a partial
    tree with a pointer to an invalid document is not an improvement on none."""
    corrupt = _build(sandbox)
    del corrupt["disclaimers"]
    with pytest.raises(snapshot_mod.InvalidSnapshot):
        snapshot_mod.write(sandbox, corrupt)
    assert _tree(sandbox) == {}


def test_the_refusal_names_the_schema_failure(sandbox):
    corrupt = _build(sandbox)
    corrupt["mode"] = "PRODUCTION_ISH"
    with pytest.raises(snapshot_mod.InvalidSnapshot, match="output schema"):
        snapshot_mod.write(sandbox, corrupt)


# --- helpers ---------------------------------------------------------------


def _tree(settings):
    root = settings.output_root
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*.json")) if "sample" not in p.parts
    }
