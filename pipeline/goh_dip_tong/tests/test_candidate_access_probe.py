"""The candidate-access probe must measure a source without becoming one.

Recovery step 1 asks one question — can a GitHub Actions runner reach BCA's
official Investor Relations pages, and what shape are the report links there? —
and the value of the answer depends entirely on the probe having no side
effects. It must not enable a provider, must not change a rights status, must
not commit anything, must not download a report file, and must not let the one
page it reads escape memory.

Three kinds of check, because none alone is sufficient:

* **Configuration** — the workflow is still manual-only and read-only, has no
  commit step and no write permission.
* **Behavioural** — the embedded script is imported and run against a fixture
  page containing markup, scripts, comments and hostile links. Whatever comes
  out is inspected for any trace of that markup, and for any off-host or
  plain-http URL that survived.
* **Structural** — the source is parsed and asserted against: exactly one
  bounded ``.read()``, in ``fetch_html``; nothing that writes a file except the
  JSON report; no request function that could fetch a discovered file's body.
  This catches a leak added later through a path the fixture does not exercise.

Nothing here performs network I/O. The script's request functions are never
called.
"""

from __future__ import annotations

import ast
import importlib.util
import json

import pytest
import yaml


WORKFLOW = ".github/workflows/gdt-source-connectivity-smoke.yml"

#: The two official BCA URLs this step exists to measure.
BCA_IR = "https://www.bca.co.id/en/Tentang-BCA/Hubungan-Investor"
BCA_REPORTS = ("https://www.bca.co.id/en/tentang-bca/Hubungan-Investor/"
               "laporan-presentasi/Laporan-Keuangan")

#: A page shaped like a real IR listing, with everything that must not survive.
FIXTURE_PAGE = """<!DOCTYPE html>
<html><head><title>Laporan Keuangan</title>
<script>var tracking = "do-not-leak-script-body";</script>
<!-- do-not-leak-comment -->
</head>
<body>
  <div class="secret-marker">do-not-leak-visible-prose</div>
  <ul>
    <li><a href="/id/-/media/Laporan-Keuangan-Q1-2026.pdf">Financial Statements Q1 2026</a></li>
    <li><a href="media/Laporan-Keuangan-FY2025.xlsx"><span>FY2025</span> &amp; notes</a></li>
    <li><a href="https://www.bca.co.id/media/annual-report-2025.zip">Annual Report 2025</a></li>
  </ul>
  <a href="/en/tentang-bca/Hubungan-Investor">Back to Investor Relations</a>
  <a href="#top">Top</a>
  <a href="javascript:void(0)">Menu</a>
  <a href="mailto:investor@bca.co.id">Contact</a>
  <a href="https://evil.example.com/Laporan-Keuangan.pdf">Totally legitimate report</a>
  <a href="http://www.bca.co.id/insecure-report.pdf">Insecure report</a>
  <a href="https://bca.co.id.attacker.example/report.pdf">Suffix lookalike</a>
  <a>No href at all</a>
</body></html>
"""

LEAK_MARKERS = (
    "do-not-leak-script-body",
    "do-not-leak-comment",
    "do-not-leak-visible-prose",
    "<!DOCTYPE",
    "<script",
    "<li",
    "secret-marker",
)


def _workflow_text(repo_root):
    return (repo_root / WORKFLOW).read_text(encoding="utf-8")


def _workflow_document(repo_root):
    document = yaml.safe_load(_workflow_text(repo_root))
    # PyYAML reads the `on:` key as the boolean True under YAML 1.1.
    document["on"] = document.get("on", document.get(True))
    return document


def _embedded_source(repo_root):
    """The probe script exactly as the workflow writes it to disk.

    Read through the parsed YAML rather than the raw file so the block scalar's
    indentation is stripped the same way the runner strips it — testing a
    differently-indented copy would prove nothing about what actually runs.
    """
    document = _workflow_document(repo_root)
    steps = document["jobs"]["smoke"]["steps"]
    run = next(s["run"] for s in steps if "candidate_probe.py" in s.get("run", ""))
    body = run.split("<<'PY'\n", 1)[1]
    return body.split("\n          PY\n", 1)[0].split("\nPY\n", 1)[0]


