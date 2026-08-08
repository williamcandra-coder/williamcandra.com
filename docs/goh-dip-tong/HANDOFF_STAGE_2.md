# Goh Dip Tong — Stage 2 Handoff (slice 1)

**Stage:** 2 — deterministic calculation and research engine
**Repository:** `williamcandra-coder/williamcandra.com`
**Slice:** 1 of N — contracts, registry, propagation, inputs, output contract,
labelling, refusal framework

## Status: `SKELETON_COMPLETE_NO_VALUATION`

Read this before building on Stage 2. The engine's structure is finished and
tested. **No valuation mathematics exists, and no issuer is valued.** Every
real issuer returns a structured refusal naming exactly what is missing.

| | |
|---|---|
| Engine unit tests | **177 passed**, 0 failed |
| Stage 2 acceptance checks | **53/53 passed** (52 requirement checks + 1 isolation self-check) |
| Stage 1 regression | **262 passed** (was 259; +3 for the new CI wiring), **71/71** acceptance |
| Model families registered | **17** — every family declared in `models.yml` |
| Model families implemented | **0** |
| Issuers valued | **0** |
| Formulas registered | **5** — generic primitives only |
| Mode of every output | `FIXTURE_TEST_ONLY`, derived from provenance |

### What this slice is not

No forecast mathematics, no valuation mathematics, no reverse solver, no
scenarios, no bridge, no narration, no UI. Those are later slices. The sections
for them exist in the output contract and say `NOT_PRODUCED` with a reason —
an explicit absence rather than an empty object a reader has to interpret.

---

## 1. The risk-free rate decision — recorded, per instruction

**BI_7DRR must not be used as a production risk-free rate, and is not.**

BI_7DRR — the Bank Indonesia 7-day reverse repo rate — is a short-term *policy*
rate. Using it to discount multi-decade equity cash flows understates the
discount rate, which inflates every valuation built on it, and does so
invisibly: the output looks like an ordinary CAPM figure. There is no honest way
to tell from the number that the input was wrong.

It therefore remains **contextual macro data**. It is collected, carried into
every snapshot's `modelAudit.macroContext`, and flagged
`usedInCalculation: false` on every row. A test and an acceptance check both
assert that no macro series feeds any calculation.

`engine/goh_dip_tong/config/cost-of-capital.yml` records this as a structured
decision, not a comment:

```yaml
risk_free:
  validated: false
  rejected_substitutes:
    - id: BI_7DRR
      reason: >
        Short-term policy rate, not a risk-free yield. Substituting it
        understates the cost of equity and inflates every valuation derived
        from it, while looking like an ordinary CAPM input.
```

The `VALIDATED_RISK_FREE_RATE` gate reads `risk_free.validated`. It is `false`
and stays `false` until a validated long-dated Indonesian government bond yield
(IndoGB 10-year or similar) is collected, with a documented source, a retrieval
date and rights permitting the derived use. **None exists today.**

### The synthetic cost of equity, and the boundary around it

The bank model's mathematics still has to be provable. So `cost-of-capital.yml`
carries a `synthetic:` block with an explicitly labelled `SYNTHETIC` cost of
equity, for engine test fixtures only.

Reaching it requires `ModelContext(allow_synthetic_cost_of_equity=True)`. That
switch has exactly one caller: the test harness. It is **not** exposed as a
command-line flag, because a flag that turns invented assumptions into
publishable output is a flag that will eventually be used by accident. The CLI
never sets it, and `test_refusal.py` asserts that by parsing `cli.py`'s AST — so
adding such a flag later fails the build.

**Consequence:** every real Stage 1 fixture issuer returns
`valuation.status = REFUSED` until a validated risk-free input, the required
bank facts, a share count and market data all exist. Even the synthetic bank —
whose data is complete — is refused unless the synthetic permission is asked for
by name.

---

## 2. Why nothing is valued, per issuer

Four gates fail for every real issuer. Each is a fact about the data, not about
the code.

| Ticker | Facts | Missing required metrics | Headline refusal |
|---|---:|---:|---|
| `BBCA` | 10 | 15 of 17 | `INSUFFICIENT_INPUTS` |
| `TLKM` | 9 | 3 of 6 | `INSUFFICIENT_INPUTS` |
| `ASII` | 2 | 5 of 6 | `INSUFFICIENT_INPUTS` |

All three additionally fail `MIN_HISTORY_PERIODS` (one annual period — a level,
not a trend), `VALIDATED_RISK_FREE_RATE`, `MARKET_DATA_AVAILABLE` and
`MODEL_IMPLEMENTED`.

