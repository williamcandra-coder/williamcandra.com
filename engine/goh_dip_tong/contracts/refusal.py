"""Refusing to value, as a first-class result rather than an omission.

The rule this exists to enforce is spec section 2.11's: *unsupported models
return a controlled status rather than a generic valuation.* A bank run through
a generic FCFF model produces a number that looks like research and is not; an
explicit refusal that names the metrics it lacks is more useful and more
honest.

A refusal is therefore structured data, not an absent field. It says which gates
failed and which inputs are missing, so "why is there no valuation" always has
a specific, checkable answer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from pipeline.goh_dip_tong.contracts.records import ContractError

from .enums import GateId, RefusalReason, ValuationMethod, ValuationOutcome


@dataclass(frozen=True)
class Gate:
    """One precondition, and whether it held."""

    gate_id: GateId
    passed: bool
    detail: str = ""

    def to_json(self) -> dict:
        return {"gate": str(self.gate_id), "passed": self.passed, "detail": self.detail}


@dataclass(frozen=True)
class ValuationRefusal:
    """No valuation was produced, and here is exactly why."""

    reason: RefusalReason
    note: str
    failed_gates: Sequence[GateId] = ()
    missing_inputs: Sequence[str] = ()
    method: Optional[ValuationMethod] = None

    def __post_init__(self) -> None:
        if not self.note:
            raise ContractError(
                f"{self.reason}: a refusal must explain itself in prose; a bare "
                f"enum tells a reader nothing they can act on"
            )

    @property
    def outcome(self) -> ValuationOutcome:
        return ValuationOutcome.REFUSED

    def to_json(self) -> dict:
        return {
            "status": str(ValuationOutcome.REFUSED),
            "reason": str(self.reason),
            "method": str(self.method) if self.method else None,
            "failedGates": sorted(str(g) for g in self.failed_gates),
            "missingInputs": sorted(self.missing_inputs),
            "note": self.note,
        }


@dataclass
class GateReport:
    """Accumulates gate outcomes, then produces the refusal they imply.

    Deliberately mirrors Stage 1's ``ValidationReport``: collect everything,
    decide at the end. Stopping at the first failed gate would report one
    missing metric at a time and turn diagnosis into a dozen round trips.
    """

    gates: List[Gate] = field(default_factory=list)
    missing_inputs: List[str] = field(default_factory=list)

    def check(self, gate_id: GateId, passed: bool, detail: str = "") -> bool:
        self.gates.append(Gate(gate_id, bool(passed), detail))
        return bool(passed)

    def require_inputs(
        self, gate_id: GateId, missing: Sequence[str], detail: str = ""
    ) -> bool:
        missing = sorted(set(missing))
        self.missing_inputs.extend(missing)
        return self.check(
            gate_id,
            not missing,
            detail or (f"absent: {', '.join(missing)}" if missing else "all present"),
        )

    @property
    def failed(self) -> List[Gate]:
        return [g for g in self.gates if not g.passed]

    @property
    def passed(self) -> bool:
        return not self.failed

    def refusal(self, reason: RefusalReason, note: str,
                method: Optional[ValuationMethod] = None) -> ValuationRefusal:
        return ValuationRefusal(
            reason=reason,
            note=note,
            failed_gates=[g.gate_id for g in self.failed],
            missing_inputs=sorted(set(self.missing_inputs)),
            method=method,
        )

    def to_json(self) -> list:
        return [g.to_json() for g in sorted(self.gates, key=lambda g: str(g.gate_id))]


class MethodNotPermitted(ContractError):
    """A valuation method was invoked for a family it is invalid for.

    This raises rather than returning a refusal on purpose. A refusal is what a
    model returns when the *data* will not support a valuation; calling
    ``ev_ebitda`` on a bank is not a data problem, it is a programming error,
    and it should fail loudly during development rather than be discovered in a
    published snapshot. Stage 1's models.yml already states the rule: for a
    bank, "debt is raw material, not financing. EV/EBITDA and FCFF are invalid
    here."
    """


__all__ = [
    "Gate",
    "GateReport",
    "ValuationRefusal",
    "MethodNotPermitted",
]
