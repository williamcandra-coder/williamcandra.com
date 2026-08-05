"""Goh Dip Tong Stage 2 engine CLI.

    python3 -m engine.goh_dip_tong.cli <command> [options]

Commands:
    research-build   build research snapshots
    registry-hash    print the formula registry fingerprint
    engine-audit     show model families, their gates and their method policy

``--write-mode validate_only`` (the default) builds and validates everything
and writes nothing, matching Stage 1's convention. Exit codes match too:

    0  ran, validation passed
    1  validation failed, nothing was written
    2  usage or configuration error

Note what this CLI never does: it never constructs a
``ModelContext(allow_synthetic_cost_of_equity=True)``. That switch exists only
so the test harness can exercise valuation mathematics against the synthetic
bank fixture, and ``test_refusal.py`` asserts this file does not set it. A
published snapshot therefore cannot rest on an invented discount rate.
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from pipeline.goh_dip_tong.settings import utc_now_iso

from . import ENGINE_VERSION, MODEL_VERSION
from .common import arithmetic as _arithmetic  # noqa: F401  (registers formulas)
from .contracts.model import ModelContext
from .contracts.registry import REGISTRY
from .valuation.guards import load_guards
from .inputs import loader
from .models.registry import build_registry, model_for
from .publishing import snapshot as snapshot_mod
from .settings import EngineSettings, get_engine_settings

EXIT_OK, EXIT_VALIDATION_FAILED, EXIT_USAGE = 0, 1, 2


def _context(settings: EngineSettings, calculated_at: str) -> ModelContext:
    """Gate configuration for a production build.

    ``allow_synthetic_cost_of_equity`` is left at its default of False. It is
    not exposed as a flag: a command-line switch that turns invented
    assumptions into publishable output is a switch that will eventually be
    used by accident.
    """
    config = settings.engine_config()
    gates = config.get("gates") or {}
    terminal = config.get("terminal") or {}
    return ModelContext(
        models_config=settings.pipeline.models(),
        min_annual_periods=int(gates.get("min_annual_periods", 3)),
        max_input_age_days=gates.get("max_input_age_days"),
        cost_of_capital_config=settings.cost_of_capital(),
        scenario_config=settings.scenarios(),
        persistence=float(terminal.get("persistence", 0.6)),
        guards=load_guards(config),
        model_version=MODEL_VERSION,
        calculated_at=calculated_at,
    )


def cmd_research_build(args) -> int:
    settings = get_engine_settings()
    calculated_at = utc_now_iso()
    context = _context(settings, calculated_at)

    if args.all:
        tickers = loader.available_tickers(settings)
    elif args.ticker:
        tickers = [args.ticker.upper()]
    else:
        print("  FAIL specify --ticker <TICKER> or --all")
        return EXIT_USAGE

    if not tickers:
        print(f"  no input snapshots under {settings.rel(settings.input_snapshots)}")
        return EXIT_OK

    print(f"[research-build] engine {ENGINE_VERSION}, model {MODEL_VERSION}, "
          f"as-of {args.as_of or loader.today_utc()}, write-mode {args.write_mode}")

    failures = 0
    for ticker in tickers:
        failures += _build_one(settings, context, ticker, args, calculated_at)

    return EXIT_VALIDATION_FAILED if failures else EXIT_OK


def _build_one(settings, context, ticker: str, args, calculated_at: str) -> int:
    try:
        engine_input = loader.load(
            settings, ticker, as_of=args.as_of,
            model_version=MODEL_VERSION, calculated_at=calculated_at,
        )
    except loader.SnapshotMissing as exc:
        print(f"  SKIP {ticker}: {exc}")
        return 0
    except loader.InputError as exc:
        print(f"  FAIL {ticker}: {exc}")
        return 1

    model = model_for(context.models_config, engine_input.identity.get("modelFamily"))
    document = snapshot_mod.build(settings, engine_input, model, context, calculated_at)
    report = snapshot_mod.validate(settings, document)

    if not report.ok:
        for issue in report.critical_failures[:5]:
            print(f"  FAIL {ticker}: {issue.message}")
        return 1

    valuation = document["valuation"]
    summary = (
        f"  {ticker}  {document['researchStatus']:<24} "
        f"valuation={valuation['status']}"
    )
    if valuation["status"] == "REFUSED":
        summary += f" ({valuation['reason']}, {len(valuation['missingInputs'])} missing)"
    print(summary)
    if args.verbose:
        print(f"        mode={document['mode']}  facts={document['reported']['count']}  "
              f"contentHash={document['contentHash'][:16]}…")
        for gate in document["modelAudit"]["gates"]:
            if not gate["passed"]:
                print(f"        gate FAIL {gate['gate']}: {gate['detail']}")

    if args.write_mode == "commit":
        path, pointer, unchanged = snapshot_mod.write(settings, document)
        if unchanged:
            print("        unchanged: content matches the newest stored snapshot")
        else:
            print(f"        wrote: {settings.rel(path)}")
            print(f"        wrote: {settings.rel(pointer)}")
    return 0


def cmd_registry_hash(args) -> int:
    print(REGISTRY.registry_hash())
    if args.verbose:
        for formula_id in REGISTRY.ids():
            formula = REGISTRY.get(formula_id)
            print(f"  {formula_id:<20} ({', '.join(formula.inputs)}) -> "
                  f"{formula.output_metric}")
    return EXIT_OK


def cmd_engine_audit(args) -> int:
    settings = get_engine_settings()
    models_config = settings.pipeline.models()
    registry = build_registry(models_config)

    print(f"[engine-audit] engine {ENGINE_VERSION}, model {MODEL_VERSION}")
    print(f"  formulas registered: {len(REGISTRY)}")
    print(f"  registry hash:       {REGISTRY.registry_hash()}")
    print(f"  model families:      {len(registry)}")

    declared = models_config.get("model_families") or {}
    for family in sorted(registry):
        model = registry[family]
        supported = (declared.get(family) or {}).get("supported", False)
        print(f"    {family:<24} supported={str(supported):<5} "
              f"implemented={str(model.implemented):<5} "
              f"required={len(model.required_metrics)}")

    risk_free = settings.cost_of_capital().get("risk_free") or {}
    print(f"  risk-free validated: {risk_free.get('validated')}  "
          f"instrument={risk_free.get('instrument')}")
    implemented = sorted(f for f, m in registry.items() if m.implemented)
    print(f"  families with valuation mathematics: "
          f"{', '.join(implemented) if implemented else 'none'}")
    print("  a validated risk-free input is still required before any real "
          "issuer can be valued")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m engine.goh_dip_tong.cli",
        description="Goh Dip Tong Stage 2 deterministic research engine",
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--verbose", action="store_true")

    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("research-build", parents=[common],
                           help="build research snapshots")
    group = build.add_mutually_exclusive_group()
    group.add_argument("--ticker", help="a single IDX ticker")
    group.add_argument("--all", action="store_true",
                       help="every issuer with a Stage 1 input snapshot")
    build.add_argument("--as-of", dest="as_of", default=None,
                       help="point-in-time cutoff, YYYY-MM-DD (default: today, UTC)")
    build.add_argument("--write-mode", choices=["validate_only", "commit"],
                       default="validate_only")
    build.set_defaults(func=cmd_research_build)

    registry_hash = sub.add_parser("registry-hash", parents=[common],
                                   help="print the formula registry fingerprint")
    registry_hash.set_defaults(func=cmd_registry_hash)

    audit = sub.add_parser("engine-audit", parents=[common],
                           help="show families, gates and method policy")
    audit.set_defaults(func=cmd_engine_audit)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
