# Rollback — v1.6.1

## Back to v1.6.0
Restore `engine-v3/reading-v2.browser.js` from that package. It is the only file
changed; `goh-pok-tong.html` is identical in both.

## Full revert
`git revert <v1.6.1-commit>`, push, purge Cloudflare if present.

## Tune instead of rolling back
- **Strength banding:** `strengthBucket(cls, score)` — the `39` and `52` cut
  points are the measured tertiles. Raising them pushes more readers into
  "weak"; lowering them into "strong".
- **Health selector:** `hBody` uses `strong` (dominant element). Change to
  `thin` to restore the old behaviour — but note that makes it restate What's
  Coming.
- **Adding phrasings:** any table entry can be a string or an array. `variant()`
  handles both, so appending an alternative needs no code change.
- **Variant indices:** `iDay`, `iMonth`, `iYear`, `iHour`, `iStem` in
  `compose()`. Each table uses a different one on purpose — if you point two
  tables at the same index they will correlate and repetition returns.

## Files touched vs v1.6.0
| File | Undo |
|---|---|
| `engine-v3/reading-v2.browser.js` | restore v1.6.0 copy |
| everything else | untouched |
