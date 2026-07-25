# Release Notes — v1.3.0

**The reading now maps time. It says what a year meant and what years are coming
— dated, chart-specific, woven into the prose.** And the whole voice got tighter.

Builds on v1.2.0 (dynamic composed reading, v3 live for everyone). If you're
jumping from v1.1.0, read the v1.2.0 notes first — the reading engine changed
fundamentally there.

---

## 1. Timeline — dated predictions, woven in

Every reading now carries a run of dated lines built from the **annual-pillar**
(流年) and **luck-pillar** (大運) systems:

- **2 past anchors + current year + next 3 years + one decade marker**,
  distributed across sections (money/career carries the fullest run).
- Each dated line is computed from that year's **Ten God relationship to the
  visitor's Day Master**, then colored by section. So 2027 says something
  different to every chart, and something different in money vs love.
- Woven into the prose, not listed — it reads like a seer talking, not an app
  printing a table.

### Sample — money section (1990-05-15, "Wira")

> Work: your name goes on it or you rot. Terrible under a micromanager. Own something. Balanced enough to lead or support, which is why you half-do both. Pick the harder one. 2024 drags money center stage — it's there, Wira, but it shows up wearing a fight. 2026 — responsibility outruns reward a while; you hold the purse before you enjoy it. 2027 — you earn the weight before the wallet; the reward is late, not absent. 2029 — the return is knowledge, not cash. Bank it; it pays out later. Around your forties, a decade of appetite arrives — money, wanting, reaching. Rewards the disciplined, punishes the greedy. Only you know which you are.

Every year and its meaning is computed. Nothing is invented.

### The past anchors are the convincing part

"2024 put something you wanted within reach — did the reaching cost more than
the having?" reads as sight because it's checkable against the visitor's own
memory. That callback in "What's Coming" is the line people screenshot.

### Honesty, enforced in code

- **Annual pillars are exact.** Verified: 2027 = Ding-Wei, 2024 = Jia-Chen,
  1990 = Geng-Wu, all correct against the sexagenary cycle.
- **The decade marker uses SOFT TIME on purpose.** The luck-pillar *direction*
  and *sequence* are exact, but its *start age* needs solar terms to the hour
  and the engine has them to the day. So the decade line says "somewhere in your
  thirties," never "at 32." That is deliberate mystique covering a real data
  limit — not fake precision. The composer test asserts no hard age ever appears.
- **No verdicts.** Dated weather, never dated fate. Nothing about marrying,
  dying, losing or failing on a date. A 528-chart scan confirms zero
  doom-vocabulary in any section.
- **Adjacent years never read identically.** Two phrasings per year-meaning,
  chosen by year parity — verified 0 verbatim repeats across 528 charts.

## 2. Concise chaotic voice

Every fragment rewritten shorter and sharper — more menace per word, less
throat-clearing. The name is woven so each reading lands as aimed at the reader.

**Before (v1.2.0):** *"You're Yang Metal — a blade, not a decoration. Direct,
tempered, made to cut through nonsense. You've hurt people by 'just being
honest' and you'd do it again."*

**Now:** *"Yang Metal — a blade, Wira. You cut, then wonder why people bleed. The
sky made you sharp. Gentle was not included."*

"Special" is specificity, not flattery — by your call. The reading earns
recognition by being uncannily about the reader, never by calling them chosen.

## 3. Composition scale

528-chart sweep: **157 distinct self paragraphs, 197 distinct money sections**
(the timeline multiplied career variety), 81 love, 42 luck. Two people with
different charts do not get the same reading, and the same person's money and
love sections speak about different years differently.

---

## 4. Unchanged from v1.2.0 / v1.1.0

v3 drives the reading for every visitor; **fail-soft** to the classic string
reading if the engine or composer fails to load or throws (verified). All TST
corrections, per-city timezones, unknown-time path, 162-city list, lazy load,
shareable links, social card, lucky-directions line — intact.

Flags: `?engine=classic` forces the old reading (instant rollback);
`?engine=v3` shows the dev panel. `CONFIG.SHEET_URL` byte-identical;
`WORKER_URL` still `""`. No new paid service, database, server, API or
framework. Static site. `bazi-engine.min.js` remains the sole pillar source.

## 5. Ceiling, restated

Still composition, not generation. The timeline reads as uncannily specific, but
it selects from written fragments — it can't reason about a chart it wasn't
pre-written for, and it can't verify its own astrology. **v3 remains
`UNVALIDATED`**; the timeline keys off its unproven signals, and no chart has
had practitioner review. The decade start-age limit is real and permanent until
the solar-term data is rebuilt to the hour (its own future project).

Per-chart *generated* prose — the Worker path, v3 handing a model a facts packet
— is the next ceiling, and costs money per reading.

## 6. Editing

The entire voice + timeline copy lives in `FRAG`, `YEAR`, `PAST_REFLECT`
and `DECADE` at the top of `engine-v3/reading-v2.browser.js`. Plain strings.
Rewrite freely; the composition and date logic never need to change.
