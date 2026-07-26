# Rollback — v1.6.0

## Back to v1.5.1 (single-block sections)
Restore both `goh-pok-tong.html` and `engine-v3/reading-v2.browser.js` from that
package. They must go back together — the v1.6.0 renderer expects arrays and the
v1.5.1 composer returns strings. (The renderer does accept both shapes, so a
mismatch degrades to single blocks rather than breaking, but restoring the pair
is cleaner.)

## Full revert
`git revert <v1.6.0-commit>`, push, purge Cloudflare if present.

## Merge or split paragraphs without a rollback
In `compose()` in `reading-v2.browser.js`, each section returns an array.
Concatenate two entries to merge them; add an entry to split. For example, to
put physical type and traits back in one paragraph:
`[ pCore, pPhysical + ' ' + pTraits, pSelfYears ]`.

## Change spacing
`.section .stext .para` in `goh-pok-tong.html` — `margin-bottom` controls the
gap. The stylesheet comment explains why alignment is left and not justified;
please read it before switching to `text-align: justify`.

## Files touched vs v1.5.1
| File | Undo |
|---|---|
| `goh-pok-tong.html` | restore v1.5.1 copy |
| `engine-v3/reading-v2.browser.js` | restore v1.5.1 copy |
| everything else | untouched |
