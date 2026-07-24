/* ============================================================================
   GOH POK TONG — BAZI KNOWLEDGE ENGINE v3 (BROWSER BUILD)
   ============================================================================

   Status: 0.3.0-strongest-responsible-candidate — UNVALIDATED.

   WHAT THIS FILE IS
   -----------------
   A classic-script (non-module) build of:
       internal/engine-v3-candidate/engine.js
       internal/engine-v3-candidate/advanced-engine.js

   The ES-module originals are kept in the repository unchanged and are what
   the Node test suite exercises. This file exists because the application is
   a static, build-tool-free site: `<script type="module">` and `import()`
   both require an http(s) origin and will fail when the page is opened over
   file://, which is how the page is tested locally. A classic script loads
   from both file:// and https:// with no bundler and no build step.

   CALCULATION LOGIC IS IDENTICAL TO THE ES-MODULE ORIGINALS.
   Only formatting, whitespace and the module wrapper differ. No coefficient,
   table, threshold or branch has been altered. Equivalence is asserted by
   internal/engine-v3-candidate/parity-test.mjs, which loads THIS file and the
   ES-module originals side by side and compares full output across every
   stem/branch combination it generates.

   NAMESPACE
   ---------
   Everything is exposed on a single global, `window.BaziV3`. Nothing else is
   written to global scope. This matters: goh-pok-tong.html already declares
   `const STEMS` and `const BRANCHES` at global scope as ARRAYS, while this
   engine uses the same two names for OBJECTS. Keeping the engine inside this
   closure is what prevents that collision.

   NO runtime AI. NO network calls. NO dependencies. NO storage access.
   ============================================================================ */

