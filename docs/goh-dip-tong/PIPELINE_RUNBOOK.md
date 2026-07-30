# Goh Dip Tong — Pipeline Runbook

How to run, inspect and operate the Stage 1 data pipeline.

---

## Setup

```bash
cd /path/to/williamcandra.com
python3 -m pip install -r pipeline/goh_dip_tong/requirements.txt
```

Python 3.9+. Dependencies are `PyYAML`, `jsonschema`, `requests` (lazy-imported,
only for live providers) and `pytest`. No pandas, no compiled extensions, no
build step.

Every command runs from the repository root:

```bash
python3 -m pipeline.goh_dip_tong.cli <command> [--write-mode …] [--provider …] [--verbose]
```

Override the repository root with `GDT_REPO_ROOT=/some/path` if you need to.

---

## Write modes

| Mode | Effect |
|---|---|
| `validate_only` (default) | Collects, parses, validates. **Promotes nothing.** |
| `commit` | Promotes validated output into the working tree. |

`commit` does **not** mean "push to the default branch" — no workflow can do
that. It means "write the validated records to their files". Everything then
goes through a `gdt/auto/*` branch and a pull request.

If any CRITICAL check fails, nothing is promoted regardless of write mode. Fail
closed is the default, not an option.

---

## Commands

### Inspect before you run anything

```bash
python3 -m pipeline.goh_dip_tong.cli sources
```

Lists every declared provider with its kind, enabled flag, runnable state and
rights status, then cross-checks the declared rights against
`docs/goh-dip-tong/SOURCE_REGISTER.md`. Exits non-zero if they disagree.

### Registry update — the IDX30 universe

```bash
python3 -m pipeline.goh_dip_tong.cli registry-update                      # dry run
python3 -m pipeline.goh_dip_tong.cli registry-update --write-mode commit  # promote
```

Discovers membership, resolves model families from `models.yml`, diffs against
the committed universe, validates, and writes `idx30.current.json`,
`companies.json`, `categories.json`, appends `idx30.history.jsonl` and produces
a human-readable diff at `data/goh-dip-tong/registry/history/latest-diff.md`.

**Run this first.** Every other collector refuses to guess a ticker list.

### Daily market update

```bash
python3 -m pipeline.goh_dip_tong.cli daily-update --write-mode commit
```

Collects only active constituents. Because `fixture_market_prices` is
`PRIVATE_RESEARCH_ONLY`, output lands in `data/goh-dip-tong/_private/` and is
git-ignored — so this legitimately produces **no git diff**. That is correct, not
a failure.

### Disclosure watch

```bash
python3 -m pipeline.goh_dip_tong.cli disclosure-watch --write-mode commit
```

Writes metadata to `disclosures/metadata/<YYYY-MM>.jsonl`, manifest rows for
documents that must not be committed, and a queue at
`disclosures/metadata/pending-financial.json` for the financial workflow.

### Financial update

```bash
python3 -m pipeline.goh_dip_tong.cli financial-update --write-mode commit
```

Parses facts, normalizes scale/period/currency/sign, detects restatements, and
writes annual and quarterly fact stores plus
`financial-statements/normalized/current-facts.jsonl` (latest revision per
fact). Superseded revisions are retained, flagged, and written to
`financial-statements/restated/`.

### Macro update

```bash
python3 -m pipeline.goh_dip_tong.cli macro-update --write-mode commit
```

Collects only series registered in `collectors/macro.py::REGISTERED_SERIES`.
Vintage is part of the primary key, so a revised observation is a new row.

### Historical backfill

```bash
python3 -m pipeline.goh_dip_tong.cli backfill --scope all --write-mode commit
python3 -m pipeline.goh_dip_tong.cli backfill --scope data_type \
    --data-type financial_facts --start-year 2020 --end-year 2025 \
    --write-mode commit
```

Fail-soft across data types: one failing dataset does not abandon the rest.
Idempotent by construction — every dataset is written through an upsert keyed on
the record's primary key.

