"""Goh Dip Tong Stage 2 — deterministic calculation and research engine.

This package consumes validated Stage 1 output and produces versioned research
snapshots. Three properties are load-bearing and everything else is detail:

**Deterministic.** No LLM, no clock-dependent arithmetic, no iteration over an
unordered collection. The same inputs produce byte-identical output on any
machine and on any calendar date. An LLM may narrate a snapshot; it is never
the source of a number in one.

**Missing never becomes zero.** Every value is a :class:`Measure`, which cannot
be constructed as missing without a reason. Formulas never see a missing input
— the registry short-circuits first — so no formula can accidentally treat one
as zero.

**Refusal is a result.** A model that cannot honestly value an issuer returns a
:class:`ValuationRefusal` naming exactly what is missing. There is no generic
fallback model to fall back to, because a bank valued with a generic FCFF model
is worse than an explicit "not covered yet".

Dependency direction is one-way: this package imports ``pipeline``, never the
reverse, so Stage 1 stays independently runnable.
"""

from __future__ import annotations

#: Engine package version. Bump on any change to the engine's own behaviour.
ENGINE_VERSION = "0.3.0"

#: Version stamped onto every value the engine calculates. Bump whenever a
#: registered formula changes, or a golden fixture stops being reproducible.
#: ``test_registry.py`` fails the build if this and
#: :data:`FORMULA_REGISTRY_HASH` do not move together.
#:
#: Bumped in slice 3 without a formula change: the output document gained the
#: research package, ``uiState`` and the rule-registry hash, so a snapshot
#: stamped 0.2.0 and one stamped 0.3.0 are not the same contract even though
#: every number in them was produced by the same arithmetic.
MODEL_VERSION = "0.3.0"

#: Fingerprint of every registered formula's identity and logic. Regenerate
#: with ``python3 -m engine.goh_dip_tong.cli registry-hash`` after a deliberate
#: formula change, and bump :data:`MODEL_VERSION` in the same commit.
#:
#: Unchanged in slice 3, deliberately. The research layer computes nothing new:
#: its comparison quantities are the existing generic primitives renamed
#: through ``output_metric``. A slice that only assembles conclusions has no
#: business moving the promise the engine makes about its arithmetic.
FORMULA_REGISTRY_HASH = "8dfb38e8519af59be48882d1dc29e71c14a5bca3f56c931239c45b13cfe92a62"

#: Fingerprint of every registered research rule's identity and logic. The
#: research counterpart of the formula hash, and it exists for the same reason:
#: a published conclusion carries the ``ruleId`` that produced it, and a reader
#: following that ID must reach the rule that actually ran.
RESEARCH_RULE_REGISTRY_HASH = (
    "f62ad7a39de1e57145b3a6ef4c346b10fc8e2a5a9204e2e4e39bb566932060ce"
)

__all__ = [
    "ENGINE_VERSION",
    "MODEL_VERSION",
    "FORMULA_REGISTRY_HASH",
    "RESEARCH_RULE_REGISTRY_HASH",
]
