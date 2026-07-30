"""Provider registry: maps sources.yml entries to provider classes.

A provider class is only ever constructed with its config from sources.yml, so
rights and enablement always come from the reviewed policy file rather than from
a default baked into the code.
"""

from __future__ import annotations

from typing import Optional

from ..contracts.provider import DataProvider, ProviderDisabledError
from ..settings import Settings, get_settings
from .disclosures import DisclosureFixtureProvider, DisclosureLiveProvider
from .financials import FinancialFixtureProvider, FinancialLiveProvider
from .idx30_registry import Idx30FixtureProvider, Idx30LiveProvider
from .macro import MacroFixtureProvider, MacroLiveProvider
from .market_prices import MarketPriceFixtureProvider, MarketPriceLiveProvider

PROVIDER_CLASSES = {
    "fixture_idx30_registry": Idx30FixtureProvider,
    "fixture_market_prices": MarketPriceFixtureProvider,
    "fixture_disclosures": DisclosureFixtureProvider,
    "fixture_financials": FinancialFixtureProvider,
    "fixture_macro": MacroFixtureProvider,
    "idx_index_constituents": Idx30LiveProvider,
    "idx_market_prices": MarketPriceLiveProvider,
    "idx_disclosures": DisclosureLiveProvider,
    "idx_financials": FinancialLiveProvider,
    "bank_indonesia": MacroLiveProvider,
    "bps": MacroLiveProvider,
    "ojk": MacroLiveProvider,
}

#: Preference order when a data type has several candidate providers. An
#: authoritative live source always outranks a fixture, so enabling one is
#: enough to take over — no code change required.
DATA_TYPE_PREFERENCE = {
    "index_membership": ["idx_index_constituents", "fixture_idx30_registry"],
    "market_prices_daily": ["idx_market_prices", "fixture_market_prices"],
    "disclosure_metadata": ["idx_disclosures", "fixture_disclosures"],
    "financial_facts": ["idx_financials", "fixture_financials"],
    "macro_series": ["bank_indonesia", "bps", "ojk", "fixture_macro"],
}


class ProviderRegistry:
    def __init__(self, settings: Optional[Settings] = None, sources_config: Optional[dict] = None):
        self.settings = settings or get_settings()
        self.sources = sources_config if sources_config is not None else self.settings.sources()
        self.provider_configs = self.sources.get("providers", {}) or {}

    def known_ids(self) -> list:
        return sorted(self.provider_configs)

    def build(self, provider_id: str) -> DataProvider:
        if provider_id not in self.provider_configs:
            raise KeyError(
                f"provider {provider_id!r} is not declared in sources.yml; "
                f"known: {self.known_ids()}"
            )
        if provider_id not in PROVIDER_CLASSES:
            raise KeyError(
                f"provider {provider_id!r} is declared in sources.yml but has no "
                f"implementation class registered"
            )
        config = dict(self.provider_configs[provider_id] or {})
        config["provider_id"] = provider_id
        return PROVIDER_CLASSES[provider_id](config, settings=self.settings)

    def runnable(self, provider_id: str) -> bool:
        try:
            return self.build(provider_id).runnable
        except KeyError:
            return False

    def resolve(self, data_type: str, preferred: Optional[str] = None) -> DataProvider:
        """Pick the best runnable provider for a data type.

        Raises rather than returning None. A pipeline that quietly finds no
        provider looks exactly like a pipeline that found no new data.
        """
        if preferred:
            provider = self.build(preferred)
            provider.ensure_runnable()
            return provider

        candidates = DATA_TYPE_PREFERENCE.get(data_type, [])
        for provider_id in candidates:
            if provider_id in self.provider_configs and self.runnable(provider_id):
                return self.build(provider_id)

        blocked = [
            f"{pid} (enabled={self.provider_configs.get(pid, {}).get('enabled', False)}, "
            f"rights={self.provider_configs.get(pid, {}).get('rights_status', '?')})"
            for pid in candidates
            if pid in self.provider_configs
        ]
        raise ProviderDisabledError(
            f"no runnable provider for data type {data_type!r}. Candidates: "
            + ("; ".join(blocked) if blocked else "none declared")
        )

    def status_table(self) -> list:
        """One row per declared provider, for the quality report and CLI."""
        rows = []
        for provider_id in self.known_ids():
            config = self.provider_configs[provider_id] or {}
            rows.append(
                {
                    "providerId": provider_id,
                    "kind": config.get("kind", "?"),
                    "enabled": bool(config.get("enabled", False)),
                    "rightsStatus": config.get("rights_status", "MANUAL_REVIEW_REQUIRED"),
                    "runnable": self.runnable(provider_id),
                    "authoritative": bool(config.get("authoritative", False)),
                    "dataTypes": list(config.get("data_types", [])),
                    "blockedReason": config.get("blocked_reason"),
                    "implemented": provider_id in PROVIDER_CLASSES,
                }
            )
        return rows
