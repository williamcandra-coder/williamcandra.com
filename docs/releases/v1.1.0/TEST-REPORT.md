# Test Report — v1.1.0

Environment: Node v22.22.2, Linux. Browser tests are the manual procedure in §4.

---

## 1. Automated — Node suite

```
cd internal/engine-v3-candidate && npm run test:all
```

| Test | Result |
|---|---|
| `test.mjs` — core engine | PASS |
| `advanced-test.mjs` — advanced engine structure | PASS |
| `parity-test.mjs` — browser build vs ES-module originals | **PASS — 13,444 comparisons, 0 mismatches** |
| `validate.mjs` — fixture runner | reviewed 0, skipped 1, passed 0, failed 0 |

`validate.mjs` prints `NOT A VALIDATION RUN — the reviewed-fixture corpus is
empty.` and exits 0. That is intentional: it fails only on a **reviewed** fixture
that mismatches, and none exist. **The suite passing is not evidence that the
engine is astrologically correct.**

### What parity covers

All 100 stem pairs through `tenGod`; all 60 sexagenary day pillars × 12 month
branches; 4,000 seeded random four-pillar charts with and without a luck pillar;
4 malformed inputs that both builds must reject identically; version and
certification strings. It proves the classic-script build computes exactly what
the ES-module originals compute. It proves nothing about whether that is right.

---

## 2. Regression — default reading unchanged by the v3 integration

Original page vs post-integration page, same engine, flag off.

- **2,520 birth inputs** (1960–2020 × 6 months × 4 days × 5 hours × 7 city/country pairs)
- Compared: all four pillars, element tally, TST object, all six reading sections
- **Result: 0 differences**
- `YEAR_RANGE` guard behaves identically on a 1959 input

## 3. Delta — TST corrections (expected to differ)

Pre-v1.1.0 page vs v1.1.0 page. **25,080 birth inputs**, 19 city/country pairs.

| Measure | Count |
|---|---|
| Charts changed | 13,486 (53.77% of this deliberately skewed sample) |
| — day pillar changed | 871 |
| — hour pillar only | 12,615 |
| — city previously had no longitude entry | 9,240 |

Per-city rates and causes are tabulated in `RELEASE-NOTES.md` §1.3. Every change
traces to either the day-rollover fix, the per-city timezone fix, or a city newly
gaining longitude support. No unexplained differences.

Day-shift spot checks (1990-05-15):

| Input | Result |
|---|---|
| Banda Aceh 00:10 | 23:35, shift −1, reads 1990-05-14 |
| Jayapura 23:50 | 00:16, shift +1, reads 1990-05-16 |
| Chengdu 00:20 | 23:20, shift −1, reads 1990-05-14 |
| Banda Aceh **1960-01-01** 00:05 | shift suppressed, stays 1960-01-01 ✓ |

Timezone spot checks: Makassar resolves to +8 (lon 119.42), Surabaya to +7
(lon 112.75), Los Angeles to −8, New York to −5.

## 4. Functional — headless DOM harness

Page script executed in a Node `vm` realm against a stubbed DOM.

| # | Check | Result |
|---|---|---|
| 1 | Engine absent at parse time; no script requested on load | PASS |
| 2 | Name appears in opener and closer; chart heading carries full name | PASS |
| 3 | Unknown time → HOUR tile `?`, three-pillar note, caveat in reading | PASS |
| 4 | Day-shift fix returns correct date | PASS |
| 5 | Per-city timezone applied | PASS |
| 6 | Day list = 28 / 29 / 30 for Feb 1990, Feb 1992, April | PASS |
| 7 | City datalist populated (162 entries) | PASS |
| 8 | Share link built and copied to clipboard | PASS |
| 9 | Shared link replays, honours `t=?` unknown-time flag | PASS |
| 10 | `?engine=v3` renders all 14 evidence sections, marked UNVALIDATED | PASS |

Syntax: `node --check` clean on the inline page script and on
`engine-v3/engine-v3.browser.js`.

Constraint verification: `CONFIG` block byte-identical to the approved file;
`CONFIG.WORKER_URL` and `CONFIG.SHEET_URL` reference counts unchanged.

---

## 5. Manual browser procedure — run before calling it done

The harness cannot test rendering, touch, or real network. Do these.

**A. Production path (no query string)**

1. Load the page. Network tab: `bazi-engine.min.js` must **not** be a
   document-blocking request. It should arrive shortly after paint.
2. `window.BaziV3` → `undefined`.
3. Consult with a birthday you know. Confirm: name in the opener, name in the
   closer, full name in the chart heading, four pillars, element bar, lucky
   directions line, TST note.
4. Ask-more button disabled with the coming-soon note.
5. Restart returns to the form and clears the share message.

**B. New behaviour**

6. Tick "I don't know" → time input greys out → consult → HOUR tile shows `?`,
   note says three pillars, reading acknowledges it.
7. Set month to February, year to a non-leap year → day list stops at 28. Switch
   to a leap year → 29.
8. Type `sur` in City → autocomplete suggests Surabaya, Surakarta.
9. Consult from Makassar or Denpasar and confirm the hour pillar differs from
   what the old build gave.
10. `SEND TO SOMEONE` → share sheet on mobile, clipboard on desktop. Open the
    link in a private window: the reading replays. Confirm no new Sheet row.
11. Paste the link into WhatsApp/Telegram and confirm the card image renders.

**C. Flag path**

12. `?engine=v3` → consult → dashed violet panel, DEV and UNVALIDATED badges,
    14 sections. `SOURCE` characters must match the pillar tiles.
13. Consult a second person — panel refreshes, no stale data.

**D. Failure isolation**

14. Temporarily rename `engine-v3/`. With the flag on, the reading must still
    render normally; only the panel shows a red load error.
15. Throttle to Slow 3G and press CONSULT immediately on load. Button shows
    `WARMING UP…`, then the reading appears. It must not hang or double-fire.

**E. Mobile — Firefox on Samsung, both flag states, portrait and landscape**

16. Panel tables scroll within themselves and do not widen the cabinet.
17. The unknown-time checkbox is comfortably tappable.

**F. `file://`**

18. Open the HTML from disk with `?engine=v3`. The classic script must load.
    This is the case ES modules would have failed.

---

## 6. Not tested

- No practitioner review of any chart output. The engine remains `UNVALIDATED`.
- No test of solar-term boundary-day births, because the data resolves only to
  the day and there is nothing finer to compare against.
- No daylight-saving cases.
- Real-device rendering, touch targets, and Cloudflare cache behaviour are
  covered only by the manual procedure above.
