"""Deciding whether output describes real data or development fixtures.

The instruction is that every Stage 2 output be labelled ``FIXTURE_TEST_ONLY``
while the inputs are fixtures. The way to fail that instruction is not to
disagree with it — it is to implement it as a constant somebody has to remember
to change, and then to change it one release too early.

So the label is *derived*, every time, from the inputs' own provenance. It
flips to ``PRODUCTION`` on its own when every input is authoritative and
rights-cleared, and it cannot be flipped by hand: nothing in the engine writes
:class:`EngineMode` except this module.

Today the answer is always ``FIXTURE_TEST_ONLY``, and
``test_fixture_labelling.py`` proves that no reachable input state produces
anything else.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from ..contracts.enums import EngineMode
from ..settings import EngineSettings

#: Quality flags on a Stage 1 snapshot that mark it as development data.
FIXTURE_FLAGS = frozenset({"FIXTURE_DATA", "SYNTHETIC", "FIXTURE_TEST_ONLY"})

#: Rights statuses under which a provider's data may back a published,
#: production-labelled research output. Anything else is either restricted or
#: not yet reviewed, and in both cases the output is not production.
PUBLISHABLE_RIGHTS = frozenset(
    {"PUBLIC_RAW_DATA_APPROVED", "PUBLIC_DERIVED_OUTPUT_APPROVED"}
)


@dataclass
class Provenance:
    """Where an issuer's inputs came from, and what that permits."""

    mode: EngineMode
    reasons: List[str] = field(default_factory=list)
    providers: List[str] = field(default_factory=list)
    universe_authoritative: bool = False
    universe_provenance: Optional[str] = None
    input_flags: List[str] = field(default_factory=list)

    @property
    def is_fixture(self) -> bool:
        return self.mode == EngineMode.FIXTURE_TEST_ONLY

    def to_json(self) -> dict:
        return {
            "mode": str(self.mode),
            "reasons": sorted(self.reasons),
            "providers": sorted(self.providers),
            "universeAuthoritative": self.universe_authoritative,
            "universeProvenance": self.universe_provenance,
            "inputFlags": sorted(self.input_flags),
        }


def assess(
    settings: EngineSettings,
    universe: dict,
    snapshot: dict,
    extra_providers: Sequence[str] = (),
) -> Provenance:
    """Derive the mode for one issuer's inputs.

    Production requires *every* condition to hold. Fixture mode requires only
    one to fail, which is the correct asymmetry: the cost of wrongly labelling
    development data as production is a false claim about real markets, and the
    cost of the reverse is an over-cautious banner.
    """
    reasons: List[str] = []

    authoritative = bool(universe.get("authoritative", False))
    universe_provenance = universe.get("provenance")
    if not authoritative:
        reasons.append(
            "idx30.current.json declares authoritative=false — the IDX30 universe "
            "is a development fixture, not the published index"
        )
    if universe_provenance and universe_provenance.upper() == "FIXTURE":
        reasons.append(f"universe provenance is {universe_provenance}")

    flags = list((snapshot.get("quality") or {}).get("flags") or [])
    for flag in sorted(set(flags) & FIXTURE_FLAGS):
        reasons.append(f"input snapshot carries the {flag} quality flag")

    providers = sorted(set(_providers_for(settings, universe)) | set(extra_providers))
    declared = settings.pipeline.sources().get("providers") or {}
    for provider_id in providers:
        entry = declared.get(provider_id) or {}
        if entry.get("kind") == "fixture":
            reasons.append(f"provider {provider_id} is fixture-backed")
        if not entry.get("authoritative", False):
            reasons.append(f"provider {provider_id} is not authoritative")
        rights = entry.get("rights_status")
        if rights not in PUBLISHABLE_RIGHTS:
            reasons.append(
                f"provider {provider_id} has rights_status {rights}, which does "
                f"not permit publishing derived output"
            )

    mode = EngineMode.PRODUCTION if not reasons else EngineMode.FIXTURE_TEST_ONLY
    return Provenance(
        mode=mode,
        reasons=reasons,
        providers=providers,
        universe_authoritative=authoritative,
        universe_provenance=universe_provenance,
        input_flags=sorted(set(flags)),
    )


def _providers_for(settings: EngineSettings, universe: dict) -> List[str]:
    """Providers that contributed to this issuer's inputs.

    The universe's own source is always one. The snapshot does not name the
    provider behind each fact — it carries a document reference — so any
    provider that supplied a data type the engine reads is treated as a
    contributor. Over-including here is safe; under-including would let an
    unreviewed source pass unnoticed into a production label.
    """
    contributors = []
    source = universe.get("source") or {}
    if source.get("providerId"):
        contributors.append(source["providerId"])

    declared: Dict[str, dict] = settings.pipeline.sources().get("providers") or {}
    consumed = {"financial_facts", "financial_statements", "macro_series"}
    for provider_id, entry in declared.items():
        if not entry.get("enabled"):
            continue
        if consumed & set(entry.get("data_types") or []):
            contributors.append(provider_id)
    return contributors


def disclaimers_for(provenance: Provenance, base: Sequence[str]) -> List[str]:
    """Stage 1's disclaimers, with the mode statement placed first.

    Order matters: a reader who stops after one line should have read the one
    that says this is not real analysis.
    """
    lead = (
        "FIXTURE_TEST_ONLY. Every value in this document was calculated from "
        "committed development fixtures. It is not live, current or "
        "authoritative analysis of any real security, and no valuation has "
        "been produced from it."
        if provenance.is_fixture
        else "Calculated from authoritative, rights-cleared sources."
    )
    return [lead, *base]


__all__ = [
    "Provenance",
    "assess",
    "disclaimers_for",
    "FIXTURE_FLAGS",
    "PUBLISHABLE_RIGHTS",
]
