# Rollback — v1.4.0

## Instant, no redeploy
In `goh-pok-tong.html` set `const FORCE_CLASSIC = true;`. Every visitor gets the
old six-section reading; the four new sections hide themselves automatically.
Commit, push, purge Cloudflare if present.

## Back to v1.3.0 (six sections, timeline voice)
Restore both `goh-pok-tong.html` and `engine-v3/reading-v2.browser.js` from the
v1.3.0 package. They must be restored together — the v1.4.0 page expects ten
section IDs.

## Full revert
`git revert <v1.4.0-commit>`, push, purge Cloudflare if present.

## Restore the Ask Uncle feature
It was fully removed (markup, CSS, handler). Restore from the v1.3.0
`goh-pok-tong.html`: the `.rpanel` ask-more block, the `.ask-more` CSS group,
the `askMoreBtn` click handler, the ask-more availability block in
`renderReading`, and `'question'` in the enter-to-submit ID list.

## Tune instead of rolling back
All copy is `FRAG` / `YEAR` / `PAST_REFLECT` / `DECADE` at the top of
`reading-v2.browser.js`. Editing strings never touches logic. Prefer this if the
issue is wording — especially for `physique`, `traits` and `health`, which are
the newest and most likely to need your voice.

## What a rollback cannot undo
Shared links carry form input, not rendered prose. A link made under v1.4.0 and
opened after a rollback replays whatever engine is then live.

## Files touched vs v1.3.0
| File | Undo |
|---|---|
| `goh-pok-tong.html` | restore v1.3.0 copy |
| `engine-v3/reading-v2.browser.js` | restore v1.3.0 copy |
| everything else | untouched |
