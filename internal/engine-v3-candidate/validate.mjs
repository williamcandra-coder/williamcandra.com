/* ============================================================================
   FIXTURE VALIDATION RUNNER
   ============================================================================
   Reads reference-fixtures.json and EXECUTES every case whose status is
   "reviewed", comparing engine output against the recorded expectations.

   Deliberate behaviour:
     - No fixtures are created by this file. An empty or unreviewed corpus
       reports as an empty corpus; it is never reported as a pass.
     - Exit 1 only when a case marked "reviewed" fails. Unreviewed cases are
       counted and reported, and do not fail the run, so that `test:all` stays
       usable while the corpus is still empty.
     - The absence of failures here is NOT validation of the engine. Only
       practitioner-reviewed fixtures can carry that meaning, and none exist.
   ============================================================================ */

import fs from 'node:fs';
import { analyseAdvanced } from './advanced-engine.js';

const FIXTURES = new URL('./reference-fixtures.json', import.meta.url);
const d = JSON.parse(fs.readFileSync(FIXTURES, 'utf8'));

let reviewed = 0, skipped = 0, passed = 0, failed = 0;
const failures = [];

/* Compare only the keys the fixture actually asserts. A fixture may pin one
   field (e.g. strength.classification) without restating the whole output. */
function subsetMatch(expected, actual, path = '') {
  if (expected === null || typeof expected !== 'object') {
    return expected === actual
      ? null
      : `${path || '(root)'}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`;
  }
  if (Array.isArray(expected)) {
    if (!Array.isArray(actual)) return `${path}: expected an array, got ${typeof actual}`;
    if (expected.length !== actual.length) return `${path}: expected length ${expected.length}, got ${actual.length}`;
    for (let i = 0; i < expected.length; i++) {
      const m = subsetMatch(expected[i], actual[i], `${path}[${i}]`);
      if (m) return m;
    }
    return null;
  }
  for (const k of Object.keys(expected)) {
    if (actual === null || typeof actual !== 'object' || !(k in actual)) return `${path}${path ? '.' : ''}${k}: missing from engine output`;
    const m = subsetMatch(expected[k], actual[k], `${path}${path ? '.' : ''}${k}`);
    if (m) return m;
  }
  return null;
}

for (const c of d.cases) {
  if (c.status !== 'reviewed') { skipped++; continue; }
  reviewed++;

  const hasInput = c.input && Object.keys(c.input).length > 0;
  const hasExpected = c.expected && Object.keys(c.expected).length > 0;
  if (!hasInput || !hasExpected) {
    failed++;
    failures.push(`${c.caseId}: marked "reviewed" but input or expected is empty`);
    continue;
  }

  try {
    const actual = analyseAdvanced(c.input.pillars || c.input, c.input.options || {});
    const mismatch = subsetMatch(c.expected, actual);
    if (mismatch) { failed++; failures.push(`${c.caseId}: ${mismatch}`); }
    else passed++;
  } catch (e) {
    failed++;
    failures.push(`${c.caseId}: threw — ${e.message}`);
  }
}

console.log(JSON.stringify({ reviewed, skipped, passed, failed }, null, 2));
for (const f of failures) console.error('  FAIL ' + f);

if (reviewed === 0) {
  console.log('NOT A VALIDATION RUN — the reviewed-fixture corpus is empty.');
  console.log(`${skipped} case(s) present, 0 reviewed. Engine remains UNVALIDATED.`);
} else if (failed === 0) {
  console.log(`${passed} reviewed fixture(s) passed. Coverage is limited to those cases; the engine remains UNVALIDATED.`);
}

process.exit(failed > 0 ? 1 : 0);
