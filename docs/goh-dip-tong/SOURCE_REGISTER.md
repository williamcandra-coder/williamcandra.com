# Goh Dip Tong — Source Register

One row per data source. This file and `config/goh-dip-tong/sources.yml` are
cross-checked at runtime: the rights gate refuses to run if a provider claims a
public right here that it does not declare there, or vice versa. `gdt-data-quality`
fails the build on any inconsistency.

**A right is `no` until it is documented.** Nothing on this page may be flipped
to `yes` on the basis of "it looked public" or "the robots.txt allowed it". A
`yes` requires a reviewed, dated reading of the operator's actual terms, recorded
in the notes for that source.

Last reviewed: **2026-07-30** · Reviewer: **repository owner (pending counter-signature)**

---

## Status summary

| | Count | Providers |
|---|---|---|
| Enabled (fixture) | 5 | `fixture_idx30_registry`, `fixture_market_prices`, `fixture_disclosures`, `fixture_financials`, `fixture_macro` |
| Disabled (live) | 7 | `idx_index_constituents`, `idx_market_prices`, `idx_disclosures`, `idx_financials`, `bank_indonesia`, `bps`, `ojk` |
| Redistribution approved | 0 | — |

**No live source is enabled.** Every live adapter is blocked by two independent
locks: `enabled: false` in `sources.yml`, and a `rights_status` of
`MANUAL_REVIEW_REQUIRED` that the rights gate refuses to run regardless of the
enabled flag.

### Verified connectivity — GitHub Actions run [30537966831](https://github.com/williamcandra-coder/williamcandra.com/actions/runs/30537966831), 2026-07-30

| Provider | HTTP | `connectivity_status` |
|---|---:|---|
| `bank_indonesia` | 302 | `REACHABLE_UNVALIDATED` |
| `ojk` | 302 | `REACHABLE_UNVALIDATED` |
| `bps` | 403 | `ACCESS_CONTROLLED` |
| `idx_index_constituents` | 403 | `ACCESS_CONTROLLED` |
| `idx_market_prices` | 403 | `ACCESS_CONTROLLED` |
| `idx_disclosures` | 403 | `ACCESS_CONTROLLED` |
| `idx_financials` | 403 | `ACCESS_CONTROLLED` |

**This changes the access column only. It changes no right.** A hosted runner
reaches all seven hosts — the earlier "network-blocked" reading came from the
build sandbox, which was refused at its own egress proxy. Five of the seven then
refuse the runner directly with HTTP 403, which is the operator declining
automated access, not an obstacle to route around. Two responded with a redirect
to a human-facing landing page, which is not evidence of a usable data endpoint.

`REACHABLE_UNVALIDATED` and a null `blocked_reason` are **not** clearance. Every
permission cell below still reads *no — not reviewed*, and every provider is
still disabled.

---

## 1. `fixture_idx30_registry`

| Field | Value |
|---|---|
| Provider ID | `fixture_idx30_registry` |
| Operator | This repository (development fixture) |
| Official URL | n/a — `pipeline/goh_dip_tong/tests/fixtures/idx30/2026H1.json` |
| Data types | index membership, company identity, sector classification |
| Access method | Local file |
| Authentication | None |
| Source authority | **Not authoritative.** Development fixture. |
| Storage permission | yes |
| Public-display permission | yes |
| Redistribution permission | no |
| Attribution | "Development fixture — not IDX data, not an authoritative constituent list." |
| Rate limits | n/a |
| Update cadence | Manual |
| Fallback | n/a |
| Enabled | **yes** |
| Last validation | 2026-07-30 |

**Known limitations.** This is a plausible 30-ticker development universe
authored in this repository, not a retrieved IDX publication. Ticker symbols,
legal names and IDX-IC sector labels are factual identity metadata, which is why
storage and display are permitted; the *composition* is not verified against any
effective IDX30 list. Every artefact generated from it carries
`provenance: "FIXTURE"` and `authoritative: false`, and the Stage 3 UI is
required to show a development-data notice when it sees them.

---

## 2. `fixture_market_prices`

