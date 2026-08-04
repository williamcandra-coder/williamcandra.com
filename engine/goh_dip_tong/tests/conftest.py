"""Shared engine-test fixtures.

Read-only assertions run against the real repository. Anything that writes runs
against a throwaway copy, so a test can exercise the publish path without
depositing a research snapshot in the working tree — which would then be
indistinguishable from one somebody meant to commit.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from engine.goh_dip_tong.settings import EngineSettings
from pipeline.goh_dip_tong.settings import Settings, find_repo_root

REPO_ROOT = find_repo_root()


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def real_engine() -> EngineSettings:
    """Engine settings on the real tree. Read-only in tests."""
    return EngineSettings(pipeline=Settings(repo_root=REPO_ROOT))


@pytest.fixture
def sandbox(tmp_path) -> EngineSettings:
    """A throwaway repo: real config, schemas and input snapshots; no output."""
    root = tmp_path / "repo"
    (root / "config").mkdir(parents=True)
    (root / "schemas").mkdir(parents=True)

    shutil.copytree(REPO_ROOT / "config" / "goh-dip-tong",
                    root / "config" / "goh-dip-tong")
    shutil.copytree(REPO_ROOT / "schemas" / "goh-dip-tong",
                    root / "schemas" / "goh-dip-tong")

    data = root / "data" / "goh-dip-tong"
    for sub in ("research-snapshots/sample", "research-snapshots/current",
                "financial-facts/annual", "financial-facts/quarterly",
                "financial-statements/restated", "macro"):
        (data / sub).mkdir(parents=True, exist_ok=True)

    source = REPO_ROOT / "data" / "goh-dip-tong"
    for relative in ("research-snapshots/sample", "financial-facts/annual",
                     "financial-facts/quarterly", "financial-statements/restated",
                     "macro"):
        origin = source / relative
        if origin.is_dir():
            shutil.copytree(origin, data / relative, dirs_exist_ok=True)

    # Engine config and fixtures resolve from the package, not from repo_root,
    # so nothing needs copying into the sandbox for them.
    return EngineSettings(pipeline=Settings(repo_root=root))


@pytest.fixture
def synthetic_bank(sandbox) -> EngineSettings:
    """A sandbox that also contains the synthetic bank fixture.

    Copied *into* the sandbox rather than read in place, so a test can never
    accidentally write next to the fixture itself.
    """
    fixture = REPO_ROOT / "engine/goh_dip_tong/fixtures/synthetic-bank/SYNB.json"
    shutil.copy2(fixture, sandbox.input_snapshots / "SYNB.json")
    return sandbox


@pytest.fixture(scope="session")
def bbca_snapshot() -> dict:
    path = REPO_ROOT / "data/goh-dip-tong/research-snapshots/sample/BBCA.json"
    return json.loads(path.read_text(encoding="utf-8"))
