"""Stage 1 tests: the workflows match schedules.yml, keep least privilege, and
cannot push to the default branch.
"""

from __future__ import annotations

import re

import pytest
import yaml

#: Workflows that may produce generated changes and open a pull request.
COMMITTING_WORKFLOWS = [
    "gdt-registry-update",
    "gdt-historical-backfill",
    "gdt-daily-update",
    "gdt-disclosure-watch",
    "gdt-financial-update",
    "gdt-macro-update",
]

#: Workflows that must never write to the repository at all.
READ_ONLY_WORKFLOWS = [
    "gdt-data-quality",
    "gdt-source-connectivity-smoke",
    "gdt-bi-discovery",
]

WORKFLOW_NAMES = COMMITTING_WORKFLOWS + READ_ONLY_WORKFLOWS


def load(path):
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    # PyYAML reads the `on:` key as the boolean True under YAML 1.1.
    document["on"] = document.get("on", document.get(True))
    return document


@pytest.fixture(scope="module")
def workflows(request):
    from pipeline.goh_dip_tong.settings import find_repo_root

    root = find_repo_root()
    return {name: load(root / ".github" / "workflows" / f"{name}.yml")
            for name in WORKFLOW_NAMES}


@pytest.fixture(scope="module")
def schedules(request):
    from pipeline.goh_dip_tong.settings import Settings, find_repo_root

    return Settings(repo_root=find_repo_root()).schedules()


# --- existence and triggers ------------------------------------------------


def test_all_declared_workflows_exist(real_settings):
    for name in WORKFLOW_NAMES:
        assert (real_settings.workflows_dir / f"{name}.yml").exists(), name
    # Nothing may sit in the workflows directory undeclared and therefore untested.
    on_disk = sorted(p.stem for p in real_settings.workflows_dir.glob("gdt-*.yml"))
    assert on_disk == sorted(WORKFLOW_NAMES)


def test_every_workflow_supports_manual_dispatch(workflows):
    """Spec section 1.14: start all workflows with workflow_dispatch."""
    for name, document in workflows.items():
        assert "workflow_dispatch" in document["on"], name


def test_backfill_has_no_schedule(workflows):
    """Backfill is expensive and correction-sensitive: manual only."""
    assert "schedule" not in workflows["gdt-historical-backfill"]["on"]


def test_backfill_accepts_the_required_inputs(workflows):
    inputs = workflows["gdt-historical-backfill"]["on"]["workflow_dispatch"]["inputs"]
    for required in ("scope", "ticker", "data_type", "start_year", "end_year",
                     "provider", "write_mode"):
        assert required in inputs, required
    assert inputs["scope"]["options"] == ["all", "ticker", "data_type"]
    assert inputs["write_mode"]["options"] == ["validate_only", "commit"]
    assert inputs["write_mode"]["default"] == "validate_only"


def test_data_quality_runs_on_pull_requests(workflows):
    assert "pull_request" in workflows["gdt-data-quality"]["on"]


# --- schedules.yml is the single source of truth ---------------------------


def test_cron_matches_schedules_yml(workflows, schedules):
    for name, declared in schedules["workflows"].items():
        document = workflows[name]
        expected = declared["cron"]
        schedule = document["on"].get("schedule")
        if expected is None:
            assert schedule is None, f"{name} must not have a schedule"
            continue
        assert schedule is not None, f"{name} is missing its schedule"
        assert [entry["cron"] for entry in schedule] == [expected], name


def test_schedules_yml_lists_every_workflow(schedules):
    assert sorted(schedules["workflows"]) == sorted(WORKFLOW_NAMES)


def test_declared_workflow_files_exist(schedules, repo_root):
    for name, declared in schedules["workflows"].items():
        assert (repo_root / declared["file"]).exists(), name


def test_cron_expressions_are_well_formed(schedules):
    for name, declared in schedules["workflows"].items():
        cron = declared["cron"]
        if cron is None:
            continue
        fields = cron.split()
        assert len(fields) == 5, f"{name}: {cron!r} is not a 5-field cron"


