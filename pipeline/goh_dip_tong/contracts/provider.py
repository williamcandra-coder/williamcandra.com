"""The provider-neutral collector interface (spec section 1.6).

Every source — live HTTP, committed fixture, or a future object-store adapter —
implements the same four verbs. Nothing downstream of :meth:`DataProvider.parse`
knows or cares which kind it was talking to, which is what makes a fixture a
genuine stand-in for a live source rather than a special case.

    discover(context) -> list[DiscoveredItem]
    fetch(item)       -> RawPayload
    parse(payload)    -> list[CanonicalRecord]
    validate(records) -> ValidationReport
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from .enums import NON_RUNNABLE_RIGHTS, RightsStatus
from .records import DiscoveredItem, RawPayload, ValidationReport


class ProviderDisabledError(RuntimeError):
    """Raised when something tries to run a provider that policy forbids.

    Deliberately an error rather than a silent empty result: a disabled source
    that quietly returns nothing looks identical to a source with no new data,
    and that ambiguity is how a pipeline ends up appearing healthy while
    collecting nothing.
    """


class RightsViolationError(RuntimeError):
    """Raised when a write would exceed what the source's rights permit."""


class ProviderContext:
    """Everything a provider needs to know about the run it is part of."""

    def __init__(
        self,
        run_id: str,
        tickers: Optional[list] = None,
        data_type: Optional[str] = None,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
        now: Optional[str] = None,
        settings: Any = None,
    ) -> None:
        self.run_id = run_id
        self.tickers = tickers or []
        self.data_type = data_type
        self.start_year = start_year
        self.end_year = end_year
        self.now = now
        self.settings = settings

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"ProviderContext(run_id={self.run_id!r}, tickers={len(self.tickers)}, "
            f"data_type={self.data_type!r}, years={self.start_year}-{self.end_year})"
        )


class DataProvider(ABC):
    """Base class for every source."""

    #: Stable id; must match a key under `providers:` in sources.yml.
    provider_id: str = "unset"
    #: Populated from sources.yml at construction. Never hard-coded in a subclass.
    rights_status: RightsStatus = RightsStatus.MANUAL_REVIEW_REQUIRED
    #: Data types this provider can serve.
    data_types: tuple = ()

    def __init__(self, config: dict, settings: Any = None) -> None:
        self.config = config or {}
        self.settings = settings
        self.provider_id = self.config.get("provider_id", self.provider_id)
        self.rights_status = RightsStatus(
            self.config.get("rights_status", RightsStatus.MANUAL_REVIEW_REQUIRED)
        )
        self.enabled = bool(self.config.get("enabled", False))
        self.authoritative = bool(self.config.get("authoritative", False))

    # -- policy ------------------------------------------------------------

    @property
    def runnable(self) -> bool:
        """Two independent locks. Flipping `enabled: true` on a provider whose
        rights are still MANUAL_REVIEW_REQUIRED does not make it runnable."""
        return self.enabled and self.rights_status not in NON_RUNNABLE_RIGHTS

    def ensure_runnable(self) -> None:
        if not self.enabled:
            raise ProviderDisabledError(
                f"provider {self.provider_id!r} is disabled in sources.yml"
            )
        if self.rights_status in NON_RUNNABLE_RIGHTS:
            raise ProviderDisabledError(
                f"provider {self.provider_id!r} has rights_status="
                f"{self.rights_status}; resolve rights and record a dated row in "
                f"docs/goh-dip-tong/SOURCE_REGISTER.md before enabling"
            )

    # -- the four verbs ----------------------------------------------------

    @abstractmethod
    def discover(self, context: ProviderContext) -> list:
        """List what is available without downloading it."""

    @abstractmethod
    def fetch(self, item: DiscoveredItem) -> RawPayload:
        """Retrieve one discovered item."""

    @abstractmethod
    def parse(self, payload: RawPayload) -> list:
        """Turn a raw payload into canonical records."""

    @abstractmethod
    def validate(self, records: list) -> ValidationReport:
        """Check canonical records before anything is written."""

    # -- convenience -------------------------------------------------------

    def collect(self, context: ProviderContext) -> tuple:
        """discover -> fetch -> parse for every item, fail-soft per item.

        Returns ``(records, failures)``. One bad item never aborts the others;
        that is the fail-soft-by-ticker rule from spec section 1.7.
        """
        self.ensure_runnable()
        records: list = []
        failures: list = []
        for item in self.discover(context):
            try:
                payload = self.fetch(item)
                records.extend(self.parse(payload))
            except Exception as exc:  # noqa: BLE001 - deliberate fail-soft boundary
                failures.append(
                    {
                        "ticker": item.ticker or item.item_id,
                        "reason": f"{type(exc).__name__}: {exc}",
                        "stage": "fetch/parse",
                    }
                )
        return records, failures

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"{type(self).__name__}(id={self.provider_id!r}, "
            f"enabled={self.enabled}, rights={self.rights_status})"
        )
