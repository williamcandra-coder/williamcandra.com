# Test Report — v1.3.0

Node v22.22.2, Linux. Browser rendering is the manual procedure §5.

## 1. Node suite — `npm run test:all`
| Test | Result |
|---|---|
| core (`test.mjs`) | PASS |
| advanced (`advanced-test.mjs`) | PASS |
| parity (`parity-test.mjs`) | PASS, 13,444 comparisons, 0 mismatch |
| **composer (`composer-test.mjs`)** | **PASS, 528 charts** |
| validate (`validate.mjs`) | reviewed 0 / exit 0 |

### Composer test asserts (timeline build)
- every section non-empty; name in opener + closer
- zero deterministic-doom vocabulary (12-phrase blocklist)
- day-branch-clash line fires iff a real day-branch clash exists (110/110)
- hour-unknown note present when hour unknown
- **timeline:** money section carries ≥3 dated lines on every chart (528/528);
  **zero adjacent verbatim year repeats**; decade marker uses soft-time band on
  every chart (528/528); **no hard age ever printed** for the decade
- variety floors: self/career well above fragment count (157 / 197 distinct)

## 2. Annual-pillar correctness (spot)
2027 = Ding-Wei · 2024 = Jia-Chen · 2020 = Geng-Zi · 1990 = Geng-Wu — all
correct against the sexagenary cycle.

## 3. Integration — headless DOM
| # | Check | Result |
|---|---|---|
| A | v3 timeline composer drives the reading; dated lines present; name woven | PASS |
| B | engine 404 → classic reading, no alert, no blank | PASS |
| C | composer 404 → classic reading | PASS |
| D | `?engine=classic` forces old reading | PASS |
| E | `?engine=v3` → dev panel + timeline reading | PASS |
| F | unknown hour → three-pillar note | PASS |

## 4. Classic-fallback regression
Forced-classic reading is byte-identical to v1.1.0 (264 inputs, 0 diff) — the
safety net is unchanged and trustworthy.

## 5. Manual browser procedure — run before shipping
1. Consult a known birthday. Reading is tighter than v1.2.0 and carries dated
   lines (past + future + a "somewhere in your <decade>" marker). Money section
   has the fullest run.
2. Read the dated lines critically: no two adjacent years identical; the decade
   line never states a hard age; nothing predicts marriage/death/loss on a date.
3. Try a birthday whose past year you remember — does the past-anchor callback
   feel plausible? (This is the line that convinces or breaks trust.)
4. Network: both engine-v3 files load on idle, neither blocks the document.
5. **Fail-soft:** block `reading-v2.browser.js` in devtools → old reading
   appears, no error. This is the live safety net.
6. `?engine=classic` returns the old reading. `?engine=v3` shows the dev panel.
7. Unknown hour → HOUR tile `?`, three-pillar note.
8. Share a reading, open the link in a private window → replays; no new Sheet row.
9. Mobile (Firefox/Samsung, portrait + landscape): long dated paragraphs wrap
   inside the cabinet, no overflow.
10. file:// open with a normal load → timeline composes (ES modules would fail here).

## 6. Not tested
- No practitioner review; v3 `UNVALIDATED`, timeline keys off unproven signals.
- Decade start-age is soft by design (day-granular solar terms) — the ±1–2 year
  imprecision is absorbed by soft-time language, not eliminated.
- No daylight saving; main market doesn't observe it.
- Real-device rendering and Cloudflare cache are manual-only.