def test_scheduled_runs_avoid_the_top_of_the_hour(schedules):
    """GitHub's scheduler is congested at :00; an off-hour minute runs sooner."""
    for name, declared in schedules["workflows"].items():
        cron = declared["cron"]
        if cron is None:
            continue
        assert cron.split()[0] != "0", f"{name} is scheduled on the hour"


# --- commit policy and least privilege -------------------------------------


def test_top_level_permissions_are_read_only(workflows):
    for name, document in workflows.items():
        assert document["permissions"] == {"contents": "read"}, name


def test_only_pr_opening_jobs_get_write_access(workflows):
    for name, document in workflows.items():
        for job_name, job in document["jobs"].items():
            permissions = job.get("permissions")
            if permissions is None:
                continue
            assert set(permissions) <= {"contents", "pull-requests"}, f"{name}.{job_name}"
            assert permissions.get("contents") in (None, "read", "write")
            # No workflow may be granted anything beyond what a PR needs.
            assert "packages" not in permissions
            assert "id-token" not in permissions
            assert "actions" not in permissions


def test_data_quality_has_no_write_permission(workflows):
    """The audit must never be able to modify the repository."""
    for job in workflows["gdt-data-quality"]["jobs"].values():
        assert job.get("permissions") is None
    assert workflows["gdt-data-quality"]["permissions"] == {"contents": "read"}


def test_no_workflow_pushes_to_the_default_branch(workflows, repo_root):
    """Every generated change must go through a branch and a pull request."""
    for name in WORKFLOW_NAMES:
        text = (repo_root / ".github" / "workflows" / f"{name}.yml").read_text(encoding="utf-8")
        for forbidden in ("git push origin main", "git push origin HEAD:main",
                          "--force", "push -f"):
            assert forbidden not in text, f"{name} contains {forbidden!r}"
        if "git push" in text:
            assert 'git push -u origin "$BRANCH"' in text, name
            assert "gh pr create" in text, f"{name} pushes without opening a PR"


def test_generated_commits_are_restricted_to_generated_paths(workflows, repo_root):
    for name in WORKFLOW_NAMES:
        text = (repo_root / ".github" / "workflows" / f"{name}.yml").read_text(encoding="utf-8")
        if "git commit" not in text:
            continue
        assert "git add config/goh-dip-tong data/goh-dip-tong" in text, name
        assert "git add -A\n" not in text, f"{name} stages everything"


def test_commit_messages_follow_the_convention(repo_root):
    """data(gdt): update <data-type> through <date>"""
    pattern = re.compile(r'git commit -m "data\(gdt\): \S+ [^"]*through \$\(date')
    for name in WORKFLOW_NAMES:
        text = (repo_root / ".github" / "workflows" / f"{name}.yml").read_text(encoding="utf-8")
        if "git commit" not in text:
            continue
        assert pattern.search(text), f"{name} has a non-conforming commit message"


def test_branch_prefixes_match_schedules_yml(schedules, repo_root):
    for name, declared in schedules["workflows"].items():
        prefix = declared["branch_prefix"]
        if prefix is None:
            continue
        text = (repo_root / ".github" / "workflows" / f"{name}.yml").read_text(encoding="utf-8")
        assert f'BRANCH="{prefix}-' in text, name


def test_no_change_means_no_commit(workflows, repo_root):
    """A workflow must exit successfully without committing when nothing changed."""
    for name, declared in _committing(workflows):
        text = (repo_root / ".github" / "workflows" / f"{name}.yml").read_text(encoding="utf-8")
        assert "git diff --quiet" in text, f"{name} does not check for changes"
        assert "steps.diff.outputs.changed == 'true'" in text, name


def _committing(workflows):
    return [(name, doc) for name, doc in workflows.items() if name in COMMITTING_WORKFLOWS]


