"""Assembling the research package, and the check that keeps it honest.

Assembly is the easy half: fire the rules, group by type, sort deterministically.

The half that matters is the reference check. Every claim cites calculated
records and evidence by ID, and this module verifies that **every cited ID
actually exists** in what the engine produced for this issuer. A claim citing a
ref that was never calculated is not a formatting problem — it is a statement
whose support cannot be inspected, which is indistinguishable from a statement
with no support. It raises here rather than being dropped quietly, because a
rule that produces one is broken and should stop a build.

This module contains no arithmetic, for the same reason
:mod:`engine.goh_dip_tong.research.rules` does not.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from ..contracts.calculated import Calculated
from .records import (
    CLAIM_TYPES,
    RecordType,
    ResearchRecord,
    UnsupportedClaim,
    sort_key,
)
from .rules import RULES, RuleContext

#: Why the claim sections are absent when nothing was valued. Stated rather
#: than left as an empty list: "no thesis" and "we produced no thesis because
#: there is no valuation to have a thesis about" are different documents.
NOT_PRODUCED_REASON = (
    "No valuation was produced for this issuer, so no thesis, counter-thesis, "
    "catalyst, risk or breaker is asserted. Research conclusions are derived "
    "from calculated records; with none to derive from, an empty section is "
    "the honest output and an inferred one would be invention."
)


@dataclass
class ResearchPackage:
    """Every research record for one issuer, grouped and ordered."""

    ticker: str
    family: str
    valued: bool
    rule_registry_hash: str
    rules_fired: Tuple[str, ...] = ()
    records: List[ResearchRecord] = field(default_factory=list)

    # ---- projections by type --------------------------------------------
    def of_type(self, record_type: RecordType) -> List[ResearchRecord]:
        return [r for r in self.records if r.record_type == record_type]

    @property
    def thesis(self) -> List[ResearchRecord]:
        return self.of_type(RecordType.THESIS)

    @property
    def counter_thesis(self) -> List[ResearchRecord]:
        return self.of_type(RecordType.COUNTER_THESIS)

    @property
    def catalysts(self) -> List[ResearchRecord]:
        return self.of_type(RecordType.CATALYST)

    @property
    def risks(self) -> List[ResearchRecord]:
        return self.of_type(RecordType.RISK)

    @property
    def breakers(self) -> List[ResearchRecord]:
        return self.of_type(RecordType.BREAKER)

    @property
    def method_comparison(self) -> List[ResearchRecord]:
        return self.of_type(RecordType.METHOD_COMPARISON)

    @property
    def evidence_refs(self) -> List[ResearchRecord]:
        return self.of_type(RecordType.EVIDENCE_REF)

    @property
    def model_audit_refs(self) -> List[ResearchRecord]:
        return self.of_type(RecordType.MODEL_AUDIT_REF)

    @property
    def claims(self) -> List[ResearchRecord]:
        return [r for r in self.records if r.record_type in CLAIM_TYPES]

    # ---- serialisation ---------------------------------------------------
    def section(self, records: Sequence[ResearchRecord]) -> dict:
        """A produced section, or an explicit absence with the reason."""
        if not self.valued:
            return {"status": "NOT_PRODUCED", "reason": NOT_PRODUCED_REASON}
        return {"status": "PRODUCED", "records": [r.to_json() for r in records]}

    def refs_section(self) -> dict:
        """Citation indexes. Produced whether or not anything was valued —
        these carry no claim, so a refusal does not suppress them."""
        return {
            "status": "PRODUCED",
            "evidence": [r.to_json() for r in self.evidence_refs],
            "modelAudit": [r.to_json() for r in self.model_audit_refs],
        }

    def audit_json(self) -> dict:
        return {
            "ruleRegistryHash": self.rule_registry_hash,
            "ruleCount": len(RULES),
            "rulesFired": list(self.rules_fired),
        }


# ---------------------------------------------------------------------------
# building
# ---------------------------------------------------------------------------


def build(
    ticker: str,
    family: str,
    valued: bool,
    comparison_records: Mapping[str, Calculated],
    fact_keys: Mapping[str, Sequence[str]],
    audit_refs: Sequence[str],
    scenario_order: Sequence[str] = (),
    cost_of_equity_basis: str = "",
) -> ResearchPackage:
    """Fire every rule for this family, then verify what they cited.

    ``valued`` is load-bearing rather than cosmetic: it is what stops the claim
    rules from running at all for a refused issuer, so there is no unsupported
    thesis to filter out afterwards.
    """
    context = RuleContext(
        ticker=ticker,
        family=family or "",
        valued=bool(valued),
        scenario_order=tuple(scenario_order),
        records=dict(comparison_records),
        fact_keys={k: tuple(v) for k, v in fact_keys.items()},
        audit_refs=tuple(audit_refs),
        cost_of_equity_basis=cost_of_equity_basis,
    )

    produced = RULES.apply(context)

    known_records = {record.ref for record in comparison_records.values()}
    known_evidence = {key for keys in fact_keys.values() for key in keys}
    known_evidence.update(audit_refs)
    _reject_dangling(produced, known_records, known_evidence)

    return ResearchPackage(
        ticker=ticker,
        family=family or "",
        valued=bool(valued),
        rule_registry_hash=RULES.registry_hash(),
        rules_fired=tuple(sorted({r.rule_id for r in produced})),
        records=sorted(produced, key=sort_key),
    )


def _reject_dangling(
    records: Iterable[ResearchRecord],
    known_records: Iterable[str],
    known_evidence: Iterable[str],
) -> None:
    """Refuse any record citing something the engine did not produce.

    Deliberately checked against the records that exist rather than against a
    pattern. A ref that merely *looks* well-formed proves nothing; the question
    a reader will ask is whether the number is there, and this is that question.
    """
    known_records = set(known_records)
    known_evidence = set(known_evidence)
    for record in records:
        missing_records = [
            ref for ref in record.supporting_records if ref not in known_records
        ]
        if missing_records:
            raise UnsupportedClaim(
                f"{record.record_id}: cites calculated record(s) that do not "
                f"exist: {', '.join(sorted(missing_records))}. A claim whose "
                f"support cannot be inspected has no support."
            )
        missing_evidence = [
            ref for ref in record.supporting_evidence if ref not in known_evidence
        ]
        if missing_evidence:
            raise UnsupportedClaim(
                f"{record.record_id}: cites evidence that does not exist: "
                f"{', '.join(sorted(missing_evidence))}."
            )


def fact_keys_for(engine_input) -> Dict[str, Tuple[str, ...]]:
    """Stage 1 fact keys, grouped by metric.

    Only consolidated facts with a value. A segment-level row is supplementary
    and a null one is not evidence of anything, so neither may be cited as the
    source behind a claim about the whole issuer.
    """
    grouped: Dict[str, List[str]] = {}
    for record in engine_input.consolidated:
        if record.is_missing:
            continue
        for ref in record.input_refs:
            grouped.setdefault(record.metric_id, [])
            if ref.ref not in grouped[record.metric_id]:
                grouped[record.metric_id].append(ref.ref)
    return {metric: tuple(sorted(keys)) for metric, keys in sorted(grouped.items())}


def audit_refs_for(
    engine_version: str,
    model_version: str,
    formula_registry_hash: str,
    cost_of_equity_basis: Optional[str] = None,
) -> Tuple[str, ...]:
    """The identifiers a reader needs to reproduce this document exactly."""
    refs = [
        f"audit:engineVersion={engine_version}",
        f"audit:modelVersion={model_version}",
        f"audit:formulaRegistryHash={formula_registry_hash}",
        f"audit:ruleRegistryHash={RULES.registry_hash()}",
    ]
    if cost_of_equity_basis:
        refs.append(f"audit:costOfEquityBasis={cost_of_equity_basis}")
    return tuple(refs)


__all__ = [
    "ResearchPackage",
    "NOT_PRODUCED_REASON",
    "build",
    "fact_keys_for",
    "audit_refs_for",
]
