"""Mapping a model family to the model that implements it.

Every family declared in `models.yml` is registered, including the ones with
``supported: false`` and the ones whose mathematics does not exist yet. That is
the whole point: an *unregistered* family falls through to whatever the caller
does next, and "whatever the caller does next" is precisely how a generic
discounted-cash-flow model ends up valuing a bank.

An unmapped classification — Stage 1's ONBOARDING rule — is not an error
either. It gets :class:`NoModel`, which refuses with ``NO_MODEL_FAMILY``.
"""

from __future__ import annotations

from typing import Dict, Optional

from ..contracts.model import DeclaredOnlyModel, SectorModel
from .bank import BankModel

#: Metrics any equity model needs before it can say anything at all. Families
#: without a bespoke declaration inherit this, so their refusals still name
#: something concrete rather than shrugging.
GENERIC_REQUIRED_METRICS = (
    "revenue",
    "net_profit_attributable_to_parent",
    "equity_attributable_to_parent",
    "shares_outstanding",
    "cfo",
    "capex",
)


class NoModel(SectorModel):
    """The ONBOARDING case: a classification that maps to no family."""

    family = ""
    implemented = False
    required_metrics = ()


def _declared(family: str) -> DeclaredOnlyModel:
    return DeclaredOnlyModel(family, GENERIC_REQUIRED_METRICS)


#: Families with a bespoke declaration. Everything else in models.yml is
#: registered generically by :func:`build_registry`.
_BESPOKE: Dict[str, SectorModel] = {
    "BANK": BankModel(),
}


def build_registry(models_config: dict) -> Dict[str, SectorModel]:
    """One model per family declared in models.yml.

    Built from the config rather than hard-coded so a family added to
    `models.yml` is registered automatically. A family the engine has never
    heard of therefore refuses with a specific reason instead of vanishing.
    """
    registry: Dict[str, SectorModel] = dict(_BESPOKE)
    for family in (models_config.get("model_families") or {}):
        registry.setdefault(family, _declared(family))
    return registry


def model_for(models_config: dict, family: Optional[str]) -> SectorModel:
    """The model for ``family``, or :class:`NoModel` when there is none.

    A family named in the universe but absent from models.yml also gets a
    registered model — declared generically — so the refusal says which family
    was unknown rather than failing with a KeyError halfway through a build.
    """
    if not family:
        return NoModel()
    registry = build_registry(models_config)
    if family not in registry:
        return _declared(family)
    return registry[family]


__all__ = ["build_registry", "model_for", "NoModel", "GENERIC_REQUIRED_METRICS"]