@pytest.fixture(scope="module")
def workflow(repo_root):
    return _workflow_document(repo_root)


@pytest.fixture(scope="module")
def workflow_text(repo_root):
    return _workflow_text(repo_root)


@pytest.fixture(scope="module")
def source(repo_root):
    return _embedded_source(repo_root)


@pytest.fixture(scope="module")
def probe_module(repo_root, tmp_path_factory):
    """Import the embedded script without running it."""
    path = tmp_path_factory.mktemp("candidate") / "candidate_probe.py"
    path.write_text(_embedded_source(repo_root), encoding="utf-8")
    spec = importlib.util.spec_from_file_location("gdt_candidate_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)          # safe: the run is under __main__
    return module


# --- 1. manual only --------------------------------------------------------


def test_the_workflow_is_workflow_dispatch_only(workflow):
    """A probe of a third party's site must never fire unattended."""
    triggers = workflow["on"]
    assert set(triggers) == {"workflow_dispatch"}, triggers
    assert "schedule" not in triggers
    assert "push" not in triggers and "pull_request" not in triggers


def test_candidate_urls_are_supplied_by_input_not_by_sources_yml(workflow):
    """The whole point: evaluate a candidate before declaring a provider."""
    inputs = workflow["on"]["workflow_dispatch"]["inputs"]
    for name in ("candidate_urls", "link_page", "max_redirects", "max_links"):
        assert name in inputs, f"{name} is not a dispatch input"
    assert inputs["candidate_urls"].get("required", False) is False
    assert inputs["candidate_urls"].get("default", "") == ""


def test_the_two_official_bca_urls_are_the_defaults(probe_module):
    assert probe_module.DEFAULT_CANDIDATES == [BCA_IR, BCA_REPORTS]
    assert probe_module.DEFAULT_LINK_PAGE == BCA_REPORTS
    for url in probe_module.DEFAULT_CANDIDATES:
        assert url.startswith("https://www.bca.co.id/")


# --- 2. read only ----------------------------------------------------------


def test_the_workflow_permissions_stay_contents_read(workflow):
    assert workflow["permissions"] == {"contents": "read"}
    for job in workflow["jobs"].values():
        assert "permissions" not in job or job["permissions"] == {"contents": "read"}


# --- 3. no body retained, 7. nothing committed -----------------------------


def test_no_markup_survives_extraction(probe_module):
    links, skipped = probe_module.extract_report_links(FIXTURE_PAGE, BCA_REPORTS)
    blob = json.dumps({"links": links, "skipped": skipped})
    for marker in LEAK_MARKERS:
        assert marker not in blob, f"{marker!r} leaked out of the extractor"
    assert "<" not in blob and ">" not in blob


def test_the_extractor_returns_only_url_label_and_extension(probe_module):
    links, _ = probe_module.extract_report_links(FIXTURE_PAGE, BCA_REPORTS)
    assert links, "the fixture contains report links; none were found"
    for link in links:
        assert set(link) == {"url", "label", "extension"}, link


def test_labels_are_visible_text_not_markup(probe_module):
    links, _ = probe_module.extract_report_links(FIXTURE_PAGE, BCA_REPORTS)
    labels = {link["label"] for link in links}
    assert "FY2025 & notes" in labels, labels     # tags stripped, entity decoded
    for label in labels:
        assert "<" not in label and ">" not in label
        assert len(label) <= probe_module.LABEL_MAX


def test_a_hostile_page_cannot_inject_markup_into_a_label(probe_module):
    hostile = ('<a href="/a.pdf">before<script>alert(1)</script>'
               '<img src=x onerror="steal()">after</a>')
    links, _ = probe_module.extract_report_links(hostile, "https://www.bca.co.id/")
    assert len(links) == 1
    label = links[0]["label"]
    assert "<" not in label and ">" not in label
    assert "alert" not in label and "onerror" not in label


def test_the_report_never_contains_the_page(probe_module):
    """End to end over the report builder, with a populated link section."""
    links, skipped = probe_module.extract_report_links(FIXTURE_PAGE, BCA_REPORTS)
    section = {
        "pageUrl": BCA_REPORTS, "pageFinalUrl": BCA_REPORTS, "pageStatus": 200,
        "pageHops": [], "pageOutcome": "HTML_DOCUMENT_NOT_A_DATASET",
        "htmlFetchedForLinkExtraction": True, "htmlRetained": False,
        "htmlBytesScanned": len(FIXTURE_PAGE), "linksFound": len(links),
        "linksProbed": 0, "skipped": skipped, "links": [],
        "filesDownloaded": 0, "detail": None,
    }
    report = probe_module.build_report([], section)
    serialised = json.dumps(report)
    for marker in LEAK_MARKERS:
        assert marker not in serialised, f"{marker!r} reached the artifact"
    assert report["bodiesRetained"] is False
    assert report["filesDownloaded"] == 0
    assert report["linkDiscovery"]["htmlRetained"] is False
    # A byte count is metadata; it is the only thing the page's size leaves behind.
    assert report["linkDiscovery"]["htmlBytesScanned"] == len(FIXTURE_PAGE)


def test_exactly_one_read_and_it_is_bounded(source):
    tree = ast.parse(source)
    readers = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr == "read"
    ]
    assert len(readers) == 1, f"expected one .read(), found {len(readers)}"
    assert readers[0].args, ".read() must be bounded by a byte limit"

    enclosing = [
        node.name for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and any(child is readers[0] for child in ast.walk(node))
    ]
    assert enclosing == ["fetch_html"], enclosing