### Stage 2 contract sample

```bash
python3 -m pipeline.goh_dip_tong.cli research-snapshot --ticker BBCA
```

### Audits

```bash
python3 -m pipeline.goh_dip_tong.cli quality --verbose    # full data-quality audit
python3 -m pipeline.goh_dip_tong.cli repo-guard --verbose # repository-data guard
python3 -m pytest pipeline/goh_dip_tong/tests -q          # 180 unit tests
./pipeline/goh_dip_tong/tests/acceptance.sh               # 63 acceptance checks
```

### The acceptance test

```bash
./pipeline/goh_dip_tong/tests/acceptance.sh
echo $?      # 0 = every check passed, 1 = at least one failed
```

Verifies all 17 Stage 1 acceptance requirements: the universe comes from
`idx30.current.json`, no ticker list is hard-coded in UI code, data is separated
by type, history is append-only, former constituents survive, simulated
membership and category changes propagate, missing never becomes zero, repeated
collection produces no duplicates, invalid data cannot replace good data, every
cron matches `schedules.yml`, no-change runs commit nothing, price collection
stays disabled, no secret or restricted document is tracked, the size guards
pass, and `index.html` / `goh-pok-tong.html` still match `HEAD`.

**It never writes to the repository.** Read-only assertions run against the
working tree; every destructive simulation — membership changes, invalid-data
rejection, idempotency cycles — runs in a throwaway sandbox under `$(mktemp -d)`
that is removed on exit. A closing self-check compares hashes of
`config/goh-dip-tong` and `data/goh-dip-tong` taken before and after, and fails
the run if either moved. Safe to run mid-work and on a CI pull request.

It resolves its own repository root from `${BASH_SOURCE[0]}`, so it works from
any checkout and any working directory.

### Full local cycle

```bash
python3 -m pipeline.goh_dip_tong.cli sources
for c in registry-update daily-update disclosure-watch financial-update macro-update; do
  python3 -m pipeline.goh_dip_tong.cli "$c" --write-mode commit || break
done
python3 -m pipeline.goh_dip_tong.cli quality
python3 -m pipeline.goh_dip_tong.cli repo-guard
git status --short config/goh-dip-tong data/goh-dip-tong
```

Running that twice in a row must leave the second run with **zero** file
changes. If it does not, something is non-idempotent and would grow the
repository on every scheduled run.

---

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Ran, validation passed (whether or not anything changed). |
| `1` | Validation failed. Nothing was promoted. |
| `2` | Usage or configuration error. |

---

## Workflows

All seven live in `.github/workflows/`, all support `workflow_dispatch`, and
their cron expressions are asserted against `config/goh-dip-tong/schedules.yml`
by `test_workflows.py` — a cron edited in only one place fails CI.

| Workflow | Cron (UTC) | Local (WIB) |
|---|---|---|
| `gdt-registry-update` | `30 22 * * 1` | Tue 05:30 |
| `gdt-historical-backfill` | *manual only* | — |
| `gdt-daily-update` | `30 11 * * 1-5` | Mon–Fri 18:30 |
| `gdt-disclosure-watch` | `17 2,6,10,14 * * *` | 09:17 / 13:17 / 17:17 / 21:17 |
| `gdt-financial-update` | `45 12 * * *` | 19:45 |
| `gdt-macro-update` | `40 23 * * 0` | Mon 06:40 |
| `gdt-data-quality` | `5 6 * * *` + every PR | 13:05 |
| `gdt-source-connectivity-smoke` | *manual only* | — |

### Source connectivity smoke test

```bash
python3 -m pipeline.goh_dip_tong.cli connectivity-smoke --output /tmp/connectivity.json
```

Diagnostic only. Probes the `official_url` of each configured live source and
records **metadata only**: provider id, URL, timestamp, HTTP status, redirect
target, content type, response size (from `Content-Length`) and an outcome. **No
response body is read, stored or printed.**

