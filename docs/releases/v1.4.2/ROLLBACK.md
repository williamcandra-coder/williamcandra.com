# Rollback — v1.4.2

## Back to v1.4.1 or v1.4.0
Restore `engine-v3/reading-v2.browser.js` from that package. It is the only
changed file; `goh-pok-tong.html` is identical across v1.4.0, v1.4.1 and v1.4.2.

## Instant, no redeploy
Set `const FORCE_CLASSIC = true;` in `goh-pok-tong.html` — every visitor gets the
old six-section reading and the newer sections hide themselves.

## Full revert
`git revert <v1.4.2-commit>`, push, purge Cloudflare if present.

## Tune instead of rolling back
In `reading-v2.browser.js`:
- `notableYears(pillars, next1, 12, 4, [next1, next2])` — raise `12` to look
  further ahead, lower `4` to surface fewer years.
- `FRAG.notable.clash.*` / `FRAG.notable.combo.*` — the eight seat-specific
  lines. Edit freely; logic never changes.
- To go back to day-seat-only, restrict the seat loop to `['day']`.

## Files touched vs v1.4.1
| File | Undo |
|---|---|
| `engine-v3/reading-v2.browser.js` | restore v1.4.1 copy |
| everything else | untouched |
