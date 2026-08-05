"""The formula registry: every calculation the engine can perform, by name.

Three things fall out of routing all arithmetic through here, and each is a
defect class the design is meant to make impossible rather than unlikely:

**Nothing computes anonymously.** A :class:`Calculated` requires a
``formula_id``, and the only way to get one is to register the formula. A
number that appeared from an ad-hoc expression somewhere cannot be published.

**Input references are populated by machine.** The registry knows what went in,
so ``inputRefs`` is never a hand-maintained list that quietly falls out of date
with the expression above it.

**Missing propagates before the formula runs.** If any input is missing the
registry short-circuits and the function is never called. No formula body can
therefore treat a missing value as zero, because no formula body ever sees one.

The registry is also hashable, which is what makes point-in-time reproducibility
enforceable: change a formula's logic without bumping ``MODEL_VERSION`` and the
hash moves, and the build fails.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import textwrap
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, Optional, Tuple

from pipeline.goh_dip_tong.contracts.enums import ValueBasis
from pipeline.goh_dip_tong.contracts.records import ContractError, Measure

from .calculated import Calculated, InputRef, Period
from .enums import ScenarioName


class FormulaError(ContractError):
    """A formula was registered or invoked incorrectly."""


@dataclass(frozen=True)
class Formula:
    """One registered calculation."""

    formula_id: str
    inputs: Tuple[str, ...]
    output_metric: str
    fn: Callable[..., Measure]
    doc: str = ""

    def source_fingerprint(self) -> str:
        """Structure of the function body, insensitive to comments and layout.

        Hashing the AST rather than the raw source means reformatting or
        rewording a comment does not force a model-version bump, while any
        change to what the function actually computes does.

        The decorator list and the function's Python name are stripped first.
        A formula's identity is its ``formula_id``, which is hashed separately;
        renaming the underlying function or moving it to another registry
        changes neither what it computes nor what it is called in published
        output, so neither should invalidate a model version.
        """
        node = ast.parse(textwrap.dedent(inspect.getsource(self.fn))).body[0]
        node.decorator_list = []
        node.name = ""
        return ast.dump(ast.Module(body=[node], type_ignores=[]))


class FormulaRegistry:
    """A name-to-formula map that can compute, and can fingerprint itself."""

    def __init__(self) -> None:
        self._formulas: Dict[str, Formula] = {}

    # ---- registration ----------------------------------------------------
    def formula(self, formula_id: str, inputs: Iterable[str], output_metric: str):
        """Decorator registering ``fn`` under ``formula_id``.

        The decorated function receives one :class:`Measure` per declared input,
        by keyword, and returns a :class:`Measure`. It is guaranteed that no
        argument is missing.
        """
        inputs = tuple(inputs)

        def decorate(fn: Callable[..., Measure]) -> Callable[..., Measure]:
            if formula_id in self._formulas:
                raise FormulaError(f"formula already registered: {formula_id!r}")
            signature = inspect.signature(fn)
            declared = tuple(signature.parameters)
            if declared != inputs:
                raise FormulaError(
                    f"{formula_id}: declared inputs {inputs} do not match the "
                    f"function signature {declared}; the registry would then "
                    f"record inputRefs that do not describe what was used"
                )
            self._formulas[formula_id] = Formula(
                formula_id=formula_id,
                inputs=inputs,
                output_metric=output_metric,
                fn=fn,
                doc=inspect.getdoc(fn) or "",
            )
            return fn

        return decorate

    # ---- introspection ---------------------------------------------------
    def __contains__(self, formula_id: object) -> bool:
        return formula_id in self._formulas

    def __len__(self) -> int:
        return len(self._formulas)

    def get(self, formula_id: str) -> Formula:
        try:
            return self._formulas[formula_id]
        except KeyError:
            raise FormulaError(
                f"unknown formula {formula_id!r}; registered: {sorted(self._formulas)}"
            ) from None

    def ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self._formulas))

    def registry_hash(self) -> str:
        """Fingerprint of every formula's identity and logic.

        Sorted, so it does not depend on import order. Covers the formula ID,
        its declared inputs, its output metric and the structure of its body.
        """
        digest = hashlib.sha256()
        for formula_id in sorted(self._formulas):
            formula = self._formulas[formula_id]
            digest.update(formula.formula_id.encode("utf-8"))
            digest.update(b"\x00".join(i.encode("utf-8") for i in formula.inputs))
            digest.update(formula.output_metric.encode("utf-8"))
            digest.update(formula.source_fingerprint().encode("utf-8"))
            digest.update(b"\x1e")
        return digest.hexdigest()

    # ---- computation -----------------------------------------------------
    def compute(
        self,
        formula_id: str,
        period: Period,
        inputs: Dict[str, Calculated],
        model_version: str,
        calculated_at: str,
        scenario: ScenarioName = ScenarioName.ACTUAL,
        segment: Optional[str] = None,
        notes: Optional[str] = None,
        output_metric: Optional[str] = None,
    ) -> Calculated:
        """Run one formula and wrap the result with its full derivation.

        ``output_metric`` renames the result. Generic formulas — ``core.ratio``,
        ``core.per_share`` — are reused across many metrics, and without this
        every value one produced would be called "ratio" or "per_share",
        which is no name at all in an audit trail.
        """
        formula = self.get(formula_id)

        supplied = tuple(sorted(inputs))
        expected = tuple(sorted(formula.inputs))
        if supplied != expected:
            raise FormulaError(
                f"{formula_id}: expected inputs {expected}, got {supplied}"
            )

        # Input refs are ordered by the formula's declaration, not by dict
        # iteration, so the same calculation always records the same list.
        refs: Tuple[InputRef, ...] = tuple(
            self._ref_for(inputs[name]) for name in formula.inputs
        )

        result = self._propagate_or_run(formula, inputs)
        result = self._propagate_basis(result, inputs, formula)

        return Calculated(
            metric_id=output_metric or formula.output_metric,
            measure=result,
            period=period,
            formula_id=formula_id,
            model_version=model_version,
            calculated_at=calculated_at,
            scenario=scenario,
            input_refs=refs,
            segment=segment,
            notes=notes,
        )

    @staticmethod
    def _propagate_basis(result: Measure, inputs: Dict[str, Calculated],
                         formula: Formula) -> Measure:
        """A figure computed from a forecast is a forecast.

        Spec's shared rules require reported, derived and forecast values to
        stay visually distinct all the way to the UI. A ratio computed off
        projected line items is not a derived historical fact, however derived
        its arithmetic — labelling it DERIVED would let a projection render
        with the same weight as something a company actually reported.
        """
        if result.is_missing or result.basis == ValueBasis.FORECAST:
            return result
        forecast_input = any(
            inputs[name].basis == ValueBasis.FORECAST for name in formula.inputs
        )
        if not forecast_input:
            return result
        return Measure(
            value=result.value, unit=result.unit, currency=result.currency,
            scale=result.scale, basis=ValueBasis.FORECAST,
            quality_status=result.quality_status,
        )

    @staticmethod
    def _ref_for(value: Calculated) -> InputRef:
        """How one input is cited in the result's derivation trail.

        A value lifted straight from a fact cites the fact itself, so the trail
        ends at a reported figure rather than at an intermediate the engine
        invented a name for. A value the engine computed cites that
        computation, and the chain continues through its own ``inputRefs``.

        The empty-``input_refs`` case is real rather than defensive: a
        hand-built ``Calculated`` — in a test, or in a later slice that
        synthesises an assumption — carries no upstream fact. Citing itself is
        the honest answer there; reaching for ``input_refs[0]`` would raise.
        """
        if value.formula_id == "source.fact" and value.input_refs:
            return value.input_refs[0]
        return value.as_input()

    @staticmethod
    def _propagate_or_run(formula: Formula, inputs: Dict[str, Calculated]) -> Measure:
        """Short-circuit on a missing input; otherwise evaluate.

        The reason carried forward is the first missing input in the formula's
        *declared* order, not in dict order, so the same missing combination
        always reports the same reason.
        """
        for name in formula.inputs:
            candidate = inputs[name]
            if candidate.is_missing:
                return Measure.missing(
                    candidate.missing_reason,
                    unit=candidate.unit,
                    currency=candidate.currency,
                    basis=candidate.basis,
                )

        measure = formula.fn(**{name: inputs[name].measure for name in formula.inputs})
        if not isinstance(measure, Measure):
            raise FormulaError(
                f"{formula.formula_id}: formulas must return a Measure, got "
                f"{type(measure).__name__}; a bare float cannot carry a missing reason"
            )
        return measure


#: The engine's single registry. Formula modules register into this on import.
REGISTRY = FormulaRegistry()


__all__ = ["Formula", "FormulaRegistry", "FormulaError", "REGISTRY"]
