# Engine test fixtures — synthetic, and never publishable

Everything in this directory is invented. It describes no real company, no real
market and no real macro series. It exists for one reason: the Stage 1 fixtures
cannot support a bank valuation, so the engine's mathematics has to be
exercised against data that can.

## What is here

| Path | Purpose |
|---|---|
| `synthetic-bank/SYNB.json` | A complete five-year bank (FY2021–FY2025) carrying all seventeen metrics the `BANK` model requires, in `research-input.schema.json` shape. |

`SYNB.json` is deliberately valid against the real Stage 1 input schema. A
fixture that only works with a bespoke loader proves the loader, not the
contract.

## The rule

**Nothing here may enter the published data tree.** Not by copy, not by
symlink, not as an input to a published snapshot, not as a golden output that
later gets promoted.

This is enforced, not merely stated. `tests/test_fixture_labelling.py` hashes
every file in this tree and asserts no published file shares a hash with any of
them, and separately asserts that no published document carries the `SYNTHETIC`
quality flag. `acceptance_stage2.sh` repeats both checks against a live build.

## The synthetic cost of equity

The `BANK` model's valuation needs a discount rate, and there is no validated
risk-free input — see the rationale at the top of
`engine/goh_dip_tong/config/cost-of-capital.yml`. BI_7DRR is a short-term
policy rate, not a risk-free yield; substituting it would understate the
discount rate and inflate every valuation built on it, invisibly.

So for fixture runs only, `cost-of-capital.yml` carries a `synthetic:` block
with an explicitly labelled `SYNTHETIC` cost of equity. Reaching it requires
`ModelContext(allow_synthetic_cost_of_equity=True)`, which only the test
harness passes. The CLI never does, and `tests/test_refusal.py` asserts that by
parsing `cli.py` — so no published snapshot can rest on an invented discount
rate, whatever anyone later adds to the command line.

## Why `SYNB`

Four uppercase letters, so it satisfies the ticker pattern the schema enforces,
and not a real IDX symbol. It is not in `idx30.current.json`, so a build over
the live universe can never pick it up.
