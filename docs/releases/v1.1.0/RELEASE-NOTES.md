# Release Notes — v1.1.0

Two groups of change: **corrections** that alter chart output for some births,
and **product fixes** that do not touch the calculation at all. Engine v3 ships
in the package but stays switched off.

---

## 1. Corrections that change chart output

These fix real defects. They will change the pillars some visitors saw before.

### 1.1 True Solar Time no longer wraps the clock without moving the date

Correcting for longitude can push a birth across midnight. The old code wrapped
the clock into 0–1440 and left the calendar date alone, producing a day pillar
from one date and an hour pillar from another.

Now the corrected time carries its date with it.

| Birth | Before | After |
|---|---|---|
| Banda Aceh 00:10 | 23:35, date unchanged | 23:35 on the **previous** day |
| Singapore 00:30 | wrapped, date unchanged | previous day |
| Jayapura 23:50 | wrapped, date unchanged | 00:16 on the **next** day |
| Surabaya 23:xx | wrapped, date unchanged | next day |

Guard: the shift is suppressed if it would move a birth before 1960-01-01, where
the engine's table ends. Verified.

### 1.2 Timezone is now per-city, not per-country

`COUNTRY_TZ` stored one offset per country. Indonesia spans **WIB +7 / WITA +8 /
WIT +9**; the United States spans −5 to −8. A wrong offset is a 60-minute error,
which can move the hour branch.

A `CITY_TZ` override table now carries the correct zone for every multi-zone city
in the list.

| City | Before | After |
|---|---|---|
| Makassar, Denpasar, Balikpapan, Manado … | +7 | **+8 (WITA)** |
| Ambon, Ternate, Jayapura, Sorong … | +7 | **+9 (WIT)** |
| Los Angeles, Seattle, San Francisco | −6 | **−8** |
| New York, Boston, Miami | −6 | **−5** |
| Denver, Phoenix | −6 | **−7** |
| Perth | +10 | **+8** |
| Adelaide | +10 | **+9.5** |

### 1.3 Measured impact

25,080 birth inputs compared old vs new across 19 city/country pairs:

- **871** charts changed **day pillar** — these were previously wrong (§1.1)
- **12,615** changed hour pillar only
- **9,240** of the changes are cities that had **no longitude entry at all** before
  and were falling back to raw clock time — new capability, not a regression

Change rate for cities that were already supported:

| City | Changed | Cause |
|---|---|---|
| Los Angeles | 100% | timezone −6 → −8 |
| Makassar | 66.7% | timezone +7 → +8 |
| New York | 66.7% | timezone −6 → −5 |
| Denpasar | 64.2% | timezone +7 → +8 |
| Singapore | 16.7% | day rollover, post-midnight births |
| Surabaya | 7.5% | day rollover, 23:xx births |
| Jakarta, Chicago, London, Tokyo, Sydney | 0% | already correct |

Jakarta and Surabaya — the bulk of real traffic — are almost entirely unaffected.
Anyone who saved a reading from an affected city will see different pillars.

---

## 2. Product fixes (no calculation change)

### 2.1 Uncle now says your name

`buildReading(b, name)` accepted a name parameter and **never used it**. The form
required a first name and the reading never mentioned it.

Openers and closers are now `{name}` templates (8 each, up from 5), lightly
title-cased so `william` comes back as `William`. The chart heading uses the full
name — the first use the last-name field has ever had.

### 2.2 "I don't know my birth time"

New checkbox. When ticked:

- the time input is disabled
- the HOUR pillar renders as `?` / unknown instead of a fabricated value
- the transparency note says three pillars are being read
- uncle acknowledges it in the reading rather than bluffing

Noon is still used internally so the chart computes; this is stated in the
evidence panel. A true three-pillar element balance would require engine work and
is **not** claimed here.

### 2.3 31 February is no longer selectable

The day list rebuilds on month/year change and respects leap years. Previously an
impossible date reached the engine and returned the generic "crystal ball
hiccuped" alert.

### 2.4 City list expanded 40 → 162, with autocomplete

Free text still works. The input now has a `<datalist>`, so visitors land on keys
we actually have instead of silently falling back to clock time. Coverage added
across Java, Sumatra, Kalimantan, Sulawesi, Bali/Nusa Tenggara, Maluku and Papua,
plus wider East Asia, US, UK, Australia and India.

Longitudes are approximate city-centre values. A 0.5° error is 2 minutes of solar
time and cannot move a 2-hour branch except within 2 minutes of a boundary.

**The Google Sheet is the better source for the next expansion** — it already
records every city visitors type.

### 2.5 Engine loads lazily

`bazi-engine.min.js` is ~2.5 MB of source (~180 KB gzipped) and was parsed on
every page view, including bounces. It is now fetched on idle after first paint
and awaited on CONSULT if it has not arrived. The button shows `WARMING UP…`
in the rare case someone beats the preload.

### 2.6 Readings are shareable

`SEND TO SOMEONE` builds a link that encodes the form and replays the same local
calculation. Web Share API where available, clipboard otherwise, raw URL as last
resort. No server, no storage.

Replaying a shared link **does not** write a new row to the Sheet, so one shared
reading cannot inflate your submission data.

Social card added: `og-goh-pok-tong.png`, plus Open Graph and Twitter meta tags.

### 2.7 Gender now does something

It was collected, then hardcoded to `'male'` at the engine call. It is now passed
through properly and drives the Eight Mansions directions, which the engine was
already computing and the page was throwing away:

> LUCKY DIRECTIONS — money **SE** · health **E** · love **S** · work **N**

---

## 3. Engine v3

Unchanged from the reviewed integration. Present, `UNVALIDATED`, and **off unless
`?engine=v3` is in the URL**. With the flag absent, `engine-v3.browser.js` is
never requested and the reading is produced entirely by the existing path.

The evidence panel gained rows for UTC offset used, date passed to the engine,
calendar day shift, and whether the birth hour was known.

**Engine v3 does not write any part of the visitor-facing reading in this
release.** It observes only.

---

## 4. Removed

The unreachable legacy pillar calculator (`BRANCH_EL`, `BRANCH_HIDDEN`, `jdn`,
`yearPillar`, `monthPillar`, `dayPillar`, `hourPillar`). It was a second pillar
implementation that disagreed with the shipping engine — `monthPillar`
approximated solar terms by calendar month. Proven unreachable before removal.

---

## 5. Not in this release

- Solar terms are still encoded at **day** granularity. A birth on a boundary day
  is not resolved to the hour. Fixing this means replacing the data table and is
  its own project.
- Daylight saving is not modelled. Indonesia, Singapore, Malaysia, China, Japan,
  Korea, Thailand, Vietnam, the Philippines, India, Hong Kong and Taiwan do not
  observe it, so the main market is unaffected. **US and UK births in summer may
  be one hour out.**
- The late-Zi convention is unchanged: the day does not roll at 23:00.
- No practitioner-reviewed fixtures. None were invented.
