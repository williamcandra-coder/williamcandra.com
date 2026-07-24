# Rollback — v1.1.0

## Fastest: revert the commit

```bash
git revert <v1.1.0-commit>
git push
```
Then purge the Cloudflare cache for `/goh-pok-tong.html` and
`/bazi-engine.min.js`.

## Disable engine v3 without reverting anything else

v3 is already off for every visitor — it needs `?engine=v3`. To hard-disable:

- in `goh-pok-tong.html`, set `const V3_FLAG = false;`, or
- delete the `engine-v3/` directory. The loader fails closed: the reading still
  renders and only the dev panel shows an error.

## Partial rollbacks

Each is independent. Order does not matter.

**Restore eager engine loading** (undo lazy load) — put back
`<script src="bazi-engine.min.js"></script>` before the inline `<script>`, and
delete the `preloadEngine` IIFE. `loadBaziEngine()` resolves immediately when
`window.BaziCalculator` already exists, so nothing else needs touching.

**Restore the old True Solar Time behaviour** — in `trueSolarHour`, force
`dayShift = 0` and always return the original `y, mo, d`. To also undo the
timezone fix, replace the `tz` lookup with `COUNTRY_TZ[country] ?? 0`.
⚠️ This reinstates the wrong day pillar for post-midnight births and the wrong
hour branch for WITA/WIT and US cities.

**Remove the name from the reading** — replace the `OPENERS`/`CLOSERS` arrays
with the previous 5-entry versions and drop the `fillName(...)` wrappers in
`buildReading`. `tidyName` can stay; it is used by the share link too.

**Remove the unknown-time option** — delete the `.tcheck` block from the form
markup. `computeBazi` defaults `hourKnown` to `true` when the argument is
omitted, so nothing else breaks.

**Remove sharing** — delete the `.sharewrap` and `#shareMsg` markup, the
`shareBtn` listener, `readingUrl`, and the `fromSharedLink` IIFE.

**Remove the lucky-directions line** — delete the `#dirLine` div. The render
block is already null-guarded.

**Restore the removed legacy pillar calculator** — it is lines 243–276 of the
pre-integration `goh-pok-tong.html`: `BRANCH_EL`, `BRANCH_HIDDEN`, `jdn`,
`yearPillar`, `monthPillar`, `dayPillar`, `hourPillar`. The replacement comment
block in the current file names every removed symbol. Nothing calls them; this
is only for reference.

## What a rollback cannot undo

Readings already shared as links replay against whatever version is live. A link
created under v1.1.0 and opened after a rollback will produce the **old** pillars
for affected cities. The link carries the form input, not the result.

## Files this release touched

| File | Action to undo |
|---|---|
| `goh-pok-tong.html` | restore previous version |
| `bazi-engine.min.js` | none — content unchanged (filename corrected only) |
| `engine-v3/engine-v3.browser.js` | delete |
| `og-goh-pok-tong.png` | delete, and remove the `og:image` / `twitter:image` tags |
| `internal/engine-v3-candidate/parity-test.mjs` | delete |
| `internal/engine-v3-candidate/validate.mjs` | restore previous version |
| `internal/engine-v3-candidate/package.json` | restore previous version |
| everything else under `internal/` | untouched |
