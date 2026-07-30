"""Shared test fixtures.

Most tests run against a *copy* of the repository's config and data trees in a
temp directory, so a test can exercise the commit path without touching the
real generated artefacts.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from pipeline.goh_dip_tong.contracts.enums import CoverageStatus
from pipeline.goh_dip_tong.contracts.records import Constituent
from pipeline.goh_dip_tong.settings import Settings, find_repo_root

REPO_ROOT = find_repo_root()


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def real_settings() -> Settings:
    """Settings pointed at the actual repository. Read-only in tests."""
    return Settings(repo_root=REPO_ROOT)


@pytest.fixture
def sandbox(tmp_path) -> Settings:
    """A throwaway repo tree: real config, schemas, fixtures; empty data."""
    root = tmp_path / "repo"
    (root / "config").mkdir(parents=True)
    (root / "schemas").mkdir(parents=True)
    (root / "pipeline" / "goh_dip_tong" / "tests").mkdir(parents=True)
    (root / "docs").mkdir(parents=True)

    shutil.copytree(REPO_ROOT / "config" / "goh-dip-tong", root / "config" / "goh-dip-tong")
    shutil.copytree(REPO_ROOT / "schemas" / "goh-dip-tong", root / "schemas" / "goh-dip-tong")
    shutil.copytree(
        REPO_ROOT / "pipeline" / "goh_dip_tong" / "tests" / "fixtures",
        root / "pipeline" / "goh_dip_tong" / "tests" / "fixtures",
    )
    shutil.copytree(REPO_ROOT / "docs" / "goh-dip-tong", root / "docs" / "goh-dip-tong")

    # Start from a clean data tree so tests observe first-run behaviour.
    for sub in (
        "registry/current", "registry/history", "market-prices/daily",
        "market-prices/corporate-actions", "financial-statements/reported",
        "financial-statements/restated", "financial-statements/normalized",
        "financial-facts/annual", "financial-facts/quarterly", "financial-facts/trailing",
        "disclosures/metadata", "disclosures/manifests", "ownership", "dividends",
        "macro/ojk", "macro/bank-indonesia", "macro/bps", "events", "derived-metrics",
        "research-snapshots/sample", "quality/latest", "quality/history", "pipeline-runs",
    ):
        (root / "data" / "goh-dip-tong" / sub).mkdir(parents=True, exist_ok=True)

    # A sandbox has no generated config yet.
    for name in ("idx30.current.json", "idx30.history.jsonl", "companies.json",
                 "categories.json"):
        (root / "config" / "goh-dip-tong" / name).unlink(missing_ok=True)

    return Settings(repo_root=root)


@pytest.fixture(scope="session")
def idx30_h1() -> dict:
    path = REPO_ROOT / "pipeline/goh_dip_tong/tests/fixtures/idx30/2026H1.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def idx30_h2() -> dict:
    path = REPO_ROOT / "pipeline/goh_dip_tong/tests/fixtures/idx30/2026H2.json"
    return json.loads(path.read_text(encoding="utf-8"))


def make_constituent(ticker="BBCA", name="Bank Central Asia Tbk",
                     sector="FINANCIALS", industry="BANKS",
                     model="BANK", coverage=CoverageStatus.FINANCIALS,
                     entered_at="2026-02-02") -> Constituent:
    return Constituent(
        ticker=ticker, name=name,
        sector_code=sector, sector_name=sector.title(),
        industry_code=industry, industry_name=industry.title(),
        model_family=model, coverage_status=coverage,
        active=True, entered_at=entered_at, source_ref=f"test:{ticker}",
    )


@pytest.fixture
def constituent_factory():
    return make_constituent