`MODEL_IMPLEMENTED` is deliberately **last** in the refusal precedence.
Implementing the mathematics would not produce a number while the data is
absent, so leading with "model not implemented" would point at the wrong
problem. The refusal names every failed gate, so nothing is hidden by the
choice of headline.

The 27 IDX30 constituents with no Stage 1 snapshot produce no engine output at
all. The engine reports `SnapshotMissing` and moves on; it will not invent one.

---

## 3. Boundaries observed

- **Engine-owned synthetic data never enters the published data tree.** Enforced
  by hashing every file under `engine/goh_dip_tong/fixtures/` and asserting no
  published file shares a hash, plus a check that no published document carries
  the `SYNTHETIC` flag and that `SYNB` appears nowhere. Both run in the unit
  suite and again against a live build in the acceptance script.
- **`PRODUCTION` mode is unreachable.** The label is derived from provenance,
  never assigned. A test asserts no module outside `provenance.py` and
  `enums.py` even mentions `EngineMode.PRODUCTION`.
- **Unsupported families return `MODEL_UNDER_VALIDATION`.** All 17 declared
  families are registered; an unregistered one would fall through to whatever
  the caller did next, which is how a generic model ends up valuing a bank.
- **No live provider enabled, no schedule changed.** `sources.yml` and
  `schedules.yml` are byte-identical to `main`.
- **No UI.** `goh-dip-tong.html` does not exist.
- **`index.html`, `goh-pok-tong.html`, `_config.yml`, `CNAME` untouched.**
- **Dependency direction is one-way.** The engine imports the pipeline, never
  the reverse; asserted by AST scan. Stage 1 remains independently runnable.
- **No new dependency.** Standard library plus what Stage 1 already installs.

---

## 4. Stage 1 changes made in this slice

Four corrections, each approved before implementation.

### 4a. Canonical bank metrics (`config/goh-dip-tong/metrics.yml`)

`metrics.yml` states that a metric not defined there must not be published, so
the model must not require vocabulary the registry lacks. Added **11 reported**
bank drivers and **14 derived** ratios.

Reported: `earning_assets`, `loans`, `deposits`, `casa_deposits`, `fee_income`,
`operating_expense`, `provision_expense`, `non_performing_loans`,
`loan_loss_allowance`, `tier1_capital`, `risk_weighted_assets`.

Derived: `eps`, `bvps`, `roe`, `roa`, `payout_ratio`, `sustainable_growth`,
`net_interest_income`, `nim`, `cost_of_credit`, `npl_ratio_gross`,
`npl_coverage_ratio`, `casa_ratio`, `capital_adequacy_ratio`,
`cost_to_income_ratio`.

Every ratio is labelled `basis: DERIVED`, asserted by an acceptance check — a
derived margin must never be able to look like a reported one. NPL and coverage
are stored as **amounts**, not ratios, so the ratio is derived and its
denominator stays visible.

**Defining these does not create them.** Not one is collected by any enabled
provider. That is precisely why the bank valuation refuses, and now it refuses
with a specific list rather than a shrug.

### 4b. `UNDEFINED_DENOMINATOR`

Added to `metrics.yml`'s `missing_reasons` and to `MissingReason` in
`pipeline/goh_dip_tong/contracts/enums.py`. A concealed divide-by-zero is the
derived-metric equivalent of missing becoming zero; this gives it a name so it
can fail visibly instead of returning `inf`, `nan`, or a swallowed zero.

### 4c. The `segment` contract correction

`research-input.schema.json` gained an optional `segment` field, and
`cmd_research_snapshot` now carries it through.

This fixed a real defect. BBCA's snapshot held two indistinguishable
`revenue FY2025` rows — one consolidated with a value, one `WHOLESALE_BANKING`
and null — and `quality.missingCriticalMetrics` therefore reported `revenue` as
missing while consolidated revenue sat two lines above it. Completeness and the
missing list are now computed over consolidated facts only.

Before and after, for BBCA:

```
completeness 0.9   missingCriticalMetrics ["revenue"]   ← wrong
completeness 1.0   missingCriticalMetrics []            ← correct
```

The engine treats genuinely indistinguishable facts as `AMBIGUOUS_FACTS` and
refuses rather than picking one, because picking one would be a silent guess
that changes a published number.

### 4d. CI wiring (`.github/workflows/gdt-data-quality.yml`)

Added two steps — the Stage 2 unit suite and the Stage 2 acceptance script —
and `engine/**` to the pull-request path filter. **No new workflow, no new
trigger, no schedule.** `test_workflows.py` now asserts all five gates stay
wired in; the engine tests live outside `pipeline/`, so the existing pytest path
would not have collected them and an engine regression would never have failed
CI.