def test_neither_the_fetcher_nor_the_extractor_can_persist_what_it_sees(source):
    tree = ast.parse(source)
    for name in ("fetch_html", "extract_report_links", "anchor_label"):
        function = next(n for n in ast.walk(tree)
                        if isinstance(n, ast.FunctionDef) and n.name == name)
        calls = {n.func.id for n in ast.walk(function)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert not ({"print", "open"} & calls), f"{name} prints or writes"


def test_only_the_json_report_is_ever_written(source):
    """One `open(...)` in the file, and it writes the report to GDT_OUTPUT."""
    tree = ast.parse(source)
    opens = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "open"]
    assert len(opens) == 1, f"expected one open(), found {len(opens)}"
    enclosing = [n.name for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef)
                 and any(c is opens[0] for c in ast.walk(n))]
    assert enclosing == ["main"], enclosing
    writers = [n for n in ast.walk(tree)
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
               and n.func.attr == "dump"]
    assert writers, "the report is not serialised with json.dump"


def test_the_report_is_written_outside_the_working_tree(workflow, workflow_text):
    """RUNNER_TEMP, so a diagnostic artifact cannot land in a commit."""
    assert "${{ runner.temp }}/candidate-access-report.json" in workflow_text
    steps = workflow["jobs"]["smoke"]["steps"]
    probe = next(s for s in steps if "candidate_probe.py" in s.get("run", ""))
    assert probe["env"]["GDT_OUTPUT"].startswith("${{ runner.temp }}")


def test_the_workflow_cannot_commit_push_or_open_a_pull_request(workflow_text):
    forbidden = ("git commit", "git push", "git add", "git merge", "git tag",
                 "gh pr create", "gh pr merge", "peter-evans/create-pull-request",
                 "stefanzweifel/git-auto-commit-action", "actions/github-script",
                 "GITHUB_TOKEN")
    for command in forbidden:
        assert command not in workflow_text, f"the read-only workflow uses {command!r}"


def test_the_working_tree_is_asserted_clean_after_probing(workflow, workflow_text):
    """The existing guard must still run, and run after the new probe."""
    assert "git status --porcelain --untracked-files=all" in workflow_text
    steps = [s.get("name", "") for s in workflow["jobs"]["smoke"]["steps"]]
    assert steps.index("Probe candidate official URLs not declared in sources.yml") \
        < steps.index("Assert nothing was enabled or modified")


# --- 4. no report file is downloaded ---------------------------------------


