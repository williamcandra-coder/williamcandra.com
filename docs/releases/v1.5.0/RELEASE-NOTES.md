# Release Notes — v1.5.0

**First accuracy release since v1.1.0.** Everything between was presentation —
the composer, timeline, ten sections, love rebuild — sitting on top of a chart
with known defects. This fixes two of them.

---

## 1. Solar terms computed to the minute

### The defect

`bazi-engine.min.js` stores solar terms at **day granularity**. Anyone born on
a term boundary day got a coin-flip month pillar — and the month pillar drives
season, strength, and the entire structure read. It was the deepest accuracy
problem in the stack.

### The fix

New module `engine-v3/solar-terms.browser.js` computes the sun's apparent
ecliptic longitude (Meeus, *Astronomical Algorithms*, ch. 25), then solves for
the exact instant of each term by bisection.

**Validated against published ephemeris** — Li Chun, seven consecutive years:

| Year | Computed (UTC) | Published (UTC) | Error |
|---|---|---|---|
| 2020 | 02-04 09:08 | 02-04 09:03 | 5 min |
| 2021 | 02-03 14:57 | 02-03 14:59 | 2 min |
| 2022 | 02-03 20:46 | 02-03 20:51 | 5 min |
| 2023 | 02-04 02:34 | 02-04 02:43 | 9 min |
| 2024 | 02-04 08:21 | 02-04 08:27 | 6 min |
| 2025 | 02-03 14:09 | 02-03 14:10 | 1 min |
| 2026 | 02-03 19:56 | 02-03 20:02 | 6 min |

Worst case **9 minutes**, against a stored granularity of **24 hours**.

### Scope — deliberately narrow

| Pillar | Action | Why |
|---|---|---|
| Year | recomputed | turns at Li Chun, not a calendar date |
| Month | recomputed | 30° solar sector + Five Tigers rule |
| **Day** | **untouched** | continuous 60-day count, no term dependency — the engine gets it right |
| **Hour** | **untouched** | derives from day stem + true-solar hour |

This narrows, but does change, the rule that `bazi-engine.min.js` is the sole
source of the Four Pillars. It remains the source for the day pillar and now
acts as a cross-check for year and month. Every disagreement is recorded in
`chart.solarFix` so it can be inspected rather than trusted.

Solar terms are global instants, so the comparison runs in **UTC** using the
offset actually applied for that city — separate from True Solar Time, which is
a local-sun quantity used only for the hour branch.

### Measured impact

Across 9,840 sampled births (1970–2010, every 3rd day, two hours):

- **2.57% of births get a corrected year or month pillar** — about 1 in 39
- **117 of those also change season**, which cascades into strength, structure
  and most of the reading

In a boundary-focused sample, **99.2% of all corrections fell within 12 hours of
a true term boundary** — the exact signature you'd expect if the fix is right.

### Two engine table errors found

Two corrections sat more than 12 hours from any boundary, so I checked them by
hand. Both are the engine's table being **a full day wrong**, not calculator
error:

- **2013-05-04** — engine assigns the Si month; Li Xia 2013 was May 5 (07:18
  UTC, published). Anyone born May 4 is in Chen. Engine is a day early.
- **1976-07-06** — engine assigns Wei; Xiao Shu fell on July 7.

So the table has genuine errors beyond granularity.

### Fail-soft

If the module doesn't load, the chart still computes on the engine's original
pillars. Verified: no alert, no blank, reading renders normally.

---

## 2. "ELEMENT BALANCE" now shows element balance

### The defect

The bar rendered the engine's `fiveFactors`, which is **not an element count**.
It weights each element by its relationship to the Day Master — Resource 3.0,
Companion 2.5, Output 2.0, Wealth 1.2, Control 1.2 — so a chart with almost no
Water could show a large Water bar simply because Water was its Resource
element. The label said one thing; the bar showed another.

### Concretely

Chart 1990-05-15 14:00 — **two Geng (Yang Metal) stems visible**, obviously
Metal-dominant:

| Element | Old bar | True count |
|---|---|---|
| Metal | 31% | **38.8%** |
| Earth | **38%** | 22.5% |
| Fire | 11% | 20.0% |
| Water | 13% | 13.8% |
| Wood | 8% | 5.0% |

The old bar showed **Earth** as largest — because Earth produces Metal, making
it the Resource element for a Geng day master, weighted 3.0×.

### The fix

`GptReadingV2.trueElements()` counts what is actually present: four visible
stems at full weight, plus every hidden stem at its own depth. No Day Master
relationship enters it. Segments now carry a percentage tooltip.

Falls back to the old figures only if the composer hasn't loaded.

---

## 3. Carried forward from v1.4.3 / v1.4.4

- No engine vocabulary ("pillar", "branch") in reader-facing copy
- Love & Spouse rebuilt on the spouse star and spouse seat — 12 opening lines
  instead of 2, 448 distinct sections per 552 charts
- Spouse-star banding corrected from 51% "thin" to 34/33/33
- Three phrasings per drive, so Companion charts don't share one line
- Ten sections, four notable years, plain wording, gentle health copy

Verified across 276 charts: zero doom vocabulary, zero jargon, zero repeated
years within a reading.

---

## 4. What is still not fixed

Stated plainly, because this is an accuracy release and the gaps matter:

- **No validated fixtures.** Nothing here has been checked against a chart a
  practitioner confirmed. The solar-term work is validated against published
  *astronomical* data — that part is solid — but the interpretation layer is
  not. **v3 remains `UNVALIDATED`.**
- **v3's strength formula still carries undocumented coefficients** (`50`, `×4`,
  `×28`, the `1.5` confidence threshold) and weights hidden stems seasonally
  while leaving visible stems unmodulated. Output still skews ~47% Weak. This
  can't be calibrated without reference charts.
- **Luck-pillar start age is still soft-timed.** The solar-term module now makes
  a precise start age *computable*, but wiring it in is its own change and I
  haven't done it. The decade line still says "somewhere in your thirties".
- **DST unmodelled** (US/UK summer births may be an hour out); late-Zi
  convention still undocumented.

The single highest-value thing remaining is **20–30 charts you can personally
verify** — your own, family, people whose life events you know. That turns the
interpretation layer from reasoned-from-the-rules into checked, and it is the
one piece I cannot produce.
