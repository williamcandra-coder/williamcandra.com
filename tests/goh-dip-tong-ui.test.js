/* ==========================================================================
   GOH DIP TONG — Stage 3 UI tests
   ==========================================================================

   Run:  node --test tests/

   ZERO DEPENDENCIES, ON PURPOSE
   -----------------------------
   This repository has no package.json, no node_modules and no npm step. Every
   page ships as static files. A test suite that needed a package manager would
   be a test suite nobody could run, so this one uses only what is already
   here: Node's built-in test runner for the harness, and the Chromium binary
   Playwright installs for anything that needs real layout.

   THREE LAYERS
   ------------
   1. Static source checks. Assertions about the files as text — no hard-coded
      ticker list, no innerHTML, no external image URLs, the icon markup.
   2. Pure logic checks. assets/goh-dip-tong.js exports its validation and
      view-model helpers, so they run in plain Node with no DOM at all.
   3. Real browser checks. goh-dip-tong.html is loaded in headless Chromium at
      an actual viewport width with fetch stubbed to serve fixtures. Layout
      overflow, ARIA state after a real click, and "did this number come from
      the snapshot" are only true if a browser says so.

   If Chromium is unavailable the browser layer skips loudly rather than
   passing silently — a green suite that tested nothing is worse than a red one.
   ========================================================================== */

'use strict';

const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFileSync } = require('node:child_process');

const ROOT = path.resolve(__dirname, '..');
const read = (p) => fs.readFileSync(path.join(ROOT, p), 'utf8');
const readJson = (p) => JSON.parse(read(p));

const HTML = read('goh-dip-tong.html');
const CSS = read('assets/goh-dip-tong.css');
const JS = read('assets/goh-dip-tong.js');
const ICON = read('assets/goh-dip-tong-icon.svg');

const GDT = require(path.join(ROOT, 'assets/goh-dip-tong.js'));

const UNIVERSE = readJson('config/goh-dip-tong/idx30.current.json');
const FIXTURE_DIR = 'engine/goh_dip_tong/fixtures/ui_states';
const FIXTURE_STATES = ['FULL_RESEARCH', 'MODEL_UNDER_VALIDATION', 'ONBOARDING',
                        'STALE', 'SUSPENDED', 'PARTIAL'];
const fixture = (state) => readJson(`${FIXTURE_DIR}/${state}.json`);

/* ==========================================================================
   1. STATIC SOURCE CHECKS
   ========================================================================== */

test('1 — the picker loads idx30.current.json and nothing else', () => {
  assert.match(JS, /config\/goh-dip-tong\/idx30\.current\.json/);
  assert.strictEqual(GDT.UNIVERSE_PATH, 'config/goh-dip-tong/idx30.current.json');
});

