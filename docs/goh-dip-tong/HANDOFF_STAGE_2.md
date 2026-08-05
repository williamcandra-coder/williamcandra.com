# Goh Dip Tong — Stage 2 Handoff to Stage 3

**Stage:** 2 — deterministic calculation and research engine
**Repository:** `williamcandra-coder/williamcandra.com`
**Slices:** 1 (contracts, registry, propagation, inputs, output contract,
labelling, refusal framework) · 2 (BANK forecast and valuation mathematics) ·
3 (research package, finalised views, UI-state fixtures, publishing)

## Status: `ENGINE_COMPLETE_NO_REAL_ISSUER_VALUED`

Read this before building Stage 3. The engine is finished: contracts, the
`BANK` mathematics, the research package, both views, the publishing rules and
the UI contract. **No real issuer is valued, and none can be yet.** Every one
returns a structured refusal naming exactly what is missing.

That was predicted in Slice 1 and proven in Slice 2: implementing the
mathematics did not move Stage 2 toward real output, because the constraint was
never the code. Slice 3 changes nothing about it either. Resolving the Stage 1
data gaps is what would.

| | |
|---|---|
| Stage 2 unit tests | **439 passed**, 0 failed |
| Stage 2 acceptance checks | **82/82 passed** (81 requirement checks + 1 isolation self-check) |
| Stage 1 regression | **262 passed**, **71/71** acceptance |
| Model families registered | **17** — every family declared in `models.yml` |
| Model families implemented | **1** (`BANK`) |
| Issuers valued | **0** |
| Formulas registered | **24** — 5 generic primitives, 12 bank drivers, 9 valuation steps |
| Research rules registered | **25** |
| Mode of every output | `FIXTURE_TEST_ONLY`, derived from provenance |
| Engine / model version | `0.3.0` / `0.3.0` |

---

## 1. What Stage 3 reads

Four files, and nothing else. The UI does not read the fact store, the
restatement log, macro series, `sources.yml`, or anything under
`engine/goh_dip_tong/`.

| Purpose | Path |
|---|---|
| **IDX30 picker config** | `config/goh-dip-tong/idx30.current.json` |
| **Current research snapshot** | `data/goh-dip-tong/research-snapshots/current/<TICKER>.json` |
| **Full research snapshot** | `data/goh-dip-tong/research-snapshots/<TICKER>/<YYYY-MM-DD>/<MODEL_VERSION>.json` |
| **Output schema** | `schemas/goh-dip-tong/research-snapshot.schema.json` |

### The picker

`config/goh-dip-tong/idx30.current.json` holds 30 constituents. Every one
carries `ticker`, `name`, `sectorCode`, `sectorName`, `industryCode`,
`industryName`, `modelFamily`, `coverageStatus`, `active`, `enteredAt` and
`sourceRef`. The first four are the UI contract and a Stage 1 quality check
(`quality.ui_contract`) fails the build if any constituent loses one.

The file also carries `authoritative: false`. **It is a development fixture, not
the published index**, and that is one of the reasons every snapshot is
`FIXTURE_TEST_ONLY`.

### The pointer

`current/<TICKER>.json` is small and is the right thing to fetch first:

```json
{
  "schemaVersion": "1.0.0", "ticker": "BBCA", "mode": "FIXTURE_TEST_ONLY",
  "asOf": "2026-07-31", "modelVersion": "0.3.0", "engineVersion": "0.3.0",
  "researchStatus": "MODEL_UNDER_VALIDATION", "uiState": "PARTIAL",
  "valuationStatus": "REFUSED", "contentHash": "…",
  "snapshot": "data/goh-dip-tong/research-snapshots/BBCA/2026-07-31/0.3.0.json"
}
```

`asOf` is the snapshot's cutoff, **not the date of the last rebuild**. A pointer
stamped with the rebuild date would churn daily while pointing at the same
unchanged research.

**There are no snapshots under `data/` today.** The engine runs in
`validate_only` mode and nothing is committed. Build against
`engine/goh_dip_tong/fixtures/ui_states/` — see section 9.

---

## 2. `uiState` — switch on this, not on anything else

