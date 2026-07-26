# GOH POK TONG — Deployment Package v1.6.0

Static site. No build step, no server, no new service.

- **Version:** 1.6.0 · Built 2026-07-25
- **Change:** prose sections split into paragraphs by kind of statement;
  left-aligned (not justified — see release notes)
- **v3 status:** LIVE, `UNVALIDATED`

## Files (site root, preserve structure)

```
goh-pok-tong.html                    MODIFIED
engine-v3/reading-v2.browser.js      MODIFIED
engine-v3/solar-terms.browser.js     unchanged
engine-v3/engine-v3.browser.js       unchanged
bazi-engine.min.js                   unchanged
og-goh-pok-tong.png                  unchanged
```

## Deploy

Copy the runtime paths into the repo root, commit, push. Purge Cloudflare for
`/goh-pok-tong.html` and `/engine-v3/` if it fronts the domain.

## Verify after deploy

1. WHO YOU ARE shows four paragraphs — nature, physical type, traits, past years.
2. WHAT'S COMING shows a paragraph per flagged year rather than one long block.
3. Spacing between paragraphs is visible but not gappy; text is left-aligned.
4. No sentence appears twice in the same reading.
5. On a narrow phone, paragraphs wrap cleanly inside the cabinet.
6. `?engine=classic` still returns the old six-section reading (single blocks).

## Constraints honoured

- `CONFIG.SHEET_URL` byte-identical; `WORKER_URL` retained as an unused key
- No new paid service, database, server, API or framework; static-host only
- No runtime AI; fail-soft unchanged
- Paragraphs rendered via `textContent`, never `innerHTML` — the name is user input
