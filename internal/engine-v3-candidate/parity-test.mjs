/* ============================================================================
   PARITY TEST — browser build vs ES-module originals
   ============================================================================
   Loads ../../engine-v3/engine-v3.browser.js in a Node vm context and compares
   its output, byte for byte via JSON.stringify, against engine.js and
   advanced-engine.js across a large generated sweep of pillar combinations.

   WHAT THIS PROVES:  the two builds compute the same thing.
   WHAT THIS DOES NOT PROVE:  that what they compute is correct. There is no
   practitioner-reviewed corpus in this package, and this test does not invent
   one. See validate.mjs and methodology.json.
   ============================================================================ */

import fs from 'node:fs';
import vm from 'node:vm';
import { analyseBazi, tenGod, STEMS, BRANCHES } from './engine.js';
import { analyseAdvanced } from './advanced-engine.js';

const BROWSER_BUILD = new URL('../../engine-v3/engine-v3.browser.js', import.meta.url);

/* ---- load the classic-script build into an isolated realm ---- */
const sandbox = { window: {} };
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(BROWSER_BUILD, 'utf8'), sandbox, { filename: 'engine-v3.browser.js' });
const B = sandbox.window.BaziV3;

if (!B) { console.error('FAIL: browser build did not expose window.BaziV3'); process.exit(1); }

const STEM_NAMES   = Object.keys(STEMS);
const BRANCH_NAMES = Object.keys(BRANCHES);

/* ---- table parity ---- */
let failures = 0;
function check(label, a, b) {
  const sa = JSON.stringify(a), sb = JSON.stringify(b);
  if (sa !== sb) {
    failures++;
    if (failures <= 5) {
      console.error('MISMATCH: ' + label);
      console.error('  esm     : ' + String(sa).slice(0, 300));
      console.error('  browser : ' + String(sb).slice(0, 300));
    }
  }
}

check('STEMS table',    STEMS,    B.STEMS);
check('BRANCHES table', BRANCHES, B.BRANCHES);

/* ---- tenGod: all 100 stem pairs ---- */
for (const d of STEM_NAMES) {
  for (const o of STEM_NAMES) {
    check(`tenGod(${d},${o})`, tenGod(d, o), B.tenGod(d, o));
  }
}

/* ---- sweep 1: all 60 sexagenary day pillars x all 12 month branches ---- */
const sexagenary = [];
for (let i = 0; i < 60; i++) {
  sexagenary.push({ stem: STEM_NAMES[i % 10], branch: BRANCH_NAMES[i % 12] });
}

let cases = 0;
for (const day of sexagenary) {
  for (const mb of BRANCH_NAMES) {
    const p = {
      year:  { stem: 'Geng', branch: 'Shen' },
      month: { stem: 'Yi',   branch: mb },
      day:   day,
      hour:  { stem: 'Ren',  branch: 'Zi' }
    };
    const clone = () => JSON.parse(JSON.stringify(p));
    check(`analyseBazi ${day.stem}${day.branch}/${mb}`, analyseBazi(clone()), B.analyseBazi(clone()));
    check(`analyseAdvanced ${day.stem}${day.branch}/${mb}`, analyseAdvanced(clone()), B.analyseAdvanced(clone()));
    cases += 2;
  }
}

/* ---- sweep 2: deterministic pseudo-random full combinations ---- */
let seed = 20260724;
const rnd = (n) => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed % n; };
const pick = (a) => a[rnd(a.length)];

for (let i = 0; i < 4000; i++) {
  const p = {
    year:  { stem: pick(STEM_NAMES), branch: pick(BRANCH_NAMES) },
    month: { stem: pick(STEM_NAMES), branch: pick(BRANCH_NAMES) },
    day:   { stem: pick(STEM_NAMES), branch: pick(BRANCH_NAMES) },
    hour:  { stem: pick(STEM_NAMES), branch: pick(BRANCH_NAMES) }
  };
  const luck = { stem: pick(STEM_NAMES), branch: pick(BRANCH_NAMES) };
  const clone = () => JSON.parse(JSON.stringify(p));

  check(`analyseBazi #${i}`, analyseBazi(clone()), B.analyseBazi(clone()));
  check(`analyseAdvanced #${i}`, analyseAdvanced(clone()), B.analyseAdvanced(clone()));
  check(`analyseAdvanced+luck #${i}`,
        analyseAdvanced(clone(), { luckPillar: luck }),
        B.analyseAdvanced(clone(), { luckPillar: luck }));
  cases += 3;
}

/* ---- both builds must reject the same bad input ---- */
const bad = [
  { label: 'missing hour',  p: { year: { stem: 'Geng', branch: 'Shen' }, month: { stem: 'Yi', branch: 'Mao' }, day: { stem: 'Xin', branch: 'You' } } },
  { label: 'unknown stem',  p: { year: { stem: 'Nope', branch: 'Shen' }, month: { stem: 'Yi', branch: 'Mao' }, day: { stem: 'Xin', branch: 'You' }, hour: { stem: 'Ren', branch: 'Zi' } } },
  { label: 'unknown branch',p: { year: { stem: 'Geng', branch: 'Nope' }, month: { stem: 'Yi', branch: 'Mao' }, day: { stem: 'Xin', branch: 'You' }, hour: { stem: 'Ren', branch: 'Zi' } } },
  { label: 'extra key',     p: { year: { stem: 'Geng', branch: 'Shen' }, month: { stem: 'Yi', branch: 'Mao' }, day: { stem: 'Xin', branch: 'You' }, hour: { stem: 'Ren', branch: 'Zi' }, extra: { precise: true } } }
];

for (const t of bad) {
  const run = (fn) => { try { fn(JSON.parse(JSON.stringify(t.p))); return 'no-throw'; } catch (e) { return 'throw'; } };
  const e = run(analyseBazi), b = run(B.analyseBazi);
  if (e !== b || e !== 'throw') {
    failures++;
    console.error(`MISMATCH: rejection of "${t.label}" — esm=${e} browser=${b} (both must be "throw")`);
  }
  cases++;
}

/* ---- version + certification must not drift ---- */
const ref = analyseBazi({ year: { stem: 'Geng', branch: 'Shen' }, month: { stem: 'Yi', branch: 'Mao' }, day: { stem: 'Xin', branch: 'You' }, hour: { stem: 'Ren', branch: 'Zi' } });
check('engineVersion', ref.engineVersion, B.ENGINE_VERSION);
check('certification', ref.certification, B.CERTIFICATION);
if (B.CERTIFICATION !== 'UNVALIDATED') { failures++; console.error('MISMATCH: certification is no longer UNVALIDATED'); }
if (B.RULE_MATCHING.status !== 'not-implemented') { failures++; console.error('MISMATCH: rule matching claims to be implemented'); }

console.log(`parity: ${cases} comparisons, ${failures} mismatch(es)`);
if (failures) { console.error('parity tests FAIL'); process.exit(1); }
console.log('parity tests PASS — browser build is output-identical to the ES-module originals');