# --- safety gate -----------------------------------------------------------


def test_scheduled_runs_are_gated_behind_a_repository_variable(workflows, schedules):
    """Schedules exist but do nothing until deliberately switched on."""
    variable = schedules["schedules_enabled_variable"]
    for name, document in workflows.items():
        if "schedule" not in document["on"] or name == "gdt-data-quality":
            continue
        for job_name, job in document["jobs"].items():
            condition = job.get("if", "")
            assert f"vars.{variable} == 'true'" in condition, f"{name}.{job_name}"
            assert "github.event_name != 'schedule'" in condition, f"{name}.{job_name}"


def test_the_schedule_gate_is_off_by_default(repo_root):
    """Nothing in the repository sets GDT_SCHEDULES_ENABLED."""
    for path in (repo_root / ".github" / "workflows").glob("*.yml"):
        text = path.read_text(encoding="utf-8")
        assert "GDT_SCHEDULES_ENABLED: " not in text
        assert "GDT_SCHEDULES_ENABLED=true" not in text


# --- no secrets ------------------------------------------------------------


def test_no_workflow_references_a_repository_secret(repo_root):
    """Stage 1 has no authenticated source, so nothing should need a secret.
    github.token is the automatic per-run token, not a stored credential."""
    for path in (repo_root / ".github" / "workflows").glob("*.yml"):
        text = path.read_text(encoding="utf-8")
        for match in re.findall(r"secrets\.\w+", text):
            assert match == "secrets.GITHUB_TOKEN", f"{path.name} uses {match}"


def test_no_secret_shaped_strings_in_config_or_workflows(repo_root):
    from pipeline.goh_dip_tong.settings import Settings
    from pipeline.goh_dip_tong.validation.repo_guard import RepoGuard

    settings = Settings(repo_root=repo_root)
    guard = RepoGuard(settings)
    paths = list((repo_root / ".github" / "workflows").glob("*.yml"))
    paths += list((repo_root / "config" / "goh-dip-tong").glob("*"))
    report = guard.check_secrets([p for p in paths if p.is_file()])
    assert report.ok, [i.message for i in report.critical_failures]


# --- workflows install what they need --------------------------------------


INSTALL = "pip install --quiet -r pipeline/goh_dip_tong/requirements.txt"


def test_every_workflow_installs_the_pipeline_requirements(repo_root):
    """A workflow that runs pipeline code must install the pipeline's
    dependencies. Stated both ways, so the guard cannot be satisfied by simply
    dropping the install: a workflow without it must also not import the
    pipeline, and is therefore restricted to the standard library."""
    for name in WORKFLOW_NAMES:
        text = (repo_root / ".github" / "workflows" / f"{name}.yml").read_text(encoding="utf-8")
        runs_pipeline = "pipeline.goh_dip_tong" in text
        if runs_pipeline:
            assert INSTALL in text, f"{name} runs pipeline code without installing it"
        else:
            assert INSTALL not in text, f"{name} installs dependencies it never uses"


def test_committing_workflows_run_the_repo_guard(repo_root):
    for name in COMMITTING_WORKFLOWS + ["gdt-data-quality"]:
        text = (repo_root / ".github" / "workflows" / f"{name}.yml").read_text(encoding="utf-8")
        assert "cli repo-guard" in text, f"{name} does not run the repository guard"


# --- the data-quality gate runs everything ---------------------------------


def test_data_quality_runs_unit_tests_acceptance_and_guard(repo_root):
    """All five gates must stay wired in; dropping one silently would leave
    the build green while the checks it covers stopped running."""
    text = (repo_root / ".github/workflows/gdt-data-quality.yml").read_text(encoding="utf-8")
    assert "python -m pytest pipeline/goh_dip_tong/tests -q" in text
    assert "./pipeline/goh_dip_tong/tests/acceptance.sh" in text
    assert "cli repo-guard" in text
    # Stage 2. The engine tests live outside pipeline/, so the path above does
    # not collect them — an engine regression would otherwise never fail CI.
    assert "python -m pytest engine/goh_dip_tong/tests -q" in text
    assert "./engine/goh_dip_tong/tests/acceptance_stage2.sh" in text


