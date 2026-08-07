# Goh Dip Tong — Stage 3 Handoff (mobile-first UI)

**Stage:** 3 — the front end
**Repository:** `williamcandra-coder/williamcandra.com`
**Page:** `goh-dip-tong.html`

## Status: `UI_COMPLETE_NO_REAL_ISSUER_RENDERED`

The page is built and renders all eight research sections and all six UI
states. **It has never rendered a real company**, because Stage 2 publishes no
snapshot for one. Everything visible today comes from the six engine UI-state
fixtures, and every one of them carries the fixture warning.

The page performs **no valuation of its own**. Every figure it shows is a
string taken from a snapshot field and tagged with the record ID it came from.

---

## 1. Files

| Path | Role |
|---|---|
| `goh-dip-tong.html` | Semantic skeleton and the three page states. Carries no data. |
| `assets/goh-dip-tong.css` | All styling. Mobile-first from 320px. |
| `assets/goh-dip-tong.js` | Loading, validation, view models, rendering, accordions. |
| `assets/goh-dip-tong-icon.svg` | The canonical icon as a standalone file. |
| `tests/goh-dip-tong-ui.test.js` | `node --test tests/` — zero dependencies. |

### Why this page is split when every other page is one file

`index.html`, `goh-pok-tong.html`, `rage-wings.html`, `snake.html` and
`breakout.html` are each a single self-contained file with inline `<style>` and
`<script>`. This page is not, for two reasons:

1. **The tests need the logic as a module.** Proving "the browser performs no
   valuation arithmetic" and "Uncle and Analyst resolve the same record IDs"
   means running the validation and view-model functions directly. A module
   that `require()` returns is testable in plain Node; an inline script inside a
   1,600-line HTML file is not.
2. **Volume.** The logic here is roughly ten times the Goh Pok Tong form. A
   single file would be ~2,300 lines with three languages interleaved.

Nothing else changes: no build step, no bundler, no package manager. Three
static files that GitHub Pages serves directly, exactly like the rest of the
site.

---

## 2. The canonical icon — **exact Stage 4 markup**

One design, two treatments, **identical rect data**. Stage 4 must reuse this
markup verbatim rather than redrawing it. `tests/goh-dip-tong-ui.test.js`
compares the icon file, the in-page menu icon, the in-page header character and
the block below, and fails if any of them drift apart.

### 2a. Homepage menu icon (for `index.html`, Stage 4)

Drop this straight into the `.mlist` row. It matches the dimensions and
conventions of the existing menu icons — `viewBox="0 0 16 16"`,
`shape-rendering="crispEdges"`, `class="ic"`, no external dependency.

```html
<a href="goh-dip-tong.html" class="special" data-cmd="$ ./goh-dip-tong — the numbers, uncle">
  <svg class="ic" viewBox="0 0 16 16" shape-rendering="crispEdges" aria-hidden="true" focusable="false">
    <rect x="4" y="2" width="8" height="1" fill="#3a3440"/>
    <rect x="3" y="3" width="1" height="4" fill="#3a3440"/>
    <rect x="12" y="3" width="1" height="4" fill="#3a3440"/>
    <rect x="4" y="3" width="8" height="6" fill="#e8b98a"/>
    <rect x="4" y="3" width="8" height="1" fill="#3a3440"/>
    <rect x="9" y="3" width="2" height="1" fill="#4a4550"/>
    <rect x="4" y="6" width="3" height="1" fill="#3a3440"/>
    <rect x="9" y="6" width="3" height="1" fill="#3a3440"/>
    <rect x="4" y="7" width="3" height="2" fill="#f2ede3"/>
    <rect x="9" y="7" width="3" height="2" fill="#f2ede3"/>
    <rect x="7" y="7" width="2" height="1" fill="#3a3440"/>
    <rect x="5" y="8" width="1" height="1" fill="#141414"/>
    <rect x="10" y="8" width="1" height="1" fill="#141414"/>
    <rect x="3" y="9" width="10" height="1" fill="#f2ede3"/>
    <rect x="3" y="10" width="10" height="3" fill="#2f3550"/>
    <rect x="6" y="10" width="1" height="1" fill="#f2ede3"/>
    <rect x="9" y="10" width="1" height="1" fill="#f2ede3"/>
    <rect x="7" y="10" width="2" height="3" fill="#5f9a8a"/>
  </svg>
  <span class="label">GOH DIP TONG</span>
</a>
```

**Stage 3 did not modify `index.html`.** The block above is the handoff; adding
it is Stage 4's decision.

### 2b. Larger character treatment (page header)

The same 18 rects at 56px with the identity glow. Not a second drawing — the
test asserts the rect lists are `deepStrictEqual`.

