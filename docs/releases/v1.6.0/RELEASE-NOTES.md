# Release Notes — v1.6.0

The eight prose sections are now broken into paragraphs, grouped by the nature
of the statement rather than run together as one block.

---

## 1. On justified alignment — I'd advise against it

You asked whether justify would help readability. It would hurt, for three
reasons, and the last is specific to this site:

- **Browsers justify badly.** There's no automatic hyphenation, so the engine
  stretches word-spacing instead of breaking words. You get "rivers" — visible
  channels of white running down the paragraph.
- **It's worst in a narrow column.** Fewer words per line means fewer gaps to
  absorb the slack, so each gap grows. A 360px phone is the pathological case,
  and that's the primary reading surface here.
- **The body font is JetBrains Mono.** Monospace already has uniform character
  widths; stretched word-gaps on top of that read as a rendering fault rather
  than as typography.

Justified text is also measurably harder for dyslexic readers, because
irregular word spacing disrupts word-shape recognition.

Paragraphs are therefore **left-aligned**, and readability comes from the
paragraph breaks themselves plus slightly increased line-height (1.5 → 1.55)
and 11px of space between paragraphs (13px on desktop). The reasoning is in a
comment in the stylesheet so it doesn't get "fixed" later.

## 2. Paragraph structure

Each section now splits by kind of statement:

| Section | Paragraphs |
|---|---|
| **Who You Are** | core nature · **physical type** · **personality traits** · what past years shaped |
| **Your Fortune** | the shape of your luck · this year |
| **Career** | the work that suits you · the coming years · the decade ahead |
| **Love & Spouse** | how love arrives · who suits you · how you love · the marriage seat + a year |
| **Your People** | one paragraph |
| **Parents & Roots** | one paragraph |
| **Health** | the element and its area · your reserves |
| **What's Coming** | what's thin · a past anchor · next year · **one paragraph per notable year** · closing |

Physical type and personality traits are separate paragraphs, as you asked —
they're different kinds of claim and shouldn't share a block.

What's Coming can now run to eight paragraphs, but each is short and scannable.
Giving every flagged year its own paragraph turns a 600-character wall into a
year-by-year forecast, which is how an almanac would set it.

Sections with a single paragraph render as plain text with no wrapper, so
nothing gains pointless markup.

## 3. A duplicate this exposed

Splitting into paragraphs made an existing bug visible: **Who You Are and
What's Coming both narrated 2028 with the same flavour**, so the identical
sentence appeared twice in one reading.

Who You Are now uses two **past** years instead. That section is about
formation, so past anchors suit it better, and it leaves What's Coming as the
only section that forecasts.

Verified across 552 charts: **zero readings contain a repeated sentence.**

## 4. Safety note on the rendering

Paragraphs are built with `createElement` + `textContent`, never `innerHTML`.
The visitor's name is woven through this copy, and it must never be parsed as
markup. Verified: a name of `<img src=x onerror=...>` renders as literal text
and the container's `innerHTML` stays empty.

## 5. Unchanged

Solar terms to the minute, true element count, ten sections, four notable years,
rebuilt Love & Spouse, no engine jargon, back-link send-offs.

Verified across 552 charts: zero empty paragraphs, zero doom vocabulary, zero
engine jargon.

## 6. Editing

Paragraph grouping is the arrays returned by `compose()` in
`engine-v3/reading-v2.browser.js`. To merge two paragraphs, concatenate the two
variables; to split one, add an array element. Spacing is `.section .stext .para`
in `goh-pok-tong.html`.
