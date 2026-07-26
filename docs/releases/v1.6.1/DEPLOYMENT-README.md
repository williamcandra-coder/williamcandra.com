# GOH POK TONG — Deployment Package v1.6.1

Static site. No build step, no server, no new service.

- **Version:** 1.6.1 · Built 2026-07-25
- **Change:** repetition fix — strength band rebalanced, health decoupled from
  What's Coming, three phrasings added to every low-variance table
- **v3 status:** LIVE, `UNVALIDATED`

## Files (site root, preserve structure)

```
engine-v3/reading-v2.browser.js      MODIFIED — the only real change
goh-pok-tong.html                    unchanged since v1.6.0
engine-v3/solar-terms.browser.js     unchanged
engine-v3/engine-v3.browser.js       unchanged
bazi-engine.min.js                   unchanged
og-goh-pok-tong.png                  unchanged
```

## Deploy

Copy the runtime paths into the repo root, commit, push. Purge Cloudflare for
`/engine-v3/` if it fronts the domain.

## Verify after deploy

1. Consult **three different birthdays** and compare HEALTH — the element named
   should differ, and it should describe an element that is *heavy*, not thin.
2. Compare LOVE & SPOUSE across a few charts — the third paragraph should not
   open the same way every time.
3. Compare YOUR FORTUNE — the opening sentence should vary.
4. WHAT'S COMING and HEALTH should no longer name the same element.
5. `?engine=classic` still returns the old six-section reading.

## Constraints honoured

- `CONFIG.SHEET_URL` byte-identical; `WORKER_URL` retained as an unused key
- No new paid service, database, server, API or framework; static-host only
- No runtime AI; fail-soft unchanged
- Health copy remains tendencies with practical habits — never diagnosis