```html
<svg class="uncle-head" viewBox="0 0 16 16" width="56" height="56"
     shape-rendering="crispEdges" role="img" aria-labelledby="gdt-uncle-title">
  <title id="gdt-uncle-title">Goh Dip Tong, the businessman uncle</title>
  <!-- …the identical 18 rects… -->
</svg>
```

```css
.uncle-head{image-rendering:pixelated;filter:drop-shadow(0 0 10px var(--accent-glow));}
```

### 2c. The design

Goh Pok Tong is the fortune-teller: grey temple tufts, bare eyes, green collar,
maroon robe. Goh Dip Tong is his brother who took a job.

**Same** face block (`8×6` at `4,3`), same brow row at `y=6`, same eye row at
`y=7`, same collar at `y=9`, same body band at `y=10..12`. Keeping the skeleton
identical is what makes them read as one family at 16px.

**Different** in exactly the ways a job changes a person: combed dark hair with
a side part instead of grey tufts, rectangular spectacles with a bridge instead
of bare eyes, a white shirt collar instead of green, a navy suit instead of a
maroon robe, and a terminal-green tie where the robe had a vest panel.

Every colour is already in the site palette: `#3a3440`, `#4a4550`, `#e8b98a`,
`#f2ede3`, `#141414` are shared with the existing icons; `#2f3550` is the suit
navy and `#5f9a8a` is the Goh Dip Tong green, which is the same green
`snake.html` uses for its snake.

---

## 3. What the page reads

| Purpose | Path |
|---|---|
| IDX30 picker | `config/goh-dip-tong/idx30.current.json` |
| Research snapshot | `data/goh-dip-tong/research-snapshots/current/<TICKER>.json` |
| Demonstration fixtures | `engine/goh_dip_tong/fixtures/ui_states/<STATE>.json` |

**No ticker list is hard-coded anywhere.** The picker renders whatever the
config contains, filtered to `active === true` and sorted by ticker. When Stage
1 changes the config, the page changes with it on the next load. When the config
cannot be read, the page shows `CONFIG UNAVAILABLE` and **does not** fall back
to a built-in list — a fallback would show companies this build cannot verify.

`data/goh-dip-tong/_private/` is refused by the fetch wrapper itself, so no
future caller can reach rights-restricted output by typing a path.

---

## 4. Validation before rendering

Nothing reaches the screen until it passes. The snapshot check covers
`schemaVersion` (major must be `1`), ticker consistency against what was asked
for, `mode`, `uiState`, `researchStatus`, valuation status — plus, for a
refusal, that it carries a reason, a note, failed gates and missing inputs —
and the presence of `freshness`, `quality`, `evidence`, `modelAudit`
(`formulaRegistryHash` and `inputProvenance`) and `disclaimers`.

A failure shows `RESEARCH SNAPSHOT UNAVAILABLE` with the reason, and leaves the
picker in place so another target can be chosen.

---

## 5. The six UI states, and what each renders

| `uiState` | Headline | Renders |
|---|---|---|
| `FULL_RESEARCH` | base value per share | thesis, counter-thesis, bear/base/bull, primary method, cross-check notes, catalysts, risks, breakers, evidence, full analyst detail |
| `MODEL_UNDER_VALIDATION` | `MODEL UNDER VALIDATION` | available evidence, the methodology gate that failed |
| `PARTIAL` | `PARTIAL RESEARCH` | missing inputs and failed gates, listed |
| `ONBOARDING` | `COVERAGE ONBOARDING` | identity and facts; no model, so no valuation shape |
| `STALE` | `STALE RESEARCH` | the previous snapshot with original timestamps; every value carries a `STALE` mark |
| `SUSPENDED` | `MODEL SUSPENDED` | coverage status and the refusal reason; no target value |

Two fail-soft states sit outside the enum: `CONFIG UNAVAILABLE` and
`RESEARCH SNAPSHOT UNAVAILABLE`.

**A refusal never looks like a valuation.** Different border colour, no large
figure, the words `VALUATION NOT PUBLISHED` in the pixel face where a number
would otherwise be, and the reason, gates, missing inputs and note beneath it.

---

## 6. Uncle View and Analyst View

Uncle View **is** the page. There is no Analyst page. Each of the eight
sections carries its Analyst drawer inline, directly beneath the Uncle
conclusion it belongs to.

| | |
|---|---|
| Default state | collapsed, `aria-expanded="false"`, panel `hidden` |
| Markup | `<button aria-expanded aria-controls>` + `<div role="region" aria-labelledby>` |
| Bulk controls | `EXPAND ALL ANALYST DETAIL` / `COLLAPSE ALL` |
| Scroll | preserved by construction — the panel opens below the button and nothing above it moves. There is no `scrollIntoView` |
| Keyboard | native button semantics; Enter and Space both work |
| Content | built lazily on first open |