---

## 5. Contracts for later slices

### Input

| Tier | Path | Why |
|---|---|---|
| 1 | `data/goh-dip-tong/research-snapshots/sample/<TICKER>.json` | The declared Stage 2 contract. Validation gate, identity, rights statement |
| 2 | `financial-facts/{annual,quarterly}/<TICKER>.jsonl` + `financial-statements/restated/restatements.jsonl` | Revision history. **Required for any historical cutoff** |
| 3 | `idx30.current.json`, `companies.json`, `models.yml`, `metrics.yml` | Universe and definitions |
| 4 | `macro/{bank-indonesia,ojk,bps}/*.jsonl` | Context only; nothing calculates with it |

The input schema calls itself *"the ONLY shape Stage 2 should have to read"*.
That is true for a current-date run and false for a historical one: the snapshot
carries only the latest revision of each fact. `modelAudit.factSource` records
which tier was actually used.

### Output

`data/goh-dip-tong/research-snapshots/<TICKER>/<YYYY-MM-DD>/<model-version>.json`
plus `current/<TICKER>.json`, against
`schemas/goh-dip-tong/research-snapshot.schema.json` — deliberately **not** the
input schema. Conflating them is how a derived figure eventually gets read back
as a reported one.

Additions beyond spec §2.9's list: `mode`, `modelVersion`, `engineVersion`,
`asOf`, `researchStatus`, `disclaimers`.

### Two vocabularies, one owner each

`coverageStatus` (`FULL_RESEARCH` / `FINANCIALS` / `ONBOARDING` / `SUSPENDED`)
belongs to Stage 1's universe registry. `researchStatus` (`DISCOVERY` /
`FINANCIALS_VALIDATED` / `MODEL_UNDER_VALIDATION` / `FULL_RESEARCH` /
`MODEL_SUSPENDED` / `STALE`) is the engine's own ladder from spec §2.8. They
overlap but are not the same. **The engine reads `coverageStatus` and never
writes it.**

---

## 6. Determinism, and the churn lesson carried forward

`calculatedAt`, `asOf` and `ageDays` are volatile and excluded from the content
hash. `asOf` and `ageDays` are the subtle ones: they are exactly Stage 1's
per-day-stamp defect in a new place. A value truncated to a date is stable *for
a day*, not stable — leaving them in would give identical research a new hash
every morning and deposit an identical document under a new date on every
rebuild.

A snapshot is written only when its substantive content differs from the newest
one already stored. Verified across a four-date sweep (2026-08-01, 2026-12-31,
2027-03-14, 2027-07-31) in both the unit suite and the acceptance script: the
output tree is byte-identical after all four.

The converse is asserted too, so the quiet was not bought by suppressing real
changes:

- A cutoff spanning the BBCA restatement **does** produce a new snapshot.
- Inputs crossing the 400-day staleness threshold **do** move the hash and flip
  `researchStatus` to `STALE`.

Reproducibility is checked across three separate processes with differing
`PYTHONHASHSEED`, so a dict iteration order leaking into output would fail.

`FORMULA_REGISTRY_HASH` fingerprints every formula's identity and logic via its
AST — insensitive to comments and layout, sensitive to behaviour. Changing a
formula without bumping `MODEL_VERSION` fails the build. (The AST dump varies
between Python versions, so that test is gated to 3.11, which is what CI pins.)

---

## 7. Known gaps for the next slice

1. **No forecast or valuation mathematics.** The declared next step: residual
   income, justified P/B and dividend discount for `BANK`, against
   `fixtures/synthetic-bank/SYNB.json` with the `SYNTHETIC` cost of equity.
2. **No reverse solver.** Spec §2.7 is blocked by rights, not by code — solving
   a price back to assumptions requires a price, and there is none.
3. **No TTM aggregation.** `periods.ttm_window()` provides the window; the
   aggregation is still the engine's to build.
4. **No normalization layer.** `normalized` is `NOT_PRODUCED`.
5. **No narration.** When it arrives, `uncleView` must be a *projection* of the
   record, never a recomputation, with identity-matching enforced by test.
6. **No FX.** Inherited from Stage 1 — `assert_same_currency()` raises rather
   than combining currencies, and the engine does not override that.
7. **Cost-of-capital config is a shape, not a set of values.** `beta`,
   `equity_risk_premium` and `risk_free` are all `validated: false`.

---

## 8. Git status

Nothing has been committed or pushed. All work is uncommitted in the working
tree of branch `claude/gdt-stage-2-engine`, awaiting review.
