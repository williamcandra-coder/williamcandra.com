"""Generation of the config files the Stage 3 UI reads.

Produces `idx30.current.json`, `companies.json` and `categories.json` from a
collected universe, applying the model mapping from `models.yml`.

The onboarding rule lives here and is the reason model assignment is a separate,
explicit step rather than a field the source happens to provide: if a
classification has no supported model, the constituent gets `modelFamily: null`
and `coverageStatus: ONBOARDING`. Nothing gets a generic valuation model by
default, because a plausible-looking wrong model is more dangerous than an
honest gap.
"""

from __future__ import annotations

from typing import Iterable, Optional

from ..contracts.enums import CoverageStatus
from ..contracts.records import Constituent
from ..settings import Settings, get_settings, utc_now_iso
from .writers import (
    content_hash,
    read_json,
    stable_content_hash,
    write_document_if_changed,
)

SCHEMA_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Model mapping
# ---------------------------------------------------------------------------


def resolve_model_family(
    sector_code: str, industry_code: str, models_config: dict
) -> Optional[str]:
    """Industry first, then sector. Unmapped returns None."""
    industry_map = models_config.get("industry_map", {}) or {}
    sector_map = models_config.get("sector_map", {}) or {}
    return industry_map.get(industry_code) or sector_map.get(sector_code)


def resolve_coverage_status(
    ticker: str, model_family: Optional[str], models_config: dict
) -> CoverageStatus:
    overrides = models_config.get("overrides", {}) or {}
    override = (overrides.get(ticker) or {}).get("coverage_status")
    if override:
        return CoverageStatus(override)

    if model_family is None:
        return CoverageStatus.ONBOARDING

    families = models_config.get("model_families", {}) or {}
    if not families.get(model_family, {}).get("supported", False):
        # Declared but not buildable is still not covered.
        return CoverageStatus.ONBOARDING

    return CoverageStatus(models_config.get("default_coverage_status", "FINANCIALS"))