| Field | Value |
|---|---|
| Provider ID | `fixture_market_prices` |
| Operator | This repository (development fixture) |
| Official URL | n/a — `pipeline/goh_dip_tong/tests/fixtures/market-prices/daily-sample.csv` |
| Data types | daily OHLCV, corporate-action flags |
| Access method | Local file |
| Authentication | None |
| Source authority | Not authoritative |
| Storage permission | yes (private tree only) |
| Public-display permission | **no** |
| Redistribution permission | **no** |
| Attribution | n/a |
| Rate limits | n/a |
| Update cadence | Manual |
| Fallback | n/a |
| Enabled | **yes** |
| Last validation | 2026-07-30 |

**Known limitations.** Deliberately held at `PRIVATE_RESEARCH_ONLY` — the most
restrictive useful status — even though the data is synthetic. Market prices are
the one data type whose redistribution rights are genuinely unresolved, so the
fixture is held to exactly the standard the live provider will be held to. The
rights gate routes its output to `data/goh-dip-tong/_private/`, which is
git-ignored. This keeps the daily-update path fully exercisable while making it
structurally impossible to commit a price series before rights are documented.

---

## 3. `fixture_disclosures`

| Field | Value |
|---|---|
| Provider ID | `fixture_disclosures` |
| Operator | This repository (development fixture) |
| Official URL | n/a — `pipeline/goh_dip_tong/tests/fixtures/disclosures/metadata-sample.json` |
| Data types | disclosure metadata, events |
| Access method | Local file |
| Authentication | None |
| Source authority | Not authoritative |
| Storage permission | yes (metadata only) |
| Public-display permission | yes (metadata only) |
| Redistribution permission | no |
| Attribution | "Development fixture — synthetic disclosure metadata." |
| Rate limits | n/a |
| Update cadence | Manual |
| Fallback | n/a |
| Enabled | **yes** |
| Last validation | 2026-07-30 |

**Known limitations.** Metadata only: stable id, official URL, title, type,
publication date, hash. No document text is stored and no summary is
synthesised from source prose. A document over 1 MiB, or any restricted
document, is represented by a manifest row recording the URL, size, media type
and retrieval outcome — never the document itself.

---

## 4. `fixture_financials`

| Field | Value |
|---|---|
| Provider ID | `fixture_financials` |
| Operator | This repository (development fixture) |
| Official URL | n/a — `pipeline/goh_dip_tong/tests/fixtures/financials/facts-sample.json` |
| Data types | financial facts, statements, restatements |
| Access method | Local file |
| Authentication | None |
| Source authority | Not authoritative |
| Storage permission | yes (derived output) |
| Public-display permission | yes (derived output) |
| Redistribution permission | no |
| Attribution | "Development fixture — synthetic XBRL-shaped facts." |
| Rate limits | n/a |
| Update cadence | Manual |
| Fallback | n/a |
| Enabled | **yes** |
| Last validation | 2026-07-30 |

**Known limitations.** Shaped like an XBRL fact table (concept id, context
period, unit, scale, sign) so a real XBRL adapter can be swapped in without
touching the parser contract. Contains one deliberate restatement, one
unreported concept and one unparseable cell so the revision, missing and
extraction-failure paths are all exercised. **XBRL extraction is not analytical
correctness** — a value that parses cleanly can still be the wrong concept.

---

## 5. `fixture_macro`

| Field | Value |
|---|---|
| Provider ID | `fixture_macro` |
| Operator | This repository (development fixture) |
| Official URL | n/a — `pipeline/goh_dip_tong/tests/fixtures/macro/series-sample.json` |
| Data types | macro series |
| Access method | Local file |
| Authentication | None |
| Source authority | Not authoritative |
| Storage permission | yes |
| Public-display permission | yes |
| Redistribution permission | no |
| Attribution | "Development fixture — synthetic macro series." |
| Rate limits | n/a |
| Update cadence | Manual |
| Fallback | n/a |
| Enabled | **yes** |
| Last validation | 2026-07-30 |

**Known limitations.** Only the three series registered in the model registry
(`BI_7DRR`, `BPS_CPI_YOY`, `OJK_BANK_NPL_GROSS`) are collected. Each observation
keeps its observation period, publication date and retrieval timestamp as three
separate fields plus a release vintage, so a revised observation is a new row
rather than an overwrite.

---

## 6. `idx_index_constituents` — DISABLED