`uiState` is derived once, in `engine/goh_dip_tong/publishing/ui_states.py`,
from `coverageStatus`, `researchStatus`, the valuation outcome and the refusal
reason. Exactly one state applies to any document.

There are three vocabularies in this repository and each has one owner:

| Vocabulary | Owner | Meaning |
|---|---|---|
| `coverageStatus` | Stage 1's universe registry | Whether the company is covered at all |
| `researchStatus` | The engine | How far research has actually got (spec §2.8) |
| `uiState` | The engine | What to render |

The engine reads `coverageStatus` and **never writes it**. A UI that recombined
all three in a template would recombine them slightly differently on the next
screen, which is why the third exists.

### Precedence, in order

1. `coverageStatus == SUSPENDED` or `researchStatus == MODEL_SUSPENDED` → **`SUSPENDED`**
2. `researchStatus == STALE` → **`STALE`**
3. no `modelFamily`, or `coverageStatus == ONBOARDING` → **`ONBOARDING`**
4. `valuation.status == VALUED` → **`FULL_RESEARCH`**
5. refusal reason in `{INSUFFICIENT_INPUTS, INSUFFICIENT_HISTORY, NO_MARKET_DATA}` → **`PARTIAL`**
6. otherwise → **`MODEL_UNDER_VALIDATION`**

Suspension and staleness are checked before anything about the model, so a
suspended issuer can never render as current research however well the
mathematics went.

### Rendering expectations

| `uiState` | Headline | Show | Do not show |
|---|---|---|---|
| **`FULL_RESEARCH`** | The base-case value per share, with bear and bull | Uncle View, Analyst View, thesis, counter-thesis, catalysts, risks, breakers, method comparison, drivers, forecast, evidence | — |
| **`MODEL_UNDER_VALIDATION`** | "The model is not validated for this issuer yet" | `valuation.reason`, `failedGates`, `note`, reported facts, evidence, freshness | Any number presented as a value or a range |
| **`PARTIAL`** | "Not enough data to run the model yet" | `valuation.missingInputs` — the specific metric list — plus `quality.completeness`, reported facts | Any valuation, any thesis, any per-share figure |
| **`ONBOARDING`** | "Not yet classified" | Identity, `coverageStatus`, reported facts | Anything model-shaped; there is no model |
| **`STALE`** | "Based on inputs from ⟨date⟩" | Everything the state would otherwise show, **with the staleness banner attached to every figure** | The figures without the banner |
| **`SUSPENDED`** | "Coverage withdrawn" | `coverageStatus`, the last `asOf`, reported facts | Any research as if it were current |

Two rules that apply in every state:

- **Render the refusal; do not hide it.** `REFUSED` is a result. `failedGates`,
  `missingInputs` and `note` exist so the UI can say *what is missing* rather
  than showing an empty panel. Five of the six states are refusals because
  five-sixths of the rendering work is where there is no number.
- **Show `disclaimers[0]`.** It states the mode, and it is first for a reason: a
  reader who stops after one line should have read the one that says this is
  not real analysis.

### `researchStatus`, in full

`DISCOVERY` · `FINANCIALS_VALIDATED` · `MODEL_UNDER_VALIDATION` ·
`FULL_RESEARCH` · `MODEL_SUSPENDED` · `STALE`

Carried in the document for audit and for anyone who wants the engine's own
ladder. **The UI should switch on `uiState`.** The two agree on four values and
deliberately differ on two: an issuer whose `researchStatus` is
`MODEL_UNDER_VALIDATION` may be `PARTIAL` (short of data) or
`MODEL_UNDER_VALIDATION` (short of methodology), and that difference is the one
a reader cares about — one is waiting on collection, the other on a decision.

---

## 3. Uncle View and Analyst View

**Two projections of one record set. Neither calculates anything.**

| | Uncle View | Analyst View |
|---|---|---|
| `items` | 4 figures | every calculated record (95 for the synthetic bank) |
| `conclusions` | up to 6, highest importance first | every research record |
| Citations on conclusions | dropped | `supportingRecords` + `supportingEvidence` |
| `evidence` | — | every evidence ref behind the conclusions |