def test_discovered_links_are_probed_by_head_and_never_fetched(source):
    """`probe` resolves by HEAD and has no body read; `discover_reports` calls
    only `probe`, never `fetch_html`, on a discovered link."""
    tree = ast.parse(source)
    discover = next(n for n in ast.walk(tree)
                    if isinstance(n, ast.FunctionDef) and n.name == "discover_reports")
    called = {n.func.id for n in ast.walk(discover)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "probe" in called, "discovered links are not probed at all"
    # fetch_html appears once in discover_reports — for the page itself. The
    # per-link loop must not reach it.
    loop = next(n for n in ast.walk(discover) if isinstance(n, ast.For))
    in_loop = {n.func.id for n in ast.walk(loop)
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "fetch_html" not in in_loop, "a discovered link's body would be fetched"
    assert "open" not in in_loop, "a discovered link would be written to disk"


def test_the_head_helper_never_reads_a_response(source):
    tree = ast.parse(source)
    head = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "head")
    reads = [n for n in ast.walk(head)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "read"]
    assert reads == [], "the HEAD helper reads a body"


def test_a_head_refusal_falls_back_to_get_without_reading(source):
    """405/501 retries as GET for headers only — still no body read."""
    tree = ast.parse(source)
    probe = next(n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == "probe")
    text = ast.unparse(probe)
    assert "405" in text and "501" in text, "no HEAD-unsupported fallback"
    assert "'GET'" in text or '"GET"' in text
    reads = [n for n in ast.walk(probe)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "read"]
    assert reads == [], "the fallback GET reads a body"


def test_every_probe_record_states_it_was_not_downloaded(probe_module):
    section_links, _ = probe_module.extract_report_links(FIXTURE_PAGE, BCA_REPORTS)
    assert section_links
    report = probe_module.build_report([], {
        "pageUrl": BCA_REPORTS, "pageFinalUrl": None, "pageStatus": None,
        "pageHops": [], "pageOutcome": "NOT_TESTED",
        "htmlFetchedForLinkExtraction": False, "htmlRetained": False,
        "htmlBytesScanned": 0, "linksFound": len(section_links), "linksProbed": 0,
        "skipped": {}, "links": [], "filesDownloaded": 0, "detail": None,
    })
    assert report["filesDownloaded"] == 0


def test_report_extensions_are_probed_not_retrieved(probe_module):
    """The formats named in the brief are recognised as links to measure."""
    for extension in (".pdf", ".zip", ".xls", ".xlsx"):
        assert extension in probe_module.REPORT_EXTENSIONS


# --- 5. only official HTTPS BCA links survive ------------------------------


def test_off_host_and_plain_http_links_are_dropped(probe_module):
    links, skipped = probe_module.extract_report_links(FIXTURE_PAGE, BCA_REPORTS)
    urls = " ".join(link["url"] for link in links)
    assert "evil.example.com" not in urls, "an off-host link would have been probed"
    assert "insecure-report.pdf" not in urls, "a plain-http link would have been probed"
    assert "attacker.example" not in urls, "a suffix lookalike host was accepted"
    assert skipped["offHost"] >= 2 and skipped["notHttps"] >= 1
    assert skipped["nonReport"] >= 1 and skipped["unusable"] >= 1


def test_every_surviving_link_is_https_on_an_official_bca_host(probe_module):
    links, _ = probe_module.extract_report_links(FIXTURE_PAGE, BCA_REPORTS)
    assert links
    for link in links:
        assert link["url"].startswith("https://")
        assert probe_module.host_allowed(link["url"])
        host = link["url"].split("/")[2].lower()
        assert host == "bca.co.id" or host.endswith(".bca.co.id"), host


def test_host_matching_cannot_be_fooled_by_a_suffix(probe_module):
    assert probe_module.host_allowed("https://www.bca.co.id/x.pdf")
    assert probe_module.host_allowed("https://bca.co.id/x.pdf")
    assert not probe_module.host_allowed("https://bca.co.id.attacker.example/x.pdf")
    assert not probe_module.host_allowed("https://notbca.co.id/x.pdf")
    assert not probe_module.host_allowed("https://evil.example.com/x.pdf")


def test_relative_links_resolve_against_the_page(probe_module):
    links, _ = probe_module.extract_report_links(FIXTURE_PAGE, BCA_REPORTS)
    by_name = {link["url"].rsplit("/", 1)[-1]: link["url"] for link in links}
    # Root-relative resolves to the host root...
    assert by_name["Laporan-Keuangan-Q1-2026.pdf"] == (
        "https://www.bca.co.id/id/-/media/Laporan-Keuangan-Q1-2026.pdf")
    # ...and a document-relative href resolves against the page's directory.
    assert by_name["Laporan-Keuangan-FY2025.xlsx"].startswith(
        "https://www.bca.co.id/en/tentang-bca/Hubungan-Investor/laporan-presentasi/")


def test_extraction_is_deduplicated(probe_module):
    once, _ = probe_module.extract_report_links(FIXTURE_PAGE, BCA_REPORTS)
    twice, _ = probe_module.extract_report_links(FIXTURE_PAGE * 2, BCA_REPORTS)
    assert len(once) == len(twice)


def test_structured_files_are_ranked_above_pdfs(probe_module):
    """A spreadsheet is worth more to a future parser than a PDF."""
    links, _ = probe_module.extract_report_links(FIXTURE_PAGE, BCA_REPORTS)
    assert links[0]["extension"] in (".xlsx", ".xls", ".xlsm", ".csv"), links[0]


def test_the_allowed_host_list_is_bca_only(probe_module, source):
    assert probe_module.ALLOWED_HOSTS == ("bca.co.id",)
    assert "idx.co.id" not in source, "the candidate probe reaches an IDX host"


# --- 6. no provider or rights status can be changed ------------------------


def test_the_probe_never_opens_config_or_data(source, workflow_text):
    """Checked against what the script *does*, not what its prose mentions —
    the notice deliberately names sources.yml and SOURCE_REGISTER.md to say
    what a run does NOT do, and a grep would flag exactly that honesty.

    The one `open()` writes the JSON report to GDT_OUTPUT, and no string
    constant anywhere in executable code points at the config or data tree.
    """
    tree = ast.parse(source)

    opens = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "open"]
    assert len(opens) == 1
    target = ast.unparse(opens[0].args[0])
    assert "GDT_OUTPUT" in target, f"open() writes to {target}"

    docstrings = {id(ast.get_docstring(n, clean=False)) for n in ast.walk(tree)
                  if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef))}
    literals = [n.value for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)
                and id(n.value) not in docstrings]
    code_paths = [s for s in literals
                  if "config/goh-dip-tong" in s or "data/goh-dip-tong" in s
                  or s.endswith("sources.yml")]
    # The notice string is the only place either name may appear, and it
    # appears there to disclaim, not to open anything.
    for value in code_paths:
        assert "requires a dated rights review" in value, f"path literal: {value!r}"

    # The workflow reads sources.yml in the pre-existing guard steps only.
    assert 'sources.yml").read_text()' in workflow_text


