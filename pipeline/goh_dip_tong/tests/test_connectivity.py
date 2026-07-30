"""Tests for the source connectivity smoke test.

Two things must hold: the outcome classification is correct for every case in
the vocabulary, and the probe never retains a response body or enables anything.
"""

from __future__ import annotations

import pytest

from pipeline.goh_dip_tong.validation import connectivity
from pipeline.goh_dip_tong.validation.connectivity import (
    OUTCOMES,
    ProbeResponse,
    probe_sources,
    probe_url,
)


def transport_returning(status, headers=None):
    def _transport(url, timeout):
        return ProbeResponse(status, headers or {})
    return _transport


def transport_raising(exc):
    def _transport(url, timeout):
        raise exc
    return _transport


# --- outcome vocabulary ----------------------------------------------------


def test_outcome_vocabulary_is_exactly_the_specified_set():
    assert set(OUTCOMES) == {
        "REACHABLE_UNVALIDATED",
        "UNREACHABLE_FROM_GITHUB_ACTIONS",
        "AUTHENTICATION_REQUIRED",
        "ACCESS_CONTROLLED",
        "CONTENT_TYPE_UNEXPECTED",
        "NETWORK_ERROR",
        "NOT_TESTED",
    }


def test_every_probe_result_uses_a_declared_outcome():
    cases = [
        transport_returning(200, {"Content-Type": "application/json"}),
        transport_returning(401),
        transport_returning(403),
        transport_returning(302, {"Location": "https://example.invalid/x"}),
        transport_returning(500),
        transport_returning(200, {"Content-Type": "text/html"}),
        transport_raising(RuntimeError("boom")),
    ]
    for transport in cases:
        record = probe_url("p", "https://example.invalid", transport=transport)
        assert record["outcome"] in OUTCOMES


# --- classification --------------------------------------------------------


def test_json_200_is_reachable_but_unvalidated():
    r = probe_url("p", "https://example.invalid",
                  transport=transport_returning(200, {"Content-Type": "application/json"}))
    assert r["outcome"] == "REACHABLE_UNVALIDATED"
    assert r["httpStatus"] == 200


def test_401_is_authentication_required():
    r = probe_url("p", "https://example.invalid", transport=transport_returning(401))
    assert r["outcome"] == "AUTHENTICATION_REQUIRED"


@pytest.mark.parametrize("status", [403, 429, 451])
def test_access_gates_are_recorded_not_worked_around(status):
    """A refusal is the answer, not an obstacle to route around."""
    r = probe_url("p", "https://example.invalid", transport=transport_returning(status))
    assert r["outcome"] == "ACCESS_CONTROLLED"
    assert str(status) in r["detail"]


def test_html_response_is_flagged_as_unexpected_content_type():
    """A landing page is not a data endpoint, even at HTTP 200."""
    r = probe_url("p", "https://example.invalid",
                  transport=transport_returning(200, {"Content-Type": "text/html; charset=utf-8"}))
    assert r["outcome"] == "CONTENT_TYPE_UNEXPECTED"


def test_redirects_are_recorded_and_not_followed():
    r = probe_url("p", "https://example.invalid",
                  transport=transport_returning(301, {"Location": "https://elsewhere.invalid/a"}))
    assert r["outcome"] == "REACHABLE_UNVALIDATED"
    assert r["redirectTarget"] == "https://elsewhere.invalid/a"
    assert "target recorded" in r["detail"]


def test_connection_failure_is_unreachable_from_github_actions():
    class ConnectionError(Exception):
        pass

    r = probe_url("p", "https://example.invalid",
                  transport=transport_raising(ConnectionError("refused")))
    assert r["outcome"] == "UNREACHABLE_FROM_GITHUB_ACTIONS"


def test_proxy_denial_is_unreachable():
    """This is the exact failure the build sandbox produced."""
    class ProxyError(Exception):
        pass

    r = probe_url("p", "https://www.idx.co.id/",
                  transport=transport_raising(ProxyError("403 to CONNECT")))
    assert r["outcome"] == "UNREACHABLE_FROM_GITHUB_ACTIONS"


def test_other_exceptions_are_network_errors():
    r = probe_url("p", "https://example.invalid",
                  transport=transport_raising(ValueError("bad TLS")))
    assert r["outcome"] == "NETWORK_ERROR"


def test_server_error_is_a_network_error():
    r = probe_url("p", "https://example.invalid", transport=transport_returning(503))
    assert r["outcome"] == "NETWORK_ERROR"


def test_missing_url_is_not_tested():
    r = probe_url("p", None, transport=transport_returning(200))
    assert r["outcome"] == "NOT_TESTED"
    assert r["httpStatus"] is None


def test_probe_never_raises_on_an_unexpected_transport_failure():
    """A diagnostic that crashes on one bad host tells you nothing about the rest."""
    class SomethingNobodyAnticipated(Exception):
        pass

    r = probe_url("p", "https://example.invalid",
                  transport=transport_raising(SomethingNobodyAnticipated("?")))
    assert r["outcome"] == "NETWORK_ERROR"
    assert r["outcome"] in OUTCOMES


