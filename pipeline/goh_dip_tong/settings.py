"""Paths and runtime settings.

Everything is derived from the repository root so the pipeline works the same
from a developer's shell, a test, and a GitHub Actions runner.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml


def find_repo_root(start: Optional[Path] = None) -> Path:
    """Walk up until we find the repository marker.

    Looks for `.git`, falling back to the known layout marker so the pipeline
    still resolves inside an exported tree with no VCS metadata.
    """
    here = (start or Path(__file__)).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / ".git").exists():
            return candidate
        if (candidate / "config" / "goh-dip-tong").is_dir() and (
            candidate / "pipeline" / "goh_dip_tong"
        ).is_dir():
            return candidate
    # pipeline/goh_dip_tong/settings.py -> repo root is two levels up
    return Path(__file__).resolve().parents[2]


def utc_now_iso() -> str:
    """Timestamps are always UTC with a trailing Z, never local time."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class Settings:
    repo_root: Path = field(default_factory=find_repo_root)

    def __post_init__(self) -> None:
        # Accept a str as well as a Path. Without this, a string root fails
        # later with an opaque "unsupported operand type(s) for /: 'str'".
        self.repo_root = Path(self.repo_root)

    # ---- roots -----------------------------------------------------------
    @property
    def config_dir(self) -> Path:
        return self.repo_root / "config" / "goh-dip-tong"

    @property
    def data_dir(self) -> Path:
        return self.repo_root / "data" / "goh-dip-tong"

    @property
    def schema_dir(self) -> Path:
        return self.repo_root / "schemas" / "goh-dip-tong"

    @property
    def docs_dir(self) -> Path:
        return self.repo_root / "docs" / "goh-dip-tong"

    @property
    def workflows_dir(self) -> Path:
        return self.repo_root / ".github" / "workflows"

    @property
    def private_dir(self) -> Path:
        """Never git-tracked. Holds anything a source's rights forbid committing."""
        return self.data_dir / "_private"

    # ---- config files ----------------------------------------------------
    @property
    def sources_file(self) -> Path:
        return self.config_dir / "sources.yml"

    @property
    def schedules_file(self) -> Path:
        return self.config_dir / "schedules.yml"

    @property
    def models_file(self) -> Path:
        return self.config_dir / "models.yml"

    @property
    def metrics_file(self) -> Path:
        return self.config_dir / "metrics.yml"

    @property
    def guard_file(self) -> Path:
        return self.config_dir / "guard.yml"

    # ---- generated artefacts --------------------------------------------
    @property
    def idx30_current(self) -> Path:
        return self.config_dir / "idx30.current.json"

    @property
    def idx30_history(self) -> Path:
        return self.config_dir / "idx30.history.jsonl"

    @property
    def companies_file(self) -> Path:
        return self.config_dir / "companies.json"

    @property
    def categories_file(self) -> Path:
        return self.config_dir / "categories.json"

    # ---- data-type partitions -------------------------------------------
    @property
    def registry_current(self) -> Path:
        return self.data_dir / "registry" / "current"

    @property
    def registry_history(self) -> Path:
        return self.data_dir / "registry" / "history"

    @property
    def market_prices_daily(self) -> Path:
        return self.data_dir / "market-prices" / "daily"

    @property
    def corporate_actions(self) -> Path:
        return self.data_dir / "market-prices" / "corporate-actions"

    @property
    def facts_annual(self) -> Path:
        return self.data_dir / "financial-facts" / "annual"

    @property
    def facts_quarterly(self) -> Path:
        return self.data_dir / "financial-facts" / "quarterly"

    @property
    def facts_trailing(self) -> Path:
        return self.data_dir / "financial-facts" / "trailing"

    @property
    def statements_reported(self) -> Path:
        return self.data_dir / "financial-statements" / "reported"

    @property
    def statements_restated(self) -> Path:
        return self.data_dir / "financial-statements" / "restated"

    @property
    def statements_normalized(self) -> Path:
        return self.data_dir / "financial-statements" / "normalized"

    @property
    def disclosures_metadata(self) -> Path:
        return self.data_dir / "disclosures" / "metadata"

    @property
    def disclosures_manifests(self) -> Path:
        return self.data_dir / "disclosures" / "manifests"

    @property
    def macro_dir(self) -> Path:
        return self.data_dir / "macro"

    @property
    def events_dir(self) -> Path:
        return self.data_dir / "events"

    @property
    def dividends_dir(self) -> Path:
        return self.data_dir / "dividends"

    @property
    def ownership_dir(self) -> Path:
        return self.data_dir / "ownership"

    @property
    def derived_metrics(self) -> Path:
        return self.data_dir / "derived-metrics"

    @property
    def research_snapshots(self) -> Path:
        return self.data_dir / "research-snapshots"

    @property
    def quality_latest(self) -> Path:
        return self.data_dir / "quality" / "latest"

    @property
    def quality_history(self) -> Path:
        return self.data_dir / "quality" / "history"

    @property
    def pipeline_runs(self) -> Path:
        return self.data_dir / "pipeline-runs"

    @property
    def fixtures_dir(self) -> Path:
        return self.repo_root / "pipeline" / "goh_dip_tong" / "tests" / "fixtures"

    # ---- loaders ---------------------------------------------------------

    def load_yaml(self, path: Path) -> dict:
        if not path.exists():
            raise FileNotFoundError(f"required config file missing: {path}")
        with path.open("r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}

    def sources(self) -> dict:
        return self.load_yaml(self.sources_file)

    def schedules(self) -> dict:
        return self.load_yaml(self.schedules_file)

    def models(self) -> dict:
        return self.load_yaml(self.models_file)

    def metrics(self) -> dict:
        return self.load_yaml(self.metrics_file)

    def guard(self) -> dict:
        return self.load_yaml(self.guard_file)

    def rel(self, path: Path) -> str:
        """Repo-relative POSIX path, for stable messages and reports."""
        try:
            return str(Path(path).resolve().relative_to(self.repo_root).as_posix())
        except ValueError:
            return str(path)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    root = os.environ.get("GDT_REPO_ROOT")
    return Settings(repo_root=Path(root).resolve()) if root else Settings()
