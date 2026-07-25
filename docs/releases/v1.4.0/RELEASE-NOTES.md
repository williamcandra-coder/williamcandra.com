# Release Notes — v1.4.0

Three changes: clearer wording, a fuller "Who You Are", and the reading split
into ten sections. The "Ask Uncle One More Thing" feature is removed.

---

## 1. Plainer wording

The v1.3.0 voice was trying to be poetic and landing as cryptic. Lines like
*"your problem isn't spine, it's waiting for a sign that isn't coming"* and
*"stillness feels like dying"* have been rewritten across the whole library.

The rule now: **say the thing, then the twist.** No riddles. Short sentences.
The bite comes from being specific, not from being obscure.

| Before | After |
|---|---|
| "Your problem isn't spine, it's waiting for a sign that isn't coming." | "Your real problem is waiting for certainty before you move." |
| "Born in the growing season, so stillness feels like dying." | "You were born in the growing season, so sitting still makes you restless." |
| "Roots shallow right now — you bend more than you admit, and hate that you do." | "Right now your support is thin. You bend more than you admit, and it annoys you that you do." |

## 2. "Who You Are" now covers physique and traits

Two additions, both standard Bazi:

- **Physique tendency** by Day Master element — Wood tall and lean, Earth solid
  and grounded, Water softer features, and so on.
- **Trait cluster** by Day Master — a plain list, good and bad together:
  *"Traits: decisive, blunt, courageous, loyal, leaves damage behind while
  calling it honesty."*

Physique is written as what the **type tends toward**, never as a claim about
the reader's actual body. The chart doesn't know anyone's height, and a tall
reader of a "short" element would rightly call it wrong. Framed as a tendency it
still lands; framed as fact it breaks trust.

## 3. Ten sections

Was six. Now ten, ordered to move from hook, to identity, then outward from self
to world, ending on time:

1. Uncle's Opening Remark
2. **Who You Are** — nature, physique, traits
3. **Your Fortune** — overall luck shape *(dated)*
4. **Career** *(dated + decade marker)*
5. **Love & Spouse** *(dated)*
6. **Your People** — siblings and friends, merged
7. **Parents & Roots**
8. **Health**
9. **What's Coming** *(dated)*
10. Uncle's Parting Shot

Each has a real basis in the chart, not padding: Fortune reads strength plus the
useful element; Your People reads the Companion god; Parents reads the Resource
god and the early pillars; Health reads the thinnest element.

**Siblings and Friends are merged** into "Your People" — both key off the same
Companion god, so separate sections would have said near-identical things and
the reader would notice.

**Dates only where they matter** — Fortune, Career, Love, What's Coming. Dates in
Siblings or Parents would feel forced. The years are also spread so no two
sections anchor on the same year.

### Health is deliberately the gentlest section

It reads the thinnest element and names the traditional association — Wood and
the liver, Water and the kidneys — as **areas to be mindful of**, with practical
habits. It never diagnoses, never names a disease, never tells anyone they will
fall ill. This engine is `UNVALIDATED`, and health copy aimed at a real person is
held to the strictest standard in the file.

## 4. Ask Uncle One More Thing — removed

The panel, input, button, loading state, answer area, error line, coming-soon
note, associated CSS, and the click handler are all gone. `CONFIG.WORKER_URL` is
retained as an unused key with a comment so the config shape is unchanged for
any future Worker-backed feature — nothing reads it at runtime.

---

## 5. Unchanged

v3 drives the reading for every visitor, with **fail-soft** to the classic
string reading if the engine or composer fails to load. When that happens the
four new sections hide themselves rather than showing empty headers — verified.

All prior fixes intact: TST day-rollover and per-city timezones, unknown-birth-
time path, 162-city list, lazy engine load, shareable links, social card,
lucky-directions line, `?engine=classic` rollback flag, `?engine=v3` dev panel.

`CONFIG.SHEET_URL` byte-identical. Static site, no build step, no new service.
`bazi-engine.min.js` remains the sole source of birth date → Four Pillars.

## 6. Still true

Composition, not generation — it selects from written fragments and can't reason
about a chart it wasn't pre-written for. **v3 remains `UNVALIDATED`.** The
decade marker stays soft-timed ("somewhere in your forties") because luck-pillar
start age needs solar terms to the hour and the engine has them to the day.

## 7. Editing

All copy lives in `FRAG` / `YEAR` / `PAST_REFLECT` / `DECADE` at the top of
`engine-v3/reading-v2.browser.js`. Plain strings. The new tables are `physique`,
`traits`, `fortuneCore`, `fortuneUseful`, `people`, `parents`, `health`.
