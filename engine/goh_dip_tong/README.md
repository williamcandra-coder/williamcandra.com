# Goh Dip Tong — Stage 2 calculation and research engine

Deterministic engine that turns validated Stage 1 output into versioned
research snapshots. **This slice builds the skeleton, not the mathematics.**
Contracts, the formula registry, missing-value propagation, point-in-time input
selection, the output schema, provenance labelling and the refusal framework
are complete and tested. Forecast and valuation mathematics are not implemented,
and every issuer's valuation is refused.

## Running it

```bash
python3 -m pip install -r pipeline/goh_dip_tong/requirements.txt   # no new deps

python3 -m engine.goh_dip_tong.cli engine-audit
python3 -m engine.goh_dip_tong.cli registry-hash --verbose
python3 -m engine.goh_dip_tong.cli research-build --all --verbose
python3 -m engine.goh_dip_tong.cli research-build --ticker BBCA --as-of 2026-07-25
python3 -m engine.goh_dip_tong.cli research-build --all --write-mode commit

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
├── common/       arithmetic          # safe_div / safe_sub / safe_add / safe_mean
├── inputs/       loader  point_in_time  provenance
├── models/       registry  bank      # 17 families registered, 0 implemented
├── publishing/   snapshot
├── config/       engine.yml  cost-of-capital.yml
├── fixtures/     synthetic-bank/     # TEST-ONLY, never published
└── tests/        7 modules + acceptance_stage2.sh
```

Deliberately absent: `forecasting/`, `valuation/`, `expectations/`, `thesis/`,
`narration/`. Empty directories for unwritten code are scaffolding that looks
like progress.

## Contracts

| | |
|---|---|
| Reads | `data/goh-dip-tong/research-snapshots/sample/<TICKER>.json` (Stage 1's `research-input` contract), plus the fact store and restatement log for any historical cutoff |
| Writes | `data/goh-dip-tong/research-snapshots/<TICKER>/<YYYY-MM-DD>/<model-version>.json` and `current/<TICKER>.json` |
| Output schema | `schemas/goh-dip-tong/research-snapshot.schema.json` — **not** the input schema |

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

`MODEL_IMPLEMENTED` fails too, and is deliberately *last* in the refusal
precedence: implementing the mathematics would not produce a number while the
data is absent, so leading with it would point at the wrong problem.

## Determinism and churn

`calculatedAt`, `asOf` and `ageDays` are volatile and excluded from the content
hash. This is Stage 1's per-day-stamp lesson applied forward: a value truncated
to a date is stable *for a day*, not stable. A snapshot is written only when its
substantive content differs from the newest one already stored, so a rebuild on
a later date deposits nothing — asserted across a four-date sweep in both the
unit suite and the acceptance script. When a cutoff genuinely changes what was
knowable, the facts differ and the hash moves on the evidence, not the calendar.