The relationship, which the UI may rely on and the tests enforce:

- **Uncle View's refs are a subset of Analyst View's.** Every figure in the
  simple view appears in the detailed one, under the same `ref`.
- **Shared numbers are byte-identical**, compared as serialised JSON rather than
  as floats. Two views agreeing to fifteen decimals and rendering differently
  still disagree on screen.
- **Uncle View's conclusion IDs are a subset of Analyst View's**, and the same
  `id` carries the same `statement` in both.
- **Neither view recalculates.** Every displayed number carries the `ref` of the
  `Calculated` record it was selected from. `narration/views.py` is parsed by a
  test that fails if an arithmetic operator ever appears in it.

**If the UI needs a figure the views do not carry, the answer is a new engine
record, not arithmetic in a template.** A percentage computed in a template is
exactly how the two views start disagreeing, and nothing downstream would
notice.

---

## 4. The research package

Thesis, counter-thesis, catalysts, risks, breakers, evidence references,
model-audit references and method-comparison notes. **No language model is
involved at any point.** Every statement is emitted by a named rule whose
condition is a comparison between calculated records.

### Where each lands in the document

| Section | Shape |
|---|---|
| `thesis`, `counterThesis`, `methodComparison` | `{status: PRODUCED, records: [...]}` or `{status: NOT_PRODUCED, reason}` |
| `catalysts`, `risks`, `breakers` | arrays of research records; `[]` on a refusal |
| `researchRefs` | `{status: PRODUCED, evidence: [...], modelAudit: [...]}` — always produced |
| `modelAudit.ruleRegistryHash`, `ruleCount`, `rulesFired` | provenance for the above |

### Every record carries

```json
{
  "id": "SYNB.THESIS.bank.roe_above_cost_of_equity.BASE",
  "type": "THESIS",
  "statement": "…",
  "ruleId": "bank.roe_above_cost_of_equity",
  "supportingRecords": ["roe|FY|2030-12-31|CONSOLIDATED|BASE|bank.return_on_average", "…"],
  "supportingEvidence": ["SYNB|equity_attributable_to_parent|FY|2025-12-31|CONSOLIDATED", "…"],
  "scenario": "BASE",
  "importance": "HIGH",
  "severity": null
}
```

`id` is stable across runs: issuer, type, rule, scenario — never a position in a
list. A record identified by its index is renamed whenever a rule ahead of it
stops firing, which is exactly when identity should hold still. **The UI may
anchor to an `id`.**

### Four things a record cannot be

Enforced at construction in `research/records.py`, so an invalid record cannot
reach a snapshot however it got written:

1. **Uncited.** A claim type must cite at least one calculated record *and* at
   least one evidence reference.
2. **Untraceable.** No `rule_id`, no record.
3. **Unranked.** Risks and breakers carry a `severity`, everything else an
   `importance`. An unranked item and a `LOW` one read identically in a list and
   only one of them is honest.
4. **A recommendation.** "target price", "buy", "undervalued", "guaranteed" and
   fourteen other phrases are refused outright.

A fifth check runs at assembly: **every cited ID must exist** in what the engine
actually produced for that issuer. A claim citing a ref that was never
calculated raises rather than being dropped quietly.

### Refusal produces no claims

For a refused issuer the claim rules **never run** — not filtered afterwards,
never run — so there is no unsupported thesis to remove. `researchRefs` is still
produced, because a pointer carries no claim and a reader who wants to know what
the engine had should be able to see it.

---

## 5. Missing-price behaviour

**`marketImplied.available` is `false` for every issuer, including the valued
synthetic bank.**

```json
"marketImplied": {
  "available": false,
  "reason": "No market data is available, so no market-implied case can be solved.",
  "rightsStatus": "PRIVATE_RESEARCH_ONLY",
  "cases": {}
}
```

This is a **rights outcome, not an unimplemented feature**. The reverse-implied
ROE solver is built and tested; solving a price back to operating assumptions
requires a price, and the only enabled price provider's `rights_status` is
`PRIVATE_RESEARCH_ONLY`. The UI should render `reason` rather than an empty
panel.

