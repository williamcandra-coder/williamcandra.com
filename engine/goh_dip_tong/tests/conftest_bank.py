"""Shared helpers for the bank-model tests.

Kept out of ``conftest.py`` so it is importable by name: several tests need to
build a context or a projection outside a fixture, and a fixture that can only
be requested is awkward to compose with.
"""

from __future__ import annotations

import shutil
from typing import Optional

from engine.goh_dip_tong import MODEL_VERSION
from engine.goh_dip_tong.contracts.model import ModelContext
from engine.goh_dip_tong.forecasting import assumptions as assumptions_mod
from engine.goh_dip_tong.forecasting import bank as forecast_mod
from engine.goh_dip_tong.inputs import loader
from engine.goh_dip_tong.models.bank import BankModel, build_history
from engine.goh_dip_tong.settings import EngineSettings
from engine.goh_dip_tong.valuation.guards import load_guards

CALCULATED_AT = "2026-08-04T00:00:00Z"
AS_OF = "2026-07-31"


def context(settings: EngineSettings, allow_synthetic: bool = True,
            persistence: Optional[float] = None) -> ModelContext:
    """A model context wired for the synthetic-bank fixture.

    ``allow_synthetic`` defaults to True here and *only* here: this is the test
    harness, which is the one caller permitted to ask for the SYNTHETIC cost of
    equity by name.
    """
    config = settings.engine_config()
    terminal = config.get("terminal") or {}
    return ModelContext(
        models_config=settings.pipeline.models(),
        allow_synthetic_cost_of_equity=allow_synthetic,
        cost_of_capital_config=settings.cost_of_capital(),
        scenario_config=settings.scenarios(),
        persistence=(persistence if persistence is not None
                     else float(terminal.get("persistence", 0.6))),
        guards=load_guards(config),
        model_version=MODEL_VERSION,
        calculated_at=CALCULATED_AT,
    )


def load(settings: EngineSettings, ticker: str = "SYNB", as_of: str = AS_OF):
    return loader.load(settings, ticker, as_of=as_of,
                       model_version=MODEL_VERSION, calculated_at=CALCULATED_AT)


def evaluate(settings: EngineSettings, ticker: str = "SYNB", **kwargs):
    return BankModel().evaluate(load(settings, ticker), context(settings, **kwargs))


def projection(settings: EngineSettings, scenario: str = "BASE",
               ticker: str = "SYNB") -> forecast_mod.Projection:
    """One scenario's projection, without running the valuation on top."""
    engine_input = load(settings, ticker)
    history = build_history(engine_input)
    anchors = assumptions_mod.derive_bank_anchors(history)
    assumption_set = assumptions_mod.build(
        anchors, scenario, settings.scenarios())
    opening_book = _fact(engine_input, "equity_attributable_to_parent")
    shares = _fact(engine_input, "shares_outstanding")
    return forecast_mod.project(history, assumption_set, opening_book, shares,
                                BankModel.horizon, MODEL_VERSION, CALCULATED_AT)


def anchors(settings: EngineSettings, ticker: str = "SYNB") -> dict:
    return assumptions_mod.derive_bank_anchors(build_history(load(settings, ticker)))


def _fact(engine_input, metric: str):
    year = max(r.period.fiscal_year for r in engine_input.consolidated
               if r.period.fiscal_year and not r.is_missing)
    for record in engine_input.consolidated:
        if (record.metric_id == metric and record.period.fiscal_year == year
                and not record.is_missing):
            return record
    raise AssertionError(f"{metric} missing for {year}")


def with_price(settings: EngineSettings, price: float,
               ticker: str = "SYNB") -> EngineSettings:
    """Inject a market price into the fixture snapshot.

    Prices are injected explicitly, never carried in the fixture, so one can
    never arrive by accident and quietly enable a market-implied case that the
    rights gate is supposed to be withholding.
    """
    import json

    path = settings.input_snapshots / f"{ticker}.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    document["marketContext"] = {
        "available": True, "reason": None, "asOfDate": "2026-07-31",
        "close": price, "currency": "IDR",
        "rightsStatus": "PRIVATE_RESEARCH_ONLY",
    }
    path.write_text(json.dumps(document), encoding="utf-8")
    return settings


def copy_fixture_in(settings: EngineSettings, repo_root) -> EngineSettings:
    shutil.copy2(
        repo_root / "engine/goh_dip_tong/fixtures/synthetic-bank/SYNB.json",
        settings.input_snapshots / "SYNB.json")
    return settings