Outcomes: `REACHABLE_UNVALIDATED` · `UNREACHABLE_FROM_GITHUB_ACTIONS` ·
`AUTHENTICATION_REQUIRED` · `ACCESS_CONTROLLED` · `CONTENT_TYPE_UNEXPECTED` ·
`NETWORK_ERROR` · `NOT_TESTED`

Conservative by construction: one request per provider, `HEAD` first with `GET`
only if the method is rejected, redirects recorded but never followed, no
retries, a pause between providers, and an identifying User-Agent. Nothing
bypasses authentication, rate limiting or bot protection — a 401 or 403 is the
answer, recorded and moved past.

**`REACHABLE_UNVALIDATED` is the best possible result and it enables nothing.**
HTTP 200 means a socket opened. Enabling a source remains a human decision
requiring an edit to `sources.yml` *and* a dated rights review in
`SOURCE_REGISTER.md`. Every record carries `enablesProvider: false`.

Run it from the Actions tab via `gdt-source-connectivity-smoke` (manual dispatch
only — it has no schedule). The report is uploaded as the artifact
`gdt-source-connectivity-report`.

### Scheduled runs are OFF by default

Every scheduled job is gated by:

```yaml
if: github.event_name != 'schedule' || vars.GDT_SCHEDULES_ENABLED == 'true'
```

`GDT_SCHEDULES_ENABLED` is unset, so **no schedule does anything** until you set
it. Manual dispatch is never gated.

To switch schedules on: repository **Settings → Secrets and variables → Actions
→ Variables → New repository variable**, name `GDT_SCHEDULES_ENABLED`, value
`true`. To switch them off again, delete it or set any other value.

### Commit policy

No workflow can push to the default branch. A workflow that produces changes
creates a `gdt/auto/*` branch, stages **only** `config/goh-dip-tong` and
`data/goh-dip-tong`, commits as `data(gdt): update <data-type> through <date>`,
pushes the branch and opens a pull request. Merge is manual.

Top-level `permissions` is `contents: read` everywhere. Only the PR-opening job
gets `contents: write` + `pull-requests: write`. `gdt-data-quality` has no write
permission at all.

A workflow that finds no change exits successfully without committing.

---

## Operational notes

**Nothing collects live data today.** Every live provider is disabled — the
hosts are unreachable from CI (egress policy answers 403 to `CONNECT`) and their
rights are unreviewed. See `SOURCE_REGISTER.md`.

**Quality reports** land in `data/goh-dip-tong/quality/latest/<workflow>.json`
and are uploaded as workflow artifacts. A copy is appended to
`quality/history/` only when the report's substance changed, so the archive
records transitions rather than one identical file per scheduled run.

**Run manifests** land in `data/goh-dip-tong/pipeline-runs/<workflow>.json`.

**Timestamps do not churn files.** `generatedAt` and `retrievedAt` are excluded
from change comparison, so a run that finds identical data rewrites nothing and
the stored `retrievedAt` keeps recording when we *first* saw that content.

---

## Troubleshooting

**`no runnable provider for data type '…'`** — expected. Every live provider is
disabled. `cli sources` shows why for each.

**`PROVIDER DISABLED: … has rights_status=MANUAL_REVIEW_REQUIRED`** — someone
set `enabled: true` without resolving rights. Both locks must be released; see
`SOURCE_REGISTER.md`.

**`RIGHTS VIOLATION: provider … does not permit 'commit_to_repo'`** — working as
designed. Document the right first.

**`no active IDX30 universe found`** — run `registry-update` first.

**`response is an HTML document, not data`** — the source returned an error
page, login wall or bot check with HTTP 200. Do not "fix" this by relaxing the
guard; a saved error page is worse than no data because it looks like success.

**Guard fails on duplicate rows** — almost always a non-idempotent collector.
Check the primary key used by the relevant `upsert_*` call.

**A second identical run changes files** — something volatile is leaking into
stored content. Check that new timestamp fields are in `writers.VOLATILE_FIELDS`
and excluded from any `contentHash`.
