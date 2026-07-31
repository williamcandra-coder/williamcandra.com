# Goh Dip Tong — Data Dictionary

What every generated file and record type means. Schemas live in
`schemas/goh-dip-tong/` and are the machine-readable authority; this page
explains the intent behind them.

---

## Generated config (read by the Stage 3 UI)

### `config/goh-dip-tong/idx30.current.json`
The active IDX30 universe. **The company picker reads this file. It must never
hard-code a ticker list.**

| Field | Meaning |
|---|---|
| `schemaVersion` | Semver of the contract. Breaking changes bump the major. |
| `indexCode` | Always `IDX30`. |
| `effectiveFrom` / `effectiveTo` | Membership period. `effectiveTo` is null while current. |
| `generatedAt` | When this content was produced — not when it was last checked. Regenerating identical content leaves it untouched. |
| `authoritative` | `false` when generated from a fixture or unverified source. **The UI must show a development-data notice when false.** |
| `provenance` | `LIVE`, `FIXTURE` or `MANUAL`. |
| `source.*` | Name, URL, provider id, publication and retrieval timestamps, rights status. |
| `constituents[]` | Sorted by ticker for stable diffs. |
| `contentHash` | SHA-256 over the content with retrieval timestamps stripped, so it moves only when the data does. |

Per constituent: `ticker`, `name`, `sectorCode`/`sectorName`,
`industryCode`/`industryName`, `modelFamily`, `coverageStatus`, `active`,
`enteredAt`, `sourceRef`.

`coverageStatus` is one of:

| Value | Meaning |
|---|---|
| `FULL_RESEARCH` | Full model coverage. Promotion to this is a human decision. |
| `FINANCIALS` | Financial data collected; a supported model family is mapped. |
| `ONBOARDING` | **No supported valuation model.** Never show a valuation. |
| `SUSPENDED` | Trading halted or delisted. |

A null `modelFamily` forces `ONBOARDING` — enforced by the schema *and* by the
`Constituent` type at construction. There is no code path that assigns a generic
valuation model to an unmapped classification, because a plausible-looking wrong
model is more dangerous than an honest gap.

### `config/goh-dip-tong/idx30.history.jsonl`
Append-only membership history. One JSON object per line. Existing rows are
never rewritten, reordered or removed.

| Field | Meaning |
|---|---|
| `changeType` | `ADDED`, `REMOVED`, `RENAMED`, `RECLASSIFIED`. `UNCHANGED` is **legacy** — no longer written, but present on rows recorded before the heartbeat was removed, and never rewritten because the file is append-only. Consumers must still tolerate it and must not treat it as a membership event. |
| `ticker` | Affected ticker; `*` on a legacy `UNCHANGED` row. |
| `observedAt` | **Date**, not timestamp. Membership is a date-granularity concept, and a date keeps a four-times-daily workflow from appending four rows for one event. A row exists only when something actually changed, so crossing a day boundary adds nothing. |
| `before` / `after` | Identity snapshots either side of the change. |
| `detail` | Human-readable description, used in the pull-request body. |

`membership_at(date, basis=…)` replays this file to reconstruct any past
universe. If it cannot, the history has lost something. Two distinct questions:

| basis | Question answered | Field replayed |
|---|---|---|
| `"effective"` (default) | *What was the index on that date?* | `effectiveFrom` |
| `"observed"` | *What did we know on that date?* | `observedAt` |

They diverge whenever collection lags the effective date, which is normal — an
index review is published before it takes effect. Use `observed` for anything
point-in-time-correct; use `effective` for factual attribution.

### `config/goh-dip-tong/companies.json`
Company master. **Includes former constituents** with `inIdx30: false` — a
company leaving the index is marked inactive, never deleted, or every past
research snapshot referencing it breaks. Carries `nameHistory` and
`classificationHistory`, each appended only on an actual change.

`lastSeenAt` is a **volatile** field: it records when we last looked, not what
we found, so it is excluded from the change comparison and from `contentHash`.
Without that, all thirty rows were restamped on the first run of every calendar
day and the file churned daily while the index stood still. The consequence is
that the stored value is the date of the last *substantive* write rather than
the last run — which is the honest reading, since for a company still in the
index `inIdx30: true` already answers the question.

### `config/goh-dip-tong/categories.json`
Sector, industry and model-family master with constituent counts. Lets the UI
group and filter without recomputing anything.

---

## Reviewed config (hand-edited)

| File | Purpose |
|---|---|
| `sources.yml` | Which sources may run and what may be done with their data. Editing a `rights` block is a rights decision. |
| `schedules.yml` | Single source of truth for every workflow trigger. `test_workflows.py` asserts the YAML matches. |
| `models.yml` | Sector/industry → model family, and which families are actually supported. |
| `metrics.yml` | Canonical metric definitions, units, scales, periods, sign conventions, missing reasons. |
| `guard.yml` | Repository-data guard thresholds. Raising one is a visible diff. |

---

## Data partitions

Data is partitioned by **type first**, then ticker and period. There is no
per-ticker top-level folder: that would produce 30+ wide directories and make
adding a data type a 30-directory change.

