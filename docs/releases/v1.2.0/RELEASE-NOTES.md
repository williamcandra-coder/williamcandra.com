# Release Notes — v1.2.0

**The headline: the reading is now composed, not selected, and the v3 engine
drives it for every visitor.**

Previous versions picked one pre-written string per section, keyed by one
signal — so everyone with the same Day Master got nearly the same reading, and
the whole thing topped out at ~10 real variants. v1.2.0 replaces that with a
**dynamic composer**: each section is assembled at runtime from fragments chosen
by *different* signals the v3 engine already produces.

---

## 1. Dynamic composed reading (the big change)

Each section is now built from several clauses, each keyed by a different fact:

```
personality = Day Master core
            + strength clause (rooted / shallow / balanced)
            + season clause (what the birth season did to you)
            + drive clause (dominant Ten God group)

career      = drive core + strength modifier
love        = yin/yang base + drive lens + [day-branch clash, if present]
luck        = weakest element + timing + [hour-unknown note, if applicable]
opener/closer = seed-picked, name woven in
```

**Measured over 1,416 charts:** 247 distinct personality paragraphs, and a
combined reading space across the self/career/love/luck axes of **741,000**.
Two people with different charts do not get the same reading.

### Position now means something

The four pillars are treated as four life domains — year (roots/public face),
month (parents/career), **day branch (the marriage seat)**, hour (children/late
life). A branch clash is no longer trivia: when the sharpest clash lands on the
day branch, the love section says so. That conditional fires on ~19% of charts
and **only** when a real day-branch clash exists (verified: 321/321 correct).

### Voice

Sharper. It names contradictions and calls out self-sabotage. Held hard line, on
purpose: **no deterministic doom** — nothing about dying, marriage ending,
illness or ruin. The uncle is brutal about who you *are*, never fatalistic about
what will destroy you. A vocabulary scan across 1,416 charts confirms zero
doom-language in any section.

### Sample (1990-05-15, "Wira"), self section

> You're Yang Metal — a blade, not a decoration. Direct, tempered, made to cut through nonsense. You've hurt people by 'just being honest' and you'd do it again. You're evenly built — enough spine to hold, enough give to bend. Your problem isn't strength, it's that you keep waiting for a clearer sign before you commit. It's not coming. Born in the hot season, so you run warm: fast to light up, fast to burn out, then confused why you're tired. Your chart is crowded with your own kind — lots of self, lots of will. You trust your own hands most. That's strength and that's exactly why you struggle to let anyone carry a corner....

Every clause traces to a fact the engine computed: Yang Metal Day Master,
balanced strength, summer season, Companion drive. Nothing invented.

---

## 2. v3 is now the live engine

Until now v3 ran only under `?engine=v3`. It now drives the reading for **every
visitor**. Two classic scripts load (both work over file:// and https, no
bundler):

- `engine-v3/engine-v3.browser.js` → chart analysis
- `engine-v3/reading-v2.browser.js` → the composer

Both are warmed on idle after first paint, so the first consult is instant.

### Fail-soft

If either file fails to load, or v3 throws for any chart, the reading silently
falls back to the built-in string engine. **A visitor never sees a blank screen
or an error in place of a reading.** Verified: engine-404, composer-404, and
compose-throw all fall back cleanly with no alert.

The classic fallback reading is **byte-identical** to v1.1.0 — confirmed across
264 inputs, 0 differences.

### Flags

- `?engine=classic` — force the old string reading (comparison / instant rollback)
- `?engine=v3` — still shows the dev evidence panel, now with a line stating
  which engine composed the visitor's prose

---

## 3. Unchanged from v1.1.0

All v1.1.0 fixes remain: True Solar Time day-rollover correction, per-city
timezones, name woven into the reading, unknown-birth-time path, 162-city list
with autocomplete, lazy engine load, shareable links, social card, gender
driving the lucky-directions line, legacy dead-code removed.

`CONFIG.SHEET_URL` byte-identical. `CONFIG.WORKER_URL` still `""`; ask-more
disabled with the coming-soon note. No new paid service, database, server, API
or framework. Still a static site. `bazi-engine.min.js` remains the sole source
of birth date → Four Pillars.

---

## 4. The honest ceiling

This is composition, not generation. It tops out at how good the ~80 fragments
are — it cannot reason about a chart it wasn't pre-written for. It reads as
"uncannily good for a free arcade page," not as a human master's bespoke prose.
Going past that needs per-chart generated text (the Worker path), where v3 hands
a model a facts packet and the model writes constrained to those facts. That
costs money per reading and is a future release.

**v3 remains `UNVALIDATED`.** The composition quality does not depend on v3's
strength score being astrologically correct — the prose reads well regardless —
but the signals it keys off are unproven, no chart has had practitioner review,
and the fixture corpus is still empty. The `UNVALIDATED` note stays in the dev
panel; it is not shown to visitors, by your decision.

---

## 5. Editing the voice

The entire voice lives in one object — `FRAG` at the top of
`engine-v3/reading-v2.browser.js`. Every clause is a plain string. Rewrite
fragments freely; the composition logic never needs to change. This is where you
put the reading in your own words — expect to rewrite a chunk of it.
