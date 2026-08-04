"""Stage 2 is additive. Stage 1 must remain independently runnable.

The dependency direction is one-way by design: the engine imports the pipeline,
never the reverse. A back-edge would mean Stage 1's collectors could not run
without the engine present, and the two stages would have to be deployed and
versioned together for no reason.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest


def _imports(path: Path) -> set:
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


def _code_strings(path: Path) -> set:
    """String literals the code actually uses, excluding docstrings.

    Scanning raw text would flag a docstring that merely *names* a path —
    documentation explaining why the engine keeps its config out of Stage 1's
    config tree would fail a test about not writing there, which would train
    people to stop explaining things.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) and isinstance(
                    body[0].value, ast.Constant) and isinstance(
                    body[0].value.value, str):
                docstrings.add(id(body[0].value))
    return {
        node.value for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and id(node) not in docstrings
    }


def test_no_pipeline_module_imports_the_engine(repo_root):
    offenders = [
        str(path.relative_to(repo_root))
        for path in sorted((repo_root / "pipeline").rglob("*.py"))
        if any(name == "engine" or name.startswith("engine.")
               for name in _imports(path))
    ]
    assert offenders == [], offenders


def test_the_engine_does_import_the_pipeline(repo_root):
    """Confirms the edge exists in the direction it should, so the test above
    is asserting a real constraint rather than a vacuous one."""
    importers = [
        path for path in sorted((repo_root / "engine").rglob("*.py"))
        if any(name.startswith("pipeline") for name in _imports(path))
    ]
    assert importers


def test_the_engine_adds_no_new_dependency(repo_root):
    """Standard library plus what Stage 1 already installs. A new third-party
    import would change what CI has to provision."""
    declared = {"yaml", "jsonschema", "pytest", "requests"}
    allowed = set(sys.stdlib_module_names) | declared | {"pipeline", "engine"}
    unexpected = set()
    for path in sorted((repo_root / "engine").rglob("*.py")):
        for name in _imports(path):
            root = name.split(".")[0]
            if root and root not in allowed:
                unexpected.add(root)
    assert unexpected == set(), sorted(unexpected)


def test_the_engine_never_writes_outside_the_research_snapshot_tree(repo_root):
    """Every write goes through EngineSettings' output paths. A raw path
    literal pointing elsewhere in the tree would bypass the emission policy."""
    markers = ("config/goh-dip-tong", "data/goh-dip-tong/market-prices",
               "data/goh-dip-tong/registry", "data/goh-dip-tong/quality")
    offenders = []
    for path in sorted((repo_root / "engine").rglob("*.py")):
        if "tests" in path.parts:
            continue
        for literal in _code_strings(path):
            for marker in markers:
                if marker in literal:
                    offenders.append(f"{path.relative_to(repo_root)}: {literal!r}")
    assert offenders == [], offenders


def test_the_engine_does_not_touch_the_website_files(repo_root):
    markers = ("index.html", "goh-pok-tong.html", "_config.yml", "CNAME")
    offenders = []
    for path in sorted((repo_root / "engine").rglob("*.py")):
        if "tests" in path.parts:
            continue
        for literal in _code_strings(path):
            for marker in markers:
                if marker in literal:
                    offenders.append(f"{path.relative_to(repo_root)}: {literal!r}")
    assert offenders == [], offenders


@pytest.mark.parametrize("module", [
    "pipeline.goh_dip_tong.cli",
    "pipeline.goh_dip_tong.settings",
    "pipeline.goh_dip_tong.publishing.writers",
])
def test_stage_1_modules_import_without_the_engine_on_the_path(repo_root, module):
    result = subprocess.run(
        [sys.executable, "-c",
         f"import sys; sys.path.insert(0, '.'); import {module}"],
        cwd=repo_root, capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin"},
    )
    assert result.returncode == 0, result.stderr


def test_the_engine_reuses_stage_1_writers_rather_than_reimplementing_them(repo_root):
    """Determinism and no-change-no-write were solved once. A second
    implementation is a second place for the churn bug to come back."""
    text = (repo_root / "engine/goh_dip_tong/publishing/snapshot.py").read_text(
        encoding="utf-8")
    assert "from pipeline.goh_dip_tong.publishing.writers import" in text
    assert "stable_content_hash" in text
    assert "canonical_json" in text
