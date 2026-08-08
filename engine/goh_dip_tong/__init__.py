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
ENGINE_VERSION = "0.1.0"

#: Version stamped onto every value the engine calculates. Bump whenever a
#: registered formula changes, or a golden fixture stops being reproducible.
#: ``test_registry.py`` fails the build if this and
#: :data:`FORMULA_REGISTRY_HASH` do not move together.
MODEL_VERSION = "0.1.0"

#: Fingerprint of every registered formula's identity and logic. Regenerate
#: with ``python3 -m engine.goh_dip_tong.cli registry-hash`` after a deliberate
#: formula change, and bump :data:`MODEL_VERSION` in the same commit.
FORMULA_REGISTRY_HASH = "a1ecff05d14d4f352832b798c02f9f4a64759fb77a3db847fcf1246ec3c4398a"

__all__ = ["ENGINE_VERSION", "MODEL_VERSION", "FORMULA_REGISTRY_HASH"]