def test_probe_does_not_swallow_keyboard_interrupt():
    """It catches Exception, not BaseException — Ctrl-C must still work."""
    with pytest.raises(KeyboardInterrupt):
        probe_url("p", "https://example.invalid",
                  transport=transport_raising(KeyboardInterrupt()))


# --- captured fields -------------------------------------------------------


EXPECTED_FIELDS = {
    "providerId", "url", "checkedAt", "httpStatus", "redirectTarget",
    "contentType", "responseBytes", "outcome", "detail", "enablesProvider",
}


def test_only_the_permitted_metadata_fields_are_captured():
    r = probe_url("p", "https://example.invalid",
                  transport=transport_returning(200, {
                      "Content-Type": "application/json", "Content-Length": "4096"}))
    assert set(r) == EXPECTED_FIELDS


def test_no_response_body_is_ever_retained():
    """ProbeResponse has no body attribute — the type cannot hold one."""
    response = ProbeResponse(200, {"Content-Type": "application/json"})
    assert not hasattr(response, "body")
    assert not hasattr(response, "text")
    assert not hasattr(response, "content")

    r = probe_url("p", "https://example.invalid", transport=lambda u, t: response)
    assert "body" not in r and "content" not in r and "text" not in r


def test_response_size_comes_from_the_header_not_from_reading():
    r = probe_url("p", "https://example.invalid",
                  transport=transport_returning(200, {"Content-Length": "12345",
                                                      "Content-Type": "text/csv"}))
    assert r["responseBytes"] == 12345


def test_unparseable_content_length_becomes_null_not_zero():
    r = probe_url("p", "https://example.invalid",
                  transport=transport_returning(200, {"Content-Length": "chunked",
                                                      "Content-Type": "text/csv"}))
    assert r["responseBytes"] is None


# --- the probe enables nothing ---------------------------------------------


def test_every_record_states_that_it_enables_nothing():
    for status in (200, 301, 401, 403, 500):
        r = probe_url("p", "https://example.invalid", transport=transport_returning(status))
        assert r["enablesProvider"] is False


def test_http_200_does_not_enable_any_provider(real_settings):
    """The central safety property: a green probe changes no policy."""
    before = real_settings.sources()
    report = probe_sources(real_settings,
                           transport=transport_returning(200, {"Content-Type": "application/json"}),
                           delay_seconds=0, sleep=lambda _: None)
    after = real_settings.sources()

    assert before == after, "probing modified sources.yml"
    assert report["providersEnabledByThisRun"] == 0
    assert report["bodiesRetained"] is False
    assert all(r["enablesProvider"] is False for r in report["results"])

    live = {p for p, c in after["providers"].items() if c.get("kind") == "http"}
    assert live, "expected live providers to exist"
    for provider_id in live:
        assert after["providers"][provider_id]["enabled"] is False
        assert after["providers"][provider_id]["rights_status"] == "MANUAL_REVIEW_REQUIRED"


def test_report_carries_an_explicit_notice(real_settings):
    report = probe_sources(real_settings, transport=transport_returning(200),
                           delay_seconds=0, sleep=lambda _: None)
    assert "not permission" in report["notice"]
    assert "SOURCE_REGISTER.md" in report["notice"]


# --- conservative behaviour ------------------------------------------------


def test_fixture_providers_are_never_probed(real_settings):
    report = probe_sources(real_settings, transport=transport_returning(200),
                           delay_seconds=0, sleep=lambda _: None)
    fixtures = [r for r in report["results"] if r["providerId"].startswith("fixture_")]
    assert fixtures
    for row in fixtures:
        assert row["outcome"] == "NOT_TESTED"
        assert row["httpStatus"] is None


def test_one_request_per_provider_and_no_retries(real_settings):
    calls = []

    def counting(url, timeout):
        calls.append(url)
        return ProbeResponse(403)

    probe_sources(real_settings, transport=counting, delay_seconds=0, sleep=lambda _: None)
    assert len(calls) == len(set(calls)), "a URL was probed more than once"

    live = [p for p, c in real_settings.sources()["providers"].items()
            if c.get("kind") == "http" and c.get("official_url")]
    assert len(calls) == len(live)


def test_a_delay_is_applied_between_providers(real_settings):
    delays = []
    probe_sources(real_settings, transport=transport_returning(200),
                  delay_seconds=2.0, sleep=delays.append)
    assert delays, "no pause between providers"
    assert all(d == 2.0 for d in delays)


def test_results_are_deterministically_ordered(real_settings):
    report = probe_sources(real_settings, transport=transport_returning(200),
                           delay_seconds=0, sleep=lambda _: None)
    ids = [r["providerId"] for r in report["results"]]
    assert ids == sorted(ids)


def test_formatted_table_contains_no_body_content(real_settings):
    report = probe_sources(real_settings, transport=transport_returning(200),
                           delay_seconds=0, sleep=lambda _: None)
    text = connectivity.format_table(report)
    assert "provider" in text
    for row in report["results"]:
        assert row["outcome"] in text
