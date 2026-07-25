# Rollback — v1.2.0

## Instant, no redeploy: force classic for everyone

The old reading is still in the page and still works. To send every visitor back
to it without touching files, in `goh-pok-tong.html` change:

```js
const FORCE_CLASSIC = ( ... ):  // make this always true
```
to
```js
const FORCE_CLASSIC = true;
```

Commit, push, purge Cloudflare. v3 stops driving readings immediately; the
composer file simply stops being used.

## Full revert

```
git revert <v1.2.0-commit>
git push
```
Then purge Cloudflare for `/goh-pok-tong.html`, `/bazi-engine.min.js`, `/engine-v3/`.

## Partial

**Drop the composer, keep v1.1.0 reading** — delete
`engine-v3/reading-v2.browser.js`. The loader's composer inject fails, `loadV3`
rejects, and every consult fail-softs to `buildReading`. No other change needed.
(This is exactly the fail-soft path, so it is already tested.)

**Tune the voice instead of rolling back** — the entire reading text is the
`FRAG` object at the top of `engine-v3/reading-v2.browser.js`. Editing fragments
never touches logic. Prefer this to a rollback if the problem is wording, not
behaviour.

## What a rollback cannot undo

Shared links carry form input, not the rendered reading. A link created under
v1.2.0 and opened after a rollback replays whatever engine is then live — so it
will show the *old* reading. The link is not frozen to v1.2.0 prose.

## Files this release touched vs v1.1.0

| File | Undo |
|---|---|
| `goh-pok-tong.html` | restore v1.1.0 copy |
| `engine-v3/reading-v2.browser.js` | delete (new file) |
| `internal/engine-v3-candidate/composer-test.mjs` | delete (new file) |
| `internal/engine-v3-candidate/package.json` | restore v1.1.0 copy |
| everything else | untouched |
