# Goh Dip Tong — Data Rights

How this project decides what it may collect, store, show and share. The rules
here are enforced in code (`pipeline/goh_dip_tong/validation/rights.py`), not
just written down: a write that exceeds a source's rights raises an exception
rather than logging a warning, because a rights breach that only logs is a
rights breach that ships.

---

## The seven statuses

| Status | Store raw | Commit to git | Public display | Redistribute |
|---|---|---|---|---|
| `PUBLIC_RAW_DATA_APPROVED` | yes | yes | yes | yes |
| `PUBLIC_DERIVED_OUTPUT_APPROVED` | no | yes | yes | no |
| `PUBLIC_METADATA_ONLY` | no | yes | yes | no |
| `PRIVATE_RESEARCH_ONLY` | yes | **no** | **no** | no |
| `DISCOVERY_ONLY` | no | yes | no | no |
| `MANUAL_REVIEW_REQUIRED` | no | no | no | no |
| `DISABLED` | no | no | no | no |

A provider may **narrow** its rights below what its status allows, via the
`rights:` block in `sources.yml`. It can never **widen** them: the gate
intersects the declared block with the status matrix, so writing
`redistribute: true` under `PUBLIC_METADATA_ONLY` has no effect.

`MANUAL_REVIEW_REQUIRED` and `DISABLED` are additionally *non-runnable*. Setting
`enabled: true` on such a provider does not make it run — the gate checks the
status independently. That is deliberate: the enabled flag is an operational
switch, and rights are not an operational question.

---

## Current position

**No source in this project has redistribution rights, and none is expected to
soon.** As of 2026-07-30:

- Every live source is disabled, for two independent reasons: the build
  environment cannot reach any of them (egress policy answers HTTP 403 to
  `CONNECT`), and none of their terms have been reviewed.
- The five enabled sources are all committed development fixtures.
- Market prices — the one data type whose redistribution rights are genuinely
  contested — are held at `PRIVATE_RESEARCH_ONLY` even in fixture form. Their
  output is written to `data/goh-dip-tong/_private/`, which is git-ignored.

See `SOURCE_REGISTER.md` for the per-source detail and the procedure for
enabling one.

---

## Rules that do not bend

**Do not bypass access controls.** No authentication bypass, no rate-limit
evasion, no anti-bot circumvention, no ignoring terms or licensing restrictions.
A source that requires circumvention to work is a source that stays disabled.
This is not a technical constraint that a clever adapter can solve.

**Do not redistribute raw provider data** unless this register marks that
specific use as approved. Today, nothing is.

**Do not store copyrighted full text.** News articles, announcement PDFs and
annual reports are represented by metadata plus a manifest: official URL, hash
(only if a permitted temporary download occurred), size, media type and
retrieval outcome. Never the content.

**Do not claim live or real-time data.** Displayed timestamps and the provider
contract must support any such claim. Right now every artefact carries
`provenance: "FIXTURE"` and `authoritative: false`, and the Stage 3 UI is
required to surface that.

**Do not present derived values as reported ones.** Every value carries a
`basis` — `REPORTED`, `RESTATED`, `NORMALIZED`, `DERIVED`, `FORECAST` or
`MARKET_IMPLIED` — and the UI must keep them visually distinct.

**No investment advice.** No buy or sell instruction, no guaranteed return, no
personalised recommendation. Every research snapshot ships with disclaimers
attached to the data itself so they cannot be dropped in transit.

**No secrets in committed files.** The repository guard scans every generated
file for secret-shaped strings and fails the build on a single hit — no
threshold, no allowlist. Stage 1 has no authenticated source, so nothing should
need a credential at all.

---

## How the gate routes a write

```
                    ┌─ commit_to_repo? ─ yes ─→ data/goh-dip-tong/…   (git-tracked)
record + provider ──┤
                    └─ no ─────────────────────→ data/goh-dip-tong/_private/…
                                                  (git-ignored, never published)
```

This is why the daily market-price collector runs end to end today and still
cannot leak anything: it collects real records, validates them properly, writes
them to a real path — and that path is outside git. When market-data rights are
eventually documented, raising the status moves the output into the tracked tree
with no code change.

---

## Reviewing a source

Full procedure in `SOURCE_REGISTER.md`. The short version:

1. Confirm access exists **and is permitted** — those are different questions.
2. Read the operator's actual terms. Record the URL and the date you read them.
3. Fill in the permission rows. Anything you are unsure about stays `no`.
4. Update `sources.yml`.
5. Run `python3 -m pipeline.goh_dip_tong.cli sources`; it fails if the register
   and the config disagree.

Reachable is not the same as permitted. A page loading in a browser tells you
nothing about whether you may store it, show it, or pass it on.
