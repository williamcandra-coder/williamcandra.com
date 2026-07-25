# GOH POK TONG — Deployment Package v1.3.0

Static site. No build step, no bundler, no server, no database, no paid service.

- **Version:** 1.3.0
- **Built:** 2026-07-25
- **Target:** GitHub Pages (+ Cloudflare CDN if in front of the domain)
- **New:** timeline — dated predictions woven into every reading; concise voice
- **v3 status:** LIVE, `UNVALIDATED`

## Files that deploy (site root, preserve structure)

```
goh-pok-tong.html                modified
bazi-engine.min.js               unchanged content (rename if repo still has underscore)
og-goh-pok-tong.png              unchanged
engine-v3/engine-v3.browser.js   unchanged
engine-v3/reading-v2.browser.js  MODIFIED — now the timeline composer
```

Only two files actually changed since v1.2.0: `goh-pok-tong.html` (passes
gender + birth year into the composer) and `engine-v3/reading-v2.browser.js`
(the timeline engine + concise voice). Everything else is carried forward.

## Not served at runtime

```
internal/engine-v3-candidate/**   (tests + engine sources)
```

## Before commit

1. Delete `bazi-engine_min.js` (underscore) from the repo if present — the page
   requests the dot form.
2. Confirm `engine-v3/` deploys BOTH `engine-v3.browser.js` and
   `reading-v2.browser.js`. The composer is required for the timeline; if it
   404s the site still works (fail-soft to the old reading) but nobody gets the
   new one.

## Deploy (Claude Code / git)

Copy the runtime paths into the repo root, delete any underscore engine copy,
commit, push. If Cloudflare fronts the domain, purge `/goh-pok-tong.html` and
the whole `/engine-v3/` path. If it's plain GitHub Pages, just wait for the
build.

## Verify after deploy

1. Consult a known birthday. The reading should be tighter than before AND carry
   dated lines — "2024…", "2027…", "somewhere in your thirties…". Money/career
   has the most.
2. Network: `engine-v3.browser.js` and `reading-v2.browser.js` both load on idle.
3. `?engine=classic` → old short reading (instant rollback).
4. `?engine=v3` → dev panel; the reading still shows dated lines.
5. Consult two different birthdays → different years, different meanings.

## Tests

```
cd internal/engine-v3-candidate && npm run test:all
```
Node 18+, no deps. Expect: core/advanced/parity PASS, composer PASS
(528 charts, 0 doom, 0 adjacent repeats, decade soft-time 528/528), validate 0.

## Constraints honoured

- `CONFIG.SHEET_URL` byte-identical; `WORKER_URL` behaviour preserved
- No new paid service, database, server, API, framework; static-host only
- `bazi-engine.min.js` remains the sole source of birth date → Four Pillars
- No runtime AI in any path; fail-soft never denies a visitor a reading
- Timeline: annual pillars exact; decade start-age intentionally soft (data limit)
