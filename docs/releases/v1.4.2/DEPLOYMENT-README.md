# GOH POK TONG — Deployment Package v1.4.2

Static site. No build step, no server, no new service.

- **Version:** 1.4.2 · Built 2026-07-25
- **Change:** "What's Coming" now surfaces up to four notable years, each tied to
  a specific pillar seat (self/marriage, career, roots, home)
- **v3 status:** LIVE, `UNVALIDATED`

## Files (site root, preserve structure)

```
engine-v3/reading-v2.browser.js  MODIFIED — the only real change
goh-pok-tong.html                unchanged since v1.4.0
engine-v3/engine-v3.browser.js   unchanged
bazi-engine.min.js               unchanged
og-goh-pok-tong.png              unchanged
```

## Deploy

Copy the runtime paths into the repo root, commit, push. Purge Cloudflare for
`/engine-v3/` if it fronts the domain; plain GitHub Pages needs no purge.

## Verify after deploy

1. WHAT'S COMING names next year, the year after, and **three to four further
   years**, each with a distinct meaning.
2. No year is mentioned twice in that section.
3. The flagged years and their meanings differ between two different birthdays.
4. Nothing predicts marriage, illness, loss or failure on a date.
5. `?engine=classic` still returns the old six-section reading.

## Constraints honoured

- `CONFIG.SHEET_URL` byte-identical; `WORKER_URL` retained as an unused key
- No new paid service, database, server, API or framework; static-host only
- `bazi-engine.min.js` remains the sole source of birth date → Four Pillars
- No runtime AI; fail-soft never denies a visitor a reading
- Notable years computed from standard branch clash/combination tables
- No dated verdicts; health copy remains tendencies only