| Field | Value |
|---|---|
| Provider ID | `idx_index_constituents` |
| Operator | PT Bursa Efek Indonesia (IDX) |
| Official URL | https://www.idx.co.id/en/market-data/stock-market-data/index-constituents/ |
| Data types | index membership, company identity, sector classification |
| Access method | Public HTTP page |
| Authentication | None |
| Source authority | **Authoritative** for IDX30 membership |
| Storage permission | **no — not reviewed** |
| Public-display permission | **no — not reviewed** |
| Redistribution permission | **no — not reviewed** |
| Attribution | "Source: PT Bursa Efek Indonesia (IDX)" |
| Rate limits | Not established |
| Update cadence | Semi-annual index review (Jan/Feb, Jul/Aug) plus ad-hoc |
| Fallback | `fixture_idx30_registry` |
| Enabled | **no** |
| Last validation | 2026-07-30 (connectivity only) |

**Blocked because.** Two independent reasons.
1. **Access** — `ACCESS_CONTROLLED`. A GitHub Actions runner reaches the host and
   IDX answers **HTTP 403** (run 30537966831, 2026-07-30). Egress is not the
   obstacle; IDX is declining automated access from that address range.
2. **Rights** — IDX's terms of use have not been read or recorded. No storage,
   display or redistribution right may be assumed.

**To enable.** (a) resolve the 403 at the operator level — an official data
agreement, a licensed vendor, or a documented permitted-use path; (b) read and
record IDX's terms covering storage and public display of constituent metadata;
(c) fill in the three permission rows above with a date; (d) set `enabled: true`
and a resolved `rights_status` in `sources.yml`; (e) implement `parse()` against
a real captured response. **Do not** bypass the 403, any rate limit, anti-bot
measure or licensing restriction — a provider that needs circumvention to work
is a provider that must stay disabled.

---

## 7. `idx_market_prices` — DISABLED

| Field | Value |
|---|---|
| Provider ID | `idx_market_prices` |
| Operator | PT Bursa Efek Indonesia (IDX) |
| Official URL | https://www.idx.co.id/en/market-data/trading-summary/stock-summary/ |
| Data types | daily OHLCV, corporate actions |
| Access method | Public HTTP page |
| Authentication | None |
| Source authority | **Authoritative** for IDX trading data |
| Storage permission | **no — not reviewed** |
| Public-display permission | **no — not reviewed** |
| Redistribution permission | **no — not reviewed** |
| Attribution | "Source: PT Bursa Efek Indonesia (IDX)" |
| Rate limits | Not established |
| Update cadence | Each trading day after the 16:00 WIB close |
| Fallback | `fixture_market_prices` |
| Enabled | **no** |
| Last validation | 2026-07-30 (connectivity only) |

**Blocked because.** `ACCESS_CONTROLLED` — the host answered **HTTP 403** to a
GitHub Actions runner (run 30537966831, 2026-07-30) — **and** rights unreviewed.

**Additional constraint.** Market-price redistribution is the highest-risk right
in this project. Even once reachable and reviewed, this provider must first run
at `PRIVATE_RESEARCH_ONLY` so its output lands in the git-ignored tree, and be
promoted only after a separate, explicit rights decision. Adjusted close prices
require the adjustment methodology to be documented as well as the rights — the
schema refuses an `adjustedClose` without an `adjustmentMethodology`.

---

## 8. `idx_disclosures` — DISABLED

| Field | Value |
|---|---|
| Provider ID | `idx_disclosures` |
| Operator | PT Bursa Efek Indonesia (IDX) |
| Official URL | https://www.idx.co.id/en/listed-companies/company-announcement/ |
| Data types | disclosure metadata, events |
| Access method | Public HTTP page |
| Authentication | None |
| Source authority | **Authoritative** for issuer disclosures |
| Storage permission | **no — not reviewed** |
| Public-display permission | **no — not reviewed** |
| Redistribution permission | **no — not reviewed** |
| Attribution | "Source: PT Bursa Efek Indonesia (IDX)" |
| Rate limits | Not established |
| Update cadence | Intraday |
| Fallback | `fixture_disclosures` |
| Enabled | **no** |
| Last validation | 2026-07-30 (connectivity only) |

**Blocked because.** `ACCESS_CONTROLLED` — the host answered **HTTP 403** to a
GitHub Actions runner (run 30537966831, 2026-07-30) — and rights unreviewed.

**Additional constraint.** Metadata-only by design. Announcement PDFs must never
be committed; they become a manifest row (official URL, hash, retrieval
outcome). Full copyrighted article or announcement text must never be stored or
republished.

---

## 9. `idx_financials` — DISABLED

