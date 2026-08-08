"""Engine paths and configuration.

Wraps Stage 1's :class:`Settings` rather than re-deriving the repository root,
so the engine and the pipeline can never disagree about where the data lives —
which is the sort of divergence that only shows up in CI at the worst moment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from pipeline.goh_dip_tong.settings import Settings as PipelineSettings
from pipeline.goh_dip_tong.settings import get_settings as get_pipeline_settings


@dataclass
class EngineSettings:
    """Everything the engine needs to find on disk."""

    pipeline: PipelineSettings = field(default_factory=get_pipeline_settings)

    # ---- roots -----------------------------------------------------------
    @property
    def repo_root(self) -> Path:
        return self.pipeline.repo_root

    @property
    def engine_root(self) -> Path:
        """The engine package itself.

        Resolved from this module's location rather than from ``repo_root``,
        because engine configuration and fixtures travel with the *code*, not
        with the data tree. A test pointing ``repo_root`` at a sandbox is
        redirecting where data is read and written; it is not asking for a
        different set of formulas.
        """
        return Path(__file__).resolve().parent

    @property
    def config_dir(self) -> Path:
        """Engine-owned configuration.

        Deliberately not under Stage 1's config tree: that is collection policy
        and is published to the site for the Stage 3 UI to read. Cost-of-capital
        assumptions are neither.
        """
        return self.engine_root / "config"

    @property
    def fixtures_dir(self) -> Path:
        """Engine test fixtures. **Never** an input to a published snapshot."""
        return self.engine_root / "fixtures"

    # ---- inputs ----------------------------------------------------------
    @property
    def input_snapshots(self) -> Path:
        """Stage 1's calculation-ready contract, one file per issuer."""
        return self.pipeline.research_snapshots / "sample"

    @property
    def facts_annual(self) -> Path:
        return self.pipeline.facts_annual

    @property
    def facts_quarterly(self) -> Path:
        return self.pipeline.facts_quarterly

    @property
    def restatements_file(self) -> Path:
        return self.pipeline.statements_restated / "restatements.jsonl"

    @property
    def macro_dir(self) -> Path:
        return self.pipeline.macro_dir

    # ---- outputs ---------------------------------------------------------
    @property
    def output_root(self) -> Path:
        return self.pipeline.research_snapshots

    @property
    def output_current(self) -> Path:
        """One pointer per issuer at the newest snapshot the engine wrote."""
        return self.output_root / "current"

    def output_snapshot(self, ticker: str, as_of: str, model_version: str) -> Path:
        """``research-snapshots/<TICKER>/<YYYY-MM-DD>/<model-version>.json``.

        Immutable once written: a given ticker, cutoff and model version always
        describes the same calculation, so re-running cannot rewrite history.
        """
        return self.output_root / ticker / as_of / f"{model_version}.json"

    @property
    def output_schema_file(self) -> Path:
        return self.pipeline.schema_dir / "research-snapshot.schema.json"

    # ---- loaders ---------------------------------------------------------
    def load_yaml(self, path: Path) -> dict:
        if not path.exists():
            raise FileNotFoundError(f"required engine config missing: {path}")
        with path.open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}

    def engine_config(self) -> dict:
        return self.load_yaml(self.config_dir / "engine.yml")

    def cost_of_capital(self) -> dict:
        return self.load_yaml(self.config_dir / "cost-of-capital.yml")

    def rel(self, path: Path) -> str:
        return self.pipeline.rel(path)


def get_engine_settings(pipeline: Optional[PipelineSettings] = None) -> EngineSettings:
    """Engine settings, optionally pinned to a specific pipeline tree.

    Tests pass a sandbox ``Settings`` here. There is no cache: a cached engine
    settings object would leak one test's sandbox into the next.
    """
    return EngineSettings(pipeline=pipeline or get_pipeline_settings())


__all__ = ["EngineSettings", "get_engine_settings"]
