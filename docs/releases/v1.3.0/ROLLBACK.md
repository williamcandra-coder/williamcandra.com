# Rollback — v1.3.0

## Instant, no redeploy: force classic for everyone
In `goh-pok-tong.html` set `const FORCE_CLASSIC = true;`. Commit, push, purge
Cloudflare if present. Every visitor gets the old short reading; the composer
stops being used.

## Drop just the timeline, keep v1.2.0 composed reading
Restore `engine-v3/reading-v2.browser.js` from the v1.2.0 package. It's the only
file with the timeline; the page works unchanged with the older composer (it
simply ignores the extra `gender`/`birthYear` options).

## Full revert
`git revert <v1.3.0-commit>`, push, purge Cloudflare if present.

## Tune instead of roll back
All timeline + voice copy is `FRAG` / `YEAR` / `PAST_REFLECT` / `DECADE` at the
top of `reading-v2.browser.js`. Editing strings never touches logic. Prefer this
if the issue is wording.

## What a rollback cannot undo
Shared links carry form input, not rendered prose. A link made under v1.3.0 and
opened after rollback replays whatever engine is then live.

## Files touched vs v1.2.0
| File | Undo |
|---|---|
| `goh-pok-tong.html` | restore v1.2.0 copy (one line: the compose() call) |
| `engine-v3/reading-v2.browser.js` | restore v1.2.0 copy |
| `internal/engine-v3-candidate/composer-test.mjs` | restore v1.2.0 copy |
| `internal/engine-v3-candidate/package.json` | version bump only |
| everything else | untouched |