def test_the_probe_declares_it_enabled_nothing(probe_module):
    report = probe_module.build_report([], {
        "pageUrl": None, "pageFinalUrl": None, "pageStatus": None, "pageHops": [],
        "pageOutcome": "NOT_TESTED", "htmlFetchedForLinkExtraction": False,
        "htmlRetained": False, "htmlBytesScanned": 0, "linksFound": 0,
        "linksProbed": 0, "skipped": {}, "links": [], "filesDownloaded": 0,
        "detail": None,
    })
    assert report["providersEnabledByThisRun"] == 0
    assert report["rightsStatusChangedByThisRun"] is False
    assert "not permission" in report["notice"]
    assert "SOURCE_REGISTER" in report["notice"]


def test_every_probe_record_restates_that_it_enables_nothing(probe_module):
    """Per record, so a single row cannot be read out of context."""
    tree = ast.parse(_probe_source_of(probe_module))
    probe = next(n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == "probe")
    text = ast.unparse(probe)
    assert "'enablesProvider': False" in text
    assert "'bodyRetained': False" in text
    assert "'downloaded': False" in text


def test_the_existing_provider_assertion_still_runs(workflow_text):
    """The pre-existing guard that re-reads sources.yml and fails if any live
    provider became enabled must survive this change."""
    assert "live providers are enabled" in workflow_text
    assert "still disabled. Nothing was activated." in workflow_text


def _probe_source_of(module):
    import pathlib
    return pathlib.Path(module.__file__).read_text(encoding="utf-8")