**Numbers are never duplicated.** Both views resolve through one record index
built from the snapshot's own `analystView.items`. Every rendered figure carries
`data-record-ref` and `data-raw`, and a browser test asserts that the same ref
never renders two different values, and that every `data-raw` is
byte-identical to the snapshot. A ref with no matching record renders
`DATA REFERENCE UNAVAILABLE` — it is never recomputed.

---

## 7. Missing price, and missing anything

`marketImplied.available` is `false` in every snapshot, so the price reads
**`NOT PUBLISHED`**, with the engine's own reason and the provider's rights
status beside it.

Never rendered: `Rp 0`, `0`, `N/A` as a numeric substitute, or a placeholder
price. `displayValue()` returns `null` for `null`, `undefined`, `''`, `NaN` and
`Infinity`, and the renderer turns that into the words. A genuine zero still
renders as `0` — the rule is that absence is not zero, not that zero is
absence.

One consequence worth stating: `quality.completeness` is shown as its raw
decimal (`0.1176`) under the label `COMPLETENESS (0–1)` rather than as
`11.76%`. Converting it would be arithmetic on a published figure, and the
metric count beside it says the same thing without inventing anything.

---

## 8. Mobile-first

Designed at 320px, enhanced at 380px, 560px and 820px.

- One column by default; `overflow-x:hidden` on `body`
- Tables scroll inside `.tablewrap` with a sticky first column
- Driver equations stack; revision cards stack
- Sensitivity is a compact 3×3 (three scenarios × three methods) with detail on demand
- Search and CTA are full width; every control clears 44px
- Evidence renders 25 rows, then `SHOW ALL …` on request
- No hover-only information anywhere

Verified in headless Chromium at real viewport widths: at both 320px and 390px
`documentElement.scrollWidth` equals `clientWidth`, and no element's right edge
passes the viewport.

---

## 9. Accessibility

Semantic landmarks, one `h1`, no heading-level jumps, `<label for>` on the
search input with `aria-describedby` for the arrow-key hint, `role="listbox"` /
`role="option"` with `aria-selected` on the picker, roving arrow-key navigation,
`aria-live` status regions for result counts and page changes, `role="alert"` on
the fixture banner, `:focus-visible` outlines that are never removed,
`aria-hidden` on decorative SVG and `role="img"` + `<title>` on the character.

Status is never colour alone: every coloured chip carries its word, and the
selected row's marker renders the text `SELECTED`.

`prefers-reduced-motion: reduce` stops the CRT flicker, the logotype pulse, the
cursor blink and the caret rotation. Nothing that animates carries meaning.

---

## 10. Security

- No `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`, `eval` or `new Function`
- Text reaches the DOM only through `textContent`; children clear via `replaceChildren()`
- Evidence becomes a link **only** when the string parses as `https:`; everything else renders as inert text
- Links carry `rel="noopener noreferrer"`
- `_private` paths are refused inside the fetch wrapper
- No analytics, no tracking, no secrets, no external images, no CDN

A browser test feeds a snapshot containing `<img onerror>`, a `javascript:`
sourceRef, an inline `<script>` in a note and markup in the company name, then
asserts nothing executed, no image element exists, and the markup is visible as
literal text.

---

## 11. Tests

`node --test tests/` — 44 required proofs across three layers: static source
checks, pure logic against the module, and real headless-Chromium rendering at
320px and 390px. Zero dependencies: the repository has no `package.json`, so the
suite uses Node's built-in runner and the Chromium binary Playwright already
installs. If Chromium is absent the browser layer skips **loudly**.

The suite is not wired into `gdt-data-quality.yml`. Stage 3 added no workflow.

---

## 12. Known limitations

1. **No real company has ever been rendered.** Stage 2 publishes no snapshot.
2. **`WHAT CHANGED` has nothing to show.** A bridge reconciles two snapshots and
   only one exists; the section says so rather than inventing a revision.
3. **No price anywhere**, so no upside, no premium to market, no market-implied
   case. This is a rights outcome.
4. **The fixture selector ships on the page.** It is clearly labelled and its
   tickers are absent from the picker, but before this page is presented as
   finished, it should move behind a query flag.
5. **Google Fonts is the one external request**, matching `index.html` and
   `goh-pok-tong.html`. Local fallbacks are declared.
6. **No offline support**, no service worker, no caching beyond the browser's.
7. **`FULL_RESEARCH.json` is ~770 KB.** It loads in one request. If that becomes
   a problem, fetch the `current/` pointer first and the snapshot on demand.

---

## 13. What Stage 4 inherits

- The exact menu-icon markup in §2a, ready to paste into `index.html`
- A page that already renders every state Stage 2 can produce
- The record-ref discipline: if Stage 4 adds a figure, it must come from a
  snapshot record and carry `data-record-ref` and `data-raw`, or the tests fail
- `index.html`, `goh-pok-tong.html`, `_config.yml` and `CNAME` untouched
