# Test Report — v1.2.0

Environment: Node v22.22.2, Linux. Browser rendering is the manual procedure §5.

## 1. Node suite — `npm run test:all`

| Test | Result |
|---|---|
| `test.mjs` — core engine | PASS |
| `advanced-test.mjs` — advanced structure | PASS |
| `parity-test.mjs` — browser build ≡ ESM originals | PASS, 13,444 comparisons, 0 mismatch |
| `composer-test.mjs` — dynamic reading | **PASS, 1,416 charts** |
| `validate.mjs` — fixture runner | reviewed 0 / skipped 1 / exit 0 |

### Composer test asserts

- every section non-empty across 1,416 charts
- name woven into opener and closer on every chart
- **zero deterministic-doom vocabulary** in any section (scanned against a
  12-phrase blocklist: die/death/cancer/divorce/never marry/doomed/cursed/…)
- day-branch-clash line fires **iff** a real clash lands on the day branch —
  321 fires, 321 correct, 0 false, 0 missed
- hour-unknown note present whenever the hour is unknown
- variety floor: personality ≥ 50 distinct (actual: 247)

Reading space across self × career × love × luck: **741,000**.

## 2. v3-live integration — headless DOM

| # | Check | Result |
|---|---|---|
| A | Default path: v3 composer drives the reading; name woven; composed phrasing present | PASS |
| B | Engine file 404 → classic reading, no alert, no blank | PASS |
| C | Composer file 404 → classic reading, no alert | PASS |
| D | `?engine=classic` → old string reading | PASS |
| E | `?engine=v3` → 14-section dev panel + composed reading | PASS |
| F | Unknown hour → composer three-pillar note with name | PASS |

## 3. Classic-fallback regression

The forced-classic reading must equal the v1.1.0 reading exactly, so the safety
net is trustworthy.

- 264 inputs, `buildReading` old vs new (`?engine=classic`)
- **0 differences**

## 4. Unchanged-behaviour regression (carried from v1.1.0)

TST corrections, per-city timezones, name-in-reading, unknown time, day-list
validity, city datalist, share links, lucky directions — all verified in the
v1.1.0 report and unaffected by this release. `CONFIG` block byte-identical;
`WORKER_URL`/`SHEET_URL` reference counts unchanged.

## 5. Manual browser procedure — run before calling it done

The harness cannot test rendering, touch, real network, or Cloudflare. Do these.

**Default (v3 live)**
1. Consult a known birthday. The reading should flow as connected prose with
   em-dash clauses and name you directly. It should feel sharper than v1.1.0.
2. Network tab: `engine-v3.browser.js` and `reading-v2.browser.js` both load
   shortly after the page (on idle), neither blocks the document.
3. Consult a second, different birthday. The two readings differ substantially,
   not just one line.
4. Consult a birthday with a day-branch clash (e.g. try a few) and confirm the
   love section sometimes carries the extra "marriage seat" paragraph.

**Fail-soft — the important one**
5. Throttle to Slow 3G, hard-reload, press CONSULT immediately. Button shows
   `WARMING UP…`, then a reading appears. It must never hang or blank.
6. In devtools, block `reading-v2.browser.js` (request blocking). Consult. The
   old short reading appears — no error, no blank. This is the live safety net.

**Flags**
7. `?engine=classic` → old reading returns (your instant rollback).
8. `?engine=v3` → dev panel shows, including the line naming which engine
   composed the prose. Confirm it says "v3 dynamic composer" on a normal load.

**Unknown hour**
9. Tick "I don't know", consult → HOUR tile `?`, and the luck section mentions
   three pillars and names you.

**Share**
10. Send a reading to yourself, open the link in a private window → the composed
    reading replays. Confirm no new Sheet row on replay.

**Mobile — Firefox on Samsung, portrait + landscape**
11. Long composed paragraphs wrap cleanly inside the cabinet, no overflow.

**file://**
12. Open the HTML from disk. The classic scripts load; a reading composes. (This
    is the case ES modules would have failed.)

## 6. Not tested

- No practitioner review of any reading. v3 is `UNVALIDATED` and the composition
  keys off its unproven signals.
- No solar-term boundary-day precision (data is day-granular).
- No daylight saving (main market doesn't observe it).
- Real-device rendering and Cloudflare cache are manual-only.