`MARKET_DATA_AVAILABLE` is a **non-blocking gate**: it is reported in
`modelAudit.gates` and does not prevent a valuation. Treating it as blocking
would mean no issuer could ever be valued without a price feed, which inverts
the relationship between research and the market it is meant to be checked
against.

**Consequence for the UI:** there is no price, so there is no upside figure, no
premium or discount to market, and no market-implied case. Do not compute one
from an external source and render it beside these numbers.

---

## 6. Freshness, quality and evidence fields

### `freshness`

| Field | Meaning |
|---|---|
| `asOf` | The point-in-time cutoff. Only information published on or before this date contributed |
| `newestPublishedAt` | The newest input's publication timestamp |
| `newestRetrievedAt` | Reserved; `null` today |
| `ageDays` | Days between `newestPublishedAt` and `asOf` |
| `stale` | `true` past the 400-day threshold in `engine.yml` |

`asOf` and `ageDays` are **volatile**: excluded from `contentHash` and from
change comparison. Render them, do not diff on them.

### `quality`

| Field | Meaning |
|---|---|
| `status` | `VALID` / `SUSPECT` / `INVALID` / `UNVALIDATED` — Stage 1's assessment of the inputs |
| `completeness` | **What the model needs**, not what the issuer reported. `0.1176` for BBCA: 2 of 17 |
| `flags` | Always includes `FIXTURE_TEST_ONLY` and `NO_VALUATION_PRODUCED` today |
| `missingCriticalMetrics` | The specific metrics the model lacks — the list a `PARTIAL` screen should show |
| `inputQuality` | Stage 1's own quality block, carried through |

`completeness` is the field most likely to be misread. An issuer whose reported
facts are all present is 100% complete by Stage 1's measure and can still be
missing fifteen of the seventeen metrics the model requires — and it is the
second number that decides whether anything can be valued.

### `evidence` and `researchRefs`

`evidence` is the flat list of every source record that contributed:
`{ref, kind, sourceRef, publishedAt}`. `ref` is a Stage 1 `factKey`
(`TICKER|metric|periodType|periodEnd|segment`) or a macro
`seriesId@observationPeriod`.

`researchRefs.evidence` is the same information grouped by metric, as research
records, so a claim's `supportingEvidence` can be resolved to a citation index
entry without walking the flat list.

Every published number can be walked back: `Calculated.inputRefs` → upstream
`Calculated` refs → Stage 1 fact keys.

---

## 7. Fixture warning requirements — mandatory

**Every snapshot is `mode: FIXTURE_TEST_ONLY` and the UI must say so.**

The label is *derived*, every time, from the inputs' own provenance
(`inputs/provenance.py`). It is not a constant somebody has to remember to
change. It flips to `PRODUCTION` on its own when every input is authoritative
and rights-cleared, and nothing else in the engine may write it — a test asserts
that no module outside `provenance.py` and `enums.py` even mentions
`EngineMode.PRODUCTION`.

It appears in four independent places: `mode`, `quality.flags`,
`disclaimers[0]` and `modelAudit.inputProvenance.mode`.

**The UI must:**

1. Render `disclaimers[0]` prominently — not in a footer, not behind a toggle.
   It reads: *"FIXTURE_TEST_ONLY. Every value in this document was calculated
   from committed development fixtures. It is not live, current or authoritative
   analysis of any real security, and no valuation has been produced from it."*
2. Render every remaining entry in `disclaimers` somewhere reachable.
3. Never present a figure as current, live, or a market view.
4. Never render `null` as `0`. Stage 1's rule survives to the UI: a null carries
   a `missingReason` and that is what should be shown.
5. Show `basis` distinctly. `REPORTED`, `DERIVED` and `FORECAST` must not look
   alike; a projected margin must never render with the weight of something a
   company actually reported.

---

## 8. The risk-free rate decision — recorded, per instruction

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

### The synthetic cost of equity, and the wall around it

The bank model's mathematics still has to be provable, so `cost-of-capital.yml`
carries a `synthetic:` block with an explicitly labelled `SYNTHETIC` cost of
equity — `usable_in_production: false` — for engine test fixtures only.