def test_data_quality_runs_on_engine_pull_requests(workflows):
    """A pull request that only touches engine/ must still be gated."""
    triggers = workflows["gdt-data-quality"].get("on", workflows["gdt-data-quality"].get(True))
    assert "engine/**" in triggers["pull_request"]["paths"]


def test_the_stage_2_acceptance_script_exists_and_is_executable(repo_root):
    import os

    path = repo_root / "engine/goh_dip_tong/tests/acceptance_stage2.sh"
    assert path.exists(), "acceptance_stage2.sh is missing"
    assert os.access(path, os.X_OK), "acceptance_stage2.sh is not executable"


def test_the_stage_2_acceptance_script_is_repo_relative_and_sandboxed(repo_root):
    """Same isolation contract as Stage 1's, for the same reason: it runs on
    every pull request and must not move the repository."""
    text = (repo_root / "engine/goh_dip_tong/tests/acceptance_stage2.sh").read_text(
        encoding="utf-8")
    assert "/home/user/" not in text, "hard-coded developer path"
    assert 'REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"' in text
    assert "mktemp -d" in text, "destructive work is not sandboxed"
    assert "trap 'rm -rf \"$WORK\"' EXIT" in text, "sandbox is not cleaned up"
    assert "REPO_DATA_BEFORE" in text and "REPO_DATA_AFTER" in text


# --- Stage 3: the UI suite runs in the same gate ----------------------------
#
# The UI is the first thing in this repository a visitor sees, and until now it
# was the only stage whose tests nobody ran automatically. These assertions pin
# the step in place — that it exists, that it sits between the Stage 2
# acceptance script and the audit, and that wiring it in did not quietly turn a
# read-only auditor into something that installs packages or writes to the
# repository.

STAGE_3_UI_COMMAND = "node --test tests/goh-dip-tong-ui.test.js"


@pytest.fixture(scope="module")
def quality_text(repo_root):
    return (repo_root / ".github/workflows/gdt-data-quality.yml").read_text(encoding="utf-8")


def test_the_stage_3_ui_test_suite_exists(repo_root):
    path = repo_root / "tests/goh-dip-tong-ui.test.js"
    assert path.exists(), "tests/goh-dip-tong-ui.test.js is missing"
    assert path.stat().st_size > 0


def test_data_quality_runs_the_stage_3_ui_suite(quality_text):
    """Sixth gate. The UI tests live outside pipeline/ and engine/, so neither
    pytest path collects them — without this step a UI regression would never
    fail CI."""
    assert STAGE_3_UI_COMMAND in quality_text
    assert "Stage 3 UI test suite" in quality_text


def test_the_stage_3_ui_step_runs_after_stage_2_acceptance(quality_text):
    """Order is the contract: the cheap data gates run first, so a broken
    engine fails before anything spends time in a browser."""
    stage_2 = quality_text.index("./engine/goh_dip_tong/tests/acceptance_stage2.sh")
    stage_3 = quality_text.index(STAGE_3_UI_COMMAND)
    assert stage_2 < stage_3, "the Stage 3 UI step runs before Stage 2 acceptance"


def test_the_stage_3_ui_step_runs_before_the_data_quality_audit(quality_text):
    stage_3 = quality_text.index(STAGE_3_UI_COMMAND)
    audit = quality_text.index("cli quality --verbose")
    assert stage_3 < audit, "the Stage 3 UI step runs after the data-quality audit"


