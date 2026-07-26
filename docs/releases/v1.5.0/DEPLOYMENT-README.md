# GOH POK TONG — Deployment Package v1.5.0

Static site. No build step, no server, no new service.

- **Version:** 1.5.0 · Built 2026-07-25
- **Type:** accuracy release
- **Changes:** solar terms computed to the minute; ELEMENT BALANCE bar now shows
  a true element count
- **v3 status:** LIVE, `UNVALIDATED`

## Files (site root, preserve structure)

```
goh-pok-tong.html                    MODIFIED
engine-v3/solar-terms.browser.js     NEW — required for the accuracy fix
engine-v3/reading-v2.browser.js      MODIFIED
engine-v3/engine-v3.browser.js       unchanged
bazi-engine.min.js                   unchanged
og-goh-pok-tong.png                  unchanged
```

## ⚠️ New file this release

`engine-v3/solar-terms.browser.js` is new. If it 404s the site still works
(chart falls back to the engine's day-granular terms) but the accuracy fix is
silently absent. Confirm the whole `engine-v3/` folder deploys.

## Deploy

Copy the runtime paths into the repo root, commit, push. Purge Cloudflare for
`/goh-pok-tong.html` and `/engine-v3/` if it fronts the domain.

## Verify after deploy

1. Consult a **boundary birth** — e.g. 4 May 2013, or 6 July 1976. In the
   console, `window._baziContext.chart.solarFix` should show
   `applied: true` and name the engine's original month.
2. Consult a normal birth (e.g. 15 May 1990) — `solarFix.applied` should be
   `false`.
3. Hover the ELEMENT BALANCE segments — each now shows a percentage. For a chart
   with two Metal stems, Metal should be the largest segment.
4. `window._barIsTrueCount` should be `true`.
5. `?engine=classic` still returns the old six-section reading — and now with
   corrected pillars, since solar terms load with the core engine.

## Constraints honoured

- `CONFIG.SHEET_URL` byte-identical; `WORKER_URL` retained as an unused key
- No new paid service, database, server, API or framework; static-host only
- No runtime AI; fail-soft never denies a visitor a reading or a chart
- Solar-term module is dependency-free, offline, and classic-script
- Day and hour pillars still come from `bazi-engine.min.js`
