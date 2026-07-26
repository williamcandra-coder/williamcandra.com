# Rollback — v1.5.1

## Revert the label change only
In `goh-pok-tong.html`, remove the two `setBackLink(...)` calls (one in
`renderReading`, one in the restart handler). The link keeps its markup default,
"NOT TODAY, UNCLE", in both states.

## Back to v1.5.0
Restore `goh-pok-tong.html` from that package. It is the only file changed.

## Full revert
`git revert <v1.5.1-commit>`, push, purge Cloudflare if present.

## Tune
`BACK_BEFORE` / `BACK_AFTER` in `goh-pok-tong.html`. Keep new labels to 19
characters or fewer — the link is 7px Press Start 2P and longer strings overflow
the cabinet on a narrow phone.

## Files touched vs v1.5.0
| File | Undo |
|---|---|
| `goh-pok-tong.html` | restore v1.5.0 copy |
| everything else | untouched |
