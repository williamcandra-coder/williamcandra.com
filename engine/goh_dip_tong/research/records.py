"""What a research record is, and what makes one inadmissible.

Spec section 2.10 wants thesis, counter-thesis, catalysts, risks and breakers.
The way that requirement fails is not that the sections are missing — it is
that they fill up with sentences nobody can trace, written once and never
re-derived, sitting beside numbers that moved underneath them.

So a research record is a *typed, identified, cited* object rather than a
string. Four constraints are enforced at construction:

**It has a stable identity.** ``record_id`` is derived from the issuer, the
record type, the rule that produced it and the scenario it applies to. The same
inputs produce the same ID on every run and on every machine, so a UI can
anchor to one, a reader can cite one, and two runs can be diffed.

**It names the rule that produced it.** There is no way to construct a record
without a ``rule_id``, which means there is no way to publish a claim that
somebody typed. The rule is the derivation, exactly as ``formula_id`` is the
derivation of a number.

**A claim must cite calculated records and evidence.** Not "should" — a
:class:`ResearchRecord` of a claim type cannot be constructed without at least
one of each. An assertion about a company that points at no figure and no
source is the thing this module exists to make impossible.

**A claim may not be a recommendation.** The banned vocabulary below is checked
on every statement. A target price, a buy or a "guaranteed" is refused at
construction, so it cannot reach a snapshot however it got written.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from pipeline.goh_dip_tong.contracts.enums import StrEnum
from pipeline.goh_dip_tong.contracts.records import ContractError


class RecordType(StrEnum):
    """What kind of statement a record makes."""

    #: A supported argument for the business, drawn from calculated records.
    THESIS = "THESIS"
    #: The argument against, or the assumption the thesis rests on most.
    COUNTER_THESIS = "COUNTER_THESIS"
    #: A driver whose movement would change the answer materially.
    CATALYST = "CATALYST"
    #: A way the forecast is wrong that the model can still absorb.
    RISK = "RISK"
    #: A condition under which the model stops being valid at all. Distinct
    #: from a risk: a breaker is not a worse number, it is no number.
    BREAKER = "BREAKER"
    #: A pointer to a source record. Carries no claim.
    EVIDENCE_REF = "EVIDENCE_REF"
    #: A pointer to the audit trail — registry hashes, gates, rate basis.
    MODEL_AUDIT_REF = "MODEL_AUDIT_REF"
    #: How a cross-check compares with the primary method, and why.
    METHOD_COMPARISON = "METHOD_COMPARISON"


class Importance(StrEnum):
    """How much a thesis, counter-thesis or catalyst moves the conclusion."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Severity(StrEnum):
    """How badly a risk or breaker would damage the conclusion."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


#: Types that assert something about the issuer. These carry the citation
#: requirement; a pointer record does not, because it *is* a citation.
CLAIM_TYPES: Tuple[RecordType, ...] = (
    RecordType.THESIS,
    RecordType.COUNTER_THESIS,
    RecordType.CATALYST,
    RecordType.RISK,
    RecordType.BREAKER,
)

#: Types that must be ranked. A risk with no severity and a risk with LOW
#: severity read identically in a list, and only one of them is honest.
RANKED_TYPES: Tuple[RecordType, ...] = CLAIM_TYPES

#: Types whose severity field is the ranking, rather than importance.
SEVERITY_TYPES: Tuple[RecordType, ...] = (RecordType.RISK, RecordType.BREAKER)

#: A statement is a sentence, not a section. The limit is a design constraint
#: rather than a formatting one: a claim that needs three hundred characters is
#: usually several claims, and several claims cannot be cited as one.
MAX_STATEMENT_CHARS = 320

#: Vocabulary that turns an observation into advice. Refused at construction,
#: because the difference between "residual income stays positive" and "buy" is
#: not a matter of tone — the second is a recommendation this project does not
#: make, and no rule may produce one.
BANNED_PHRASES: Tuple[str, ...] = (
    "target price",
    "price target",
    "fair value target",
    "recommend",
    "recommendation",
    "buy",
    "sell",
    "accumulate",
    "overweight",
    "underweight",
    "outperform",
    "underperform",
    "undervalued",
    "overvalued",
    "guaranteed",
    "guarantee",
    "risk-free return",
    "sure thing",
)

_BANNED = tuple(
    (phrase, re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE))
    for phrase in BANNED_PHRASES
)


class UnsupportedClaim(ContractError):
    """A research record was constructed without the support it claims.

    Raised rather than returned. An uncited assertion is not a degraded
    result the caller might reasonably publish anyway — it is the specific
    thing the research package exists to prevent, and it should stop a build
    rather than reach a reader.
    """


def stable_id(
    ticker: str,
    record_type: RecordType,
    rule_id: str,
    scenario: Optional[str] = None,
) -> str:
    """The record's identity: issuer, type, rule, scenario.

    Deterministic and free of any timestamp, index or ordering. A record that
    identified itself by its position in a list would be renamed every time a
    rule ahead of it stopped firing, which is exactly when a reader most wants
    the identity to have held still.
    """
    return ".".join([ticker, str(record_type), rule_id, scenario or "ALL"])


@dataclass(frozen=True)
class ResearchRecord:
    """One research conclusion, with its full derivation."""

    record_id: str
    record_type: RecordType
    statement: str
    rule_id: str
    #: ``Calculated.ref`` values. Every number behind this claim.
    supporting_records: Tuple[str, ...] = ()
    #: Evidence refs — Stage 1 fact keys, macro series, audit identifiers.
    supporting_evidence: Tuple[str, ...] = ()
    #: The scenario this applies to, or ``None`` where it applies to all.
    scenario: Optional[str] = None
    importance: Optional[Importance] = None
    severity: Optional[Severity] = None

    def __post_init__(self) -> None:
        if not self.record_id:
            raise UnsupportedClaim("a research record must have a stable ID")
        if not self.rule_id:
            raise UnsupportedClaim(
                f"{self.record_id}: a research record must name the rule that "
                f"produced it; an untraceable claim is not publishable"
            )
        self._check_statement()
        self._check_support()
        self._check_ranking()

    # ---- construction checks --------------------------------------------
    def _check_statement(self) -> None:
        statement = self.statement.strip()
        if not statement:
            raise UnsupportedClaim(
                f"{self.record_id}: a research record must state something"
            )
        if len(statement) > MAX_STATEMENT_CHARS:
            raise UnsupportedClaim(
                f"{self.record_id}: statement is {len(statement)} characters, "
                f"limit {MAX_STATEMENT_CHARS}. A claim that long is usually "
                f"several claims, and several claims cannot be cited as one."
            )
        for phrase, pattern in _BANNED:
            if pattern.search(statement):
                raise UnsupportedClaim(
                    f"{self.record_id}: statement contains {phrase!r}. This "
                    f"project publishes observations with their derivations, "
                    f"not recommendations, and no rule may produce one."
                )

    def _check_support(self) -> None:
        if self.record_type not in CLAIM_TYPES:
            return
        if not self.supporting_records:
            raise UnsupportedClaim(
                f"{self.record_id}: a {self.record_type} must cite at least one "
                f"calculated record. A claim pointing at no figure is an opinion."
            )
        if not self.supporting_evidence:
            raise UnsupportedClaim(
                f"{self.record_id}: a {self.record_type} must cite at least one "
                f"evidence reference, so the claim can be walked back to a source."
            )

    def _check_ranking(self) -> None:
        if self.record_type not in RANKED_TYPES:
            return
        ranked = (
            self.severity
            if self.record_type in SEVERITY_TYPES
            else self.importance
        )
        if ranked is None:
            field = (
                "severity" if self.record_type in SEVERITY_TYPES else "importance"
            )
            raise UnsupportedClaim(
                f"{self.record_id}: a {self.record_type} must carry a {field}. "
                f"An unranked item and a LOW one read identically in a list, and "
                f"only one of them is honest."
            )

    # ---- serialisation ---------------------------------------------------
    def to_json(self) -> dict:
        return {
            "id": self.record_id,
            "type": str(self.record_type),
            "statement": self.statement,
            "ruleId": self.rule_id,
            "supportingRecords": list(self.supporting_records),
            "supportingEvidence": list(self.supporting_evidence),
            "scenario": self.scenario,
            "importance": str(self.importance) if self.importance else None,
            "severity": str(self.severity) if self.severity else None,
        }


def sort_key(record: ResearchRecord) -> tuple:
    """Deterministic ordering. Type, then rule, then scenario, then ID.

    Never insertion order: rules fire in registry order today, and a rule added
    later would silently reorder every section it landed in.
    """
    return (
        str(record.record_type),
        record.rule_id,
        record.scenario or "",
        record.record_id,
    )


__all__ = [
    "RecordType",
    "Importance",
    "Severity",
    "ResearchRecord",
    "UnsupportedClaim",
    "CLAIM_TYPES",
    "RANKED_TYPES",
    "SEVERITY_TYPES",
    "BANNED_PHRASES",
    "MAX_STATEMENT_CHARS",
    "stable_id",
    "sort_key",
]