def test_the_quality_checkout_fetches_enough_history_for_the_ui_suite(workflows):
    """The UI suite proves the protected files are untouched by diffing against
    origin/main. A default shallow checkout fetches only the commit under test
    and creates no origin/main ref, so that check cannot resolve a base and
    fails for a reason that has nothing to do with the UI. Depth 0 brings the
    remote branches with it."""
    steps = workflows["gdt-data-quality"]["jobs"]["quality"]["steps"]
    checkout = next(s for s in steps if str(s.get("uses", "")).startswith("actions/checkout"))
    assert checkout.get("with", {}).get("fetch-depth") == 0, (
        "the quality checkout is shallow; the UI suite's protected-file diff "
        "has no origin/main to compare against"
    )


def test_a_deeper_checkout_did_not_grant_the_quality_job_any_write_access(workflows):
    """Fetching more history is a read. It must not have come with anything
    else: no explicit token and no deploy key handed to the checkout, and no
    repository the job was not already reading. What the checkout can do is
    still bounded by the job's `contents: read` permission, asserted above."""
    steps = workflows["gdt-data-quality"]["jobs"]["quality"]["steps"]
    checkout = next(s for s in steps if str(s.get("uses", "")).startswith("actions/checkout"))
    options = checkout.get("with", {})
    assert "token" not in options, "the checkout was handed an explicit token"
    assert "ssh-key" not in options, "the checkout was handed a deploy key"
    assert "repository" not in options, "the checkout reaches outside this repository"
    assert set(options) == {"fetch-depth"}, f"unexpected checkout options: {sorted(options)}"


# --- the browser layer must actually run on the clean runner -----------------
#
# The first CI run of the UI suite reported success while skipping 29 of its 55
# tests, because no browser was found and the suite treated that as a reason to
# skip rather than a reason to fail. A green tick that means "half the suite did
# not run" is worse than a red one. These assertions close that hole from both
# ends: the workflow must hand the suite a browser, and the suite must refuse to
# skip when it is running in CI.

UI_TEST_RELPATH = "tests/goh-dip-tong-ui.test.js"

#: A pattern no test name contains, so node loads the file — running the
#: module-level browser resolution under test — without spending six minutes
#: driving a browser.
NO_TESTS = "zzz-no-such-test-name-zzz"


@pytest.fixture(scope="module")
def ui_test_source(repo_root):
    return (repo_root / UI_TEST_RELPATH).read_text(encoding="utf-8")


def _run_ui_suite(repo_root, env_overrides):
    """Load the UI suite with no test selected and return (exit code, output).

    Only the module-level browser resolution runs, which is the behaviour under
    test here. node --test runs the file in a child process and folds its
    stderr into the TAP stream as `#` diagnostics, so the two streams are
    merged rather than inspected separately."""
    import os
    import subprocess

    env = dict(os.environ)
    env.pop("CI", None)
    env.pop("GDT_CHROMIUM_PATH", None)
    env.update({k: v for k, v in env_overrides.items() if v is not None})
    done = subprocess.run(
        ["node", "--test", "--test-name-pattern", NO_TESTS, UI_TEST_RELPATH],
        cwd=repo_root, env=env, capture_output=True, text=True, timeout=120,
    )
    return done.returncode, done.stdout + done.stderr


def test_the_quality_workflow_exports_gdt_chromium_path(quality_text):
    """The workflow, not the test file, decides which of the runner's browsers
    is used, and publishes that decision through the environment."""
    assert 'echo "GDT_CHROMIUM_PATH=$resolved" >> "$GITHUB_ENV"' in quality_text
    locate = quality_text.index("Locate a browser for the Stage 3 UI tests")
    suite = quality_text.index(STAGE_3_UI_COMMAND)
    assert locate < suite, "the browser is located after the suite that needs it"


def test_the_workflow_looks_for_every_supported_browser_command(quality_text):
    for candidate in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        assert candidate in quality_text, f"the workflow never looks for {candidate}"


