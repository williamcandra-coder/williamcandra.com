# Goh Dip Tong — Stage 2 calculation and research engine

Deterministic engine that turns validated Stage 1 output into versioned
research snapshots.

**Slice 1** built the skeleton: contracts, the formula registry, missing-value
propagation, point-in-time input selection, the output schema, provenance
labelling and the refusal framework.

**Slice 2** built the `BANK` mathematics: the driver chain, a five-year
forecast, bear/base/bull scenarios, residual income with justified-P/B and
dividend-discount cross-checks, terminal guards, the reverse-implied ROE
solver, the valuation bridge, and the Uncle and Analyst views.

**Slice 3** built the research package — thesis, counter-thesis, catalysts,
risks, breakers, evidence and model-audit references, method-comparison notes —
finalised both views, added the `uiState` vocabulary and its six Stage 3
fixtures, and closed the publishing rules.

**No real issuer is valued.** The mathematics runs against the synthetic-bank
fixture only. Every real issuer still fails the data gates and the risk-free
gate, and returns a structured refusal. `docs/goh-dip-tong/HANDOFF_STAGE_2.md`
is the Stage 3 contract.

## Running it

```bash
python3 -m pip install -r pipeline/goh_dip_tong/requirements.txt   # no new deps

python3 -m engine.goh_dip_tong.cli engine-audit
python3 -m engine.goh_dip_tong.cli registry-hash --verbose
python3 -m engine.goh_dip_tong.cli registry-hash --rules
python3 -m engine.goh_dip_tong.cli research-build --all --verbose
python3 -m engine.goh_dip_tong.cli research-build --ticker BBCA --as-of 2026-07-25
python3 -m engine.goh_dip_tong.cli research-build --all --write-mode commit
python3 -m engine.goh_dip_tong.cli ui-fixtures --write-mode commit

python3 -m pytest engine/goh_dip_tong/tests -q
./engine/goh_dip_tong/tests/acceptance_stage2.sh
```

`--write-mode` defaults to `validate_only`: everything runs and nothing is
written. Exit codes match Stage 1's — `0` ok, `1` validation failed, `2` usage.

## Three properties everything else serves

**Deterministic.** No LLM, no clock-dependent arithmetic, no iteration over an
unordered collection. The same inputs produce byte-identical output on any
machine and on any calendar date.

**Missing never becomes zero.** Every value is a Stage 1 `Measure`, which cannot
be constructed as missing without a reason. The formula registry short-circuits
on a missing input, so no formula body ever *sees* one and none can treat one as
zero. Its derived-metric counterpart: a division that cannot be performed
returns `UNDEFINED_DENOMINATOR`, never `inf`, `nan`, or a swallowed zero.

**Refusal is a result.** A model that cannot honestly value an issuer returns a
structured refusal naming the gates that failed and the metrics that are
missing. There is no generic fallback model, because a bank valued with a
generic FCFF model is worse than an explicit "not covered yet".

## Layout

```text
engine/goh_dip_tong/
├── cli.py  settings.py
├── contracts/    enums  calculated  registry  refusal  model
├── common/       arithmetic  solvers  bridge
├── inputs/       loader  point_in_time  provenance
├── forecasting/  assumptions  bank      # anchors, scenarios, the driver chain
├── valuation/    cost_of_capital  guards  methods  comparison
├── expectations/ reverse_solver
├── research/     records  rules  package # 25 rules; no arithmetic
├── narration/    views                 # projections only; no arithmetic
├── models/       registry  bank        # 17 families registered, 1 implemented
├── publishing/   snapshot  ui_states
├── config/       engine.yml  cost-of-capital.yml  scenarios.yml
├── fixtures/     synthetic-bank/       # TEST-ONLY input, never published
│                 ui_states/            # TEST-ONLY output, the Stage 3 contract
└── tests/        15 modules + acceptance_stage2.sh
```

`valuation/comparison.py` exists because of a constraint the research layer
places on itself: a rule may compare two numbers but may not produce a third.
Anything a rule needs beyond the records the valuation already made is computed
there, through the formula registry, so it arrives with a `formula_id` attached.

## The research package

Every conclusion is emitted by a named rule whose condition is a comparison
between calculated records. **No language model is involved at any point.**

A `ResearchRecord` cannot be constructed uncited (a claim must name at least one
calculated record *and* one evidence ref), untraceable (no `rule_id`, no
record), unranked, or as a recommendation — "target price", "buy",
"undervalued" and fifteen other phrases are refused outright. A fifth check runs
at assembly: every cited ID must exist in what the engine actually produced.

For a refused issuer the claim rules **never run**. Not filtered afterwards —
never run, so there is no unsupported thesis to remove. The citation index is
still produced, because a pointer carries no claim.

`RESEARCH_RULE_REGISTRY_HASH` fingerprints every rule's identity and logic, the
same way `FORMULA_REGISTRY_HASH` does for arithmetic: a published conclusion
carries the `ruleId` that produced it, and following that ID must reach the rule
that actually ran.