Reaching it requires `ModelContext(allow_synthetic_cost_of_equity=True)`. That
switch has exactly one caller: the test harness. It is **not** exposed as a
command-line flag, because a flag that turns invented assumptions into
publishable output is a flag that will eventually be used by accident. The CLI
never sets it, and `test_refusal.py` asserts that by parsing `cli.py`'s AST — so
adding such a flag later fails the build.

When the rate is synthetic the research package says so, in the document, as a
`HIGH`-importance counter-thesis: *"The discount rate is an explicitly SYNTHETIC
assumption, not a validated market input."*

---

## 9. The six UI-state fixtures

`engine/goh_dip_tong/fixtures/ui_states/` — build Stage 3 against these.

| File | Ticker | `uiState` | Valuation |
|---|---|---|---|
| `FULL_RESEARCH.json` | `SYNB` | `FULL_RESEARCH` | `VALUED` |
| `MODEL_UNDER_VALIDATION.json` | `SYNM` | `MODEL_UNDER_VALIDATION` | `REFUSED` — `NO_VALIDATED_RISK_FREE_RATE` |
| `PARTIAL.json` | `SYNP` | `PARTIAL` | `REFUSED` — `INSUFFICIENT_INPUTS` |
| `ONBOARDING.json` | `SYNO` | `ONBOARDING` | `REFUSED` — `NO_MODEL_FAMILY` |
| `STALE.json` | `SYNS` | `STALE` | `REFUSED` |
| `SUSPENDED.json` | `SYNX` | `SUSPENDED` | `REFUSED` — `COVERAGE_SUSPENDED` |

They are **real engine output**, generated by running the engine over controlled
mutations of the synthetic bank, and `test_ui_states.py` regenerates all six and
compares byte for byte. A fixture that stopped describing real engine output
would be worse than no fixture, because Stage 3 would build against a contract
nothing honours.

Every ticker is synthetic and none is in `idx30.current.json`. `PARTIAL.json` is
the state every real issuer is in today. Full detail in
`engine/goh_dip_tong/fixtures/ui_states/README.md`.

```bash
python3 -m engine.goh_dip_tong.cli ui-fixtures                     # dry run
python3 -m engine.goh_dip_tong.cli ui-fixtures --write-mode commit # regenerate
```

---

## 10. Why nothing is valued, per issuer

Four gates fail for every real issuer. Each is a fact about the data, not about
the code.

| Ticker | Facts | Missing required metrics | Headline refusal | `uiState` |
|---|---:|---:|---|---|
| `BBCA` | 10 | 15 of 17 | `INSUFFICIENT_INPUTS` | `PARTIAL` |
| `TLKM` | 9 | 3 of 6 | `INSUFFICIENT_INPUTS` | `PARTIAL` |
| `ASII` | 2 | 5 of 6 | `INSUFFICIENT_INPUTS` | `PARTIAL` |

All three additionally fail `MIN_HISTORY_PERIODS` (one annual period — a level,
not a trend), `VALIDATED_RISK_FREE_RATE` and `MARKET_DATA_AVAILABLE`.

`MODEL_IMPLEMENTED` passes for `BANK` and is deliberately **last** in the
refusal precedence. Implementing the mathematics does not produce a number while
the data is absent, so leading with "model not implemented" would point at the
wrong problem. The refusal names every failed gate, so nothing is hidden by the
choice of headline.

The 27 IDX30 constituents with no Stage 1 snapshot produce no engine output at
all. The engine reports `SnapshotMissing` and moves on; it will not invent one.

**Real-issuer valuation remains unavailable, and will remain so until all four
of these exist:** a validated risk-free input, the seventeen required bank
facts, a share count, and — for the market-implied case only — rights-cleared
price data.

---

## 11. Publishing guarantees

The write path is `engine/goh_dip_tong/publishing/snapshot.py`. Every property
below is asserted in `test_publishing.py` and again in the acceptance script.

- **Unchanged content writes nothing.** A snapshot is written only when its
  substantive content differs from the newest one already stored.
