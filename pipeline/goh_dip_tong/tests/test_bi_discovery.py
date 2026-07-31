"""The BI discovery workflow must not leak the page it scans.

Link discovery is the one place in Stage 1 that reads a response body, so it is
the one place where "we only keep metadata" could quietly stop being true. A
page is fetched, held in memory, scanned for anchors, and dropped — and the
claim that it is never persisted or logged is worth exactly as much as the test
that enforces it.

Two kinds of check here, because either alone is weak:

* **Behavioural** — the script is imported and run against a fixture page that
  contains markup, scripts, comments and hostile-looking links. Whatever it
  returns is inspected for any trace of that markup. This catches a real leak.
* **Structural** — the source is read and asserted against: exactly one
  ``.read()``, in ``fetch_html``, bounded; no ``print`` or file write anywhere
  that could receive the HTML. This catches a leak added later through a path
  the fixture happens not to exercise.

Nothing here performs network I/O. The workflow's own request functions are
never called.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import re

import pytest
import yaml


WORKFLOW = ".github/workflows/gdt-bi-discovery.yml"

#: Markup that must never appear in anything the script returns or writes.
FIXTURE_PAGE = """<!DOCTYPE html>
<html><head><title>SEKI June 2026</title>
<script>var tracking = "do-not-leak-script-body";</script>
<!-- do-not-leak-comment -->
</head>
<body>
  <div class="secret-marker">do-not-leak-visible-prose</div>
  <table>
    <tr><td><a href="/en/statistik/ekonomi-keuangan/seki/Documents/SEKI%20JUNE%202026.zip">
        SEKI JUNE 2026.zip</a></td></tr>
    <tr><td><a href="Documents/Tabel-1.xlsx"><span>Table 1</span> &amp; notes</a></td></tr>
    <tr><td><a href="https://www.bi.go.id/en/publikasi/laporan.pdf">Laporan PDF</a></td></tr>
  </table>
  <a href="/en/statistik/ekonomi-keuangan/seki/default.aspx">Back to index</a>
  <a href="#top">Top</a>
  <a href="javascript:void(0)">Menu</a>
  <a href="mailto:someone@bi.go.id">Contact</a>
  <a href="https://evil.example.com/payload.zip">Totally legitimate archive</a>
  <a href="http://www.bi.go.id/insecure.zip">Insecure archive</a>
  <a>No href at all</a>
