# GOH POK TONG — Deployment Package v1.1.0

Static site. No build step, no bundler, no server, no database, no paid service.
Drop the files in, commit, push.

- **Package version:** 1.1.0
- **Built:** 2026-07-24
- **Git commit:** _(fill in at commit time — this package was produced outside the repo)_
- **Target:** GitHub Pages + Cloudflare CDN, `williamcandra.com`
- **Engine v3 status:** present, **disabled by default**, `UNVALIDATED`

---

## What deploys

Copy to the site root, preserving structure:

```
goh-pok-tong.html            ← modified
bazi-engine.min.js           ← unchanged content, RENAMED (see below)
og-goh-pok-tong.png          ← new (social share card, 1200x630)
engine-v3/
  engine-v3.browser.js       ← new, only fetched under ?engine=v3
```

## What does NOT need to be served

```
internal/engine-v3-candidate/**
```

Development only: the ES-module engine originals, the Node test suite, the
methodology and rules files. Commit it to the repo if you want the tests in
version control — nothing at runtime requests it, and it is safe to exclude
from the published site entirely.

## ⚠️ One rename before you commit

The file you supplied was named `bazi-engine_min.js` (underscore). The page has
always requested `bazi-engine.min.js` (dot). **This package already contains the
corrected filename.** If your repo still has the underscore version, delete it —
otherwise you will ship two copies of a 2.5 MB file.

## External dependencies (unchanged)

- Google Fonts CDN — Press Start 2P, VT323, JetBrains Mono
- `index.html` at site root — target of the "NOT TODAY, UNCLE" link. Not in this
  package; it is an existing site file.
- `CONFIG.SHEET_URL` — the existing Google Apps Script endpoint. **Not modified.**
- `CONFIG.WORKER_URL` — still `""`. Behaviour unchanged: the ask-more button stays
  disabled with the coming-soon note, and no LLM call is possible.

---

## Deploy

```bash
# from the repo root
cp -r goh-pok-tong-v1.1.0/goh-pok-tong.html .
cp -r goh-pok-tong-v1.1.0/og-goh-pok-tong.png .
cp -r goh-pok-tong-v1.1.0/bazi-engine.min.js .
cp -r goh-pok-tong-v1.1.0/engine-v3 .
cp -r goh-pok-tong-v1.1.0/internal .
rm -f bazi-engine_min.js        # remove the old misnamed copy if present

git add -A
git commit -m "goh pok tong v1.1.0: TST corrections, reading fixes, engine v3 behind flag"
git push
```

Cloudflare: purge the cache for `/goh-pok-tong.html` and `/bazi-engine.min.js`
after pushing, or the old page will keep the eager `<script src>` tag.

## Verify after deploy

1. Open `/goh-pok-tong.html`. In the network tab, `bazi-engine.min.js` should
   **not** load with the document — it arrives shortly after, on idle.
2. Consult with a known birthday. Uncle should say the name out loud, and the
   chart heading should carry the full name.
3. `window.BaziV3` must be `undefined`.
4. Open `/goh-pok-tong.html?engine=v3` and consult. A dashed violet **DEV /
   UNVALIDATED** panel appears below the restart button.
5. Paste the share link into a chat app and confirm the card renders.

Full procedure in `TEST-REPORT.md`. Undo in `ROLLBACK.md`.

## Run the tests

```bash
cd internal/engine-v3-candidate
npm run test:all
```

No dependencies to install. Requires Node 18+.

---

## Standing constraints honoured

- `CONFIG.SHEET_URL` byte-identical
- `CONFIG.WORKER_URL` behaviour preserved (`""`, ask-more disabled)
- No new paid service, database, server, API or framework
- Static-host compatible; classic scripts only, no ES modules at runtime
- `bazi-engine.min.js` remains the sole source of birth date → Four Pillars
- No runtime AI in any default path
