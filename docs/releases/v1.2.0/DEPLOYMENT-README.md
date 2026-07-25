# GOH POK TONG — Deployment Package v1.2.0

Static site. No build step, no bundler, no server, no database, no paid service.

- **Version:** 1.2.0
- **Built:** 2026-07-25
- **Target:** GitHub Pages + Cloudflare CDN, williamcandra.com
- **Big change:** the reading is now dynamically composed and driven by the v3
  engine for every visitor, with fail-soft fallback to the old reading.
- **v3 status:** LIVE, `UNVALIDATED`

## Files that deploy (site root, preserve structure)

```
goh-pok-tong.html                modified
bazi-engine.min.js               unchanged content (rename if repo still has underscore)
og-goh-pok-tong.png              unchanged
engine-v3/engine-v3.browser.js   unchanged
engine-v3/reading-v2.browser.js  NEW — the dynamic composer
```

## Not served at runtime (commit if you want tests in git)

```
internal/engine-v3-candidate/**
```

## ⚠️ Two things before commit

1. If the repo still has `bazi-engine_min.js` (underscore), the page won't find
   it — the page requests the dot form `bazi-engine.min.js`. This package ships
   the correct name; delete the underscore copy.
2. `engine-v3/reading-v2.browser.js` is **new** and **required**. If it 404s in
   production the site still works (fail-soft to the old reading) but nobody gets
   the new one. Make sure the whole `engine-v3/` folder deploys.

## Deploy (Claude Code / git)

Copy the five runtime paths into the repo root, delete any underscore engine
copy, commit, push. Then **purge Cloudflare** for `/goh-pok-tong.html`,
`/bazi-engine.min.js`, and the whole `/engine-v3/` path — otherwise the cached
page loads the old bytes.

## Verify after deploy

1. Load `/goh-pok-tong.html`, consult with a known birthday. The reading should
   read as flowing prose with em-dash clauses, not the old short blurbs. Uncle
   names your contradictions.
2. Network tab: `engine-v3.browser.js` AND `reading-v2.browser.js` both load
   (on idle, shortly after the page).
3. `/goh-pok-tong.html?engine=classic` → the old short reading returns. This is
   your instant rollback.
4. `/goh-pok-tong.html?engine=v3` → dev panel appears, with a line naming which
   engine composed the reading.
5. Consult two different birthdays → the readings differ substantially, not just
   in one blurb.

Full procedure in `TEST-REPORT.md`. Undo in `ROLLBACK.md`.

## Tests

```
cd internal/engine-v3-candidate && npm run test:all
```

Node 18+, no dependencies. Expect: core PASS, advanced PASS, parity PASS
(13,444 comparisons), composer PASS (1,416 charts, zero doom), validate exit 0.

## Constraints honoured

- `CONFIG.SHEET_URL` byte-identical; `CONFIG.WORKER_URL` behaviour preserved
- No new paid service, database, server, API, framework
- Static-host compatible; classic scripts only, no runtime ES modules
- `bazi-engine.min.js` remains the sole source of birth date → Four Pillars
- No runtime AI anywhere in the default path
- Fail-soft: v3 failure never denies a visitor a reading