## `uiState`

Three vocabularies, one owner each. `coverageStatus` is Stage 1's view of a
company; `researchStatus` is the engine's view of how far research has got;
`uiState` is what to render. The third exists because a template that
recombined the first two itself would recombine them slightly differently on the
next screen.

Six states — `FULL_RESEARCH`, `MODEL_UNDER_VALIDATION`, `PARTIAL`,
`ONBOARDING`, `STALE`, `SUSPENDED` — derived in one function with a fixed
precedence, with a worked fixture for each under `fixtures/ui_states/`. The
fixtures are regenerated and compared byte for byte by the test suite.

Deliberately absent: empty directories for unwritten code. Scaffolding that
looks like progress is worse than a gap you can see.

## Contracts

| | |
|---|---|
| Reads | `data/goh-dip-tong/research-snapshots/sample/<TICKER>.json` (Stage 1's `research-input` contract), plus the fact store and restatement log for any historical cutoff |
| Writes | `data/goh-dip-tong/research-snapshots/<TICKER>/<YYYY-MM-DD>/<model-version>.json` and `current/<TICKER>.json` |
| Output schema | `schemas/goh-dip-tong/research-snapshot.schema.json` — **not** the input schema |
| Stage 3 reads | the picker config, `current/<TICKER>.json`, the dated snapshot, and the output schema. Nothing else — see `docs/goh-dip-tong/HANDOFF_STAGE_2.md` |

The input snapshot carries only the latest revision of each fact, so it cannot
answer "what did we believe in July". Point-in-time reproducibility therefore
reads the fact store as well; which tier was used is recorded in
`modelAudit.factSource`.

## Two vocabularies, one owner each

`coverageStatus` belongs to Stage 1's universe registry. `researchStatus` is the
engine's own ladder (spec §2.8). The engine reads the first and never writes it;
collapsing them would let the engine silently promote a company Stage 1 has not.

## Why nothing is valued

Four gates fail for every real issuer, and each is a fact about the data rather
than about the code:

| Gate | Why it fails |
|---|---|
| `REQUIRED_INPUTS_PRESENT` | The bank model needs 17 metrics; the fixtures supply 2 |
| `MIN_HISTORY_PERIODS` | One annual period. A level, not a trend |
| `VALIDATED_RISK_FREE_RATE` | No validated yield exists. BI_7DRR is a policy rate and is refused as a substitute — see `config/cost-of-capital.yml` |
| `MARKET_DATA_AVAILABLE` | The price provider is `PRIVATE_RESEARCH_ONLY` |

`MODEL_IMPLEMENTED` now passes for `BANK` — and nothing changes, which was the
point. Implementing the mathematics does not move Stage 2 toward real output;
resolving the Stage 1 data gaps does. Slice 3 is the second demonstration of
the same thing: the research package is built and every real issuer's refusal is
unchanged, because there is nothing to have a thesis about.

## The BANK model

```
EA_t     = EA_{t-1} x (1 + g)          loans_t = EA_t x loans/EA
II_t     = EA_t x asset_yield          IE_t    = dep_t x funding_cost
NII_t    = II_t - IE_t                 fee_t   = NII_t x fee_ratio
opex_t   = (NII_t + fee_t) x cost_to_income
prov_t   = loans_t x cost_of_credit
PPOP_t   = NII_t + fee_t - opex_t      PBT_t   = PPOP_t - prov_t
NP_t     = PBT_t x (1 - tax)           NPpar_t = NP_t x minority_share
B_t      = B_{t-1} + NPpar_t - DIV_t   (clean surplus)

V0 = B0 + SUM RI_t/(1+r)^t + CV,   RI_t = NPpar_t - r x B_{t-1}
CV = omega x RI_T / (1 + r - omega) / (1+r)^T
```

Cross-checks: justified P/B `(ROE-g)/(r-g)` and Gordon `D1/(r-g)`. Under a
steady state all three are the same expression, and
`test_valuation_bank.py` asserts they agree to 1e-12. Over the explicit
forecast they diverge, because residual income *fades* abnormal returns while
both cross-checks assume they persist — reported, not reconciled away.

Guards refuse before dividing: `r - g` must clear 100 bps, persistence must
stay below 1, and the discount rate must be positive.

## Determinism and churn

`calculatedAt`, `asOf` and `ageDays` are volatile and excluded from the content
hash. This is Stage 1's per-day-stamp lesson applied forward: a value truncated
to a date is stable *for a day*, not stable. A snapshot is written only when its
substantive content differs from the newest one already stored, so a rebuild on
a later date deposits nothing — asserted across a four-date sweep in both the
unit suite and the acceptance script. When a cutoff genuinely changes what was
knowable, the facts differ and the hash moves on the evidence, not the calendar.