test('2 — no hard-coded IDX30 ticker array exists in any shipped file', () => {
  const real = UNIVERSE.constituents.map((c) => c.ticker);
  for (const source of [HTML, JS, CSS]) {
    /* A list of real tickers would show up as several of them close together.
       One appearing in placeholder copy is fine; three in a row is a list. */
    const hits = real.filter((t) => source.includes(t));
    assert.ok(hits.length <= 1,
      `expected at most one incidental ticker mention, found: ${hits.join(', ')}`);
  }
  assert.ok(!/\[\s*(['"])[A-Z]{4}\1\s*,\s*(['"])[A-Z]{4}\2/.test(JS),
    'JS contains an array literal of four-letter tickers');
});

test('25 — no innerHTML anywhere in the shipped JavaScript', () => {
  assert.ok(!/\.innerHTML/.test(JS), 'assets/goh-dip-tong.js uses innerHTML');
  assert.ok(!/\.outerHTML/.test(JS), 'assets/goh-dip-tong.js uses outerHTML');
  assert.ok(!/insertAdjacentHTML/.test(JS));
  assert.ok(!/document\.write/.test(JS));
  assert.ok(!/\bnew Function\b|\beval\(/.test(JS));
  /* and the page's own bootstrap is equally clean */
  assert.ok(!/\.innerHTML/.test(HTML));
});

test('26 — only https evidence URLs are treated as links', () => {
  const unsafe = ['javascript:alert(1)', 'data:text/html,<script>x</script>',
                  'file:///etc/passwd', 'http://example.com/doc.pdf',
                  '//example.com/doc', 'vbscript:x', ''];
  for (const u of unsafe) assert.strictEqual(GDT.isSafeHttpUrl(u), false, u);
  assert.strictEqual(GDT.isSafeHttpUrl('https://idx.co.id/filing/1'), true);
  assert.strictEqual(GDT.isSafeHttpUrl(null), false);
  assert.strictEqual(GDT.isSafeHttpUrl(42), false);
});

test('27 — the page cannot fetch a _private path', async () => {
  assert.strictEqual(GDT.isPermittedPath('data/goh-dip-tong/_private/prices.json'), false);
  assert.strictEqual(GDT.isPermittedPath('data/goh-dip-tong/research-snapshots/current/BBCA.json'), true);
  assert.ok(!/_private/.test(HTML.replace(/FORBIDDEN_PATH_SEGMENT/g, '')),
    'the HTML references a private path');

  /* and the guard is wired into the fetch wrapper, not merely exported */
  let asked = null;
  const app = GDT.create({
    document: stubDocument(),
    fetchImpl: (url) => { asked = url; return Promise.resolve({ ok: true, json: () => ({}) }); }
  });
  await assert.rejects(() => app.getJson('data/goh-dip-tong/_private/x.json'), /refused path/);
  assert.strictEqual(asked, null, 'a refused path still reached the network');
});

test('28-31 — the 16x16 icon is local, inline, and drawn on the documented grid', () => {
  assert.ok(fs.existsSync(path.join(ROOT, 'assets/goh-dip-tong-icon.svg')));
  assert.match(ICON, /viewBox="0 0 16 16"/);
  assert.match(ICON, /shape-rendering="crispEdges"/);
  assert.ok(!/https?:\/\//.test(ICON.replace(/xmlns="[^"]*"/g, '')),
    'the icon references an external URL');
  assert.ok(!/xlink:href|<image|url\(/.test(ICON), 'the icon embeds an external asset');
  assert.ok(!/base64/.test(ICON));

  /* the menu treatment inside the page */
  const menuIcon = HTML.match(/<svg class="ic"[\s\S]*?<\/svg>/);
  assert.ok(menuIcon, 'no class="ic" icon in the page');
  assert.match(menuIcon[0], /viewBox="0 0 16 16"/);
  assert.match(menuIcon[0], /shape-rendering="crispEdges"/);
  assert.ok(!/https?:\/\//.test(menuIcon[0]));
});

test('32 — every icon treatment uses the identical canonical rect set', () => {
  const rects = (s) => (s.match(/<rect[^>]*\/>/g) || [])
    .map((r) => r.replace(/\s+/g, ' ').trim());

  const canonical = rects(ICON);
  assert.strictEqual(canonical.length, 18, 'canonical icon should be 18 rects');

  const menu = HTML.match(/<svg class="ic"[\s\S]*?<\/svg>/)[0];
  const header = HTML.match(/<svg class="uncle-head"[\s\S]*?<\/svg>/)[0];

  assert.deepStrictEqual(rects(menu), canonical,
    'the menu icon has drifted from assets/goh-dip-tong-icon.svg');
  assert.deepStrictEqual(rects(header), canonical,
    'the header character has drifted from the menu icon — it is a second character');

  /* and the handoff documents exactly this markup */
  const handoff = read('docs/goh-dip-tong/HANDOFF_STAGE_3.md');
  for (const rect of canonical) {
    assert.ok(handoff.includes(rect), `HANDOFF_STAGE_3.md is missing rect: ${rect}`);
  }
});

test('24 — the browser performs no arithmetic on a published value', () => {
  /* Financial arithmetic in a renderer is the defect this whole page is built
     to avoid, so it is checked as a property of the source rather than of one
     rendered example. Index arithmetic (at + 1) is permitted; anything touching
     a value-bearing identifier is not. */
  const offenders = [];
  /* Strings are stripped as well as comments: a CSS class called
     "verdict-value" is not a subtraction, and neither is a label. */
  stripStrings(stripComments(JS)).split('\n').forEach((code, i) => {
    if (code.trim() === '') return;
    if (/[Vv]alue\w*\s*[-*/]\s*\w/.test(code)) offenders.push(`${i + 1}: ${code.trim()}`);
    if (/\w\s*[-*/]\s*\w*[Vv]alue\w*/.test(code)) offenders.push(`${i + 1}: ${code.trim()}`);
    if (/\*\*/.test(code)) offenders.push(`${i + 1}: exponent — ${code.trim()}`);
    if (/Math\.(pow|round|floor|ceil|abs)\s*\(/.test(code)) offenders.push(`${i + 1}: ${code.trim()}`);
  });
  assert.deepStrictEqual(offenders, []);

  /* displayValue is a pass-through, not a converter */
  assert.strictEqual(GDT.displayValue(2094.6279653632146), '2,094.628');
  assert.strictEqual(GDT.displayValue(0), '0');
  assert.strictEqual(GDT.displayValue(0.1176), '0.1176');
  assert.strictEqual(GDT.displayValue(null), null);
});

test('38 — BACK TO ARCADE points at the existing homepage', () => {
  const back = HTML.match(/<a href="([^"]+)" class="back-link"[^>]*>([^<]*)</);
  assert.ok(back, 'no back link found');
  assert.strictEqual(back[1], 'index.html');
  assert.strictEqual(back[2].trim(), 'BACK TO ARCADE');
  assert.ok(fs.existsSync(path.join(ROOT, 'index.html')));
});

test('no external images, icon fonts or frameworks are referenced', () => {
  for (const [name, src] of [['html', HTML], ['js', JS]]) {
    assert.ok(!/<img\b/i.test(src), `${name} uses an <img> tag`);
    assert.ok(!/base64/i.test(src), `${name} embeds a base64 payload`);
    assert.ok(!/cdn\.|unpkg|jsdelivr|cdnjs/i.test(src), `${name} pulls from a CDN`);
  }
  /* The only permitted external request is the webfont the rest of the site
     already uses; it is a font, not an image or a framework.
     The SVG XML namespace is not a request — it is an identifier the parser
     compares as a string and never resolves — and it appears in the inline
     data-URI cursors that index.html and goh-pok-tong.html already use. */
  const external = (CSS.match(/https?:\/\/[^)'"\s]+/g) || [])
    .filter((u) => u !== 'http://www.w3.org/2000/svg');
  assert.deepStrictEqual(external.filter((u) => !u.startsWith('https://fonts.googleapis.com/')), []);
});

test('39-41 — protected files are untouched by this branch', () => {
  const { execFileSync: run } = require('node:child_process');
  const changed = run('git', ['diff', '--name-only', 'origin/main', '--',
                              'index.html', 'goh-pok-tong.html', '_config.yml', 'CNAME'],
                      { cwd: ROOT, encoding: 'utf8' }).trim();
  assert.strictEqual(changed, '', `protected files changed: ${changed}`);
});

/* ==========================================================================
   2. PURE LOGIC CHECKS
   ========================================================================== */

test('3 — only active constituents render, in a deterministic order', () => {
  const doc = JSON.parse(JSON.stringify(UNIVERSE));
  doc.constituents[0].active = false;
  const dropped = doc.constituents[0].ticker;
  const list = GDT.activeConstituents(doc);
  assert.ok(!list.some((c) => c.ticker === dropped));
  assert.strictEqual(list.length, doc.constituents.length - 1);

  const tickers = list.map((c) => c.ticker);
  assert.deepStrictEqual(tickers, tickers.slice().sort(), 'order is not deterministic');
  assert.deepStrictEqual(GDT.activeConstituents(doc).map((c) => c.ticker), tickers);
});

test('4 — search matches ticker', () => {
  const list = GDT.activeConstituents(UNIVERSE);
  const target = list[0];
  const hits = GDT.searchConstituents(list, target.ticker.toLowerCase());
  assert.ok(hits.some((c) => c.ticker === target.ticker));
  assert.ok(hits.length < list.length);
});

test('5 — search matches company name', () => {
  const list = GDT.activeConstituents(UNIVERSE);
  const target = list.find((c) => c.name.includes(' '));
  const word = target.name.split(' ')[0];
  const hits = GDT.searchConstituents(list, word.toUpperCase());
  assert.ok(hits.some((c) => c.ticker === target.ticker),
    `searching "${word}" did not find ${target.ticker}`);
});

test('universe validation rejects a broken config rather than rendering it', () => {
  assert.ok(GDT.validateUniverse(UNIVERSE).ok);
  assert.ok(!GDT.validateUniverse({ schemaVersion: '9.0.0', constituents: [] }).ok);
  assert.ok(!GDT.validateUniverse({ schemaVersion: '1.0.0' }).ok);
  assert.ok(!GDT.validateUniverse(null).ok);
});

test('snapshot validation covers every field the specification names', () => {
  const good = fixture('FULL_RESEARCH');
  assert.ok(GDT.validateSnapshot(good, 'SYNB').ok);

  const cases = {
    'schemaVersion': (d) => { d.schemaVersion = '2.0.0'; },
    'ticker mismatch': (d) => { d.ticker = 'ZZZZ'; },
    'mode': (d) => { d.mode = 'LIVE'; },
    'uiState': (d) => { d.uiState = 'GREAT'; },
    'researchStatus': (d) => { d.researchStatus = 'DONE'; },
    'valuation status': (d) => { d.valuation.status = 'MAYBE'; },
    'freshness': (d) => { delete d.freshness; },
    'quality': (d) => { delete d.quality; },
    'evidence': (d) => { delete d.evidence; },
    'modelAudit': (d) => { delete d.modelAudit; }
  };
  for (const [name, mutate] of Object.entries(cases)) {
    const doc = JSON.parse(JSON.stringify(good));
    mutate(doc);
    assert.ok(!GDT.validateSnapshot(doc, 'SYNB').ok, `${name} was accepted`);
  }
});

test('15 — a missing price displays NOT PUBLISHED, never a zero', () => {
  for (const state of FIXTURE_STATES) {
    const price = GDT.marketPrice(fixture(state));
    assert.strictEqual(price.available, false);
    assert.strictEqual(price.text, 'NOT PUBLISHED');
    assert.strictEqual(price.raw, null);
    assert.ok(price.reason, `${state} gives no reason for the absent price`);
  }
});

test('16 — a refused valuation reports VALUATION NOT PUBLISHED with its cause', () => {
  for (const state of FIXTURE_STATES.filter((s) => s !== 'FULL_RESEARCH')) {
    const h = GDT.headline(fixture(state));
    assert.strictEqual(h.valued, false);
    assert.strictEqual(h.text, 'VALUATION NOT PUBLISHED');
    assert.ok(h.reason, `${state} refusal has no reason`);
    assert.ok(h.note, `${state} refusal has no note`);
    assert.ok(Array.isArray(h.failedGates));
  }
  const valued = GDT.headline(fixture('FULL_RESEARCH'));
  assert.strictEqual(valued.valued, true);
  assert.strictEqual(valued.method, 'RESIDUAL_INCOME');
});

test('17 — a missing numeric never renders as zero', () => {
  assert.strictEqual(GDT.displayValue(null), null);
  assert.strictEqual(GDT.displayValue(undefined), null);
  assert.strictEqual(GDT.displayValue(''), null);
  assert.strictEqual(GDT.displayValue(NaN), null);
  assert.strictEqual(GDT.displayValue(Infinity), null);
  /* a real zero is still a zero — the rule is that absence is not zero, not
     that zero is absence */
  assert.strictEqual(GDT.displayValue(0), '0');

  const partial = fixture('PARTIAL');
  const nulls = (partial.reported.values || []).filter((v) => v.value === null);
  for (const v of nulls) {
    assert.strictEqual(GDT.displayValue(v.value), null);
    assert.ok(v.missingReason, 'a null fact arrived without a reason');
  }
});

test('23 — Uncle and Analyst resolve the same record IDs to the same numbers', () => {
  const doc = fixture('FULL_RESEARCH');
  const index = GDT.recordIndex(doc);

  const uncleRefs = doc.uncleView.items.map((i) => i.ref);
  const analystRefs = new Set(doc.analystView.items.map((i) => i.ref));
  assert.ok(uncleRefs.length > 0);
  for (const ref of uncleRefs) {
    assert.ok(analystRefs.has(ref), `Uncle shows ${ref}, Analyst does not`);
  }

  const uncleByRef = new Map(doc.uncleView.items.map((i) => [i.ref, i.value]));
  for (const item of doc.analystView.items) {
    if (!uncleByRef.has(item.ref)) continue;
    assert.strictEqual(JSON.stringify(item.value), JSON.stringify(uncleByRef.get(item.ref)),
      `${item.ref} differs between views`);
    assert.strictEqual(GDT.resolveRecord(index, item.ref).text, GDT.displayValue(item.value));
  }
});

test('a missing record reference reports itself instead of being recomputed', () => {
  const index = GDT.recordIndex(fixture('FULL_RESEARCH'));
  const missing = GDT.resolveRecord(index, 'no_such_metric|FY|2030-12-31|CONSOLIDATED|BASE|nope');
  assert.strictEqual(missing.found, false);
  assert.strictEqual(missing.text, 'DATA REFERENCE UNAVAILABLE');
  assert.strictEqual(missing.raw, null);
});

test('the sensitivity grid is 3x3 and every cell cites a record', () => {
  const grid = GDT.sensitivityGrid(fixture('FULL_RESEARCH'));
  assert.strictEqual(grid.rows.length, 3);
  assert.strictEqual(grid.methods.length, 3);
  for (const row of grid.rows) {
    assert.strictEqual(row.cells.length, 3);
    for (const cell of row.cells) {
      assert.ok(cell.ref, `${row.scenario} cell has no record ref`);
      assert.strictEqual(cell.text, GDT.displayValue(cell.raw));
    }
  }
  assert.strictEqual(GDT.sensitivityGrid(fixture('PARTIAL')), null);
});

test('every UI state in the fixture set is one the renderer knows', () => {
  for (const state of FIXTURE_STATES) {
    const doc = fixture(state);
    assert.ok(GDT.UI_STATES.includes(doc.uiState));
    assert.strictEqual(doc.uiState, state);
  }
  assert.deepStrictEqual(GDT.UI_STATES.slice().sort(), FIXTURE_STATES.slice().sort());
});

test('14 — every fixture declares a non-production mode, so the banner must show', () => {
  for (const state of FIXTURE_STATES) {
    const doc = fixture(state);
    assert.strictEqual(doc.mode, 'FIXTURE_TEST_ONLY');
    assert.strictEqual(GDT.isFixtureMode(doc), true);
  }
  assert.strictEqual(GDT.isFixtureMode({ mode: 'PRODUCTION' }), false);
});

test('the eight research sections are fixed, ordered and paired', () => {
  assert.deepStrictEqual(GDT.SECTIONS.map((s) => s.uncle), [
    "UNCLE'S VERDICT", 'HOW THIS COMPANY MAKES MONEY', 'BUSINESS HEALTH', 'WHAT CHANGED',
    'WHAT MAY IT BE WORTH?', 'WHY UNCLE MAY BE WRONG', 'WHAT BREAKS THE THESIS?',
    'EVIDENCE AND MODEL AUDIT'
  ]);
  assert.deepStrictEqual(GDT.SECTIONS.map((s) => s.analyst), [
    'ANALYST THESIS', 'BUSINESS DRIVER MODEL', 'FINANCIAL DETAIL', 'ESTIMATE REVISIONS',
    'VALUATION MODEL', 'COUNTER-THESIS', 'MONITORING RULES',
    'SOURCES, QUALITY, FORMULAS AND VERSIONS'
  ]);
});

test('loading steps are named work, not a fake percentage', () => {
  assert.deepStrictEqual(GDT.LOADING_STEPS, ['COMPANY PROFILE', 'VERIFIED FINANCIALS',
    'RESEARCH SNAPSHOT', 'VALUATION STATUS', 'COUNTER-THESIS']);
  assert.ok(!/%|percent|progress-bar/i.test(HTML.replace(/max-width|width=/g, '')),
    'the page shows a progress percentage');
});

/* ==========================================================================
   3. REAL BROWSER CHECKS
   ========================================================================== */

const CHROME = [
  '/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell',
  '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
].find((p) => fs.existsSync(p));

/** Build a self-contained copy of the real page with fetch stubbed, load it in
 *  Chromium at a given width, run a scenario, and return the rendered DOM plus
 *  whatever the scenario measured.
 *
 *  `trigger` fires the thing under test — a click that starts a fetch. The
 *  probe then *waits* for the render to settle before `scenario` measures
 *  anything. Measuring straight after the click was the first version of this
 *  helper and it produced fifteen confident, meaningless failures: the click
 *  returns immediately and the render happens a microtask later. */
function renderPage({ width = 390, height = 900, routes = {}, trigger = '', scenario = '',
                     waitFor = null, reducedMotion = false }) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'gdt-ui-'));
  try {
    fs.mkdirSync(path.join(dir, 'assets'));
    fs.copyFileSync(path.join(ROOT, 'assets/goh-dip-tong.css'), path.join(dir, 'assets/goh-dip-tong.css'));
    fs.copyFileSync(path.join(ROOT, 'assets/goh-dip-tong.js'), path.join(dir, 'assets/goh-dip-tong.js'));

    const stub = `
<script>
window.__ROUTES__ = ${JSON.stringify(routes)};
window.fetch = function (url) {
  var key = Object.keys(window.__ROUTES__).find(function (k) { return String(url).indexOf(k) !== -1; });
  if (!key) return Promise.resolve({ ok: false, status: 404, json: function () { return Promise.reject(new Error('404')); } });
  return Promise.resolve({ ok: true, status: 200, json: function () { return Promise.resolve(window.__ROUTES__[key]); } });
};
</script>`;

    const settleCondition = waitFor || (trigger
      ? `document.querySelector('[data-page="result"].on')`
      : `document.querySelector('#gdt-results .result-btn') || document.querySelector('.failsoft')`);

    const probe = `
<pre id="gdt-probe" style="display:none"></pre>
<script>
function __settle(check, budget) {
  return new Promise(function (resolve, reject) {
    var waited = 0;
    (function poll() {
      var ready = false;
      try { ready = !!(check()); } catch (e) { ready = false; }
      if (ready) return resolve();
      waited = waited + 25;
      if (waited > budget) return reject(new Error('render never settled: ' + check.toString()));
      setTimeout(poll, 25);
    })();
  });
}
window.addEventListener('load', function () {
  setTimeout(function () {
    var out = { ok: true };
    Promise.resolve()
      .then(function () { ${trigger} })
      .then(function () { return __settle(function () { return ${settleCondition}; }, 3000); })
      .then(function () { return new Promise(function (r) { setTimeout(r, 120); }); })
      .then(function () {
        ${scenario}
        out.scrollWidth = document.documentElement.scrollWidth;
        out.clientWidth = document.documentElement.clientWidth;
        out.bodyScrollWidth = document.body.scrollWidth;
        out.overflowing = [];
        function inScroller(node) {
          for (var p = node.parentElement; p; p = p.parentElement) {
            var ox = getComputedStyle(p).overflowX;
            if (ox === 'auto' || ox === 'scroll' || ox === 'hidden') return true;
          }
          return false;
        }
        document.querySelectorAll('*').forEach(function (n) {
          var r = n.getBoundingClientRect();
          if (r.width > 0 && r.right > document.documentElement.clientWidth + 1 && !inScroller(n)) {
            out.overflowing.push(n.tagName + '.' + String(n.className).slice(0, 40));
          }
        });
      })
      .catch(function (e) { out.ok = false; out.error = String(e && e.stack || e); })
      .then(function () {
        document.getElementById('gdt-probe').textContent = JSON.stringify(out);
      });
  }, 150);
});
</script>`;

    let page = HTML.replace('<link rel="stylesheet"', stub + '\n<link rel="stylesheet"');
    page = page.replace('</body>', probe + '\n</body>');
    fs.writeFileSync(path.join(dir, 'page.html'), page);

    const args = ['--headless', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
                  `--window-size=${width},${height}`, '--virtual-time-budget=4000',
                  '--dump-dom', `file://${path.join(dir, 'page.html')}`];
    if (reducedMotion) args.splice(1, 0, '--force-prefers-reduced-motion');

    const dom = execFileSync(CHROME, args, { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024,
                                             stdio: ['ignore', 'pipe', 'ignore'] });
    const m = dom.match(/<pre id="gdt-probe"[^>]*>([\s\S]*?)<\/pre>/);
    const result = m && m[1].trim() ? JSON.parse(decodeEntities(m[1])) : { ok: false, error: 'probe never ran' };
    return { dom, result };
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}

function decodeEntities(s) {
  return s.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"');
}

const routesFor = (state) => ({
  'idx30.current.json': UNIVERSE,
  [`ui_states/${state}.json`]: fixture(state)
});

/* Fires the fixture load. Passed as `trigger`, never as `scenario`: the probe
   waits for the render to settle between the two. */
const loadFixture = (state) => `
  document.getElementById('gdt-fixture-select').value = '${state}.json';
  document.getElementById('gdt-fixture-run').click();
`;

const browser = { skip: !CHROME, concurrency: 1 };
if (!CHROME) console.error('WARNING: Chromium not found — browser layer skipped');

for (const state of FIXTURE_STATES) {
  test(`8-13 — the ${state} fixture renders`, browser, () => {
    const { dom, result } = renderPage({
      routes: routesFor(state),
      trigger: loadFixture(state),
      scenario: 'out.rendered = true;'
    });
    assert.ok(result.ok, result.error);
    assert.ok(dom.includes(`data-page="result" class="on"`) || /data-page="result"[^>]*class="[^"]*\bon\b/.test(dom),
      'the result page did not become visible');
    assert.ok(dom.includes(fixture(state).ticker), 'the ticker is not on the page');

    /* 14 — every fixture shows the persistent warning, both lines */
    assert.ok(dom.includes('FIXTURE TEST ONLY'), 'missing FIXTURE TEST ONLY');
    assert.ok(dom.includes('NOT LIVE, CURRENT OR AUTHORITATIVE ANALYSIS'),
      'missing the second warning line');

    /* the state's own required wording */
    const NOTICE = {
      MODEL_UNDER_VALIDATION: 'MODEL UNDER VALIDATION',
      ONBOARDING: 'COVERAGE ONBOARDING',
      STALE: 'STALE RESEARCH',
      SUSPENDED: 'MODEL SUSPENDED',
      PARTIAL: 'PARTIAL RESEARCH'
    };
    if (NOTICE[state]) assert.ok(dom.includes(NOTICE[state]), `missing "${NOTICE[state]}"`);

    /* every one of the eight sections is present, in order */
    let cursor = 0;
    for (const section of GDT.SECTIONS) {
      const at = dom.indexOf(section.uncle.replace(/'/g, '&#39;'), cursor) >= 0
        ? dom.indexOf(section.uncle.replace(/'/g, '&#39;'), cursor)
        : dom.indexOf(section.uncle, cursor);
      assert.ok(at >= 0, `section "${section.uncle}" missing or out of order`);
      cursor = at;
    }
  });
}

test('8 — FULL_RESEARCH shows the valuation, scenarios and cross-checks', browser, () => {
  const { dom } = renderPage({
    routes: routesFor('FULL_RESEARCH'),
    trigger: loadFixture('FULL_RESEARCH')
  });
  assert.ok(dom.includes('data-valuation="VALUED"'));
  assert.ok(dom.includes('RESIDUAL_INCOME'));
  for (const s of ['BEAR', 'BASE', 'BULL']) assert.ok(dom.includes(s), `${s} missing`);
  assert.ok(dom.includes('RI (PRIMARY)'));
  assert.ok(dom.includes('P/B CHECK') && dom.includes('DDM CHECK'));
  assert.ok(!dom.includes('VALUATION NOT PUBLISHED'));
});

test('16 — a refused state never looks like a completed valuation', browser, () => {
  const { dom } = renderPage({
    routes: routesFor('PARTIAL'),
    trigger: loadFixture('PARTIAL')
  });
  assert.ok(dom.includes('VALUATION NOT PUBLISHED'));
  assert.ok(dom.includes('data-valuation="REFUSED"'));
  assert.ok(dom.includes('INSUFFICIENT_INPUTS'));
  assert.ok(dom.includes('REFUSAL REASON'));
  assert.ok(dom.includes('MISSING INPUTS'));
  assert.ok(dom.includes('FAILED GATES'));
});

test('15 — the price reads NOT PUBLISHED and never Rp 0', browser, () => {
  const { dom } = renderPage({
    routes: routesFor('FULL_RESEARCH'),
    trigger: loadFixture('FULL_RESEARCH')
  });
  assert.ok(dom.includes('CURRENT PRICE'));
  assert.ok(dom.includes('NOT PUBLISHED'));
  assert.ok(!/Rp\s*0\b/.test(dom), 'a zero rupiah price was rendered');
  assert.ok(!/>\s*N\/A\s*</.test(dom), 'N/A was used as a numeric substitute');
});

test('18-19 — Uncle View is visible and Analyst detail is collapsed by default', browser, () => {
  const { dom, result } = renderPage({
    routes: routesFor('FULL_RESEARCH'),
    trigger: loadFixture('FULL_RESEARCH'),
    scenario: `
      out.toggles = [].map.call(document.querySelectorAll('.analyst-toggle'), function (b) {
        return { expanded: b.getAttribute('aria-expanded'), controls: b.getAttribute('aria-controls'),
                 panelHidden: document.getElementById(b.getAttribute('aria-controls')).hidden };
      });
      out.uncleVisible = document.querySelectorAll('.section-body').length;
    `
  });
  assert.ok(result.ok, result.error);
  assert.strictEqual(result.toggles.length, 8, 'expected one accordion per section');
  for (const t of result.toggles) {
    assert.strictEqual(t.expanded, 'false');
    assert.strictEqual(t.panelHidden, true);
    assert.ok(t.controls, 'aria-controls is missing');
  }
  assert.strictEqual(result.uncleVisible, 8);
  assert.ok(dom.includes("UNCLE'S VERDICT") || dom.includes('UNCLE&#39;S VERDICT'));
});

test('20, 36 — an Analyst section expands inline with correct ARIA state', browser, () => {
  const { result } = renderPage({
    routes: routesFor('FULL_RESEARCH'),
    trigger: loadFixture('FULL_RESEARCH'),
    scenario: `
      var btn = document.querySelectorAll('.analyst-toggle')[4];
      var panel = document.getElementById(btn.getAttribute('aria-controls'));
      out.before = { expanded: btn.getAttribute('aria-expanded'), hidden: panel.hidden };
      btn.click();
      out.after = { expanded: btn.getAttribute('aria-expanded'), hidden: panel.hidden,
                    text: panel.textContent.slice(0, 200),
                    inlineAfterButton: panel.previousElementSibling === btn,
                    insideSameSection: panel.closest('[data-section]') === btn.closest('[data-section]') };
      btn.click();
      out.reclosed = { expanded: btn.getAttribute('aria-expanded'), hidden: panel.hidden };
    `
  });
  assert.ok(result.ok, result.error);
  assert.deepStrictEqual(result.before, { expanded: 'false', hidden: true });
  assert.strictEqual(result.after.expanded, 'true');
  assert.strictEqual(result.after.hidden, false);
  assert.ok(result.after.text.length > 0, 'the panel expanded but is empty');
  assert.strictEqual(result.after.inlineAfterButton, true, 'the panel is not inline below its button');
  assert.strictEqual(result.after.insideSameSection, true, 'the panel is not inside its Uncle section');
  assert.deepStrictEqual(result.reclosed, { expanded: 'false', hidden: true });
});

test('21-22 — EXPAND ALL and COLLAPSE ALL work', browser, () => {
  const { result } = renderPage({
    routes: routesFor('FULL_RESEARCH'),
    trigger: loadFixture('FULL_RESEARCH'),
    scenario: `
      function states() {
        return [].map.call(document.querySelectorAll('.analyst-toggle'),
          function (b) { return b.getAttribute('aria-expanded'); });
      }
      out.initial = states();
      out.scrollBeforeExpand = window.scrollY;
      document.getElementById('gdt-expand-all').click();
      out.expanded = states();
      out.scrollAfterExpand = window.scrollY;
      document.getElementById('gdt-collapse-all').click();
      out.collapsed = states();
    `
  });
  assert.ok(result.ok, result.error);
  assert.ok(result.initial.every((s) => s === 'false'));
  assert.ok(result.expanded.every((s) => s === 'true'), 'EXPAND ALL did not open everything');
  assert.ok(result.collapsed.every((s) => s === 'false'), 'COLLAPSE ALL did not close everything');
  assert.strictEqual(result.scrollBeforeExpand, result.scrollAfterExpand,
    'expanding moved the scroll position');
});

test('23 — shared numbers are byte-identical between Uncle and Analyst in the DOM', browser, () => {
  const { result } = renderPage({
    routes: routesFor('FULL_RESEARCH'),
    trigger: loadFixture('FULL_RESEARCH'),
    scenario: `
      document.getElementById('gdt-expand-all').click();
      var seen = {};
      out.conflicts = [];
      document.querySelectorAll('[data-record-ref]').forEach(function (n) {
        var ref = n.getAttribute('data-record-ref');
        var raw = n.getAttribute('data-raw');
        var text = n.textContent;
        if (ref in seen) {
          if (seen[ref].raw !== raw || seen[ref].text !== text) {
            out.conflicts.push({ ref: ref, a: seen[ref], b: { raw: raw, text: text } });
          }
        } else { seen[ref] = { raw: raw, text: text }; }
      });
      out.refCount = Object.keys(seen).length;
      out.sample = seen[Object.keys(seen)[0]];
    `
  });
  assert.ok(result.ok, result.error);
  assert.deepStrictEqual(result.conflicts, [],
    'the same record ID rendered two different numbers');
  assert.ok(result.refCount > 5, 'too few record-backed figures to be meaningful');
});

test('24 — every rendered figure is byte-identical to the snapshot value', browser, () => {
  const doc = fixture('FULL_RESEARCH');
  const { result } = renderPage({
    routes: routesFor('FULL_RESEARCH'),
    trigger: loadFixture('FULL_RESEARCH'),
    scenario: `
      document.getElementById('gdt-expand-all').click();
      out.figures = [].map.call(document.querySelectorAll('[data-record-ref][data-raw]'),
        function (n) { return { ref: n.getAttribute('data-record-ref'), raw: n.getAttribute('data-raw') }; });
    `
  });
  assert.ok(result.ok, result.error);
  const index = GDT.recordIndex(doc);
  let checked = 0;
  for (const f of result.figures) {
    const record = index[f.ref];
    if (!record) continue;
    assert.strictEqual(f.raw, String(record.value),
      `${f.ref} was rendered as ${f.raw} but the snapshot says ${record.value}`);
    checked += 1;
  }
  assert.ok(checked > 5, `only ${checked} figures could be traced back to a record`);
});

test('6 — a config-load failure shows CONFIG UNAVAILABLE and no empty picker', browser, () => {
  const { dom } = renderPage({ routes: { 'ui_states/FULL_RESEARCH.json': fixture('FULL_RESEARCH') } });
  assert.ok(dom.includes('CONFIG UNAVAILABLE'), 'the fail-soft state did not appear');
  assert.ok(!/<ul class="results" id="gdt-results"[^>]*>\s*<\/ul>/.test(dom),
    'an empty picker was left on screen');
  /* the fixture selector survives, so the page is still usable */
  assert.ok(dom.includes('DEVELOPMENT — UI STATE FIXTURES') ||
            dom.includes('DEVELOPMENT &mdash; UI STATE FIXTURES'));
});

test('7 — a snapshot-load failure shows RESEARCH SNAPSHOT UNAVAILABLE and keeps the picker', browser, () => {
  const list = GDT.activeConstituents(UNIVERSE);
  const { dom } = renderPage({
    routes: { 'idx30.current.json': UNIVERSE },   /* no snapshot route: 404 */
    scenario: `
      document.querySelector('.result-btn').click();
      document.getElementById('gdt-run').click();
    `
  });
  assert.ok(dom.includes('RESEARCH SNAPSHOT UNAVAILABLE'));
  assert.ok(dom.includes('CHOOSE ANOTHER TARGET'), 'no route back to the picker');
  assert.ok(dom.includes(list[0].ticker), 'the picker was destroyed');
});

test('1, 3 — the picker renders from the config, not from a literal', browser, () => {
  const trimmed = JSON.parse(JSON.stringify(UNIVERSE));
  trimmed.constituents = trimmed.constituents.slice(0, 3);
  trimmed.constituents[2].active = false;
  const { dom, result } = renderPage({
    routes: { 'idx30.current.json': trimmed },
    scenario: `
      out.rendered = [].map.call(document.querySelectorAll('#gdt-results .result-btn'),
        function (b) { return b.getAttribute('data-ticker'); });
    `
  });
  assert.ok(result.ok, result.error);
  /* Asserted against the rendered list rather than the whole document: the
     test harness embeds the stub config in the page, so the inactive ticker is
     legitimately present in the DOM as data. What matters is that the picker
     did not render it. */
  assert.strictEqual(result.rendered.length, 2, 'inactive constituents were rendered');
  assert.ok(result.rendered.includes(trimmed.constituents[0].ticker));
  assert.ok(!result.rendered.includes(trimmed.constituents[2].ticker),
    'an inactive constituent reached the picker');
  assert.ok(dom.includes('NOT AUTHORITATIVE'), 'the config authority status is not shown');
  assert.ok(dom.includes(trimmed.effectiveFrom), 'the config effective date is not shown');
});

test('4, 5 — search filters the rendered list by ticker and by name', browser, () => {
  const list = GDT.activeConstituents(UNIVERSE);
  const target = list[0];
  const { result } = renderPage({
    routes: { 'idx30.current.json': UNIVERSE },
    scenario: `
      var input = document.getElementById('gdt-search');
      function count() { return document.querySelectorAll('#gdt-results .result-btn').length; }
      out.all = count();
      input.value = '${target.ticker}';
      input.dispatchEvent(new Event('input'));
      out.byTicker = count();
      out.byTickerFirst = document.querySelector('#gdt-results .r-ticker').textContent;
      input.value = '${target.name.split(' ')[0]}';
      input.dispatchEvent(new Event('input'));
      out.byName = count();
      input.value = 'zzzzzznope';
      input.dispatchEvent(new Event('input'));
      out.none = count();
      out.emptyText = document.querySelector('#gdt-results .results-empty').textContent;
    `
  });
  assert.ok(result.ok, result.error);
  assert.strictEqual(result.all, list.length);
  assert.ok(result.byTicker >= 1 && result.byTicker < result.all);
  assert.strictEqual(result.byTickerFirst, target.ticker);
  assert.ok(result.byName >= 1);
  assert.strictEqual(result.none, 0);
  assert.ok(result.emptyText.includes('No IDX30 company matches'));
});

test('the selected company is obvious and remembered for the session', browser, () => {
  const { result } = renderPage({
    routes: { 'idx30.current.json': UNIVERSE },
    scenario: `
      var first = document.querySelector('#gdt-results .result-btn');
      out.beforeSelected = first.getAttribute('aria-selected');
      out.ctaDisabledBefore = document.getElementById('gdt-run').disabled;
      first.click();
      out.afterSelected = first.getAttribute('aria-selected');
      out.ctaDisabledAfter = document.getElementById('gdt-run').disabled;
      out.ctaLabel = document.getElementById('gdt-run-label').textContent;
      out.stored = sessionStorage.getItem('gdt.selectedTicker');
      out.markText = getComputedStyle(first.querySelector('.r-mark'), '::after').content;
    `
  });
  assert.ok(result.ok, result.error);
  assert.strictEqual(result.beforeSelected, 'false');
  assert.strictEqual(result.afterSelected, 'true');
  assert.strictEqual(result.ctaDisabledBefore, true);
  assert.strictEqual(result.ctaDisabledAfter, false);
  assert.ok(result.ctaLabel.includes('RUN THE NUMBERS'));
  assert.ok(result.stored, 'the selection was not remembered for the session');
  /* selection is not colour-only: the pseudo-element says SELECTED */
  assert.ok(/SELECTED/.test(result.markText), 'selection is conveyed by colour alone');
});

for (const width of [320, 390]) {
  test(`33-34 — no page-level horizontal overflow at ${width}px`, browser, () => {
    const { result } = renderPage({
      width,
      routes: routesFor('FULL_RESEARCH'),
      trigger: loadFixture('FULL_RESEARCH'),
    scenario: `
        document.getElementById('gdt-expand-all').click();
      `
    });
    assert.ok(result.ok, result.error);
    assert.strictEqual(result.clientWidth, width, 'the viewport was not honoured');
    assert.ok(result.scrollWidth <= width,
      `documentElement.scrollWidth ${result.scrollWidth} exceeds ${width}`);
    assert.ok(result.bodyScrollWidth <= width,
      `body.scrollWidth ${result.bodyScrollWidth} exceeds ${width}`);
    assert.deepStrictEqual(result.overflowing, [],
      `elements extend past the viewport: ${JSON.stringify(result.overflowing)}`);
  });
}

test('35 — keyboard focus is visible and the list is keyboard navigable', browser, () => {
  const { result } = renderPage({
    routes: { 'idx30.current.json': UNIVERSE },
    scenario: `
      var input = document.getElementById('gdt-search');
      input.focus();
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
      out.afterArrow = document.activeElement.className;
      var buttons = document.querySelectorAll('#gdt-results .result-btn');
      buttons[0].focus();
      buttons[0].dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
      out.movedTo = document.activeElement.getAttribute('data-ticker');
      out.second = buttons[1].getAttribute('data-ticker');
      out.focusedTag = document.activeElement.tagName;
    `
  });
  assert.ok(result.ok, result.error);
  assert.ok(result.afterArrow.includes('result-btn'), 'arrow down did not enter the list');
  assert.strictEqual(result.movedTo, result.second, 'arrow down did not move within the list');
  assert.strictEqual(result.focusedTag, 'BUTTON', 'focus did not land on a real control');

  /* The focus ring is asserted against the stylesheet source rather than
     through document.styleSheets: over file:// Chromium treats a linked sheet
     as cross-origin and cssRules throws, which would make this check quietly
     pass on an empty result. */
  const focusRule = CSS.match(/:focus-visible\s*\{[^}]*\}/);
  assert.ok(focusRule, 'no :focus-visible rule is declared');
  assert.match(focusRule[0], /outline\s*:\s*\d/, 'the focus outline has no width');
  assert.ok(!/outline\s*:\s*none/i.test(CSS.replace(/outline:none;border-color/g, '')),
    'the stylesheet removes a focus outline without replacing it');
});

test('37 — reduced motion disables non-essential animation', browser, () => {
  const { result } = renderPage({
    reducedMotion: true,
    routes: routesFor('FULL_RESEARCH'),
    trigger: loadFixture('FULL_RESEARCH'),
    scenario: `
      out.reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      out.screenAnim = getComputedStyle(document.querySelector('.screen')).animationName;
      out.logoAnim = getComputedStyle(document.querySelector('.logotype')).animationName;
      var caret = document.querySelector('.caret');
      out.caretTransition = caret ? getComputedStyle(caret).transitionDuration : null;
    `
  });
  assert.ok(result.ok, result.error);
  assert.strictEqual(result.reduced, true, 'the reduced-motion flag did not apply');
  assert.strictEqual(result.screenAnim, 'none', 'the CRT flicker still animates');
  assert.strictEqual(result.logoAnim, 'none', 'the logotype still pulses');
  assert.ok(!result.caretTransition || parseFloat(result.caretTransition) < 0.01,
    'the caret still transitions');
});

test('25, 26 — a hostile snapshot cannot inject markup or a link', browser, () => {
  const doc = fixture('PARTIAL');
  doc.evidence = [
    { ref: '<img src=x onerror=alert(1)>', kind: 'FACT',
      sourceRef: 'javascript:alert(document.domain)', publishedAt: null },
    { ref: 'SYNP|equity|FY|2025-12-31|CONSOLIDATED', kind: 'FACT',
      sourceRef: 'https://example.org/filing', publishedAt: null }
  ];
  doc.valuation.note = '</p><script>window.__PWNED__=1;<\\/script>';
  doc.company.name = '<b>NOT BOLD</b>';

  const { dom, result } = renderPage({
    routes: { 'idx30.current.json': UNIVERSE, 'ui_states/PARTIAL.json': doc },
    trigger: loadFixture('PARTIAL'),
    scenario: `
      document.getElementById('gdt-expand-all').click();
      out.pwned = !!window.__PWNED__;
      out.injectedImg = document.querySelectorAll('img').length;
      out.links = [].map.call(document.querySelectorAll('#gdt-result-host a'), function (a) {
        return { href: a.getAttribute('href'), rel: a.getAttribute('rel') };
      });
      out.nameText = document.querySelector('.rh-name').textContent;
      out.nameChildElements = document.querySelector('.rh-name').children.length;
      /* <b> is excluded on purpose: the status chips legitimately build one.
         What must not exist is an element the snapshot created. */
      var host = document.getElementById('gdt-result-host');
      out.hostElementCount = host.querySelectorAll('script, iframe, object, embed, img, svg[onload]').length;
      out.smuggled = [].filter.call(host.querySelectorAll('*'), function (n) {
        return n.textContent === 'NOT BOLD';
      }).length;
    `
  });
  assert.ok(result.ok, result.error);
  assert.strictEqual(result.pwned, false, 'a snapshot executed script');
  assert.strictEqual(result.injectedImg, 0, 'a snapshot injected an image element');
  assert.strictEqual(result.nameText, '<b>NOT BOLD</b>', 'markup in a name was interpreted');
  /* Asserted on the rendered subtree, not the whole dump: the harness embeds
     the hostile snapshot as stub data, so the string is legitimately present
     in the document as JSON inside a script tag. What matters is that it
     produced no elements. */
  assert.strictEqual(result.nameChildElements, 0, 'the company name produced child elements');
  assert.strictEqual(result.hostElementCount, 0, 'a snapshot created elements in the result region');
  assert.strictEqual(result.smuggled, 0, 'markup in the company name became a real element');
  for (const link of result.links) {
    assert.ok(link.href.startsWith('https://'), `unsafe href rendered: ${link.href}`);
    assert.strictEqual(link.rel, 'noopener noreferrer');
  }
  assert.ok(!result.links.some((l) => /javascript:/i.test(l.href)));
});

test('27 — no request is ever made to a private path', browser, () => {
  const { result } = renderPage({
    routes: routesFor('FULL_RESEARCH'),
    scenario: `
      out.requested = [];
      var real = window.fetch;
      window.fetch = function (u) { out.requested.push(String(u)); return real.apply(null, arguments); };
      ${loadFixture('FULL_RESEARCH')}
      out.privateHits = out.requested.filter(function (u) { return u.indexOf('_private') !== -1; });
    `
  });
  assert.ok(result.ok, result.error);
  assert.deepStrictEqual(result.privateHits, []);
});

test('accessibility — headings, labels and landmarks are coherent', browser, () => {
  const { result } = renderPage({
    routes: routesFor('FULL_RESEARCH'),
    trigger: loadFixture('FULL_RESEARCH'),
    scenario: `
      out.h1 = document.querySelectorAll('h1').length;
      out.headings = [].map.call(document.querySelectorAll('h1,h2,h3,h4'),
        function (h) { return Number(h.tagName.slice(1)); });
      out.labelled = !!document.querySelector('label[for="gdt-search"]');
      out.searchDescribed = document.getElementById('gdt-search').getAttribute('aria-describedby');
      out.decorativeSvgHidden = [].every.call(document.querySelectorAll('svg.ic'),
        function (s) { return s.getAttribute('aria-hidden') === 'true'; });
      out.meaningfulSvgTitled = [].every.call(document.querySelectorAll('svg.uncle-head'),
        function (s) { return !!s.querySelector('title') && s.getAttribute('role') === 'img'; });
      out.liveRegions = document.querySelectorAll('[aria-live]').length;
      out.alerts = document.querySelectorAll('[role="alert"]').length;
    `
  });
  assert.ok(result.ok, result.error);
  assert.strictEqual(result.h1, 1, 'there must be exactly one h1');
  let previous = 0;
  for (const level of result.headings) {
    assert.ok(level <= previous + 1, `heading level jumped from h${previous} to h${level}`);
    previous = level;
  }
  assert.strictEqual(result.labelled, true, 'the search input has no associated label');
  assert.ok(result.searchDescribed, 'the search input has no description');
  assert.strictEqual(result.decorativeSvgHidden, true, 'a decorative SVG is exposed to AT');
  assert.strictEqual(result.meaningfulSvgTitled, true, 'the character SVG has no accessible name');
  assert.ok(result.liveRegions >= 2, 'status changes are not announced');
  assert.ok(result.alerts >= 1, 'the fixture warning is not an alert');
});

test('status is never conveyed by colour alone', browser, () => {
  const { result } = renderPage({
    routes: routesFor('SUSPENDED'),
    trigger: loadFixture('SUSPENDED'),
    scenario: `
      out.chips = [].map.call(document.querySelectorAll('.chip'), function (c) { return c.textContent.trim(); });
      out.verdictText = document.querySelector('.verdict').textContent;
    `
  });
  assert.ok(result.ok, result.error);
  assert.ok(result.chips.some((c) => /DATA MODE\s+FIXTURE_TEST_ONLY/.test(c)),
    'the mode chip has no text');
  assert.ok(result.chips.some((c) => /UI STATE\s+SUSPENDED/.test(c)));
  assert.ok(result.verdictText.includes('VALUATION NOT PUBLISHED'));
});

test('back closes expanded detail before leaving the page', browser, () => {
  const { result } = renderPage({
    routes: routesFor('FULL_RESEARCH'),
    trigger: loadFixture('FULL_RESEARCH'),
    scenario: `
      document.getElementById('gdt-expand-all').click();
      out.openBefore = [].filter.call(document.querySelectorAll('.analyst-toggle'),
        function (b) { return b.getAttribute('aria-expanded') === 'true'; }).length;
      window.GDT_APP.onPopState();
      out.openAfter = [].filter.call(document.querySelectorAll('.analyst-toggle'),
        function (b) { return b.getAttribute('aria-expanded') === 'true'; }).length;
    `
  });
  assert.ok(result.ok, result.error);
  assert.strictEqual(result.openBefore, 8);
  assert.strictEqual(result.openAfter, 0, 'back did not close the expanded detail');
});

test('long tables render a window first rather than a hundred rows', browser, () => {
  const { result } = renderPage({
    routes: routesFor('FULL_RESEARCH'),
    trigger: loadFixture('FULL_RESEARCH'),
    scenario: `
      var btns = document.querySelectorAll('.analyst-toggle');
      btns[7].click();                       /* EVIDENCE AND MODEL AUDIT */
      out.initialRows = document.querySelectorAll('.evidence-list li').length;
      var more = [].find.call(document.querySelectorAll('.more-btn'),
        function (b) { return /SOURCE RECORDS/.test(b.textContent); });
      out.hasMore = !!more;
      if (more) { more.click(); out.allRows = document.querySelectorAll('.evidence-list li').length; }
    `
  });
  assert.ok(result.ok, result.error);
  assert.strictEqual(result.initialRows, 25, 'the evidence list did not render a window');
  assert.strictEqual(result.hasMore, true);
  assert.ok(result.allRows > 100, 'the full evidence list did not expand on request');
});

/* ------------------------------------------------------------------ helpers */

/** Strip comments so prose about arithmetic is not mistaken for arithmetic —
 *  and so a JSDoc opener is not mistaken for an exponent operator. */
function stripComments(source) {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, (block) => block.replace(/[^\n]/g, ' '))
    .replace(/(^|[^:])\/\/.*$/gm, '$1');
}

/** Blank out string literals, preserving length and line breaks. */
function stripStrings(source) {
  return source.replace(/'(?:[^'\\\n]|\\.)*'|"(?:[^"\\\n]|\\.)*"/g,
                        (s) => "'" + ' '.repeat(Math.max(s.length - 2, 0)) + "'");
}

function stubDocument() {
  return {
    getElementById: () => null,
    querySelector: () => null,
    querySelectorAll: () => [],
    createElement: () => ({ setAttribute() {}, appendChild() {}, classList: { toggle() {}, add() {} } }),
    createTextNode: () => ({})
  };
}