(function (root) {
  'use strict';

  /* ==========================================================================
     SECTION 1 — core engine   (source: engine.js)
     ========================================================================== */

  var STEMS = {
    Jia:  { element: 'Wood',  polarity: 'Yang' },
    Yi:   { element: 'Wood',  polarity: 'Yin'  },
    Bing: { element: 'Fire',  polarity: 'Yang' },
    Ding: { element: 'Fire',  polarity: 'Yin'  },
    Wu:   { element: 'Earth', polarity: 'Yang' },
    Ji:   { element: 'Earth', polarity: 'Yin'  },
    Geng: { element: 'Metal', polarity: 'Yang' },
    Xin:  { element: 'Metal', polarity: 'Yin'  },
    Ren:  { element: 'Water', polarity: 'Yang' },
    Gui:  { element: 'Water', polarity: 'Yin'  }
  };

  /* NOTE: `Wu` appears in BOTH tables — the stem 戊 (Yang Earth) and the
     branch 午 (Horse). They are different tables, so lookups stay correct,
     but a stem and a branch must never be swapped by a caller. */
  var BRANCHES = {
    Zi:   { hidden: [['Gui', 1]] },
    Chou: { hidden: [['Ji', 0.6], ['Gui', 0.3], ['Xin', 0.1]] },
    Yin:  { hidden: [['Jia', 0.6], ['Bing', 0.3], ['Wu', 0.1]] },
    Mao:  { hidden: [['Yi', 1]] },
    Chen: { hidden: [['Wu', 0.6], ['Yi', 0.3], ['Gui', 0.1]] },
    Si:   { hidden: [['Bing', 0.6], ['Wu', 0.3], ['Geng', 0.1]] },
    Wu:   { hidden: [['Ding', 0.7], ['Ji', 0.3]] },
    Wei:  { hidden: [['Ji', 0.6], ['Ding', 0.3], ['Yi', 0.1]] },
    Shen: { hidden: [['Geng', 0.6], ['Ren', 0.3], ['Wu', 0.1]] },
    You:  { hidden: [['Xin', 1]] },
    Xu:   { hidden: [['Wu', 0.6], ['Xin', 0.3], ['Ding', 0.1]] },
    Hai:  { hidden: [['Ren', 0.7], ['Jia', 0.3]] }
  };

  var PRODUCES = { Wood: 'Fire', Fire: 'Earth', Earth: 'Metal', Metal: 'Water', Water: 'Wood' };
  var CONTROLS = { Wood: 'Earth', Earth: 'Water', Water: 'Fire', Fire: 'Metal', Metal: 'Wood' };

  function tenGod(d, o) {
    var a = STEMS[d], b = STEMS[o], same = a.polarity === b.polarity;
    if (a.element === b.element)          return same ? 'Friend'         : 'RobWealth';
    if (PRODUCES[a.element] === b.element) return same ? 'EatingGod'      : 'HurtingOfficer';
    if (CONTROLS[a.element] === b.element) return same ? 'IndirectWealth' : 'DirectWealth';
    if (CONTROLS[b.element] === a.element) return same ? 'SevenKillings'  : 'DirectOfficer';
    if (PRODUCES[b.element] === a.element) return same ? 'IndirectResource' : 'DirectResource';
  }

  /* Yin-Hai and Si-Shen appear in both Combination and Destruction. That is
     correct against the standard tables, and it means one branch pair can
     legitimately emit two entries in `dynamics`. */
  var PAIRS = {
    Clash:       [['Zi','Wu'],  ['Chou','Wei'], ['Yin','Shen'], ['Mao','You'],  ['Chen','Xu'],  ['Si','Hai']],
    Combination: [['Zi','Chou'],['Yin','Hai'],  ['Mao','Xu'],   ['Chen','You'], ['Si','Shen'],  ['Wu','Wei']],
    Harm:        [['Zi','Wei'], ['Chou','Wu'],  ['Yin','Si'],   ['Mao','Chen'], ['Shen','Hai'], ['You','Xu']],
    Destruction: [['Zi','You'], ['Chou','Chen'],['Yin','Hai'],  ['Mao','Wu'],   ['Si','Shen'],  ['Wei','Xu']]
  };

  /* Seasonal strength of each element by month branch. Coefficients are
     undocumented in the source package and are model-specific. */
  var MONTH = {
    Yin:  { Wood: 1,    Fire: 0.55, Water: 0.35, Earth: 0.2,  Metal: 0.1  },
    Mao:  { Wood: 1,    Fire: 0.6,  Water: 0.3,  Earth: 0.15, Metal: 0.1  },
    Chen: { Earth: 0.75, Wood: 0.55, Water: 0.3, Metal: 0.25, Fire: 0.2   },
    Si:   { Fire: 1,    Earth: 0.6, Wood: 0.3,   Metal: 0.15, Water: 0.1  },
    Wu:   { Fire: 1,    Earth: 0.65, Wood: 0.25, Metal: 0.1,  Water: 0.05 },
    Wei:  { Earth: 0.8, Fire: 0.55, Wood: 0.25,  Metal: 0.2,  Water: 0.1  },
    Shen: { Metal: 1,   Water: 0.6, Earth: 0.35, Wood: 0.15,  Fire: 0.1   },
    You:  { Metal: 1,   Water: 0.55, Earth: 0.3, Wood: 0.1,   Fire: 0.1   },
    Xu:   { Earth: 0.8, Metal: 0.5, Fire: 0.3,   Water: 0.15, Wood: 0.1   },
    Hai:  { Water: 1,   Wood: 0.6,  Metal: 0.3,  Earth: 0.1,  Fire: 0.05  },
    Zi:   { Water: 1,   Wood: 0.55, Metal: 0.3,  Earth: 0.1,  Fire: 0.05  },
    Chou: { Earth: 0.75, Water: 0.55, Metal: 0.35, Wood: 0.15, Fire: 0.1  }
  };

  function inverse(m, v) {
    return Object.keys(m).find(function (k) { return m[k] === v; });
  }

  /* Expects EXACTLY four keys: year, month, day, hour.
     Any additional key is iterated by the loop below and will throw. */
  function analyseBazi(p) {
    var required = ['year', 'month', 'day', 'hour'];
    for (var i = 0; i < required.length; i++) {
      var k = required[i];
      if (!p[k] || !STEMS[p[k].stem] || !BRANCHES[p[k].branch]) {
        throw Error('Invalid ' + k + ' pillar');
      }
    }

    var dm  = STEMS[p.day.stem];
    var es  = { Wood: 0, Fire: 0, Earth: 0, Metal: 0, Water: 0 };
    var tg  = {};
    var pos = { year: 0.75, month: 1.25, day: 1, hour: 0.85 };

    Object.entries(p).forEach(function (entry) {
      var key = entry[0], x = entry[1];
      var w = pos[key];

      /* Visible stem: positional weight only, no seasonal modulation. */
      es[STEMS[x.stem].element] += w;
      tg[tenGod(p.day.stem, x.stem)] = (tg[tenGod(p.day.stem, x.stem)] || 0) + w;

      /* Hidden stems: positional weight x depth x seasonal modulation.
         The asymmetry against visible stems is inherited from the source. */
      BRANCHES[x.branch].hidden.forEach(function (h) {
        var stem = h[0], q = h[1];
        var v = w * q * (0.55 + 0.45 * MONTH[p.month.branch][STEMS[stem].element]);
        es[STEMS[stem].element] += v;
        tg[tenGod(p.day.stem, stem)] = (tg[tenGod(p.day.stem, stem)] || 0) + v;
      });
    });

    var resource = inverse(PRODUCES, dm.element);
    var output   = PRODUCES[dm.element];
    var wealth   = CONTROLS[dm.element];
    var officer  = inverse(CONTROLS, dm.element);

    var raw = 50
      + ((es[dm.element] + es[resource]) - (es[output] + es[wealth] + es[officer])) * 4
      + (MONTH[p.month.branch][dm.element] - 0.5) * 28;

    var score = Math.max(0, Math.min(100, Math.round(raw)));
    var strength = score < 26 ? 'Very Weak'
                 : score < 46 ? 'Weak'
                 : score < 61 ? 'Balanced'
                 : score < 81 ? 'Strong'
                 : 'Very Strong';

    var bs = Object.values(p).map(function (x) { return x.branch; });
    var dynamics = [];
    Object.entries(PAIRS).forEach(function (entry) {
      var type = entry[0], pairs = entry[1];
      pairs.forEach(function (pair) {
        if (bs.includes(pair[0]) && bs.includes(pair[1])) {
          dynamics.push({
            type: type,
            branches: [pair[0], pair[1]],
            status: 'relationship-detected-transformation-unresolved'
          });
        }
      });
    });

    return {
      pillars: p,
      dayMaster: p.day.stem,
      dayMasterElement: dm.element,
      elementScores: es,
      tenGodScores: tg,
      strength: { classification: strength, diagnosticScore: score, status: 'experimental-model' },
      dynamics: dynamics,
      engineVersion: '0.3.0-strongest-responsible-candidate',
      certification: 'UNVALIDATED'
    };
  }

  /* ==========================================================================
     SECTION 2 — advanced engine   (source: advanced-engine.js)
     ========================================================================== */

  var HARMONY = { 'Shen-Zi-Chen': 'Water', 'Hai-Mao-Wei': 'Wood', 'Yin-Wu-Xu': 'Fire', 'Si-You-Chou': 'Metal' };
  var MEETING = { 'Yin-Mao-Chen': 'Wood', 'Si-Wu-Wei': 'Fire', 'Shen-You-Xu': 'Metal', 'Hai-Zi-Chou': 'Water' };

  function groups(t) {
    return {
      Companion: (t.Friend || 0)        + (t.RobWealth || 0),
      Output:    (t.EatingGod || 0)     + (t.HurtingOfficer || 0),
      Wealth:    (t.DirectWealth || 0)  + (t.IndirectWealth || 0),
      Officer:   (t.DirectOfficer || 0) + (t.SevenKillings || 0),
      Resource:  (t.DirectResource || 0)+ (t.IndirectResource || 0)
    };
  }

  function analyseAdvanced(p, opts) {
    var luckPillar = (opts && opts.luckPillar) || null;

    var b = analyseBazi(p);
    var g = groups(b.tenGodScores);
    var r = Object.entries(g).sort(function (a, c) { return c[1] - a[1]; });
    var set = new Set(Object.values(p).map(function (x) { return x.branch; }));
    var multi = [];

    [['ThreeHarmony', HARMONY], ['ThreeMeeting', MEETING]].forEach(function (pairEntry) {
      var type = pairEntry[0], map = pairEntry[1];
      Object.entries(map).forEach(function (entry) {
        var k = entry[0], e = entry[1];
        var x = k.split('-');
        if (x.every(function (v) { return set.has(v); })) {
          multi.push({
            type: type,
            branches: x,
            element: e,
            /* Detected only. Completion of transformation is NOT asserted. */
            status: 'relationship-complete-transformation-unresolved'
          });
        }
      });
    });

    var roots = Object.entries(p).filter(function (entry) {
      return BRANCHES[entry[1].branch].hidden.some(function (h) {
        return STEMS[h[0]].element === b.dayMasterElement;
      });
    }).map(function (entry) {
      return { position: entry[0], branch: entry[1].branch };
    });

    var out = {};
    Object.keys(b).forEach(function (k) { out[k] = b[k]; });

    out.strengthEvidence = {
      roots: roots,
      caveat: 'Diagnostic score is model-specific, not a universal BaZi scale.'
    };
    out.structure = {
      candidate: r[0][0] + ' Structure',
      secondary: r[1][0] + ' Structure',
      scores: g,
      status: 'candidate-only',
      confidence: (r[0][1] - r[1][1]) >= 1.5 ? 'Medium' : 'Low'
    };
    out.groupInteractions = multi;
    out.usefulElementMethods = {
      balancing:      { status: 'implemented-heuristic' },
      climate:        { status: 'coarse-candidate-only' },
      mediation:      { status: 'not-implemented' },
      illnessRemedy:  { status: 'not-implemented' },
      structureMethod:{ status: 'not-implemented' },
      resolutionStatus: 'provisional-or-manual-review'
    };
    out.luckInteraction = luckPillar ? {
      status: 'interaction-signals-only',
      introducedTenGod: tenGod(p.day.stem, luckPillar.stem),
      introducedElement: STEMS[luckPillar.stem].element,
      branch: luckPillar.branch,
      warning: 'Direction and start age are not calculated.'
    } : { status: 'not-requested' };
    out.limitations = [
      'No practitioner-reviewed corpus included',
      'Luck direction and start age not calculated',
      'Transformation completion unresolved',
      'Advanced Useful Element methods incomplete'
    ];

    return out;
  }

  /* ==========================================================================
     SECTION 3 — rule matching
     ==========================================================================
     internal/engine-v3-candidate/rules_example.json ships one hypothesis rule
     and no code in the candidate package reads it. There is no rule-matching
     implementation to port, and inventing match semantics would be inventing
     findings. The status below is what the evidence panel reports.
     ========================================================================== */

  var RULE_MATCHING = {
    status: 'not-implemented',
    detail: 'No rule engine exists in the candidate package. rules_example.json is not read by any code.',
    matched: []
  };

  /* ==========================================================================
     SECTION 4 — export surface
     ========================================================================== */

  root.BaziV3 = {
    STEMS: STEMS,
    BRANCHES: BRANCHES,
    tenGod: tenGod,
    analyseBazi: analyseBazi,
    analyseAdvanced: analyseAdvanced,
    RULE_MATCHING: RULE_MATCHING,
    ENGINE_VERSION: '0.3.0-strongest-responsible-candidate',
    CERTIFICATION: 'UNVALIDATED',
    BUILD: 'browser-classic-script'
  };

})(typeof window !== 'undefined' ? window : globalThis);