- **The calendar alone changes nothing.** `calculatedAt`, `generatedAt`,
  `retrievedAt`, `snapshotAt`, `asOf` and `ageDays` are excluded from the
  content hash. Verified across a four-date sweep: the output tree is
  byte-identical after all four.
- **The pointer moves only when validated analytical content does.** It carries
  the snapshot's `asOf`, not today's.
- **Bytes are stable.** Repeated writes of the same content leave the file
  untouched, including its original `generatedAt`.
- **An invalid snapshot never replaces a valid one.** Validation happens at the
  writer, not only in the caller. The worst case is a stale-but-valid snapshot,
  which is recoverable; the alternative is a fresh invalid one with the pointer
  aimed at it, which is not.

The converse is asserted too, so the quiet was not bought by suppressing real
changes: a cutoff spanning the BBCA restatement **does** produce a new snapshot,
and inputs crossing the 400-day threshold **do** move the hash and flip
`researchStatus` to `STALE`.

Reproducibility is checked across three separate processes with differing
`PYTHONHASHSEED`. `FORMULA_REGISTRY_HASH` and `RESEARCH_RULE_REGISTRY_HASH`
fingerprint every formula's and every rule's identity and logic via AST —
insensitive to comments and layout, sensitive to behaviour. (The AST dump varies
between Python versions, so that test is gated to 3.11, which is what CI pins.)

---

## 12. Boundaries observed

- **Engine-owned synthetic data never enters the published data tree.** Enforced
  by hashing every file under `engine/goh_dip_tong/fixtures/` and asserting no
  published file shares a hash, plus checks that no published document carries
  the `SYNTHETIC` flag and that none of `SYNB`, `SYNM`, `SYNO`, `SYNP`, `SYNS`,
  `SYNX` appears anywhere under `data/`.
- **`PRODUCTION` mode is unreachable.** Derived from provenance, never assigned.
- **Unsupported families return `MODEL_UNDER_VALIDATION`.** All 17 declared
  families are registered; an unregistered one would fall through to whatever
  the caller did next, which is how a generic model ends up valuing a bank.
- **No live provider enabled, no schedule changed, no source rights changed.**
  `sources.yml` and `schedules.yml` byte-identical to `main`.
- **No new GitHub Actions workflow.** The existing `gdt-data-quality` workflow
  already runs both Stage 2 gates.
- **No UI.** `goh-dip-tong.html` does not exist.
- **`index.html`, `goh-pok-tong.html`, `_config.yml`, `CNAME` untouched.**
- **No model family other than `BANK`, and no change to its methodology.**
  Residual income remains primary; justified P/B and dividend discount remain
  sensitivity cross-checks. No weighted or blended value is produced anywhere.
- **Dependency direction is one-way.** The engine imports the pipeline, never
  the reverse; asserted by AST scan.
- **No new dependency.**

---

## 13. Known limitations

1. **No real issuer can be valued.** Four gates fail for every one. This is the
   headline and it is a data problem.
2. **Nothing is published under `data/`.** The engine defaults to
   `validate_only`. Stage 3 builds against the UI-state fixtures.
3. **No market-implied case.** Blocked by rights, not by code.
4. **No TTM aggregation.** `periods.ttm_window()` provides the window; the
   aggregation is still unbuilt.
5. **No normalization layer.** `normalized` is `NOT_PRODUCED`.
6. **No FX.** Inherited from Stage 1 — `assert_same_currency()` raises rather
   than combining currencies.
7. **Cost-of-capital config is a shape, not a set of values.** `beta`,
   `equity_risk_premium` and `risk_free` are all `validated: false`.
8. **Scenario offsets are stated, not estimated.** Plausible magnitudes chosen
   so the monotonicity guarantee is testable, not a view on how any real bank's
   drivers vary. `fee_ratio` has no offset at all, which is why no fee catalyst
   fires — the rule's condition is real, and it is currently unmet.
9. **The research rules are BANK-specific.** Sixteen families have no rules
   because they have no mathematics. A second family needs both.
10. **Cross-check divergence is wide in the bull case** — 2.8× the primary
    method on the synthetic bank. Reported, not reconciled away: residual income
    fades abnormal returns where both cross-checks assume they persist, and a
    cross-check that always agrees is measuring nothing.
