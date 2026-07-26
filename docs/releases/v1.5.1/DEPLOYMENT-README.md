# GOH POK TONG — Deployment Package v1.5.1

Static site. No build step, no server, no new service.

- **Version:** 1.5.1 · Built 2026-07-25
- **Change:** back-link label changes to a send-off once the reading is shown
- **v3 status:** LIVE, `UNVALIDATED`

## Files (site root, preserve structure)

```
goh-pok-tong.html                    MODIFIED — the only real change
engine-v3/solar-terms.browser.js     unchanged
engine-v3/reading-v2.browser.js      unchanged
engine-v3/engine-v3.browser.js       unchanged
bazi-engine.min.js                   unchanged
og-goh-pok-tong.png                  unchanged
```

## Deploy

Copy the runtime paths into the repo root, commit, push. Purge Cloudflare for
`/goh-pok-tong.html` if it fronts the domain.

## Verify after deploy

1. On load, the top-left link reads **NOT TODAY, UNCLE**.
2. Consult — it changes to a send-off ("THANK YOU, UNCLE", "RUDE. ACCURATE.", …).
3. Press ASK ABOUT SOMEONE ELSE — it reverts to NOT TODAY, UNCLE.
4. Consult two different birthdays — the send-off usually differs.
5. On a narrow phone, the label stays inside the cabinet edge.

## Constraints honoured

- `CONFIG.SHEET_URL` byte-identical; `WORKER_URL` retained as an unused key
- No new paid service, database, server, API or framework; static-host only
- No runtime AI; fail-soft unchanged
- Link still points to `index.html` in both states
