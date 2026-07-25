# Release Notes — v1.4.2

Deeper forecast. "What's Coming" now surfaces **up to four** notable years
instead of two, and each one is tied to a specific area of life.

## Why v1.4.1 could only ever find two

A branch has exactly **one** clash partner and **one** combination partner in
the 12-branch cycle. So scanning 12 years against a single seat — the day branch
— can only ever return two hits. Raising the limit would have changed nothing;
widening the window to 24 years would just have found the same two again, a
cycle later.

## The fix: scan all four pillar seats

Each pillar is a different area of life, so the same clash means something
different depending on which seat it lands on:

| Seat | Area |
|---|---|
| Day | self, marriage |
| Month | career, parents |
| Year | roots, reputation, elders |
| Hour | children, home, later life |

Eight new copy variants — clash and combination for each seat:

- **Clash on month** → *"the ground under your work shifts: a role ends, a boss
  leaves, a direction stops making sense. People who prepared treat it as an
  exit. People who didn't call it bad luck."*
- **Combination on year** → *"Old connections resurface and prove useful —
  someone from earlier in your life reappears with something you need. Answer
  the message."*

When two seats flag the same year, the more significant seat wins
(day > month > year > hour), so no year is described twice.

### Overlap with the narrated years is excluded

Next year and the year after are already described in detail at the top of the
section, so they're skipped by the notable scan. Verified: **zero repeated years
within a reading**, across 276 charts.

## Result

"What's Coming" now carries roughly **7 dated touchpoints**: a past anchor, next
year in detail, the year after, and up to four notable years. Median length
1,327 characters — nearly triple v1.4.0.

Distribution across 276 charts: 240 got four notable years, 34 got three, 2 got
two (charts with repeated branches have fewer distinct seats to match). 35
distinct seat-combinations observed, so the forecast shape varies between people.

## Unchanged

Ten sections, plain wording, physique and traits, no section-label prefixes,
gentle health copy, fail-soft to the classic reading, `?engine=classic`
rollback, `CONFIG.SHEET_URL` byte-identical.

Still no verdicts — every notable-year line is about **movement and timing**,
never about marrying, losing, failing or falling ill on a date. Verified
doom-clean across 276 charts. Decade marker still soft-timed. v3 remains
`UNVALIDATED`.

## Editing

`FRAG.notable.clash.*` and `FRAG.notable.combo.*` hold the eight new lines. The
scan is `notableYears(pillars, next1, 12, 4, [next1, next2])` — the `12` is the
look-ahead window, the `4` is the cap, the array is the exclusion list.