| Field | Value |
|---|---|
| Provider ID | `idx_financials` |
| Operator | PT Bursa Efek Indonesia (IDX); issuer filings |
| Official URL | https://www.idx.co.id/en/listed-companies/financial-statements-and-annual-report/ |
| Data types | financial facts, statements, restatements |
| Access method | Public HTTP page |
| Authentication | None |
| Source authority | **Authoritative** (issuer filings) |
| Storage permission | **no — not reviewed** |
| Public-display permission | **no — not reviewed** |
| Redistribution permission | **no — not reviewed** |
| Attribution | "Source: PT Bursa Efek Indonesia (IDX); issuer filings" |
| Rate limits | Not established |
| Update cadence | Quarterly filing windows plus ad-hoc restatements |
| Fallback | `fixture_financials` |
| Enabled | **no** |
| Last validation | 2026-07-30 (connectivity only) |

**Blocked because.** `ACCESS_CONTROLLED` — the host answered **HTTP 403** to a
GitHub Actions runner (run 30537966831, 2026-07-30) — and rights unreviewed. No
response has been captured, so there is nothing to write a parser against.

**Additional constraint.** XBRL instance documents are the intended input. PDF
and Excel filings need separate adapters with stronger validation and must never
be committed — they become manifest rows.

---

## 10–12. `bank_indonesia`, `bps`, `ojk` — DISABLED

| Field | `bank_indonesia` | `bps` | `ojk` |
|---|---|---|---|
| Operator | Bank Indonesia | Badan Pusat Statistik | Otoritas Jasa Keuangan |
| Official URL | https://www.bi.go.id/en/statistik/ | https://www.bps.go.id/en | https://www.ojk.go.id/en/ |
| Data types | macro series | macro series | macro series, ownership |
| Access method | Public HTTP page | Public HTTP page | Public HTTP page |
| Authentication | None | None | None |
| Source authority | Authoritative | Authoritative | Authoritative |
| Storage permission | **no — not reviewed** | **no — not reviewed** | **no — not reviewed** |
| Public-display permission | **no — not reviewed** | **no — not reviewed** | **no — not reviewed** |
| Redistribution permission | **no — not reviewed** | **no — not reviewed** | **no — not reviewed** |
| Attribution | "Source: Bank Indonesia" | "Source: Badan Pusat Statistik" | "Source: Otoritas Jasa Keuangan" |
| Rate limits | Not established | Not established | Not established |
| Update cadence | Monthly | Monthly | Monthly |
| Fallback | `fixture_macro` | `fixture_macro` | `fixture_macro` |
| Enabled | **no** | **no** | **no** |
| Last validation | 2026-07-30 | 2026-07-30 | 2026-07-30 |

**Blocked because.** Rights: none of their terms have been reviewed. Access, per
run 30537966831 (2026-07-30): `bank_indonesia` and `ojk` are
`REACHABLE_UNVALIDATED` (HTTP 302 to a landing page); `bps` is
`ACCESS_CONTROLLED` (HTTP 403). Reachability does not lift the rights lock, and
all three remain disabled.

**Known limitations.** Official statistics are frequently revised. Any adapter
must preserve the release vintage alongside the observation period, or the
dataset silently becomes unusable for anything point-in-time.

---

## Review procedure

To move a source from disabled to enabled:

1. Confirm network access exists and is permitted. `connectivity_status` in
   `sources.yml` records what the last probe found; run
   `gdt-source-connectivity-smoke` to refresh it. An `ACCESS_CONTROLLED` result
   is an operator decision and cannot be resolved by retrying.
2. Read the operator's terms of use. Record what they say about automated
   access, storage, display and redistribution — with the date and the URL of
   the terms you read.
3. Fill in the three permission rows in this file. Leave anything you are unsure
   about as `no`.
4. Set `rights_status` and `enabled: true` in `config/goh-dip-tong/sources.yml`,
   narrowing the per-provider `rights:` block if the terms are narrower than the
   status.
5. Implement `parse()` against a real captured response and add a fixture of
   that response to the test suite.
6. Run `python3 -m pipeline.goh_dip_tong.cli sources` — it fails if this file and
   `sources.yml` disagree.
7. Run the first collection at `--write-mode validate_only` and read the quality
   report before promoting anything.

Never mark a right as approved because a page was reachable. Reachable is not
the same as permitted.
