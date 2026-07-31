# Goh Dip Tong — Failure Modes

The ways a financial-data pipeline goes wrong quietly, and what this one does
about each. The dangerous failures are not crashes — a crash announces itself. The
dangerous ones produce plausible numbers.

---

## 1. Missing becomes zero

**How it happens.** A parser reads an empty cell and returns `0.0`. A ratio is
computed, a margin looks terrible, and nobody can tell it apart from a company
that genuinely earned nothing.

**Defence.** `Measure` makes missing a first-class value that cannot be
constructed without a reason, and cannot carry both a value and a reason —
either raises at construction. `coerce()` has exactly three outcomes: null token
→ `NOT_REPORTED`, parseable number → the value (including a genuine `0`),
anything else → `EXTRACTION_FAILED`. There is no branch producing `0.0` from
unparseable input.

Backed by: schema `allOf` rules requiring a reason on every null;
`check_missing_vs_zero()` across every dataset; the guard's sentinel scan;
`assert_not_zero_from_missing()`.

**Residual risk.** A source that *itself* reports 0 for a missing figure. No
pipeline can detect this from the data alone.

---

## 2. An error page saved as data

**How it happens.** The server returns HTTP 200 with a login wall, a rate-limit
notice or a Cloudflare interstitial. The collector saves it, the run reports
success, and the dataset now contains HTML.

**Defence.** Every payload passes `assert_is_data()` before any parser sees it —
it rejects HTML markers, known block-page phrases, unexpected content types,
empty bodies and unparseable JSON. `PayloadRejected` is explicitly *not*
retried: retrying a bot check five times just means five requests at a source
that already said no. The repository guard independently scans committed files
for HTML markers.

**Do not** relax the guard to make a source work. A saved error page is worse
than no data because it looks like success.

---

## 3. A rerun duplicates everything

**How it happens.** A collector appends instead of merging. Every scheduled run
adds another copy; the repository grows and the numbers double.

**Defence.** Every dataset is written through an upsert keyed on the record's
primary key, so a rerun matches rows in place. The guard fails on duplicate-row
ratios above 2%. `gdt-historical-backfill` runs itself a second time and fails
the build if the second run changes anything.

---

## 4. Timestamp churn

**How it happens.** Each run stamps `retrievedAt` and rewrites every file. Every
scheduled run produces a diff, reviewers stop reading them, and a real change
slips through unnoticed.

**Defence.** `VOLATILE_FIELDS` (`generatedAt`, `retrievedAt`, `snapshotAt`,
`source.retrievedAt`) are excluded from every change comparison, and
`contentHash` is computed with them stripped. A run that finds identical data
rewrites nothing, and the stored `retrievedAt` keeps recording when we *first*
saw that content. Membership history uses date-granularity `observedAt`, so a
four-times-daily workflow cannot append four rows for one event.

A second variant, and the one that actually got through review: a **per-day
stamp**. Truncating a timestamp to a date does not make it stable, it makes it
stable *for a day*. Two fields had this shape — an `UNCHANGED` heartbeat row
appended to `idx30.history.jsonl` whenever a run found nothing, and
`companies.json`'s `lastSeenAt`, restamped on all thirty constituents every run.
Both were invisible for as long as every run happened on the date the seed data
was generated: the value already committed was today's, so nothing moved. On the
first run of the next day, both moved at once, and a no-change run would have
opened a pull request containing no facts.

The heartbeat is gone — membership history now records membership events only,
and "we looked and nothing had changed" lives in the per-run report under
`data/goh-dip-tong/pipeline-runs/`, where a statement about a run belongs.
`lastSeenAt` joined `VOLATILE_FIELDS`, and the volatile strip now recurses into
lists, because these stamps sit on array elements rather than at the top level
and a top-level-only strip never saw them.

The lesson generalises past these two fields: **a test that only ever runs on
one date cannot detect date-dependent churn.** Both the unit suite
(`test_no_change_churn.py`) and the acceptance script now drive the pipeline
through 2026-08-01, 2026-12-31, 2027-03-14 and 2031-06-30 and require
`filesChanged=0` with a byte-identical config tree at each.

A third variant is worth naming separately: a **side-car status file**. An
earlier design wrote `pipeline-runs/last-success.json` on every successful run
to support the staleness check. Its entire content is timestamps, so it changed
every run — and once tracked it would have produced a commit on every scheduled
run with no data change, defeating the whole commit policy. The fix was to stop
writing it and derive the same signal from the newest `retrievedAt` already
present in the committed data. If you find yourself adding a file that records
*when a process ran*, check whether the data can answer the question instead.

*(All three were caught by the pipeline's own idempotency check and the Stage 1
acceptance run, not by inspection.)*

---

## 5. A restatement silently overwrites history

**How it happens.** A company reissues FY2025 with a lower profit. The pipeline
updates the row. Every prior analysis becomes irreproducible and nobody knows a
restatement occurred.

**Defence.** `factKey` excludes `basis`, so a `RESTATED` revision shares an
identity with the `REPORTED` original and supersedes it explicitly. The prior
revision stays in the store flagged `SUPERSEDED` and is written to
`financial-statements/restated/`. `normalized/current-facts.jsonl` holds the
current view; the full revision history sits alongside it.

*(Getting this wrong is easy: an earlier draft of this pipeline put `basis` in
the key, which split every restatement into two unrelated lineages and made the
supersession chain silently non-functional. The test suite now pins it.)*

---

## 6. Segment data collides with consolidated

