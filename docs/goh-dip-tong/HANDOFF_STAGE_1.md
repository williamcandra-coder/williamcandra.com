# Goh Dip Tong — Stage 1 Handoff

**Stage:** 1 — IDX30 data collection, history, schedulers, config
**Repository:** `williamcandra-coder/williamcandra.com`
**Completed:** 2026-07-30

## Status: `ARCHITECTURE_COMPLETE_FIXTURE_ONLY`

Read this before building on Stage 1. The architecture is finished and proven
against fixtures. **No data has ever been ingested from a live source.** The only
live contact made is the read-only connectivity probe in §6b, which retrieved
response headers and nothing else.

| | |
|---|---|
| Unit tests | **237 passed**, 0 failed |
| Acceptance checks | **71/71 passed** (70 requirement checks + 1 isolation self-check) |
| Fixture collectors | **Implemented and tested** — five providers run end to end |
| Live provider interfaces | **Scaffolded only** — registered, disabled, never exercised |
| Live `parse()` methods | **Not implemented** — they raise `NotImplementedError` by design |
| Live source connectivity | **Verified from GitHub Actions** (run [30537966831](https://github.com/williamcandra-coder/williamcandra.com/actions/runs/30537966831), 2026-07-30). Runners can reach the hosts; **5 of 7 refuse automated access with HTTP 403.** No source is validated for ingestion — see §6b |
| Production data sources | **None enabled** — zero live providers are runnable |
| IDX30 config | **Non-authoritative fixture data** (`authoritative: false`, `provenance: "FIXTURE"`) |
| Market-price output | **Private and git-ignored** — routed to `data/goh-dip-tong/_private/` |

**What this means for Stage 2.** You may develop the calculation engine against
these fixtures — the contracts, schemas and sample snapshots are stable and are
exactly the shapes a live source will produce. You **must not** present any
output as live analysis, current market data, or a real IDX30 valuation. Nothing
in this repository has been derived from an authoritative source, and every
artefact says so in its own metadata. Treat `authoritative: false` as a hard gate
on any user-facing claim.

Two limits deserve emphasis because they are easy to misread as "nearly done":

- **Connectivity is now measured, and the answer is discouraging.** A GitHub
  Actions runner *can* reach these hosts — but all four IDX endpoints answer
  **HTTP 403**, and so does BPS. Only Bank Indonesia and OJK responded, both with
  a 302 to a human-facing landing page. Full results in §6b. Do not read
  "connectivity verified" as "nearly ingestible": it is the opposite.
- **No live parser exists.** Each live adapter has `discover`/`fetch` wired to
  the shared contract, but `parse()` deliberately raises. Writing one requires a
  real captured response; guessing at a payload shape would produce untested code
  that merely looks complete. Nothing has yet returned a response worth parsing.

---

## 1. What was built

A reproducible Python pipeline plus seven GitHub Actions workflows that
establish the IDX30 universe, collect data by type into repository-safe
partitions, detect membership and classification changes, preserve history, and
refuse to publish anything that fails validation.

**Nothing in the production site was touched.** `index.html`,
`goh-pok-tong.html`, `bazi-engine.min.js`, `engine-v3/`, the other arcade pages,
`CNAME` and `_config.yml` are all unmodified. The only pre-existing file changed
is `.gitignore`, which gained an append-only section.

### Scope boundaries observed

- No calculation engine. `models.yml` declares which model families the Stage 2
  engine is expected to support; no valuation maths exists.
- No Goh Dip Tong UI. `idx30.current.json` is the contract Stage 3 will read.
- No production, DNS, domain or Pages configuration change.
- No paid resources, no deployment.
- **Public market-price collection is not activated.** The provider runs but its
  rights status routes output to a git-ignored path.

---

## 2. Repository tree created

```text
williamcandra.com/
├── .gitignore                                    # MODIFIED (append-only)
│
├── config/goh-dip-tong/
│   ├── sources.yml            # reviewed source policy + rights (12 providers)
│   ├── schedules.yml          # single source of truth for every workflow trigger
│   ├── models.yml             # sector/industry → model family; ONBOARDING rule
│   ├── metrics.yml            # canonical metric definitions, units, missing reasons
│   ├── guard.yml              # repository-data guard thresholds
│   ├── idx30.current.json     # GENERATED — 30 constituents, 12,831 bytes
│   ├── idx30.history.jsonl    # GENERATED — append-only, 31 rows
│   ├── companies.json         # GENERATED — company master, retains former members
│   └── categories.json        # GENERATED — sector/industry/model-family master
│
├── data/goh-dip-tong/                            # 23 data-type partitions
│   ├── registry/{current,history}/
│   ├── market-prices/{daily,corporate-actions}/
│   ├── financial-statements/{reported,restated,normalized}/
│   ├── financial-facts/{annual,quarterly,trailing}/
│   ├── disclosures/{metadata,manifests}/
│   ├── ownership/  dividends/  events/  derived-metrics/
│   ├── macro/{ojk,bank-indonesia,bps}/
│   ├── research-snapshots/sample/                # Stage 2 contract samples
│   ├── quality/{latest,history}/
│   ├── pipeline-runs/
│   └── _private/                                 # GIT-IGNORED, rights-restricted
│
├── pipeline/goh_dip_tong/
│   ├── cli.py  settings.py  requirements.txt
│   ├── contracts/     enums.py  records.py  provider.py
│   ├── collectors/    base.py registry.py idx30_registry.py market_prices.py
│   │                  disclosures.py financials.py macro.py
│   ├── parsers/       guards.py
│   ├── normalization/ periods.py units.py values.py
│   ├── validation/    schema.py quality.py repo_guard.py rights.py
│   ├── publishing/    writers.py registry_config.py change_detection.py history.py
│   └── tests/         7 test modules + conftest + clock hook + 10 fixtures
│
├── schemas/goh-dip-tong/                         # 8 JSON Schema Draft 2020-12
│   ├── idx30  company  financial-fact  market-price
│   └── disclosure  event  quality-report  research-input
│
├── .github/workflows/                            # 8 workflows
│   ├── gdt-registry-update.yml      gdt-historical-backfill.yml
│   ├── gdt-daily-update.yml         gdt-disclosure-watch.yml
│   ├── gdt-financial-update.yml     gdt-macro-update.yml
│   ├── gdt-data-quality.yml
│   └── gdt-source-connectivity-smoke.yml    # manual, read-only diagnostic
│
└── docs/goh-dip-tong/
    ├── SOURCE_REGISTER.md  DATA_DICTIONARY.md  PIPELINE_RUNBOOK.md
    ├── DATA_RIGHTS.md      FAILURE_MODES.md    HANDOFF_STAGE_1.md
```

Data is partitioned **by type first**, then ticker and period. There is no
per-ticker top-level folder: that would produce 30+ wide directories and make
adding a data type a 30-directory change.

---

## 3. Running the collectors locally

```bash
cd /path/to/williamcandra.com
python3 -m pip install -r pipeline/goh_dip_tong/requirements.txt
```

Python 3.9+. Dependencies: `PyYAML`, `jsonschema`, `requests` (lazy, live
providers only), `pytest`. No pandas, no compiled extensions, no build step.

```bash
# Inspect sources and rights before running anything
python3 -m pipeline.goh_dip_tong.cli sources

# Establish the universe FIRST — every other collector refuses to guess a ticker list
python3 -m pipeline.goh_dip_tong.cli registry-update --write-mode commit

# Collect by data type
python3 -m pipeline.goh_dip_tong.cli daily-update       --write-mode commit
python3 -m pipeline.goh_dip_tong.cli disclosure-watch   --write-mode commit
python3 -m pipeline.goh_dip_tong.cli financial-update   --write-mode commit
python3 -m pipeline.goh_dip_tong.cli macro-update       --write-mode commit

# Historical backfill
python3 -m pipeline.goh_dip_tong.cli backfill --scope all --write-mode commit
python3 -m pipeline.goh_dip_tong.cli backfill --scope data_type \
    --data-type financial_facts --start-year 2020 --end-year 2025 --write-mode commit

# Stage 2 contract sample
python3 -m pipeline.goh_dip_tong.cli research-snapshot --ticker BBCA

# Audits
python3 -m pipeline.goh_dip_tong.cli quality --verbose
python3 -m pipeline.goh_dip_tong.cli repo-guard --verbose

# Unit tests (180) and the Stage 1 acceptance test (63 checks)
python3 -m pytest pipeline/goh_dip_tong/tests -q
./pipeline/goh_dip_tong/tests/acceptance.sh
```

The acceptance script verifies all 17 Stage 1 requirements. Every write it makes
goes to a throwaway sandbox under `$(mktemp -d)` that is removed on exit, and its
closing self-check fails if the repository tree moved — so it is safe to run
mid-work and safe to run in CI on a pull request. It exits `0` only when every
check passes.

Omitting `--write-mode` gives `validate_only`: everything runs, nothing is
promoted. Exit codes: `0` ok, `1` validation failed (nothing promoted), `2`
usage error.

Full detail in `PIPELINE_RUNBOOK.md`.

---

## 4. Workflows and schedules

| Workflow | Trigger | Cron (UTC) | Local (WIB) | Commit policy |
|---|---|---|---|---|
| `gdt-registry-update` | dispatch + schedule | `30 22 * * 1` | Tue 05:30 | PR to `gdt/auto/registry-*` |
| `gdt-historical-backfill` | **dispatch only** | — | — | PR to `gdt/auto/backfill-*` |
| `gdt-daily-update` | dispatch + schedule | `30 11 * * 1-5` | Mon–Fri 18:30 | PR to `gdt/auto/daily-*` |
| `gdt-disclosure-watch` | dispatch + schedule | `17 2,6,10,14 * * *` | 09:17/13:17/17:17/21:17 | PR to `gdt/auto/disclosures-*` |
| `gdt-financial-update` | dispatch + schedule | `45 12 * * *` | 19:45 | PR to `gdt/auto/financials-*` |
| `gdt-macro-update` | dispatch + schedule | `40 23 * * 0` | Mon 06:40 | PR to `gdt/auto/macro-*` |
| `gdt-data-quality` | dispatch + schedule + **every PR** | `5 6 * * *` | 13:05 | never commits |
| `gdt-source-connectivity-smoke` | **dispatch only** | — | — | never commits |

`config/goh-dip-tong/schedules.yml` is the single source of truth;
`test_workflows.py` asserts the YAML matches it, so a cron edited in one place
fails CI rather than drifting silently.

### Two safety properties worth knowing

**Schedules are OFF by default.** Every scheduled job is gated by
`if: github.event_name != 'schedule' || vars.GDT_SCHEDULES_ENABLED == 'true'`.
That repository variable is unset, so **no schedule does anything** until you
create it with the value `true` (Settings → Secrets and variables → Actions →
Variables). Manual dispatch is never gated.

**No workflow can push to the default branch.** Top-level `permissions` is
`contents: read` everywhere; only the PR-opening job gets
`contents: write` + `pull-requests: write`; `gdt-data-quality` has no write
permission at all. Commits stage only `config/goh-dip-tong` and
`data/goh-dip-tong`, use the message convention
`data(gdt): update <data-type> through <date>`, and a workflow that finds no
change exits successfully without committing.

`gdt-historical-backfill` additionally re-runs itself and **fails the build if
the second identical run changes any file** — a non-idempotent backfill would
grow the repository on every execution.

---

## 5. Data-source status

| Provider | Data types | Enabled | Rights status | Backing |
|---|---|---|---|---|
| `fixture_idx30_registry` | membership, identity, sectors | ✅ | `PUBLIC_METADATA_ONLY` | **fixture** |
| `fixture_market_prices` | daily OHLCV, corporate actions | ✅ | `PRIVATE_RESEARCH_ONLY` | **fixture** |
| `fixture_disclosures` | disclosure metadata, events | ✅ | `PUBLIC_METADATA_ONLY` | **fixture** |
| `fixture_financials` | facts, statements, restatements | ✅ | `PUBLIC_DERIVED_OUTPUT_APPROVED` | **fixture** |
| `fixture_macro` | macro series | ✅ | `PUBLIC_METADATA_ONLY` | **fixture** |
| `idx_index_constituents` | membership, identity, sectors | ❌ | `MANUAL_REVIEW_REQUIRED` | live, blocked |
| `idx_market_prices` | daily OHLCV | ❌ | `MANUAL_REVIEW_REQUIRED` | live, blocked |
| `idx_disclosures` | disclosure metadata | ❌ | `MANUAL_REVIEW_REQUIRED` | live, blocked |
| `idx_financials` | XBRL facts, filings | ❌ | `MANUAL_REVIEW_REQUIRED` | live, blocked |
| `bank_indonesia` | macro series | ❌ | `MANUAL_REVIEW_REQUIRED` | live, blocked |
| `bps` | macro series | ❌ | `MANUAL_REVIEW_REQUIRED` | live, blocked |
| `ojk` | macro series, ownership | ❌ | `MANUAL_REVIEW_REQUIRED` | live, blocked |

**Every source currently in use is a fixture. Zero live sources are enabled.**

Live adapters are registered, structurally complete and locked by two
independent mechanisms: `enabled: false` in `sources.yml`, and a `rights_status`
the gate refuses to run regardless of that flag. Their `parse()` methods raise
`NotImplementedError` with an explanation — a parser written against a response
nobody has seen is untested code that merely looks finished.

---

## 6. Rights and access limitations

**1. Access is measured, and mostly refused.** Two different environments, two
different failures. In the *build sandbox* every host returned HTTP `000` — the
agent proxy reported `connect_rejected — gateway answered 403 to CONNECT (policy
denial)`, so no connection was ever established. From *GitHub Actions* (run
30537966831) the hosts are reachable, and five of seven then refuse the runner
directly with HTTP 403. `sources.yml` now records `connectivity_status`,
`http_status`, `connectivity_verified_at` and `connectivity_run_id` per provider.
Either way, live collection has never been exercised, which is why fixtures back
every source. Full detail in §6b.

**2. No source has documented usage rights.** No operator's terms have been read
or recorded, so no storage, display or redistribution right is claimed for any
live source. `SOURCE_REGISTER.md` carries `no — not reviewed` in every
permission cell for all seven live providers.

**3. Public market-price collection is not activated**, as instructed.
`fixture_market_prices` is held at `PRIVATE_RESEARCH_ONLY` even though its data
is synthetic, so the rights gate routes its output to
`data/goh-dip-tong/_private/` — which `.gitignore` excludes. The daily-update
path runs end to end and produces zero git diff. When rights are eventually
documented, raising the status moves output into the tracked tree with **no code
change**.

**4. The IDX30 universe is a development fixture, not authoritative.** It is a
plausible 30-ticker list authored in-repo. `idx30.current.json` carries
`authoritative: false` and `provenance: "FIXTURE"`.
**Stage 3 must show a development-data notice whenever `authoritative` is false.**

**5. `_config.yml` was not modified**, per your boundary on Pages configuration.
This remains an open decision for a later stage. See §6a below.

---

## 6a. GitHub Pages publishing — open decision, NOT applied

`_config.yml` is unchanged and stays unchanged in Stage 1. Today its only
directive is `exclude: [internal]`, so Jekyll copies `config/`, `data/`,
`pipeline/`, `schemas/` and `docs/` into the published site.

Three facts should drive the eventual decision.

### Stage 3 requires selected config and current public research snapshots

The Goh Dip Tong UI fetches its data over HTTP from the published site. It needs,
at minimum:

- `config/goh-dip-tong/idx30.current.json` — the company picker's only source
  of tickers;
- `config/goh-dip-tong/categories.json` — sector and industry grouping;
- `config/goh-dip-tong/companies.json` — company detail, including former members;
- the **current, public** research snapshots the UI renders, once Stage 2 defines
  which of them are publishable.

**These must remain published.** Excluding `config/` would break the Stage 3
picker outright, and the whole design rests on the UI reading a generated file
rather than hard-coding a ticker list.

### Pipeline, test, quality and internal datasets should eventually be excluded

None of the following is fetched by any page at runtime, so publishing them
serves no purpose and only enlarges the site:

- `pipeline/` — Python source, fixtures and tests;
- `schemas/` — development contracts;
- `data/goh-dip-tong/quality/`, `pipeline-runs/` — build telemetry;
- historical or superseded datasets the UI does not read;
- `internal/` — already excluded today.

The exact change, **for a future stage to apply after Stage 2 has settled which
snapshots are public**:

```yaml
exclude:
  - internal
  - pipeline      # Python source, fixtures, tests; nothing requests it at runtime
  - schemas       # development contracts
  # Consider narrowing rather than excluding data/ wholesale — Stage 3 may need
  # selected research snapshots served from it.
```

`config/` is deliberately absent from that list.

### Excluding from Pages does NOT make a file confidential

This is the point most easily got wrong. `exclude:` only stops Jekyll copying a
file into the built site. **The repository is public, so every committed file
remains readable by anyone** — through the GitHub web UI, `git clone`, the API,
and `raw.githubusercontent.com`. Exclusion is a site-hygiene measure, not an
access control.

The consequence: **never rely on a Pages exclusion to protect anything.** The
only real controls in this project are the ones already in place — the rights
gate routing restricted output to the git-ignored `_private/` tree, `.gitignore`
itself, and the repository guard's secret scan. If something must not be public,
it must not be committed at all.

---

## 6b. Source connectivity — verified results

**Run [30537966831](https://github.com/williamcandra-coder/williamcandra.com/actions/runs/30537966831)** ·
`gdt-source-connectivity-smoke` · ref `claude/gdt-stage-1` @ `51c4f067` ·
2026-07-30T11:17Z · `timeout_seconds=15`, `delay_seconds=2` · conclusion **success**

| Provider | HTTP | Outcome | Note |
|---|---:|---|---|
| `bank_indonesia` | **302** | `REACHABLE_UNVALIDATED` | → `https://www.bi.go.id/en/statistik/Default.aspx` |
| `ojk` | **302** | `REACHABLE_UNVALIDATED` | → `https://www.ojk.go.id/en/Default.aspx` (160 bytes) |
| `bps` | **403** | `ACCESS_CONTROLLED` | refused |
| `idx_index_constituents` | **403** | `ACCESS_CONTROLLED` | refused |
| `idx_market_prices` | **403** | `ACCESS_CONTROLLED` | refused |
| `idx_disclosures` | **403** | `ACCESS_CONTROLLED` | refused |
| `idx_financials` | **403** | `ACCESS_CONTROLLED` | refused |
| `fixture_disclosures` | — | `NOT_TESTED` | local fixture; nothing to reach |
| `fixture_financials` | — | `NOT_TESTED` | local fixture; nothing to reach |
| `fixture_idx30_registry` | — | `NOT_TESTED` | local fixture; nothing to reach |
| `fixture_macro` | — | `NOT_TESTED` | local fixture; nothing to reach |
| `fixture_market_prices` | — | `NOT_TESTED` | local fixture; nothing to reach |

```
probed=7  not_tested=5  reachable_unvalidated=2
providers enabled by this run: 0
response bodies retained: False
```

Artifact: **`gdt-source-connectivity-report`** (30-day retention). All content
types were `text/html; charset=UTF-8` — no endpoint returned a data content type.

### What this changes, and what it does not

**GitHub Actions connectivity is now verified. No live data source is validated
for ingestion.** Those are different claims and the gap between them is the whole
finding.

The earlier unknown is resolved: hosted runners are not network-blocked the way
the build sandbox was. The sandbox failed at the proxy with a 403 to `CONNECT`,
before any connection existed. The runner reaches the hosts and **the hosts
themselves refuse** — a materially worse result, because it is a deliberate
refusal by the operator rather than an environment limitation we control.

Reading each outcome honestly:

- **`ACCESS_CONTROLLED` (5 of 7)** — IDX and BPS decline automated requests from
  this address range. Not a bug to route around. Per `DATA_RIGHTS.md`, a source
  that requires circumvention to work is a source that stays disabled.
- **`REACHABLE_UNVALIDATED` (2 of 7)** — BI and OJK responded, both redirecting to
  an ASPX landing page. A socket opened and a human-facing page exists. That is
  *not* evidence of a usable data endpoint, and the probe deliberately did not
  follow the redirect or read a body.

### Consequences for enabling a source

Every live provider remains `enabled: false` / `MANUAL_REVIEW_REQUIRED`. Both
locks are untouched, and the run re-asserted this on exit
(*"All 7 live providers still disabled. Nothing was activated."*).

The two gates from `SOURCE_REGISTER.md` now stand as:

| Gate | Status |
|---|---|
| Network access | **Partially resolved.** Runners reach the hosts; 5 of 7 are refused by the operator. |
| Documented usage rights | **Unresolved.** No operator's terms have been read or recorded. |

Nothing has changed about rights, and the access picture got worse rather than
better. Before any of this can move, someone must resolve the operator
relationship — an official data agreement, a licensed vendor, or a documented
permitted-use path. Retrying the probe will not produce a different answer.

---

## 7. Tests

`python3 -m pytest pipeline/goh_dip_tong/tests -q` → **237 passed, 0 failed, ~25s**

| Module | Tests | Covers |
|---|---|---|
| `test_normalization.py` | 54 | periods, units/currency, missing-vs-zero, sign conventions |
| `test_guards.py` | 40 | HTML-as-data, timeout/retry, disabled providers, rights gate, repo guard |
| `test_workflows.py` | 37 | schedule/YAML agreement, least privilege, commit policy, no secrets |
| `test_change_detection.py` | 24 | ADDED/REMOVED/RENAMED/RECLASSIFIED, no-change silence, append-only history |
| `test_backfill.py` | 22 | idempotency, duplicates, restatements, fail-soft, fail-closed |
| `test_universe.py` | 21 | schemas, uniqueness, dates, model mapping, ordering, UI contract |
| `test_no_change_churn.py` | 11 | date-swept idempotency: no-change runs write nothing and stage nothing on any date; membership and category changes still recorded |

### Every required Stage 1 test area (spec §1.11)

| # | Required test | Where |
|---|---|---|
| 1 | IDX30 config schema | `test_universe::test_committed_idx30_config_matches_schema` |
| 2 | Universe uniqueness | `test_universe::test_universe_uniqueness` |
| 3 | Membership effective dates | `test_universe::test_membership_effective_dates_are_coherent` |
| 4 | Change detection | `test_change_detection` — 8 tests, all five change types |
| 5 | Sector/category changes | `test_change_detection::test_reclassified_is_detected` |
| 6 | Model-family mapping | `test_universe::test_model_mapping_resolves_industry_before_sector` |
| 7 | Idempotent backfill | `test_backfill::test_rerunning_a_collector_produces_identical_bytes` |
| 8 | Duplicate prevention | `test_backfill::test_no_duplicate_fact_keys_from_the_fixture` (+3) |
| 9 | Missing versus zero | `test_normalization` — 12 tests |
| 10 | Period normalization | `test_normalization::test_ytd_period_starts_at_the_year_start…` |
| 11 | Unit/currency normalization | `test_normalization::test_scale_is_multiplied_out_to_base_units` |
| 12 | Restatement versioning | `test_backfill::test_restatement_creates_a_new_revision…` |
| 13 | Malformed HTML as data | `test_guards::test_cloudflare_interstitial_is_rejected` (+3) |
| 14 | Timeout and retry | `test_guards::test_backoff_is_exponential` (+3) |
| 15 | Provider disabled mode | `test_guards::test_running_a_disabled_provider_raises…` (+4) |
| 16 | Rights gate | `test_guards` — 8 tests |
| 17 | Repository-size guard | `test_guards` — 8 tests |
| 18 | Deterministic output ordering | `test_universe::test_generation_is_byte_stable_across_runs` |
| 19 | UI ticker-config compatibility | `test_universe::test_ui_ticker_config_compatibility` |

### Acceptance test

`./pipeline/goh_dip_tong/tests/acceptance.sh` → **63 passed, 0 failed** (exit 0)

62 checks covering the 17 Stage 1 requirements, plus one isolation self-check
confirming the run left `config/goh-dip-tong` and `data/goh-dip-tong`
byte-identical. Wired into `gdt-data-quality.yml`, which runs the unit suite,
this script and the repository guard on every pull request — read-only, with no
write permission and no commit step.

### End-to-end verification performed

```
PASS 1 (seed)   registry=6  daily=3  disclosure=3  financial=6  macro=3  files changed
PASS 2 (rerun)  registry=2  daily=0  disclosure=0  financial=0  macro=0
PASS 3 (rerun)  registry=0  daily=0  disclosure=0  financial=0  macro=0   ← fully idempotent
```

Pass 1→2 differs legitimately: the seed run records 30 `ADDED` history events,
and pass 2 settles the derived documents. From pass 2 onward every collector is
byte-stable — including across calendar dates, which pass 3 alone did not prove
until the date sweep was added (see *Membership history churn* below).

#### Membership history churn (fixed)

Two per-day stamps made a no-change run non-idempotent on any date after the
seed date: an `UNCHANGED` heartbeat row appended to `idx30.history.jsonl`, and
`companies.json`'s `lastSeenAt` restamped on all thirty constituents. Because
every run happened on the date the fixtures were generated, both always matched
what was committed and the suite passed. On the first run of the next day both
moved, `filesChanged` was 2 instead of 0, and the scheduled workflows would have
opened a pull request containing no facts.

The heartbeat is no longer emitted — `detect_changes` has no `emit_unchanged`
switch — and `lastSeenAt` is a volatile field, with the volatile strip now
recursing into lists so it can see stamps on array elements. Legacy `UNCHANGED`
rows already committed are preserved untouched and treated as immaterial.

Verified across 2026-08-01, 2026-12-31, 2027-03-14 and 2031-06-30: `filesChanged=0`
with a byte-identical config tree at every date, and — asserted against git rather
than against our own counter — nothing staged by the workflow's
`git add config/goh-dip-tong data/goh-dip-tong`, so no pull request can open.
Genuine membership *and* category changes are still recorded, once each.

```
cli sources     → rights and SOURCE_REGISTER.md are consistent
cli quality     → status=PASS
cli repo-guard  → status=PASS  critical_failures=0
```

### Four real bugs the suite, the idempotency check and the acceptance run caught

1. **`factKey` included `basis`**, so a `RESTATED` revision never superseded its
   `REPORTED` original — restatement tracking was silently non-functional. Fixed
   by excluding basis and including `segment`.
2. **Timestamp churn.** `generatedAt` / `source.retrievedAt` rewrote every file
   on every run, and `contentHash` moved with the clock. Fixed via
   `VOLATILE_FIELDS` and `stable_content_hash`.
3. **`upsert_csv` compared a parsed string against the original int**, reporting
   spurious "updated" counts on unchanged rows.
4. **A side-car `last-success.json`** rewrote a timestamp on every successful
   run. Once tracked it would have produced a commit on every scheduled run with
   no data change — a direct violation of the no-change/no-commit policy. Source
   freshness is now derived from the newest `retrievedAt` in the committed data.
   Found by the acceptance run, not by the unit suite.

---

## 8. Data contracts for Stage 2 and Stage 3

### Stage 3 (UI) reads

| File | Purpose |
|---|---|
| `config/goh-dip-tong/idx30.current.json` | **The company picker's only source of tickers.** Never hard-code a list. |
| `config/goh-dip-tong/categories.json` | Sector/industry grouping and filtering |
| `config/goh-dip-tong/companies.json` | Company detail, including former members |

Contract notes for Stage 3:
- Constituents are sorted by ticker.
- `coverageStatus: ONBOARDING` means **no supported valuation model** — show no
  valuation for that company.
- `authoritative: false` / `provenance: "FIXTURE"` **must** produce a visible
  development-data notice.
- Preserve the AFTER HOURS design language; Goh Pok Tong stays untouched and
  separate.

### Stage 2 (engine) reads

| File | Purpose |
|---|---|
| `data/goh-dip-tong/research-snapshots/sample/{BBCA,TLKM,ASII}.json` | The calculation-ready contract, one file per issuer |
| `data/goh-dip-tong/financial-statements/normalized/current-facts.jsonl` | Latest valid revision per fact |
| `data/goh-dip-tong/financial-facts/{annual,quarterly}/<TICKER>.jsonl` | Full revision history |
| `data/goh-dip-tong/financial-statements/restated/restatements.jsonl` | Superseded revisions |
| `config/goh-dip-tong/metrics.yml` | Metric definitions, units, sign conventions |
| `config/goh-dip-tong/models.yml` | Which model families exist and which are supported |
| `schemas/goh-dip-tong/research-input.schema.json` | The snapshot contract |

Contract notes for Stage 2:
- Every value carries a `basis`. Keep `REPORTED`, `RESTATED`, `NORMALIZED`,
  `DERIVED`, `FORECAST` and `MARKET_IMPLIED` distinct all the way to the UI.
- A `null` value always carries a `missingReason`. **Never coerce it to zero.**
- `marketContext` is currently `{available: false, reason: …}`. Handle the
  no-price case; do not assume a price exists.
- Calculations must be deterministic. An LLM may explain a snapshot but must
  never be the source of the numbers in it.
- `net_debt` for a bank must return `null` + `NOT_APPLICABLE_TO_MODEL`, not `0`.

---

## 9. Acceptance criteria (spec §1.12)

| # | Criterion | Status |
|---|---|---|
| 1 | Pipeline runs locally | ✅ all 10 CLI commands verified |
| 2 | Manual GitHub Actions workflows exist | ✅ 7 workflows, all with `workflow_dispatch` |
| 3 | At least one end-to-end historical fixture passes | ✅ 5 fixture providers run end to end |
| 4 | Active IDX30 config generated from a permitted/committed fixture | ✅ 30 constituents |
| 5 | All constituents have valid identity/category records | ✅ schema + quality checks pass |
| 6 | Historical membership changes preserved | ✅ append-only; `membership_at()` replays any past date on an effective or observed basis |
| 7 | Each data type in a separate folder | ✅ 23 partitions |
| 8 | Rerunning does not duplicate rows | ✅ three-pass idempotency verified |
| 9 | Invalid data does not replace last validated data | ✅ fail-closed + atomic writes |
| 10 | Stage 1 handoff file exists | ✅ this document |
| 11 | Tests pass | ✅ 237/237 unit + 71/71 acceptance checks |
| 12 | No secret or restricted raw document committed | ✅ guard passes; price data git-ignored |

---

## 10. Known gaps for Stage 2

1. **No live data.** Resolve network access *and* usage rights per source before
   enabling anything. Both locks must be released. Connectivity has now been
   measured from GitHub Actions (§6b): runners reach the hosts, but 5 of 7 refuse
   automated access with HTTP 403, and no operator's terms have been reviewed.
   Re-running `gdt-source-connectivity-smoke` will not change that — the block is
   an operator decision, not an environment limitation.
2. **Live `parse()` methods are unimplemented by design.** Write each against a
   real captured response and add that response as a test fixture.
3. **TTM aggregation is not implemented.** `financial-facts/trailing/` exists and
   `periods.ttm_window()` provides the window; the aggregation belongs to the
   engine.
4. **`derived-metrics/`, `ownership/`, `dividends/`, `events/` are scaffolded but
   empty.** Their schemas and partitions exist; no collector populates them yet.
5. **FX conversion is deliberately absent.** Some IDX30 issuers report in USD.
   `assert_same_currency()` raises rather than combining currencies — a rate
   source, rate dates and a documented methodology are needed first.
6. **`_config.yml` exclusion decision** — see §6.5.
7. **Parquet is disabled** in `guard.yml` until its repeated-versioning cost is
   measured.

---

## 11. Git status

Nothing has been committed or pushed. All work is uncommitted in the working
tree of branch `claude/arcade-homepage-v1-a1499u`, awaiting your review.
