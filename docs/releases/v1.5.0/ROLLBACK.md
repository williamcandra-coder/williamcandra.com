# Rollback — v1.5.0

## Disable the accuracy fix only, keep everything else
Delete `engine-v3/solar-terms.browser.js`. `computeBazi` checks for
`window.SolarTerms` and falls back to the engine's pillars when absent — this is
the tested fail-soft path, so nothing else breaks.

## Revert the element bar only
In `goh-pok-tong.html`, in `renderReading`, set `barData = b.tally;` and remove
the `trueElements` block. The bar returns to the old (mislabelled) figures.

## Instant, no redeploy
Set `const FORCE_CLASSIC = true;` — visitors get the old six-section reading.
Note the pillars stay corrected, because solar terms load with the core engine.

## Full revert
`git revert <v1.5.0-commit>`, push, purge Cloudflare if present.

## Back to v1.4.4
Restore `goh-pok-tong.html` and `engine-v3/reading-v2.browser.js` from that
package, and delete `engine-v3/solar-terms.browser.js`.

## Tune
- `solar-terms.browser.js` → `pillars()` returns `detail.hoursFromMonthBoundary`,
  useful for logging how near the edge a birth was.
- `trueElements()` in `reading-v2.browser.js` → the `HIDDEN` table sets
  hidden-stem depths.

## Files touched vs v1.4.4
| File | Undo |
|---|---|
| `goh-pok-tong.html` | restore v1.4.4 copy |
| `engine-v3/reading-v2.browser.js` | restore v1.4.4 copy |
| `engine-v3/solar-terms.browser.js` | delete (new file) |
| everything else | untouched |