**How it happens.** Segment revenue and consolidated revenue for the same period
share a key. One overwrites the other, or the run fails with a confusing
duplicate error.

**Defence.** `segment` is part of `factKey`, defaulting to `CONSOLIDATED`.

---

## 7. Cumulative interim figures read as standalone quarters

**How it happens.** Indonesian interim filings are year-to-date. The "Q3" report
contains nine months. Treated as a quarter, revenue looks 3x too high.

**Defence.** `YTD_Q1/Q2/Q3` and standalone `Q1..Q4` are distinct period types.
`standalone_from_ytd()` returns `None` when either input is missing rather than
treating the absent prior period as zero — which would report nine months as one
quarter.

---

## 8. A wrong-but-plausible valuation model

**How it happens.** A new sector enters the index. The pipeline assigns a
generic enterprise-DCF model. A bank gets valued on EV/EBITDA, which is
meaningless — debt is a bank's raw material, not its financing.

**Defence.** Unmapped classification → `modelFamily: null` +
`coverageStatus: ONBOARDING`. Enforced by the schema *and* by the `Constituent`
type at construction. A family declared with `supported: false` also yields
`ONBOARDING`. There is no generic fallback model anywhere in the codebase.

---

## 9. Scale and currency errors

**How it happens.** A filing reports in millions; another in billions; a third in
USD. Mixed, they are off by 1000x, or silently cross-currency.

**Defence.** Scale is normalized to base units on ingest with the reported scale
retained on the record. `assert_same_currency()` raises rather than combining
across currencies — Stage 1 has no FX source, and inventing one is worse than
refusing.

**Residual risk.** A filing that misstates its own scale header.

---

## 10. Rumour rendered as fact

**How it happens.** A media report about an acquisition is stored like an
official announcement.

**Defence.** Events carry a certainty ladder: `RUMOR` → `MEDIA_REPORT` →
`PROPOSAL` → `OFFICIAL_DECISION` → `IMPLEMENTED` →
`COMPANY_IMPACT_CONFIRMED`. Only `OFFICIAL_DECISION` and above may be treated as
fact; the disclosure collector raises a warning for anything below.

---

## 11. Rights breach

**How it happens.** A collector writes provider data into a public repository,
or the UI displays data the licence does not permit.

**Defence.** The rights gate answers two questions in one place: may this
provider run, and may this record go to *this* destination. A restricted write
raises `RightsViolationError` rather than logging. Restricted output is routed to
the git-ignored `_private/` tree. `sources.yml` and `SOURCE_REGISTER.md` are
cross-checked at runtime and in CI. A provider may narrow its rights, never
widen them.

---

## 12. A disabled source that looks healthy

**How it happens.** A provider is turned off. Collection returns an empty list.
The run passes. Nobody notices data stopped arriving.

**Defence.** Running a disabled provider raises `ProviderDisabledError` rather
than returning empty. `resolve()` raises when nothing is runnable, naming every
candidate and why it was rejected. `check_source_staleness()` flags enabled
sources with no recent success. Every quality report lists source state.

---

## 13. Hard-coded index size

**How it happens.** The pipeline asserts exactly 30 constituents. A suspension
produces 29. Everything fails on the day the data matters most.

**Defence.** The active count is compared to the count the *source* declared. A
deviation from 30 is a warning asking a human to look — never a hard failure.
Disagreeing with the source is critical, whatever the number.

---

## 14. Repository degradation

**How it happens.** A PDF here, an unfiltered dump there. Two years later the
clone is 4 GB.

**Defence.** The repository guard checks file size, total size, file count,
forbidden extensions, accidental binaries, secret patterns, HTML-as-data,
duplicate rows, schema growth and sentinel values before any commit.
Thresholds live in `guard.yml` so raising one is a visible diff. Parquet is off
until someone measures its versioning cost.

---

## 15. Invalid data replacing good data

**How it happens.** A partial outage yields half a dataset. It validates loosely,
gets written, and the previously-good data is gone.

**Defence.** Fail-closed publication: any CRITICAL failure means nothing is
promoted and the last validated data stands. Writes are atomic (temp file +
rename), so a crash mid-write cannot truncate a good file. An empty universe is
refused outright. Fail-soft is scoped to collection — one issuer failing does not
abandon the others — and never to publication.

---

## 16. Secrets committed

**Defence.** The guard scans every generated file for secret-shaped strings and
fails on a single hit — no threshold, no allowlist. `test_workflows.py` asserts
no workflow references a stored secret. Stage 1 has no authenticated source, so
nothing should need a credential.

---

## 17. Scheduled workflows firing unexpectedly

**How it happens.** Schedules are added during development and start opening
pull requests, burning Actions minutes, or hitting a source before its rights
are settled.

**Defence.** Every scheduled job is gated behind `GDT_SCHEDULES_ENABLED`, which
is unset by default. Manual dispatch is never gated. No workflow can push to the
default branch; commits are restricted to `config/goh-dip-tong` and
`data/goh-dip-tong`.

---

## 18. Claiming data is live when it is not

**Defence.** Every generated artefact carries `provenance` and `authoritative`.
Everything currently produced is `FIXTURE` / `false`. Research snapshots carry
disclaimers in the payload so they cannot be dropped in transit, and
`marketContext` is explicitly `{available: false, reason: …}` rather than absent
— the engine must handle the no-price case instead of assuming one exists.

**Stage 3 obligation:** the UI must show a development-data notice whenever
`authoritative` is `false`.