def test_the_workflow_fails_rather_than_continuing_without_a_browser(quality_text):
    """`exit 1` under an ::error:: annotation, not a warning and not a skip."""
    locate = quality_text.index("Locate a browser for the Stage 3 UI tests")
    step = quality_text[locate:quality_text.index(STAGE_3_UI_COMMAND)]
    assert "::error::" in step, "a missing browser is not reported as an error"
    assert "exit 1" in step, "the workflow continues when no browser is found"
    assert "::warning::" not in step
    assert "continue-on-error" not in step


def test_no_browser_or_package_installation_was_introduced(quality_text):
    """Requirement 4 and 5: use what the runner already has. Downloading a
    browser would make this workflow depend on a third-party endpoint being up
    in order to report on data that is already committed."""
    forbidden = (
        "npm install", "npm ci", "npx ", "yarn", "pnpm", "bun install", "corepack",
        "playwright", "puppeteer", "browser-actions/setup-chrome",
        "apt-get install", "apt install", "snap install", "wget ", "curl ",
        "setup-node", "actions/setup-node",
    )
    for command in forbidden:
        assert command.lower() not in quality_text.lower(), \
            f"the workflow installs or downloads something: {command!r}"


def test_the_ui_suite_prefers_gdt_chromium_path_over_anything_it_could_detect(repo_root):
    """Behavioural, not a source grep: point the variable at a real file that is
    not a browser and check the suite reports that file. If detection won, it
    would report this container's Playwright build instead."""
    import sys

    code, output = _run_ui_suite(repo_root, {"GDT_CHROMIUM_PATH": sys.executable})
    assert code == 0, output
    assert f"Stage 3 browser: {sys.executable}" in output, output


def test_the_ui_suite_fails_when_gdt_chromium_path_cannot_be_resolved(repo_root):
    """A variable pointing at nothing is a broken CI configuration, not a
    licence to fall back to detection and quietly test something else."""
    code, output = _run_ui_suite(
        repo_root, {"CI": "true", "GDT_CHROMIUM_PATH": "/nonexistent/chrome"})
    assert code != 0, "an unresolvable GDT_CHROMIUM_PATH was tolerated"
    assert "/nonexistent/chrome" in output
    assert "does not exist" in output


def test_the_browser_layer_cannot_silently_skip_when_ci_is_true(repo_root, ui_test_source):
    """Two halves of the same guarantee. The skip flag is gated on CI in the
    source, and the one unresolvable case that can be constructed on a machine
    that does have a browser exits non-zero under CI=true instead of skipping."""
    assert "const BROWSER_ENFORCED = Boolean(CHROME) || IN_CI;" in ui_test_source
    assert "skip: !BROWSER_ENFORCED" in ui_test_source
    assert 'IN_CI = process.env.CI === "true"' in ui_test_source \
        or "IN_CI = process.env.CI === 'true'" in ui_test_source

    code, output = _run_ui_suite(
        repo_root, {"CI": "true", "GDT_CHROMIUM_PATH": "/nonexistent/chrome"})
    assert code != 0
    assert "# skipped 0" in output, "the suite skipped something instead of failing"


def test_the_ui_suite_may_still_skip_locally_when_no_browser_exists(ui_test_source):
    """Requirement 8. A contributor with no Chrome installed still gets the
    static and pure-logic layers rather than a wall of red."""
    assert "because CI is not set" in ui_test_source
    assert "console.error(`WARNING: no Chromium or Chrome found" in ui_test_source


def test_the_ui_suite_reports_which_browser_it_used(repo_root):
    """So the CI log records the binary instead of leaving it to be inferred."""
    code, output = _run_ui_suite(repo_root, {})
    assert code == 0, output
    assert re.search(r"Stage 3 browser: \S+ \| layer: (enforced|skipped)", output), output


