# UI-state fixtures — the Stage 3 contract, six ways

Six research snapshots, one per state a Stage 3 UI has to render. They are the
worked examples behind `docs/goh-dip-tong/HANDOFF_STAGE_2.md`: build against
these and every branch of the renderer has something real to render before any
live data exists.

**Everything here is synthetic and none of it may be published.** Every ticker
is a `SYN*` placeholder, no real issuer appears, and only one fixture carries a
valuation at all.

## The six

| File | Ticker | `uiState` | `researchStatus` | Valuation | What it demonstrates |
|---|---|---|---|---|---|
| `FULL_RESEARCH.json` | `SYNB` | `FULL_RESEARCH` | `FULL_RESEARCH` | `VALUED` | The complete case: three scenarios, both views, the full research package |
| `MODEL_UNDER_VALIDATION.json` | `SYNM` | `MODEL_UNDER_VALIDATION` | `MODEL_UNDER_VALIDATION` | `REFUSED` — `NO_VALIDATED_RISK_FREE_RATE` | Complete data, unvalidated methodology |
| `PARTIAL.json` | `SYNP` | `PARTIAL` | `MODEL_UNDER_VALIDATION` | `REFUSED` — `INSUFFICIENT_INPUTS` | 2 of 17 required metrics. **The state every real issuer is in today** |
| `ONBOARDING.json` | `SYNO` | `ONBOARDING` | `FINANCIALS_VALIDATED` | `REFUSED` — `NO_MODEL_FAMILY` | Identity known, no model family mapped |
| `STALE.json` | `SYNS` | `STALE` | `STALE` | `REFUSED` | Inputs 1,234 days old against a 400-day threshold |
| `SUSPENDED.json` | `SYNX` | `SUSPENDED` | `MODEL_SUSPENDED` | `REFUSED` — `COVERAGE_SUSPENDED` | Coverage withdrawn by Stage 1 |

## How Stage 3 should use them

**Switch on `uiState`, not on `researchStatus`.** `uiState` is derived once, in
`engine/goh_dip_tong/publishing/ui_states.py`, from `coverageStatus`,
`researchStatus`, the valuation outcome and the refusal reason. Exactly one
state applies to any document. A template that recombined those four inputs
itself would recombine them slightly differently on the next screen.

**Render the refusal, do not hide it.** `valuation.status = REFUSED` is a
result. `failedGates`, `missingInputs` and `note` are populated precisely so the
UI can say *what is missing* rather than showing an empty panel. Five of the six
fixtures are refusals because five-sixths of the interesting rendering work is
in the states where there is no number.

**Show the disclaimer.** `disclaimers[0]` states the mode and every fixture
carries it. `mode` is `FIXTURE_TEST_ONLY` in all six.

**Never compute.** Every number a view shows carries the `ref` of the
`Calculated` record it came from. If the UI needs a figure the views do not
carry, the answer is a new engine record, not arithmetic in a template — that
is exactly how the two views would start disagreeing.

### What differs between the states, for the renderer

| | FULL_RESEARCH | the other five |
|---|---|---|
| `valuation.status` | `VALUED` | `REFUSED` |
| `drivers`, `forecast` | `PRODUCED` | `NOT_PRODUCED` with a reason |
| `uncleView`, `analystView` | `PRODUCED` | `NOT_PRODUCED` with a reason |
| `thesis`, `counterThesis`, `methodComparison` | `PRODUCED` with records | `NOT_PRODUCED` with a reason |
| `catalysts`, `risks`, `breakers` | populated | `[]` |
| `researchRefs` | `PRODUCED` | `PRODUCED` — a pointer carries no claim |
| `evidence`, `freshness`, `quality`, `modelAudit` | present | present |
| `marketImplied.available` | `false` | `false` |

`marketImplied` is `false` even in the valued case. Solving a price back to
implied assumptions needs a price, and the price provider's rights are
`PRIVATE_RESEARCH_ONLY`. That is a rights outcome, not an unimplemented
feature, and `marketImplied.reason` says so.

## They are generated, not written

```bash
python3 -m engine.goh_dip_tong.cli ui-fixtures                     # dry run
python3 -m engine.goh_dip_tong.cli ui-fixtures --write-mode commit # regenerate
```

The engine runs against a throwaway sandbox under `mktemp`, because generating a
fixture means writing input snapshots and one of those left in `data/` would be
indistinguishable from one Stage 1 produced.

`test_ui_states.py` regenerates all six and compares **byte for byte**. That is
the assertion the rest of this directory rests on: a fixture that stopped
describing real engine output would be worse than no fixture at all, because
Stage 3 would build against a contract nothing honours.

Each case is reached by a named mutation of `synthetic-bank/SYNB.json` —
clearing the model family, back-dating the facts, suspending coverage, trimming
the metrics. The mutations are in `ui_states.py` next to the case table, so
"how do I get an issuer into this state" has a readable answer.

`FIXTURE_CALCULATED_AT` is pinned. A wall-clock stamp would make every
regeneration a diff and leave the comparison test unable to tell drift from the
passage of time.

## Containment

- No fixture ticker appears in `idx30.current.json`
- No fixture ticker appears anywhere under `data/`
- No fixture file shares a SHA-256 with any published file
- Only `SYNB` — the synthetic bank — is ever valued
- Every fixture is `mode: FIXTURE_TEST_ONLY`; `PRODUCTION` is unreachable

All five are asserted in `test_ui_states.py` and again against a live build in
`acceptance_stage2.sh`.