</body></html>
"""

LEAK_MARKERS = (
    "do-not-leak-script-body",
    "do-not-leak-comment",
    "do-not-leak-visible-prose",
    "<!DOCTYPE",
    "<table",
    "<script",
    "secret-marker",
)


def _workflow_document(repo_root):
    text = (repo_root / WORKFLOW).read_text(encoding="utf-8")
    document = yaml.safe_load(text)
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
    steps = document["jobs"]["discover"]["steps"]
    run = next(s["run"] for s in steps if "probe.py" in s.get("run", ""))
    body = run.split("<<'PY'\n", 1)[1]
    return body.split("\n          PY\n", 1)[0].split("\nPY\n", 1)[0]


@pytest.fixture(scope="module")
def source(repo_root):
    return _embedded_source(repo_root)


@pytest.fixture(scope="module")
def probe_module(repo_root, tmp_path_factory):
    """Import the embedded script without running it."""
    path = tmp_path_factory.mktemp("bi") / "probe.py"
    path.write_text(_embedded_source(repo_root), encoding="utf-8")
    spec = importlib.util.spec_from_file_location("gdt_bi_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)          # safe: everything runs under __main__
    return module


# --- behaviour: what comes out of the extractor ----------------------------


def test_extractor_returns_only_urls_and_labels(probe_module):
    links, _skipped = probe_module.extract_attachment_links(
        FIXTURE_PAGE, "https://www.bi.go.id/en/statistik/ekonomi-keuangan/seki/"
        "Pages/SEKI-JUNI-2026.aspx")
    assert links, "the fixture contains attachments; none were found"
    for link in links:
        assert set(link) == {"url", "label"}, link


def test_no_markup_survives_extraction(probe_module):
    links, skipped = probe_module.extract_attachment_links(
        FIXTURE_PAGE, "https://www.bi.go.id/x/y.aspx")
    blob = json.dumps({"links": links, "skipped": skipped})
    for marker in LEAK_MARKERS:
        assert marker not in blob, f"{marker!r} leaked out of the extractor"
    assert "<" not in blob and ">" not in blob


def test_the_seki_zip_is_found_and_ranked_first(probe_module):
    links, _ = probe_module.extract_attachment_links(
        FIXTURE_PAGE, "https://www.bi.go.id/en/statistik/ekonomi-keuangan/seki/"
        "Pages/SEKI-JUNI-2026.aspx")
    assert links[0]["url"].lower().endswith(".zip")
    assert "SEKI%20JUNE%202026.zip" in links[0]["url"]
    assert links[0]["label"] == "SEKI JUNE 2026.zip"


def test_relative_links_resolve_against_the_page(probe_module):
    links, _ = probe_module.extract_attachment_links(
        FIXTURE_PAGE, "https://www.bi.go.id/en/statistik/ekonomi-keuangan/seki/"
        "Pages/SEKI-JUNI-2026.aspx")
    by_name = {link["url"].rsplit("/", 1)[-1]: link["url"] for link in links}
    # Root-relative resolves to the host root...
    assert by_name["SEKI%20JUNE%202026.zip"].startswith(
        "https://www.bi.go.id/en/statistik/ekonomi-keuangan/seki/Documents/")
    # ...and a document-relative href resolves against the page's directory.
    assert by_name["Tabel-1.xlsx"] == (
        "https://www.bi.go.id/en/statistik/ekonomi-keuangan/seki/Pages/"
        "Documents/Tabel-1.xlsx")
    for url in by_name.values():
        assert url.startswith("https://www.bi.go.id/")


def test_labels_are_visible_text_not_markup(probe_module):
    links, _ = probe_module.extract_attachment_links(
        FIXTURE_PAGE, "https://www.bi.go.id/x/y.aspx")
    labels = {link["label"] for link in links}
    assert "Table 1 & notes" in labels, labels     # tags stripped, entity decoded
    for label in labels:
        assert "<" not in label and ">" not in label
        assert len(label) <= probe_module.LABEL_MAX


def test_untrusted_and_non_attachment_links_are_dropped(probe_module):
    links, skipped = probe_module.extract_attachment_links(
        FIXTURE_PAGE, "https://www.bi.go.id/x/y.aspx")
    urls = " ".join(link["url"] for link in links)
    assert "evil.example.com" not in urls, "an off-host link would have been probed"
    assert "insecure.zip" not in urls, "a plain-http link would have been probed"
    assert ".aspx" not in urls, "a navigation link is not an attachment"
    assert skipped["offHost"] >= 1 and skipped["notHttps"] >= 1
    assert skipped["nonAttachment"] >= 1 and skipped["unusable"] >= 1


def test_extraction_is_deduplicated(probe_module):
    doubled = FIXTURE_PAGE + FIXTURE_PAGE
    once, _ = probe_module.extract_attachment_links(FIXTURE_PAGE, "https://www.bi.go.id/")
    twice, _ = probe_module.extract_attachment_links(doubled, "https://www.bi.go.id/")
    assert len(once) == len(twice)


def test_a_hostile_page_cannot_inject_markup_into_a_label(probe_module):
    hostile = ('<a href="/a.zip">before<script>alert(1)</script>'
               '<img src=x onerror="steal()">after</a>')
    links, _ = probe_module.extract_attachment_links(hostile, "https://www.bi.go.id/")
    assert len(links) == 1
    label = links[0]["label"]
    assert "<" not in label and ">" not in label
    assert "alert" not in label and "onerror" not in label


def test_the_report_never_contains_the_page(probe_module):
    """End to end over the report builder, with a populated link section."""
    links, skipped = probe_module.extract_attachment_links(
        FIXTURE_PAGE, "https://www.bi.go.id/x/y.aspx")
    section = {
        "pageUrl": "https://www.bi.go.id/x/y.aspx", "pageFinalUrl": None,
        "pageStatus": 200, "pageHops": [], "pageOutcome": "HTML_DOCUMENT_NOT_A_DATASET",
        "htmlFetchedForLinkExtraction": True, "htmlRetained": False,
        "htmlBytesScanned": len(FIXTURE_PAGE), "linksFound": len(links),
        "attachmentsProbed": 0, "skipped": skipped, "attachments": [],
        "detail": None,
    }
    report = probe_module.build_report([], section)
    serialised = json.dumps(report)
    for marker in LEAK_MARKERS:
        assert marker not in serialised, f"{marker!r} reached the artifact"
    assert report["bodiesRetained"] is False
    assert report["attachmentsDownloaded"] == 0
    assert report["providersEnabledByThisRun"] == 0
    assert report["linkDiscovery"]["htmlRetained"] is False
    # A byte count is metadata; it is the only thing the page's size leaves behind.
    assert report["linkDiscovery"]["htmlBytesScanned"] == len(FIXTURE_PAGE)


# --- structure: no path exists for the HTML to escape ----------------------


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


def test_no_function_both_reads_html_and_writes_output(source):
    """`fetch_html` must not be able to persist what it reads."""
    tree = ast.parse(source)
    fetch = next(n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == "fetch_html")
    calls = {n.func.id for n in ast.walk(fetch)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "print" not in calls, "fetch_html prints"
    assert "open" not in calls, "fetch_html opens a file"


def test_the_extractor_neither_prints_nor_writes(source):
    tree = ast.parse(source)
    for name in ("extract_attachment_links", "anchor_label"):
        function = next(n for n in ast.walk(tree)
                        if isinstance(n, ast.FunctionDef) and n.name == name)
        calls = {n.func.id for n in ast.walk(function)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert not ({"print", "open"} & calls), f"{name} prints or writes"


def test_only_the_report_is_ever_written(source):
    """One `open(...)` in the file, and it writes the JSON report."""
    tree = ast.parse(source)
    opens = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "open"]
    assert len(opens) == 1, f"expected one open(), found {len(opens)}"
    dumps = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "dump"]
    assert len(dumps) == 1, "the report should be written with a single json.dump"


def test_the_html_local_is_cleared_after_scanning(source):
    """`discover_attachments` drops its reference rather than holding it."""
    assert "html_text = None" in source
    assert "del html_text" in source


def test_the_scanned_text_never_reaches_the_section_dict(source):
    tree = ast.parse(source)
    function = next(n for n in ast.walk(tree)
                    if isinstance(n, ast.FunctionDef)
                    and n.name == "discover_attachments")
    # Every assignment into `section[...]` must store something other than the
    # raw text; the only thing derived from it may be its length.
    for node in ast.walk(function):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not (isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "section"):
                continue
            if isinstance(node.value, ast.Name):
                assert node.value.id != "html_text", "raw HTML stored in the report"


def test_the_header_documents_the_single_body_read(repo_root):
    """The file must not still claim no body is ever read — it now reads one."""
    text = (repo_root / WORKFLOW).read_text(encoding="utf-8")
    header = text.split("name: gdt-bi-discovery", 1)[0]
    assert "NO RESPONSE BODY IS EVER READ" not in header, \
        "the header makes a claim the script no longer satisfies"
    assert "in memory" in header.lower()
    assert "never downloaded" in text.lower() or "never fetched" in text.lower()


# --- the workflow around it stays a read-only manual diagnostic ------------


def test_still_manual_only_and_read_only(repo_root):
    document = _workflow_document(repo_root)
    assert list(document["on"]) == ["workflow_dispatch"]
    assert document["permissions"] == {"contents": "read"}
    for name, job in document["jobs"].items():
        assert job.get("permissions") is None, name


def test_the_workflow_cannot_commit_or_download(repo_root):
    text = (repo_root / WORKFLOW).read_text(encoding="utf-8")
    for forbidden in ("git commit", "git push", "git add", "gh pr create",
                      "urlretrieve", "shutil.copyfileobj"):
        assert forbidden not in text, forbidden


def test_discovered_links_are_probed_by_head_only(probe_module, source):
    assert probe_module.ATTACHMENT_EXTENSIONS
    assert probe_module.ALLOWED_HOSTS == ("bi.go.id",)
    # The attachment loop calls probe(), which issues HEAD (with a GET fallback
    # that never reads). It must not call fetch_html.
    tree = ast.parse(source)
    function = next(n for n in ast.walk(tree)
                    if isinstance(n, ast.FunctionDef)
                    and n.name == "discover_attachments")
    calls = [n.func.id for n in ast.walk(function)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
    assert calls.count("fetch_html") == 1, "the page is fetched exactly once"
    assert "probe" in calls


def test_the_artifact_step_uploads_only_the_json_report(repo_root):
    document = _workflow_document(repo_root)
    steps = document["jobs"]["discover"]["steps"]
    upload = next(s for s in steps if "upload-artifact" in str(s.get("uses", "")))
    assert upload["with"]["name"] == "gdt-bi-discovery-report"
    assert upload["with"]["path"].endswith("bi-discovery-report.json")


def test_the_guard_step_rejects_html_in_the_report(repo_root):
    text = (repo_root / WORKFLOW).read_text(encoding="utf-8")
    assert "the discovery report contains HTML markup" in text
    assert re.search(r"grep -qiE .*doctype", text, re.IGNORECASE)


def test_bank_indonesia_is_still_disabled(real_settings):
    providers = real_settings.sources().get("providers", {})
    bank = providers["bank_indonesia"]
    assert bank["enabled"] is False
    assert bank["rights_status"] == "MANUAL_REVIEW_REQUIRED"
    for right in ("store_raw", "commit_to_repo", "public_display", "redistribute"):
        assert bank["rights"][right] is False, right