def test_the_ui_suite_downloads_no_browser_and_imports_no_package(ui_test_source):
    """Checked against what the file *does*, not what its prose mentions: every
    require() is a Node builtin, and nothing reaches the network."""
    required = set(re.findall(r"require\(['\"]([^'\"]+)['\"]\)", ui_test_source))
    external = {name for name in required
                if not name.startswith("node:") and not name.startswith(".")}
    assert external == set(), f"the UI suite imports non-builtin modules: {sorted(external)}"

    for forbidden in ("https.get", "http.get", "XMLHttpRequest",
                      "npm install", "npx ", "curl ", "wget "):
        assert forbidden not in ui_test_source, f"the UI suite uses {forbidden!r}"

    # child_process is a builtin, and it is used to launch a browser that is
    # already installed. Every launch is accounted for: CHROME is the resolved
    # binary, `run`/`git` is the protected-file diff, and `sh` exists only to
    # give `command -v` the shell builtin it needs. Nothing fetches anything.
    # `run` is the file's local alias for execFileSync, so both spellings count.
    launched = {name for _, name in
                re.findall(r"\b(?:execFileSync|run)\(\s*(['\"]?)([\w.:/-]+)\1",
                           ui_test_source)}
    assert launched == {"CHROME", "sh", "git"}, \
        f"unexpected subprocess targets: {sorted(launched)}"


def test_the_quality_workflow_installs_no_javascript_packages(quality_text):
    """Node's built-in test runner needs nothing installed. A package manager
    appearing here would add a network dependency and a lockfile-shaped supply
    chain to a workflow whose whole job is to audit what is already committed."""
    for command in ("npm install", "npm ci", "npm i ", "yarn", "pnpm",
                    "npx ", "bun install", "corepack"):
        assert command not in quality_text, f"the workflow runs {command!r}"
    assert "package.json" not in quality_text


def test_the_repository_still_has_no_package_manifest(repo_root):
    for manifest in ("package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"):
        assert not (repo_root / manifest).exists(), f"{manifest} was introduced"


def test_the_quality_workflow_remains_read_only(workflows, quality_text):
    document = workflows["gdt-data-quality"]
    assert document["permissions"] == {"contents": "read"}
    for job in document["jobs"].values():
        assert "permissions" not in job or job["permissions"] == {"contents": "read"}
    assert "GITHUB_TOKEN" not in quality_text


def test_the_quality_workflow_cannot_commit_push_merge_or_open_a_pr(quality_text):
    forbidden = ("git commit", "git push", "git merge", "git tag",
                 "gh pr create", "gh pr merge", "peter-evans/create-pull-request",
                 "stefanzweifel/git-auto-commit-action", "actions/github-script")
    for command in forbidden:
        assert command not in quality_text, f"the read-only workflow runs {command!r}"


def test_wiring_the_ui_suite_changed_no_trigger_or_schedule(workflows):
    """The step was added inside the existing job. Nothing about when this
    workflow runs may have moved."""
    triggers = workflows["gdt-data-quality"]["on"]
    assert set(triggers) == {"workflow_dispatch", "pull_request", "schedule"}
    assert triggers["schedule"] == [{"cron": "5 6 * * *"}]
    assert triggers["workflow_dispatch"] is None
    assert triggers["pull_request"]["paths"] == [
        "pipeline/**", "engine/**", "config/goh-dip-tong/**",
        "data/goh-dip-tong/**", "schemas/goh-dip-tong/**", ".github/workflows/gdt-*.yml",
    ]


def test_no_new_workflow_file_was_introduced(repo_root):
    present = sorted(p.stem for p in (repo_root / ".github/workflows").glob("*.yml"))
    assert present == sorted(WORKFLOW_NAMES)


def test_acceptance_script_exists_and_is_executable(repo_root):
    import os

    path = repo_root / "pipeline/goh_dip_tong/tests/acceptance.sh"
    assert path.exists(), "acceptance.sh is missing"
    assert os.access(path, os.X_OK), "acceptance.sh is not executable"