11. **`FULL_RESEARCH.json` is ~770 KB.** The Analyst View carries every
    calculated record with its full derivation. If that is too much for a first
    paint, fetch the pointer first and the snapshot on demand.

**This is not production-ready and does not claim to be.** It is a complete,
tested engine with no authoritative inputs.

---

## 14. Stage 1 changes made in these slices

Four corrections, each approved before implementation, all in Slice 1.

### 14a. Canonical bank metrics (`config/goh-dip-tong/metrics.yml`)

Added **11 reported** bank drivers — `earning_assets`, `loans`, `deposits`,
`casa_deposits`, `fee_income`, `operating_expense`, `provision_expense`,
`non_performing_loans`, `loan_loss_allowance`, `tier1_capital`,
`risk_weighted_assets` — and **14 derived** ratios: `eps`, `bvps`, `roe`, `roa`,
`payout_ratio`, `sustainable_growth`, `net_interest_income`, `nim`,
`cost_of_credit`, `npl_ratio_gross`, `npl_coverage_ratio`, `casa_ratio`,
`capital_adequacy_ratio`, `cost_to_income_ratio`.

Every ratio is `basis: DERIVED`. NPL and coverage are stored as **amounts**, not
ratios, so the ratio is derived and its denominator stays visible.

**Defining these does not create them.** Not one is collected by any enabled
provider. That is precisely why the bank valuation refuses, and now it refuses
with a specific list rather than a shrug.

### 14b. `UNDEFINED_DENOMINATOR`

Added to `metrics.yml`'s `missing_reasons` and to `MissingReason`. A concealed
divide-by-zero is the derived-metric equivalent of missing becoming zero; this
gives it a name so it fails visibly instead of returning `inf`, `nan`, or a
swallowed zero.

### 14c. The `segment` contract correction

`research-input.schema.json` gained an optional `segment` field, and
`cmd_research_snapshot` now carries it through. This fixed a real defect: BBCA's
snapshot held two indistinguishable `revenue FY2025` rows and
`quality.missingCriticalMetrics` reported `revenue` as missing while
consolidated revenue sat two lines above it.

```
completeness 0.9   missingCriticalMetrics ["revenue"]   ← wrong
completeness 1.0   missingCriticalMetrics []            ← correct
```

### 14d. CI wiring (`.github/workflows/gdt-data-quality.yml`)

Added the Stage 2 unit suite and the Stage 2 acceptance script as steps, and
`engine/**` to the pull-request path filter. **No new workflow, no new trigger,
no schedule.**

---

## 15. Running it

```bash
python3 -m pip install -r pipeline/goh_dip_tong/requirements.txt   # no new deps

python3 -m engine.goh_dip_tong.cli engine-audit
python3 -m engine.goh_dip_tong.cli registry-hash            # formula fingerprint
python3 -m engine.goh_dip_tong.cli registry-hash --rules    # research-rule fingerprint
python3 -m engine.goh_dip_tong.cli research-build --all --verbose
python3 -m engine.goh_dip_tong.cli ui-fixtures

python3 -m pytest engine/goh_dip_tong/tests -q
./engine/goh_dip_tong/tests/acceptance_stage2.sh
```

`--write-mode` defaults to `validate_only`: everything runs and nothing is
written. Exit codes match Stage 1's — `0` ok, `1` validation failed, `2` usage.

---

## 16. What would unblock a real valuation

In order of what removes the most refusals:

1. **A validated long-dated Indonesian government bond yield**, with a
   documented source, a retrieval date and rights permitting derived use. Set
   `risk_free.validated: true` in `cost-of-capital.yml` and the gate opens. This
   alone changes nothing else — the data gates still fail.
2. **The seventeen bank metrics for at least one issuer, across three annual
   periods.** Three, not one: a forecast needs a historical anchor and a level
   is not a trend.
3. **A share count** for the same issuer, for any per-share figure to exist.
4. **Rights-cleared price data**, for the market-implied case only. Not required
   to value a business.

Until (1) through (3) hold together for the same issuer, the honest output is
the refusal that is there now.
