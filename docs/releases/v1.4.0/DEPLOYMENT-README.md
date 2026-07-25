# GOH POK TONG — Deployment Package v1.4.0

Static site. No build step, no bundler, no server, no database, no paid service.

- **Version:** 1.4.0 · Built 2026-07-25
- **Changes:** plainer wording · physique + traits in Who You Are · ten sections
  · Ask Uncle feature removed
- **v3 status:** LIVE, `UNVALIDATED`

## Files (site root, preserve structure)

```
goh-pok-tong.html                modified
engine-v3/reading-v2.browser.js  modified — ten-section composer
engine-v3/engine-v3.browser.js   unchanged
bazi-engine.min.js               unchanged
og-goh-pok-tong.png              unchanged
```

Two files actually changed: `goh-pok-tong.html` and
`engine-v3/reading-v2.browser.js`. The rest is carried forward so the tree is
complete.

## Before commit

1. Delete `bazi-engine_min.js` (underscore) from the repo if present — the page
   requests the dot form.
2. Confirm `engine-v3/` deploys **both** files. If `reading-v2.browser.js` 404s
   the site still works (fail-soft to the old six-section reading) but nobody
   gets the new one.

## Deploy

Copy the runtime paths into the repo root, commit, push. If Cloudflare fronts
the domain, purge `/goh-pok-tong.html` and `/engine-v3/`. Plain GitHub Pages
needs no purge — just wait for the build.

## Verify after deploy

1. Consult a known birthday → **ten sections**, and Who You Are includes a
   physique line and a `Traits:` list.
2. Wording reads plainly — no cryptic lines.
3. "Ask Uncle One More Thing" is gone from the page.
4. Dated lines appear in Fortune, Career, Love, What's Coming — and no two of
   those anchor on the same year.
5. Health reads as gentle habits, never a diagnosis.
6. `?engine=classic` → old six-section reading (instant rollback); the four new
   sections hide rather than showing empty.

## Constraints honoured

- `CONFIG.SHEET_URL` byte-identical; `WORKER_URL` retained as an unused key
- No new paid service, database, server, API, framework; static-host only
- `bazi-engine.min.js` remains the sole source of birth date → Four Pillars
- No runtime AI anywhere; fail-soft never denies a visitor a reading
- Annual pillars exact; decade start-age intentionally soft (data limit)
- Health copy: tendencies only, never diagnosis
