# Release Notes — v1.6.1

You were right. I measured it, and the numbers were bad.

---

## What I measured

For every paragraph in the reading, I calculated **what fraction of readers see
the single most common version**. Across 2,400 charts:

| Paragraph | Before | After |
|---|---|---|
| Health — your reserves | **51.0%** | 14.1% |
| Your People | 26.7% | 12.9% |
| Health — the body | 25.6% | 13.0% |
| What's Coming — what's thin | 25.6% | 9.6% |
| Who You Are — physical type | 20.4% | 7.8% |
| Career — the work | 19.0% | 9.3% |
| Parents & Roots | 13.8% | 6.4% |
| Your Fortune | 13.6% | 4.3% |
| Love — how you love | 8.7% | 3.2% |

Worst case went from **51% to 14.1%**. Every line you flagged was in the top
half of that table.

## Three root causes

### 1. The strength band was skewed, again

v3 classifies anything under 46 as "weak" — but the real median is 45, so
**51% of all charts came out "weak"**. That's the model's weighting showing
through, not the charts speaking. It's the same bug I found in the spouse star
last release, in a different table.

Copy now bands on the measured tertiles of the diagnostic score (39 and 52).
Result: **36.5% strong / 32.8% weak / 30.7% balanced.** v3's own label is
untouched for the dev panel.

That one fix explains most of the improvement, because four sections key off
strength.

### 2. One signal was narrating three sections

The chart's *thinnest element* drove Your Fortune, Health, **and** What's
Coming. So a Fire-thin chart got Fire-flavoured advice three times in one
reading, and every other Fire-thin person got the same three.

Health now keys off the **dominant** element instead — excess is as legitimate
a health story in the tradition as deficiency, and it decouples the sections.
Your line *"Your chart runs light on Fire…"* is now *"You're Fire-heavy…"* and
no longer echoes What's Coming.

### 3. Most tables had exactly one phrasing per key

`loveApproach` was the worst: a straight yin/yang coin flip, so **half of
everyone** read *"You tend to wait to be chosen…"* — exactly the line you
quoted.

Every low-variance table now carries **three phrasings**, each picked by a
chart feature chosen to vary *independently* of whatever selected the bucket —
day branch, month branch, hour branch, year branch. Two people who share a
bucket rarely share the sentence.

Tables expanded: `physique`, `strength`, `fortuneCore`, `fortuneUseful`,
`careerCore`, `careerMod`, `loveApproach`, `spouseSeat`, `people`, `peopleMod`,
`parents`, `health`, `healthStrength`, `luckCore`.

---

## Your other question: is it accurate and personalised, or generic?

Straight answer, in three parts.

**Personalised: yes, structurally — and now measurably better distributed.**
Every fragment is selected by a real chart signal. But it is **selection from
written text, not generation**. It cannot say anything I did not write in
advance. At 14% worst-case overlap it will feel individual; it is not bespoke.

**The chart itself: accurate, and newly so.** v1.5.0 put solar terms on real
astronomy — validated against published ephemeris to within 9 minutes. The
pillars are right, including for boundary births the old table got wrong.

**The interpretation: unvalidated, and I won't claim otherwise.** No chart has
been checked against a practitioner. The rules it follows are standard, but
whether its conclusions are *correct* is untested. It remains `UNVALIDATED`,
and the skews I keep finding — spouse star, strength band — are evidence that
the underlying model has more of them.

The honest description is a **well-built, unvalidated reading engine** — not an
accurate one. Making it accurate needs reference charts, which is the one part
I can't produce.

---

## Unchanged

Paragraph structure, solar terms, true element count, ten sections, four
notable years, back-link send-offs, no engine jargon.

Verified across 552 charts: zero empty paragraphs, zero doom vocabulary, zero
engine jargon, **zero readings with a repeated sentence**.