def test_acceptance_script_is_repo_relative_and_sandboxed(repo_root):
    """It must work from any checkout, and must never write to the repository."""
    text = (repo_root / "pipeline/goh_dip_tong/tests/acceptance.sh").read_text(encoding="utf-8")
    assert "/home/user/" not in text, "hard-coded developer path"
    assert 'REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"' in text
    assert "mktemp -d" in text, "destructive work is not sandboxed"
    assert "trap 'rm -rf \"$WORK\"' EXIT" in text, "sandbox is not cleaned up"
    # The isolation self-check is what actually enforces the promise.
    assert "REPO_TREE_BEFORE" in text and "REPO_TREE_AFTER" in text


# --- gdt-source-connectivity-smoke: manual-only, read-only, cannot commit ---


CONNECTIVITY = "gdt-source-connectivity-smoke"


@pytest.fixture(scope="module")
def connectivity_text(request):
    from pipeline.goh_dip_tong.settings import find_repo_root

    return (find_repo_root() / ".github/workflows" / f"{CONNECTIVITY}.yml").read_text(
        encoding="utf-8")


def test_connectivity_smoke_is_manual_only(workflows):
    """No schedule key at all — it must never probe third-party hosts unattended."""
    document = workflows[CONNECTIVITY]
    assert "workflow_dispatch" in document["on"]
    assert "schedule" not in document["on"], "connectivity probe must not be scheduled"
    assert "push" not in document["on"]
    assert "pull_request" not in document["on"]
    assert list(document["on"]) == ["workflow_dispatch"]


def test_connectivity_smoke_is_read_only(workflows):
    document = workflows[CONNECTIVITY]
    assert document["permissions"] == {"contents": "read"}
    for job_name, job in document["jobs"].items():
        assert job.get("permissions") is None, f"{job_name} requests extra permissions"


def test_connectivity_smoke_cannot_commit_push_or_open_a_pr(connectivity_text):
    for forbidden in ("git commit", "git push", "gh pr create", "git merge",
                      "git add", "peter-evans/create-pull-request"):
        assert forbidden not in connectivity_text, f"contains {forbidden!r}"


def test_connectivity_smoke_does_not_touch_data_or_config(connectivity_text):
    """Its report goes to RUNNER_TEMP, outside the working tree."""
    assert "RUNNER_TEMP" in connectivity_text or "runner.temp" in connectivity_text
    assert "--output \"${RUNNER_TEMP}/connectivity-report.json\"" in connectivity_text
    # It must not write anywhere under the generated trees.
    assert "--output config/" not in connectivity_text
    assert "--output data/" not in connectivity_text


def test_connectivity_smoke_asserts_a_clean_tree_and_no_activation(connectivity_text):
    assert "git diff --quiet" in connectivity_text
    assert "git status --porcelain --untracked-files=all" in connectivity_text
    assert "live providers are enabled" in connectivity_text


def test_connectivity_smoke_uploads_an_artifact(connectivity_text):
    assert "actions/upload-artifact@v4" in connectivity_text
    assert "gdt-source-connectivity-report" in connectivity_text


def test_connectivity_smoke_declares_the_full_outcome_vocabulary(connectivity_text):
    from pipeline.goh_dip_tong.validation.connectivity import OUTCOMES

    for outcome in OUTCOMES:
        assert outcome in connectivity_text, f"{outcome} not documented in the workflow"


def test_connectivity_smoke_states_that_200_enables_nothing(connectivity_text):
    lowered = connectivity_text.lower()
    assert "http 200 means a socket opened" in lowered
    assert "does not enable any provider" in lowered


def test_connectivity_smoke_does_not_enable_providers_or_schedules(connectivity_text):
    assert "GDT_SCHEDULES_ENABLED" not in connectivity_text
    assert "enabled: true" not in connectivity_text


def test_connectivity_smoke_is_registered_in_schedules_yml(schedules):
    declared = schedules["workflows"][CONNECTIVITY]
    assert declared["cron"] is None
    assert declared["commit_policy"] == "never"
    assert declared["branch_prefix"] is None