| Path | Contents | Format |
|---|---|---|
| `registry/current/` | Latest universe snapshot | JSON |
| `registry/history/` | Human-readable diff summaries | Markdown |
| `market-prices/daily/<TICKER>/<YEAR>.csv` | Daily OHLCV | CSV |
| `market-prices/corporate-actions/` | Splits, dividends, rights issues | JSONL |
| `financial-statements/reported/` | As originally filed | JSONL |
| `financial-statements/restated/` | Superseded revisions, retained | JSONL |
| `financial-statements/normalized/current-facts.jsonl` | Latest valid revision per fact — **what the engine reads** | JSONL |
| `financial-facts/annual/<TICKER>.jsonl` | FY facts, all revisions | JSONL |
| `financial-facts/quarterly/<TICKER>.jsonl` | Interim facts, all revisions | JSONL |
| `financial-facts/trailing/` | TTM aggregates | JSONL |
| `disclosures/metadata/<YYYY-MM>.jsonl` | Disclosure metadata by month | JSONL |
| `disclosures/manifests/documents.jsonl` | Documents that must not be committed | JSONL |
| `macro/<agency>/<SERIES>.jsonl` | Macro series with release vintages | JSONL |
| `quality/latest/`, `quality/history/` | Data-quality reports | JSON |
| `pipeline-runs/` | Run manifests | JSON |
| `research-snapshots/sample/` | Stage 2 contract samples | JSON |
| `_private/` | **Git-ignored.** Rights-restricted output. | varies |

Source freshness is **derived** from the newest `retrievedAt` in the committed
data (`quality.derive_last_success`), not recorded in a side-car file. A file
whose whole content is timestamps would change on every run and produce a commit
even when no data changed. A provider whose rights forbid committing leaves no
trace in the repository and is reported as untrackable rather than stale.

---

## The `Measure` type: missing versus zero

The rule: *missing data is null plus a reason; extraction failure must never
become zero.*

`Measure` makes this structural rather than a convention people remember most of
the time. You cannot construct a missing `Measure` without stating why, and you
cannot construct one that has both a value and a missing reason — either raises
at construction.

| Raw input | Result |
|---|---|
| `""`, `"-"`, `"n/a"`, `"nil"`, `"tidak ada"`, `None` | `null` + `NOT_REPORTED` |
| `"0"` | **`0.0`** — a reported zero is real data |
| `"see note 14"`, `"pending"` | `null` + `EXTRACTION_FAILED` |
| `-999999999` and similar sentinels | `null` + `EXTRACTION_FAILED` |
| `"(1,234.5)"` | `-1234.5` |

Missing reasons:

| Reason | Meaning |
|---|---|
| `NOT_REPORTED` | The issuer did not report this concept. |
| `NOT_APPLICABLE_TO_MODEL` | Meaningless for this model family (net debt for a bank). |
| `EXTRACTION_FAILED` | Document retrieved, value unparseable. |
| `SOURCE_UNAVAILABLE` | Source unreachable or disabled. |
| `RIGHTS_WITHHELD` | Collected but withheld — a licensing gap, not a data gap. |
| `INSUFFICIENT_PERIODS` | A derived metric lacked its input periods. |
| `PENDING_REVIEW` | Value exists but failed validation and was not promoted. |
| `SUPERSEDED` | Replaced by a restatement. |
| `TRADING_HALTED` | No price because the stock was suspended. |

`RIGHTS_WITHHELD` versus `NOT_REPORTED` matters: one is fixed by a lawyer, the
other by a better parser.

---

## Facts and revisions

`factKey` = `ticker|metric|periodType|periodEnd|segment` (segment defaults to
`CONSOLIDATED`).

It deliberately **excludes** `basis`. A restatement is the same fact observed
again: revision 1 carries `REPORTED`, revision 2 carries `RESTATED`, and they
share a `factKey` so the supersession chain links up. Putting basis in the key
would split every restatement into two unrelated lineages and silently break
correction tracking.

It deliberately **includes** `segment`, because segment revenue and consolidated
revenue for the same period are different facts, not revisions of one.

A restatement never overwrites. The prior revision stays in the store flagged
`SUPERSEDED`, so "what did we believe in July" remains answerable.

`basis` values — the disclosure classes the UI must keep visually distinct:

| Basis | Meaning |
|---|---|
| `REPORTED` | As originally filed. |
| `RESTATED` | Reissued by the company. |
| `NORMALIZED` | Adjusted by this pipeline; adjustment must be disclosed. |
| `DERIVED` | Computed from other values. |
| `FORECAST` | Projected. Not a fact. |
| `MARKET_IMPLIED` | Backed out from a price. |

---

## Periods

Indonesian interim filings are **cumulative**: the "Q3" report contains nine
months, not three. `YTD_Q1/Q2/Q3` and standalone `Q1..Q4` are separate period
types and conversion between them is explicit. `standalone_from_ytd()` returns
`None` when either input is missing — treating a missing prior period as zero
would report nine months as a single quarter.

`POINT_IN_TIME` facts (balance-sheet instants) have no `periodStart`; the schema
enforces this.

---

## Timestamps

Three distinct concepts, never collapsed:

| Field | Meaning |
|---|---|
| `periodEnd` / `observationPeriod` | The period the number describes. |
| `publishedAt` | When the issuer or agency released it. |
| `retrievedAt` | When we fetched it. |
| `releaseVintage` | Which release of a revisable statistic this is. |

Collapsing these is how you accidentally backtest on numbers that did not exist
at the time.

---

## Events

`status` is a certainty ladder: `RUMOR` → `MEDIA_REPORT` → `PROPOSAL` →
`OFFICIAL_DECISION` → `IMPLEMENTED` → `COMPANY_IMPACT_CONFIRMED`. **Only
`OFFICIAL_DECISION` and above may be treated as fact.** Anything below must be
labelled as unconfirmed in the UI; the disclosure collector raises a warning
whenever it sees one.

---

## Quality reports

`status` is `PASS`, `PASS_WITH_WARNINGS` or `FAIL`. `promoted` is the fail-closed
switch: when `false`, nothing was written and the last validated data still
stands. `notPromotedReason` says why. `failedTickers[]` records fail-soft
outcomes — one issuer failing must not corrupt the others.