def apply_model_mapping(constituents: Iterable[Constituent], models_config: dict) -> list:
    """Return constituents with modelFamily and coverageStatus resolved."""
    out = []
    for c in constituents:
        family = resolve_model_family(c.sector_code, c.industry_code, models_config)
        coverage = resolve_coverage_status(c.ticker, family, models_config)
        # An unsupported family is recorded as no family at all, so the config
        # never advertises a model the engine cannot actually run.
        if coverage == CoverageStatus.ONBOARDING:
            families = models_config.get("model_families", {}) or {}
            if family is not None and not families.get(family, {}).get("supported", False):
                family = None
        out.append(
            Constituent(
                ticker=c.ticker,
                name=c.name,
                sector_code=c.sector_code,
                sector_name=c.sector_name,
                industry_code=c.industry_code,
                industry_name=c.industry_name,
                model_family=family,
                coverage_status=coverage,
                active=c.active,
                entered_at=c.entered_at,
                source_ref=c.source_ref,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Document builders
# ---------------------------------------------------------------------------


def build_idx30_document(
    constituents: Iterable[Constituent],
    effective_from: str,
    source: dict,
    effective_to: Optional[str] = None,
    provenance: str = "FIXTURE",
    authoritative: bool = False,
) -> dict:
    """Assemble idx30.current.json.

    Constituents are sorted by ticker so a real membership change produces a
    small, readable diff instead of a reshuffle.
    """
    rows = sorted((c.to_json() for c in constituents), key=lambda r: r["ticker"])
    document = {
        "schemaVersion": SCHEMA_VERSION,
        "indexCode": "IDX30",
        "effectiveFrom": effective_from,
        "effectiveTo": effective_to,
        "generatedAt": utc_now_iso(),
        "authoritative": authoritative,
        "provenance": provenance,
        "source": source,
        "constituents": rows,
    }
    # The hash covers content, not when we looked: regenerating an unchanged
    # universe must produce an unchanged hash, so generatedAt and the source's
    # retrievedAt are both excluded.
    document["contentHash"] = stable_content_hash(
        {k: v for k, v in document.items() if k != "contentHash"}
    )
    return document


def build_companies_document(
    constituents: Iterable[Constituent],
    previous: Optional[dict] = None,
    observed_at: Optional[str] = None,
) -> dict:
    """Assemble companies.json, carrying former members forward.

    A company that has left the index keeps its row with ``inIdx30: false`` and
    its full name/classification history. Deleting it would break every past
    research snapshot that references it.
    """
    observed_at = (observed_at or utc_now_iso())[:10]
    existing = {c["ticker"]: c for c in (previous or {}).get("companies", [])}
    current_tickers = set()
    companies = []

    for c in sorted(constituents, key=lambda x: x.ticker):
        current_tickers.add(c.ticker)
        prior = existing.get(c.ticker, {})

        name_history = list(prior.get("nameHistory", []))
        if not name_history or name_history[-1]["name"] != c.name:
            name_history.append({"name": c.name, "observedAt": observed_at})

        classification_history = list(prior.get("classificationHistory", []))
        latest = classification_history[-1] if classification_history else None
        entry = {
            "sectorCode": c.sector_code,
            "industryCode": c.industry_code,
            "modelFamily": c.model_family,
            "observedAt": observed_at,
        }
        if not latest or (
            latest["sectorCode"],
            latest["industryCode"],
            latest.get("modelFamily"),
        ) != (c.sector_code, c.industry_code, c.model_family):
            classification_history.append(entry)

        companies.append(
            {
                "ticker": c.ticker,
                "name": c.name,
                "legalName": prior.get("legalName"),
                "listingIdentity": prior.get("listingIdentity"),
                "sectorCode": c.sector_code,
                "sectorName": c.sector_name,
                "industryCode": c.industry_code,
                "industryName": c.industry_name,
                "modelFamily": c.model_family,
                "coverageStatus": str(c.coverage_status),
                "inIdx30": True,
                "firstSeenAt": prior.get("firstSeenAt", observed_at),
                "lastSeenAt": observed_at,
                "reportingCurrency": prior.get("reportingCurrency"),
                "sourceRef": c.source_ref,
                "nameHistory": name_history,
                "classificationHistory": classification_history,
            }
        )

    # Retain everyone who has ever been a member.
    for ticker, prior in sorted(existing.items()):
        if ticker in current_tickers:
            continue
        former = dict(prior)
        former["inIdx30"] = False
        companies.append(former)

    companies.sort(key=lambda r: r["ticker"])
    document = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": utc_now_iso(),
        "companies": companies,
    }
    # Stable, not raw: every company row carries a lastSeenAt that moves with the
    # run date, so a raw hash would change daily and reintroduce the churn the
    # volatile-field strip exists to remove.
    document["contentHash"] = stable_content_hash({"companies": companies})
    return document


def build_categories_document(
    constituents: Iterable[Constituent], models_config: dict
) -> dict:
    """Assemble categories.json: the sector/industry master with counts."""
    families = models_config.get("model_families", {}) or {}
    sectors: dict = {}
    industries: dict = {}

    for c in sorted(constituents, key=lambda x: x.ticker):
        sector = sectors.setdefault(
            c.sector_code,
            {"sectorCode": c.sector_code, "sectorName": c.sector_name,
             "industryCodes": [], "tickers": [], "constituentCount": 0},
        )
        sector["tickers"].append(c.ticker)
        sector["constituentCount"] += 1
        if c.industry_code not in sector["industryCodes"]:
            sector["industryCodes"].append(c.industry_code)

        industry = industries.setdefault(
            c.industry_code,
            {"industryCode": c.industry_code, "industryName": c.industry_name,
             "sectorCode": c.sector_code, "modelFamily": c.model_family,
             "modelSupported": bool(families.get(c.model_family, {}).get("supported", False))
             if c.model_family else False,
             "tickers": [], "constituentCount": 0},
        )
        industry["tickers"].append(c.ticker)
        industry["constituentCount"] += 1

    for entry in sectors.values():
        entry["industryCodes"].sort()
        entry["tickers"].sort()
    for entry in industries.values():
        entry["tickers"].sort()

    payload = {
        "sectors": sorted(sectors.values(), key=lambda r: r["sectorCode"]),
        "industries": sorted(industries.values(), key=lambda r: r["industryCode"]),
        "modelFamilies": sorted(
            (
                {
                    "modelFamily": name,
                    "label": cfg.get("label", name),
                    "supported": bool(cfg.get("supported", False)),
                    "basis": cfg.get("basis"),
                }
                for name, cfg in families.items()
            ),
            key=lambda r: r["modelFamily"],
        ),
    }
    document = {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": utc_now_iso(),
        **payload,
    }
    document["contentHash"] = content_hash(payload)
    return document


# ---------------------------------------------------------------------------
# Loading back
# ---------------------------------------------------------------------------


def load_current_constituents(settings: Optional[Settings] = None) -> list:
    """Read the committed universe back into Constituent objects.

    Returns an empty list when nothing has been generated yet, so the first run
    naturally produces an all-ADDED history.
    """
    settings = settings or get_settings()
    document = read_json(settings.idx30_current)
    if not document:
        return []
    return [
        Constituent(
            ticker=row["ticker"],
            name=row["name"],
            sector_code=row["sectorCode"],
            sector_name=row["sectorName"],
            industry_code=row["industryCode"],
            industry_name=row["industryName"],
            model_family=row["modelFamily"],
            coverage_status=CoverageStatus(row["coverageStatus"]),
            active=row["active"],
            entered_at=row.get("enteredAt"),
            source_ref=row.get("sourceRef", "unknown"),
        )
        for row in document.get("constituents", [])
    ]


def write_configs(
    idx30: dict,
    companies: dict,
    categories: dict,
    settings: Optional[Settings] = None,
) -> dict:
    """Write all three generated configs. Returns which of them changed."""
    settings = settings or get_settings()
    # write_document_if_changed ignores generatedAt, so regenerating an
    # unchanged universe leaves all three files completely untouched.
    return {
        "idx30.current.json": write_document_if_changed(settings.idx30_current, idx30),
        "companies.json": write_document_if_changed(settings.companies_file, companies),
        "categories.json": write_document_if_changed(settings.categories_file, categories),
    }
