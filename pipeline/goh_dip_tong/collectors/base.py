"""Shared provider behaviour: fixture loading, HTTP with timeout and retry.

Both provider kinds live here so a live adapter and its fixture stand-in differ
only in where the bytes come from — everything after `fetch` is identical code.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Optional

from ..contracts.provider import DataProvider, ProviderContext
from ..contracts.records import DiscoveredItem, RawPayload
from ..parsers.guards import PayloadRejected, assert_is_data
from ..settings import get_settings, utc_now_iso


class FetchError(RuntimeError):
    """A retryable transport failure that exhausted its retries."""


def with_retry(
    call: Callable[[], Any],
    max_retries: int = 3,
    backoff_seconds: float = 2.0,
    sleep: Callable[[float], None] = time.sleep,
    retry_on: tuple = (Exception,),
    give_up_on: tuple = (PayloadRejected,),
) -> Any:
    """Retry with exponential backoff.

    ``give_up_on`` matters as much as ``retry_on``: a rejected payload is a
    deterministic failure. Retrying a bot-check page five times just means five
    requests at a source that has already said no.
    """
    attempt = 0
    last: Optional[BaseException] = None
    while attempt <= max_retries:
        try:
            return call()
        except give_up_on:
            raise
        except retry_on as exc:  # noqa: PERF203 - retry loop
            last = exc
            attempt += 1
            if attempt > max_retries:
                break
            sleep(backoff_seconds * (2 ** (attempt - 1)))
    raise FetchError(f"failed after {max_retries} retries: {type(last).__name__}: {last}")


class FixtureProvider(DataProvider):
    """A provider whose bytes come from a committed file.

    Not a mock: it goes through the same guards, parsers, normalization and
    validation as a live source. The only thing it skips is the network.
    """

    def __init__(self, config: dict, settings: Any = None) -> None:
        super().__init__(config, settings)
        self.settings = settings or get_settings()
        raw_path = self.config.get("fixture_path")
        if not raw_path:
            raise ValueError(f"{self.provider_id}: fixture provider needs a fixture_path")
        self.fixture_path = self.settings.repo_root / raw_path

    def load_fixture(self, path: Optional[Path] = None, expect: Optional[str] = None) -> str:
        path = Path(path or self.fixture_path)
        if not path.exists():
            raise FileNotFoundError(f"{self.provider_id}: fixture not found: {path}")
        text = path.read_text(encoding="utf-8")
        assert_is_data(text, expect=expect, source=str(path))
        return text

    def fetch(self, item: DiscoveredItem) -> RawPayload:
        path = Path(item.hint.get("fixture_path", self.fixture_path))
        expect = item.hint.get("expect")
        text = self.load_fixture(path, expect=expect)
        return RawPayload(
            item=item,
            content=text,
            media_type=item.hint.get("media_type", "application/json"),
            retrieved_at=utc_now_iso(),
            byte_size=len(text.encode("utf-8")),
            http_status=None,
            from_fixture=True,
        )


class HttpProvider(DataProvider):
    """A live HTTP provider.

    Every Stage 1 subclass of this is disabled: the hosts are unreachable from
    the build environment and the rights are undocumented. The class exists so
    enabling one later is a config change plus a parser, not an architecture
    change.
    """

    def __init__(self, config: dict, settings: Any = None) -> None:
        super().__init__(config, settings)
        self.settings = settings or get_settings()
        defaults = (self.settings.sources().get("defaults") or {})
        self.timeout = float(config.get("timeout_seconds", defaults.get("timeout_seconds", 20)))
        self.max_retries = int(config.get("max_retries", defaults.get("max_retries", 3)))
        self.backoff = float(
            config.get("retry_backoff_seconds", defaults.get("retry_backoff_seconds", 2.0))
        )
        self.user_agent = config.get("user_agent", defaults.get("user_agent", "goh-dip-tong/1.0"))
        ceilings = defaults.get("ceilings") or {}
        self.max_payload_bytes = int(ceilings.get("max_payload_bytes", 25 * 1024 * 1024))

    def fetch(self, item: DiscoveredItem) -> RawPayload:
        self.ensure_runnable()  # never reachable while the provider is disabled

        import requests  # imported lazily so the pipeline runs without network deps

        def _call():
            response = requests.get(
                item.url,
                timeout=self.timeout,
                headers={"User-Agent": self.user_agent, "Accept": "application/json, text/csv"},
            )
            response.raise_for_status()
            if len(response.content) > self.max_payload_bytes:
                raise PayloadRejected(
                    f"{item.url}: payload is {len(response.content)} bytes, over the "
                    f"{self.max_payload_bytes}-byte ceiling"
                )
            media_type = response.headers.get("Content-Type", "")
            # Guard before anything downstream can mistake an error page for data.
            assert_is_data(
                response.text,
                media_type=media_type,
                expect=item.hint.get("expect"),
                source=item.url or item.item_id,
            )
            return RawPayload(
                item=item,
                content=response.text,
                media_type=media_type,
                retrieved_at=utc_now_iso(),
                byte_size=len(response.content),
                http_status=response.status_code,
                from_fixture=False,
            )

        return with_retry(_call, max_retries=self.max_retries, backoff_seconds=self.backoff)

    def discover(self, context: ProviderContext) -> list:
        self.ensure_runnable()
        return []

    def parse(self, payload: RawPayload) -> list:
        raise NotImplementedError(
            f"{self.provider_id}: no parser implemented. A live parser must be written "
            f"against a real response, not guessed — the host is unreachable from this "
            f"environment, so writing one now would produce untested code that looks "
            f"finished."
        )

    def validate(self, records: list):
        from ..contracts.records import ValidationReport

        return ValidationReport()
