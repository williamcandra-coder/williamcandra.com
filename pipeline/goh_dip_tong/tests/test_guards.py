"""Stage 1 tests: malformed HTML returned as data, timeout and retry, provider
disabled mode, the rights gate, and the repository-size guard.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.goh_dip_tong.collectors.base import FetchError, with_retry
from pipeline.goh_dip_tong.collectors.registry import ProviderRegistry
from pipeline.goh_dip_tong.contracts.enums import RightsStatus
from pipeline.goh_dip_tong.contracts.provider import (
    ProviderDisabledError,
    RightsViolationError,
)
from pipeline.goh_dip_tong.parsers.guards import (
    PayloadRejected,
    assert_is_data,
    is_numeric_text,
    looks_like_block_page,
    looks_like_html,
    parse_numeric,
)
from pipeline.goh_dip_tong.validation.repo_guard import RepoGuard
from pipeline.goh_dip_tong.validation.rights import RIGHTS_MATRIX, RightsGate

FIXTURES = Path(__file__).parent / "fixtures" / "malformed"


# --- malformed HTML returned as data ---------------------------------------


def test_cloudflare_interstitial_is_rejected():
    content = (FIXTURES / "cloudflare-block.html").read_text(encoding="utf-8")
    assert looks_like_html(content)
    assert looks_like_block_page(content)
    with pytest.raises(PayloadRejected, match="HTML document"):
        assert_is_data(content, expect="json", source="test")


def test_error_page_saved_with_a_json_extension_is_rejected():
    """HTTP 200 with an error body is the commonest silent-corruption mode."""
    content = (FIXTURES / "error-page.json").read_text(encoding="utf-8")
    with pytest.raises(PayloadRejected):
        assert_is_data(content, expect="json", source="test")


def test_truncated_json_is_rejected():
    content = (FIXTURES / "truncated.json").read_text(encoding="utf-8")
    with pytest.raises(PayloadRejected, match="parse failed"):
        assert_is_data(content, expect="json", source="test")


def test_empty_payload_is_rejected():
    assert (FIXTURES / "empty.csv").read_text(encoding="utf-8") == ""
    with pytest.raises(PayloadRejected, match="empty"):
        assert_is_data("", source="test")
    with pytest.raises(PayloadRejected, match="empty"):
        assert_is_data(None, source="test")


def test_unexpected_content_type_is_rejected():
    with pytest.raises(PayloadRejected, match="unexpected content type"):
        assert_is_data('{"a":1}', media_type="application/pdf", source="test")


def test_valid_json_passes():
    assert_is_data('{"constituents": []}', media_type="application/json",
                   expect="json", source="test")


def test_numeric_detection_does_not_coerce_text_to_zero():
    assert is_numeric_text("1,234") and parse_numeric("1,234") == 1234.0
    assert not is_numeric_text("n/a") and parse_numeric("n/a") is None
    assert not is_numeric_text("") and parse_numeric("") is None
    assert parse_numeric("(50)") == -50.0


# --- timeout and retry -----------------------------------------------------


def test_retry_succeeds_after_transient_failures():
    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise TimeoutError("connection timed out")
        return "ok"

    assert with_retry(flaky, max_retries=3, sleep=lambda _: None) == "ok"
    assert attempts["n"] == 3


def test_retry_gives_up_and_raises_fetch_error():
    def always_fails():
        raise TimeoutError("connection timed out")

    with pytest.raises(FetchError, match="failed after 3 retries"):
        with_retry(always_fails, max_retries=3, sleep=lambda _: None)


def test_backoff_is_exponential():
    delays = []

    def always_fails():
        raise TimeoutError("nope")

    with pytest.raises(FetchError):
        with_retry(always_fails, max_retries=3, backoff_seconds=2.0,
                   sleep=delays.append)
    assert delays == [2.0, 4.0, 8.0]


def test_a_rejected_payload_is_not_retried():
    """Retrying a bot-check five times just means five requests at a source
    that has already said no."""
    attempts = {"n": 0}

    def blocked():
        attempts["n"] += 1
        raise PayloadRejected("bot check")

    with pytest.raises(PayloadRejected):
        with_retry(blocked, max_retries=3, sleep=lambda _: None)
    assert attempts["n"] == 1


# --- provider disabled mode ------------------------------------------------


def test_every_live_provider_is_disabled(real_settings):
    registry = ProviderRegistry(real_settings)
    for row in registry.status_table():
        if row["kind"] == "http":
            assert not row["enabled"], f"{row['providerId']} must stay disabled"
            assert not row["runnable"]


def test_running_a_disabled_provider_raises_rather_than_returning_empty(real_settings):
    """A disabled source that silently returns nothing looks exactly like a
    source with no new data."""
    registry = ProviderRegistry(real_settings)
    provider = registry.build("idx_index_constituents")
    with pytest.raises(ProviderDisabledError, match="disabled"):
        provider.ensure_runnable()


def test_enabling_a_provider_does_not_bypass_unresolved_rights(real_settings):
    """Two independent locks: the enabled flag AND a resolved rights status."""
    registry = ProviderRegistry(real_settings)
    config = dict(registry.provider_configs["idx_index_constituents"])
    config["enabled"] = True          # someone flips the flag...
    config["provider_id"] = "idx_index_constituents"
    from pipeline.goh_dip_tong.collectors.idx30_registry import Idx30LiveProvider

    provider = Idx30LiveProvider(config, settings=real_settings)
    # ...and it still refuses, because rights are MANUAL_REVIEW_REQUIRED.
    assert provider.rights_status == RightsStatus.MANUAL_REVIEW_REQUIRED
    assert not provider.runnable
    with pytest.raises(ProviderDisabledError, match="rights_status"):
        provider.ensure_runnable()


def test_resolve_falls_back_to_the_fixture_when_the_live_source_is_disabled(real_settings):
    registry = ProviderRegistry(real_settings)
    assert registry.resolve("index_membership").provider_id == "fixture_idx30_registry"
    assert registry.resolve("market_prices_daily").provider_id == "fixture_market_prices"


def test_resolve_raises_when_nothing_is_runnable(real_settings):
    sources = {"providers": {"idx_market_prices":
                             dict(real_settings.sources()["providers"]["idx_market_prices"])}}
    registry = ProviderRegistry(real_settings, sources_config=sources)
    with pytest.raises(ProviderDisabledError, match="no runnable provider"):
        registry.resolve("market_prices_daily")


def test_undeclared_provider_is_rejected(real_settings):
    registry = ProviderRegistry(real_settings)
    with pytest.raises(KeyError):
        registry.build("some_provider_nobody_reviewed")


# --- rights gate -----------------------------------------------------------


def test_rights_matrix_covers_every_status():
    assert set(RIGHTS_MATRIX) == set(RightsStatus)


def test_private_research_only_may_not_be_committed(real_settings):
    gate = RightsGate(real_settings.sources())
    assert gate.status("fixture_market_prices") == RightsStatus.PRIVATE_RESEARCH_ONLY
    assert gate.may("fixture_market_prices", "store_raw")
    assert not gate.may("fixture_market_prices", "commit_to_repo")
    assert not gate.may("fixture_market_prices", "public_display")


def test_price_writes_are_routed_to_the_git_ignored_tree(real_settings):
    gate = RightsGate(real_settings.sources())
    public = real_settings.market_prices_daily
    private = real_settings.private_dir / "market-prices" / "daily"
    assert gate.destination_for("fixture_market_prices", public, private) == private
    assert gate.destination_for("fixture_disclosures", public, private) == public


def test_committing_restricted_data_raises(real_settings):
    gate = RightsGate(real_settings.sources())
    with pytest.raises(RightsViolationError, match="commit_to_repo"):
        gate.assert_write_allowed(
            "fixture_market_prices",
            real_settings.market_prices_daily / "BBCA" / "2026.csv",
            real_settings.private_dir,
        )


def test_writing_restricted_data_to_the_private_tree_is_allowed(real_settings):
    gate = RightsGate(real_settings.sources())
    gate.assert_write_allowed(
        "fixture_market_prices",
        real_settings.private_dir / "market-prices" / "daily" / "BBCA" / "2026.csv",
        real_settings.private_dir,
    )


def test_no_source_claims_redistribution(real_settings):
    """Redistribution is the one right nothing in Stage 1 has."""
    gate = RightsGate(real_settings.sources())
    for provider_id in real_settings.sources()["providers"]:
        assert not gate.may(provider_id, "redistribute"), provider_id


def test_a_provider_may_narrow_its_rights_but_not_widen_them():
    sources = {"providers": {"greedy": {
        "rights_status": "PUBLIC_METADATA_ONLY",
        # Claims a right its status does not grant.
        "rights": {"redistribute": True, "commit_to_repo": True},
        "enabled": True,
    }}}
    gate = RightsGate(sources)
    assert gate.may("greedy", "commit_to_repo") is True     # granted by status
    assert gate.may("greedy", "redistribute") is False      # cannot be widened


def test_rights_register_cross_check(real_settings):
    """Every provider claiming a public right must have a documented row."""
    gate = RightsGate(real_settings.sources())
    register = (real_settings.docs_dir / "SOURCE_REGISTER.md").read_text(encoding="utf-8")
    assert gate.cross_check_register(register) == []
    # With no register at all, the gate must fail closed.
    assert gate.cross_check_register(None) != []


def test_private_dir_is_git_ignored(repo_root):
    ignore = (repo_root / ".gitignore").read_text(encoding="utf-8")
    assert "data/goh-dip-tong/_private/" in ignore


# --- repository-size guard -------------------------------------------------


def test_guard_passes_on_the_committed_tree(real_settings):
    report = RepoGuard(real_settings).run()
    assert report.ok, [i.message for i in report.critical_failures]


def test_guard_flags_an_oversized_file(sandbox):
    guard = RepoGuard(sandbox)
    guard.limits = {**guard.limits, "max_file_bytes": 100}
    path = sandbox.data_dir / "registry" / "current" / "big.json"
    path.write_text("x" * 500, encoding="utf-8")
    report = guard.check_file_sizes(guard.guarded_files())
    assert not report.ok
    assert "over the 100-byte limit" in report.critical_failures[0].message


def test_guard_flags_a_forbidden_extension(sandbox):
    (sandbox.data_dir / "disclosures" / "manifests" / "report.pdf").write_bytes(b"%PDF-1.7\n")
    report = RepoGuard(sandbox).check_extensions(RepoGuard(sandbox).guarded_files())
    assert not report.ok
    assert ".pdf" in report.critical_failures[0].message


def test_guard_flags_a_binary(sandbox):
    (sandbox.data_dir / "events" / "blob.json").write_bytes(b'{"a":\x00\x01}')
    report = RepoGuard(sandbox).check_binaries(RepoGuard(sandbox).guarded_files())
    assert not report.ok


def test_guard_flags_a_secret(sandbox):
    # Assembled at runtime rather than written as a literal: a repository-wide
    # secret scanner (GitHub push protection, for one) would otherwise flag this
    # test file itself, and a test for a secret detector should not be the thing
    # that trips one.
    fake_key = "AKIA" + "IOSFODNN7EXAMPLE"
    (sandbox.data_dir / "events" / "leak.json").write_text(
        '{"note": "%s"}' % fake_key, encoding="utf-8")
    report = RepoGuard(sandbox).check_secrets(RepoGuard(sandbox).guarded_files())
    assert not report.ok
    assert "aws_access_key_id" in report.critical_failures[0].message


def test_guard_flags_an_html_error_page_stored_as_data(sandbox):
    (sandbox.data_dir / "events" / "oops.json").write_text(
        "<!doctype html><html><body>403 Forbidden</body></html>", encoding="utf-8")
    report = RepoGuard(sandbox).check_html_error_pages(RepoGuard(sandbox).guarded_files())
    assert not report.ok


def test_guard_flags_excessive_row_duplication(sandbox):
    """The signature of a non-idempotent backfill."""
    path = sandbox.data_dir / "financial-facts" / "annual" / "DUPE.jsonl"
    path.write_text(('{"a":1}\n' * 50) + '{"b":2}\n', encoding="utf-8")
    report = RepoGuard(sandbox).check_duplicate_rows(RepoGuard(sandbox).guarded_files())
    assert not report.ok
    assert "duplicates" in report.critical_failures[0].message


def test_guard_flags_unexpected_schema_growth(sandbox):
    import json

    path = sandbox.data_dir / "financial-facts" / "annual" / "GROW.jsonl"
    first = {"a": 1}
    last = {"a": 1, **{f"f{i}": i for i in range(20)}}
    path.write_text(json.dumps(first) + "\n" + json.dumps(last) + "\n", encoding="utf-8")
    report = RepoGuard(sandbox).check_schema_growth(RepoGuard(sandbox).guarded_files())
    assert not report.ok


def test_guard_ignores_the_private_tree(sandbox):
    """The guard protects the repository; the private tree never enters it."""
    private = sandbox.private_dir / "market-prices"
    private.mkdir(parents=True)
    (private / "huge.pdf").write_bytes(b"%PDF" + b"x" * 10_000_000)
    guard = RepoGuard(sandbox)
    assert all("huge.pdf" not in str(f) for f in guard.guarded_files())
    assert guard.run().ok


# --- recorded connectivity status --------------------------------------------


CONNECTIVITY_RUN_ID = "30537966831"
CONNECTIVITY_VERIFIED_AT = "2026-07-30"


def _live_providers(real_settings):
    return {p: c for p, c in real_settings.sources()["providers"].items()
            if c.get("kind") == "http"}


def test_every_live_provider_records_the_connectivity_run(real_settings):
    """Provenance for the status: which run measured it, and when."""
    live = _live_providers(real_settings)
    assert len(live) == 7
    for provider_id, config in live.items():
        assert config.get("connectivity_run_id") == CONNECTIVITY_RUN_ID, provider_id
        assert config.get("connectivity_verified_at") == CONNECTIVITY_VERIFIED_AT, provider_id


def test_connectivity_status_uses_the_declared_vocabulary(real_settings):
    from pipeline.goh_dip_tong.validation.connectivity import OUTCOMES

    for provider_id, config in _live_providers(real_settings).items():
        assert config.get("connectivity_status") in OUTCOMES, provider_id


def test_access_controlled_providers_state_a_reason_and_reachable_ones_do_not(real_settings):
    """blocked_reason describes the network. It must agree with the status, or
    the file is telling two different stories about the same probe."""
    for provider_id, config in _live_providers(real_settings).items():
        status = config["connectivity_status"]
        reason = config.get("blocked_reason")
        if status == "ACCESS_CONTROLLED":
            assert reason, f"{provider_id}: refused but no blocked_reason"
            assert str(config.get("http_status")) == "403", provider_id
        elif status == "REACHABLE_UNVALIDATED":
            assert reason is None, f"{provider_id}: reachable but claims {reason!r}"


def test_connectivity_does_not_unlock_any_provider(real_settings):
    """The whole point: a reachable source is still disabled and still
    MANUAL_REVIEW_REQUIRED. Reachability is not permission."""
    for provider_id, config in _live_providers(real_settings).items():
        assert config["enabled"] is False, provider_id
        assert config["rights_status"] == "MANUAL_REVIEW_REQUIRED", provider_id

    reachable = [p for p, c in _live_providers(real_settings).items()
                 if c["connectivity_status"] == "REACHABLE_UNVALIDATED"]
    assert reachable, "expected some reachable providers to guard against"
    for provider_id in reachable:
        assert not RightsGate(real_settings.sources()).is_enabled(provider_id)


def test_source_register_records_the_same_connectivity_outcome(real_settings):
    """sources.yml and the register must not disagree about what happened."""
    register = (real_settings.docs_dir / "SOURCE_REGISTER.md").read_text(encoding="utf-8")
    assert CONNECTIVITY_RUN_ID in register
    for provider_id, config in _live_providers(real_settings).items():
        assert config["connectivity_status"] in register, provider_id
