/* ==========================================================================
   GOH DIP TONG — Stage 3 UI logic
   ==========================================================================

   This file renders Stage 2 output. It does not produce Stage 2 output.

   THE ONE RULE
   ------------
   Every number on the page is a string taken from a snapshot field. Nothing
   here multiplies, divides, adds or subtracts a financial value; there is no
   target price derived in the browser, no percentage computed from a ratio, no
   total summed from parts. Where a figure would need arithmetic to look nicer
   — completeness as a percentage, say — the raw value is shown instead and the
   label carries the units. A prettier number that the engine never produced is
   a different number.

   Every rendered figure also carries `data-record-ref` and `data-raw`, so the
   test suite can assert that what the page shows is byte-identical to what the
   snapshot said, and that Uncle View and Analyst View cite the same record IDs.

   THE OTHER RULE
   --------------
   No snapshot string is ever interpreted as markup. There is no innerHTML in
   this file. Text reaches the DOM through textContent and nothing else, and
   children are cleared with replaceChildren(). Evidence links are rendered as
   links only when the URL parses as https:.
   ========================================================================== */
(function (global) {
  'use strict';

  var GDT = {};

  /* ---------------------------------------------------------------- paths */

  GDT.UNIVERSE_PATH = 'config/goh-dip-tong/idx30.current.json';
  GDT.SNAPSHOT_DIR = 'data/goh-dip-tong/research-snapshots/current/';
  GDT.FIXTURE_DIR = 'engine/goh_dip_tong/fixtures/ui_states/';

  /* Rights-restricted collector output lives here and is git-ignored. The UI
     must never reach for it, so the fetch wrapper refuses the path outright
     rather than relying on nobody typing it. */
  GDT.FORBIDDEN_PATH_SEGMENT = '_private';

  /* ------------------------------------------------------------ vocabulary */

  GDT.SCHEMA_MAJOR = '1';
  GDT.MODES = ['FIXTURE_TEST_ONLY', 'PRODUCTION'];
  GDT.UI_STATES = ['FULL_RESEARCH', 'MODEL_UNDER_VALIDATION', 'ONBOARDING',
                   'STALE', 'SUSPENDED', 'PARTIAL'];
  GDT.RESEARCH_STATUSES = ['DISCOVERY', 'FINANCIALS_VALIDATED',
                           'MODEL_UNDER_VALIDATION', 'FULL_RESEARCH',
                           'MODEL_SUSPENDED', 'STALE'];
  GDT.VALUATION_STATUSES = ['VALUED', 'REFUSED'];
  GDT.QUALITY_STATUSES = ['VALID', 'SUSPECT', 'INVALID', 'UNVALIDATED'];

  GDT.FIXTURE_FILES = [
    { state: 'FULL_RESEARCH', file: 'FULL_RESEARCH.json' },
    { state: 'MODEL_UNDER_VALIDATION', file: 'MODEL_UNDER_VALIDATION.json' },
    { state: 'PARTIAL', file: 'PARTIAL.json' },
    { state: 'ONBOARDING', file: 'ONBOARDING.json' },
    { state: 'STALE', file: 'STALE.json' },
    { state: 'SUSPENDED', file: 'SUSPENDED.json' }
  ];

  /* --------------------------------------------------------- fixed strings */

  GDT.TEXT = {
    NOT_PUBLISHED: 'NOT PUBLISHED',
    VALUATION_NOT_PUBLISHED: 'VALUATION NOT PUBLISHED',
    DATA_REFERENCE_UNAVAILABLE: 'DATA REFERENCE UNAVAILABLE',
    CONFIG_UNAVAILABLE: 'CONFIG UNAVAILABLE',
    SNAPSHOT_UNAVAILABLE: 'RESEARCH SNAPSHOT UNAVAILABLE',
    FIXTURE_L1: 'FIXTURE TEST ONLY',
    FIXTURE_L2: 'NOT LIVE, CURRENT OR AUTHORITATIVE ANALYSIS'
  };

  /* The eight research sections, in the order the specification fixes them.
     `uncle` is the plain-language heading; `analyst` is the inline detail
     drawer beneath it. Nothing reorders this list at runtime. */
  GDT.SECTIONS = [
    { key: 'verdict',   uncle: "UNCLE'S VERDICT",             analyst: 'ANALYST THESIS' },
    { key: 'money',     uncle: 'HOW THIS COMPANY MAKES MONEY', analyst: 'BUSINESS DRIVER MODEL' },
    { key: 'health',    uncle: 'BUSINESS HEALTH',              analyst: 'FINANCIAL DETAIL' },
    { key: 'changed',   uncle: 'WHAT CHANGED',                 analyst: 'ESTIMATE REVISIONS' },
    { key: 'worth',     uncle: 'WHAT MAY IT BE WORTH?',        analyst: 'VALUATION MODEL' },
    { key: 'wrong',     uncle: 'WHY UNCLE MAY BE WRONG',       analyst: 'COUNTER-THESIS' },
    { key: 'breaks',    uncle: 'WHAT BREAKS THE THESIS?',      analyst: 'MONITORING RULES' },
    { key: 'evidence',  uncle: 'EVIDENCE AND MODEL AUDIT',
      analyst: 'SOURCES, QUALITY, FORMULAS AND VERSIONS' }
  ];

  GDT.LOADING_STEPS = ['COMPANY PROFILE', 'VERIFIED FINANCIALS', 'RESEARCH SNAPSHOT',
                       'VALUATION STATUS', 'COUNTER-THESIS'];

  /* Evidence rows are long and there are up to 105 of them. Render a window
     first and let the reader ask for the rest. */
  GDT.EVIDENCE_PAGE = 25;

  /* ======================================================================
     PURE HELPERS — no DOM, no network. These are what the unit tests drive.
     ====================================================================== */

  /** Only https: links are ever rendered as links. Everything else — including
   *  javascript:, data:, file: and protocol-relative URLs — is shown as inert
   *  text, because a snapshot is external content and a link is an action. */
  GDT.isSafeHttpUrl = function (value) {
    if (typeof value !== 'string' || value === '') return false;
    var parsed;
    try { parsed = new URL(value); } catch (e) { return false; }
    return parsed.protocol === 'https:';
  };

  /** Refuses any path reaching into the rights-restricted private tree. */
  GDT.isPermittedPath = function (path) {
    if (typeof path !== 'string' || path === '') return false;
    return path.split('/').indexOf(GDT.FORBIDDEN_PATH_SEGMENT) === -1;
  };

  function majorOf(version) {
    return typeof version === 'string' ? version.split('.')[0] : null;
  }

  function isFiniteNumber(v) {
    return typeof v === 'number' && isFinite(v);
  }

  /** A displayable string for a snapshot value.
   *
   *  Null is never zero and never "N/A" standing in for a figure: it is the
   *  words NOT PUBLISHED. The number itself is passed through String() — no
   *  scaling, no rounding, no unit conversion, because every one of those is
   *  arithmetic on a published figure. Grouping is applied for readability
   *  only, and the ungrouped original travels beside it in data-raw. */
  GDT.displayValue = function (raw) {
    if (raw === null || raw === undefined || raw === '') return null;
    if (typeof raw === 'number') {
      if (!isFinite(raw)) return null;
      return raw.toLocaleString('en-US', { maximumFractionDigits: 4 });
    }
    return String(raw);
  };

  /** Validate the IDX30 picker config before anything renders from it. */
  GDT.validateUniverse = function (doc) {
    var errors = [];
    if (!doc || typeof doc !== 'object') {
      return { ok: false, errors: ['universe document is not an object'] };
    }
    if (majorOf(doc.schemaVersion) !== GDT.SCHEMA_MAJOR) {
      errors.push('unsupported schemaVersion: ' + String(doc.schemaVersion));
    }
    if (!Array.isArray(doc.constituents)) {
      errors.push('constituents is missing or not an array');
    } else {
      doc.constituents.forEach(function (c, i) {
        if (!c || typeof c !== 'object') { errors.push('constituent ' + i + ' is not an object'); return; }
        if (typeof c.ticker !== 'string' || !/^[A-Z]{4}$/.test(c.ticker)) {
          errors.push('constituent ' + i + ' has no valid ticker');
        }
        if (typeof c.name !== 'string' || c.name === '') {
          errors.push(String(c.ticker) + ' has no name');
        }
        if (typeof c.coverageStatus !== 'string') {
          errors.push(String(c.ticker) + ' has no coverageStatus');
        }
      });
    }
    if (typeof doc.effectiveFrom !== 'string') errors.push('effectiveFrom is missing');
    return { ok: errors.length === 0, errors: errors };
  };

  /** Only active constituents render. Sorted by ticker so the order is the
   *  same on every device and every reload. */
  GDT.activeConstituents = function (doc) {
    if (!doc || !Array.isArray(doc.constituents)) return [];
    return doc.constituents
      .filter(function (c) { return c && c.active === true; })
      .slice()
      .sort(function (a, b) { return a.ticker < b.ticker ? -1 : a.ticker > b.ticker ? 1 : 0; });
  };

  /** Search matches ticker or company name, case-insensitively. */
  GDT.searchConstituents = function (list, query) {
    var q = String(query || '').trim().toLowerCase();
    if (q === '') return list.slice();
    return list.filter(function (c) {
      return String(c.ticker).toLowerCase().indexOf(q) !== -1 ||
             String(c.name).toLowerCase().indexOf(q) !== -1;
    });
  };

  /** Validate a research snapshot before a single figure reaches the screen. */
  GDT.validateSnapshot = function (doc, expectedTicker) {
    var errors = [];
    if (!doc || typeof doc !== 'object') {
      return { ok: false, errors: ['snapshot document is not an object'] };
    }
    if (majorOf(doc.schemaVersion) !== GDT.SCHEMA_MAJOR) {
      errors.push('unsupported schemaVersion: ' + String(doc.schemaVersion));
    }
    if (typeof doc.ticker !== 'string' || doc.ticker === '') {
      errors.push('snapshot has no ticker');
    } else if (expectedTicker && doc.ticker !== expectedTicker) {
      errors.push('ticker mismatch: asked for ' + expectedTicker + ', got ' + doc.ticker);
    }
    if (GDT.MODES.indexOf(doc.mode) === -1) {
      errors.push('unknown mode: ' + String(doc.mode));
    }
    if (GDT.UI_STATES.indexOf(doc.uiState) === -1) {
      errors.push('unknown uiState: ' + String(doc.uiState));
    }
    if (GDT.RESEARCH_STATUSES.indexOf(doc.researchStatus) === -1) {
      errors.push('unknown researchStatus: ' + String(doc.researchStatus));
    }
    var val = doc.valuation;
    if (!val || typeof val !== 'object') {
      errors.push('valuation section is missing');
    } else if (GDT.VALUATION_STATUSES.indexOf(val.status) === -1) {
      errors.push('unknown valuation status: ' + String(val.status));
    } else if (val.status === 'REFUSED') {
      if (typeof val.reason !== 'string' || val.reason === '') errors.push('refusal has no reason');
      if (typeof val.note !== 'string' || val.note === '') errors.push('refusal has no note');
      if (!Array.isArray(val.failedGates)) errors.push('refusal has no failedGates');
      if (!Array.isArray(val.missingInputs)) errors.push('refusal has no missingInputs');
    }
    if (!doc.freshness || typeof doc.freshness !== 'object') {
      errors.push('freshness section is missing');
    } else if (typeof doc.freshness.asOf !== 'string') {
      errors.push('freshness.asOf is missing');
    }
    if (!doc.quality || typeof doc.quality !== 'object') {
      errors.push('quality section is missing');
    } else if (GDT.QUALITY_STATUSES.indexOf(doc.quality.status) === -1) {
      errors.push('unknown quality status: ' + String(doc.quality.status));
    }
    if (!Array.isArray(doc.evidence)) errors.push('evidence section is missing');
    if (!doc.modelAudit || typeof doc.modelAudit !== 'object') {
      errors.push('modelAudit section is missing');
    } else {
      if (typeof doc.modelAudit.formulaRegistryHash !== 'string') {
        errors.push('modelAudit.formulaRegistryHash is missing');
      }
      if (!doc.modelAudit.inputProvenance || typeof doc.modelAudit.inputProvenance !== 'object') {
        errors.push('modelAudit.inputProvenance is missing');
      }
    }
    if (!Array.isArray(doc.disclaimers) || doc.disclaimers.length === 0) {
      errors.push('disclaimers are missing');
    }
    return { ok: errors.length === 0, errors: errors };
  };

  GDT.isFixtureMode = function (doc) {
    return !!doc && doc.mode !== 'PRODUCTION';
  };

  GDT.isStale = function (doc) {
    return !!doc && (doc.uiState === 'STALE' || (!!doc.freshness && doc.freshness.stale === true));
  };

  /** Index every calculated record the Analyst View carries, by its ref.
   *  This is the single lookup both views resolve through, which is what makes
   *  "the same record ID in both places" a fact rather than an intention. */
  GDT.recordIndex = function (doc) {
    var index = Object.create(null);
    ['analystView', 'uncleView'].forEach(function (view) {
      var v = doc && doc[view];
      if (!v || !Array.isArray(v.items)) return;
      v.items.forEach(function (item) {
        if (item && typeof item.ref === 'string' && !(item.ref in index)) {
          index[item.ref] = item;
        }
      });
    });
    return index;
  };

  /** Resolve a record ref for display. A missing ref is reported, never
   *  recomputed and never quietly dropped. */
  GDT.resolveRecord = function (index, ref) {
    var item = index[ref];
    if (!item) {
      return { found: false, ref: ref, text: GDT.TEXT.DATA_REFERENCE_UNAVAILABLE, raw: null };
    }
    var shown = GDT.displayValue(item.value);
    return {
      found: true,
      ref: ref,
      raw: item.value,
      unit: item.unit,
      label: item.label,
      missingReason: item.missingReason,
      text: shown === null ? GDT.TEXT.NOT_PUBLISHED : shown
    };
  };

  /** The market price, or the words NOT PUBLISHED with the reason beside them.
   *  There is no price in any snapshot today: the provider's rights are
   *  PRIVATE_RESEARCH_ONLY, which is a licensing outcome and not a bug. */
  GDT.marketPrice = function (doc) {
    var m = (doc && doc.marketImplied) || {};
    var available = m.available === true;
    var close = m.close;
    if (!available || !isFiniteNumber(close)) {
      return {
        available: false,
        text: GDT.TEXT.NOT_PUBLISHED,
        raw: null,
        asOf: null,
        reason: typeof m.reason === 'string' ? m.reason : null,
        rightsStatus: typeof m.rightsStatus === 'string' ? m.rightsStatus : null
      };
    }
    return { available: true, text: GDT.displayValue(close), raw: close, reason: null,
             asOf: typeof m.asOfDate === 'string' ? m.asOfDate : null,
             rightsStatus: m.rightsStatus || null };
  };

  /** The headline figure, or the refusal. Reads only; computes nothing. */
  GDT.headline = function (doc) {
    var val = (doc && doc.valuation) || {};
    if (val.status !== 'VALUED') {
      return {
        valued: false,
        text: GDT.TEXT.VALUATION_NOT_PUBLISHED,
        reason: val.reason || null,
        note: val.note || null,
        failedGates: Array.isArray(val.failedGates) ? val.failedGates : [],
        missingInputs: Array.isArray(val.missingInputs) ? val.missingInputs : []
      };
    }
    var order = Array.isArray(val.scenarioOrder) ? val.scenarioOrder : [];
    var scenarios = val.scenarios || {};
    var base = scenarios.BASE || scenarios[order[0]] || {};
    var ref = base.primary && base.primary.valuePerShare ? refOf(base.primary.valuePerShare) : null;
    var shown = GDT.displayValue(base.valuePerShare);
    return {
      valued: true,
      method: val.method || null,
      raw: base.valuePerShare,
      ref: ref,
      text: shown === null ? GDT.TEXT.NOT_PUBLISHED : shown,
      unit: base.primary && base.primary.valuePerShare ? base.primary.valuePerShare.unit : null,
      order: order,
      scenarios: scenarios
    };
  };

  /** Rebuild a Calculated record's ref from its serialised form. The engine
   *  builds this identity as metric|periodType|periodEnd|segment|scenario|formula;
   *  reproducing it here is string assembly, not arithmetic. */
  function refOf(calc) {
    if (!calc || typeof calc !== 'object') return null;
    var segment = calc.segment || 'CONSOLIDATED';
    return [calc.metric, calc.periodType, calc.periodEnd, segment, calc.scenario, calc.formulaId]
      .join('|');
  }
  GDT.refOf = refOf;

  /** The 3x3 sensitivity table: three scenarios by three methods, every cell a
   *  figure the engine already produced. */
  GDT.sensitivityGrid = function (doc) {
    var val = (doc && doc.valuation) || {};
    if (val.status !== 'VALUED') return null;
    var order = Array.isArray(val.scenarioOrder) ? val.scenarioOrder : [];
    var methods = [val.method || 'RESIDUAL_INCOME'];
    var base = (val.scenarios || {})[order[0]] || {};
    (base.crossChecks || []).forEach(function (c) { methods.push(c.method); });

    var rows = order.map(function (name) {
      var sc = (val.scenarios || {})[name] || {};
      var cells = [];
      cells.push(cellFor(sc.primary, sc.valuePerShare));
      (sc.crossChecks || []).forEach(function (c) {
        cells.push(cellFor(c, c.valuePerShare ? c.valuePerShare.value : null));
      });
      return { scenario: name, cells: cells };
    });
    return { methods: methods, rows: rows };

    function cellFor(result, rawValue) {
      var vps = result && result.valuePerShare ? result.valuePerShare : null;
      var raw = vps ? vps.value : rawValue;
      var shown = GDT.displayValue(raw);
      return {
        ref: vps ? refOf(vps) : null,
        raw: raw,
        text: shown === null ? GDT.TEXT.NOT_PUBLISHED : shown
      };
    }
  };

  /* ======================================================================
     DOM — textContent only. There is no innerHTML in this file.
     ====================================================================== */

  function el(tag, attrs, kids) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        var v = attrs[k];
        if (v === null || v === undefined || v === false) return;
        if (k === 'text') { node.textContent = String(v); return; }
        if (k === 'class') { node.className = String(v); return; }
        if (v === true) { node.setAttribute(k, ''); return; }
        node.setAttribute(k, String(v));
      });
    }
    (kids || []).forEach(function (kid) {
      if (kid === null || kid === undefined) return;
      node.appendChild(typeof kid === 'string' ? document.createTextNode(kid) : kid);
    });
    return node;
  }
  GDT.el = el;

  function clear(node) { if (node) node.replaceChildren(); }

  /** A figure, tagged with the record it came from so a test can prove the
   *  page did not invent it. */
  function figure(text, opts) {
    var o = opts || {};
    var node = el('span', { class: o.class || 'fig', text: text });
    if (o.ref) node.setAttribute('data-record-ref', o.ref);
    if (o.raw !== null && o.raw !== undefined) node.setAttribute('data-raw', String(o.raw));
    if (text === GDT.TEXT.NOT_PUBLISHED || text === GDT.TEXT.DATA_REFERENCE_UNAVAILABLE) {
      node.classList.add('not-published');
    }
    return node;
  }

  function kv(pairs) {
    var dl = el('dl', { class: 'kv' });
    pairs.forEach(function (p) {
      if (!p) return;
      var dd = el('dd');
      if (typeof p[1] === 'string') dd.textContent = p[1];
      else if (p[1]) dd.appendChild(p[1]);
      dl.appendChild(el('div', null, [el('dt', { text: p[0] }), dd]));
    });
    return dl;
  }

  function chip(label, value, tone) {
    return el('span', { class: 'chip' + (tone ? ' ' + tone : '') }, [
      document.createTextNode(label + ' '),
      el('b', { text: value })
    ]);
  }

  function para(text) { return el('p', { text: text }); }

  /* ======================================================================
     APPLICATION
     ====================================================================== */

  GDT.create = function (options) {
    var opts = options || {};
    var doc = opts.document || global.document;
    var fetchImpl = opts.fetchImpl || (global.fetch ? global.fetch.bind(global) : null);
    var store = opts.sessionStore || safeSessionStorage();
    var base = opts.basePath || '';

    var app = {
      universe: null,          // validated picker config
      constituents: [],        // active, sorted
      filtered: [],
      selected: null,          // ticker string
      snapshot: null,          // validated snapshot
      index: Object.create(null),
      accordions: [],
      historyPushed: false
    };

    var $ = function (id) { return doc.getElementById(id); };

    /* ------------------------------------------------------------ network */

    function getJson(path) {
      if (!GDT.isPermittedPath(path)) {
        return Promise.reject(new Error('refused path: ' + path));
      }
      if (!fetchImpl) return Promise.reject(new Error('no fetch implementation'));
      return fetchImpl(base + path, { credentials: 'same-origin' }).then(function (res) {
        if (!res || !res.ok) {
          throw new Error('HTTP ' + (res ? res.status : '?') + ' for ' + path);
        }
        return res.json();
      });
    }
    app.getJson = getJson;

    /* -------------------------------------------------------- page states */

    function showPage(name) {
      ['select', 'loading', 'result'].forEach(function (p) {
        var node = doc.querySelector('[data-page="' + p + '"]');
        if (node) node.classList.toggle('on', p === name);
      });
      var live = $('gdt-page-announce');
      if (live) live.textContent = 'Showing ' + name + ' view.';
    }
    app.showPage = showPage;

    /* ------------------------------------------------------------- picker */

    function loadUniverse() {
      return getJson(GDT.UNIVERSE_PATH).then(function (json) {
        var report = GDT.validateUniverse(json);
        if (!report.ok) throw new Error(report.errors.join('; '));
        app.universe = json;
        app.constituents = GDT.activeConstituents(json);
        renderUniverseMeta();
        renderResults(GDT.searchConstituents(app.constituents, currentQuery()));
        restoreSelection();
      }).catch(function (err) {
        app.universe = null;
        app.constituents = [];
        renderConfigUnavailable(err);
      });
    }
    app.loadUniverse = loadUniverse;

    function currentQuery() {
      var input = $('gdt-search');
      return input ? input.value : '';
    }

    function renderUniverseMeta() {
      var meta = $('gdt-picker-meta');
      if (!meta || !app.universe) return;
      clear(meta);
      var u = app.universe;
      var authoritative = u.authoritative === true;
      meta.appendChild(el('span', {
        class: 'tag' + (authoritative ? '' : ' warn'),
        text: authoritative ? 'AUTHORITATIVE' : 'NOT AUTHORITATIVE'
      }));
      meta.appendChild(el('span', { class: 'tag', text: 'PROVENANCE ' + String(u.provenance || 'UNKNOWN') }));
      meta.appendChild(doc.createTextNode(
        ' effective from ' + String(u.effectiveFrom) +
        (u.effectiveTo ? ' to ' + String(u.effectiveTo) : ' (current)') +
        ' · ' + String(app.constituents.length) + ' active constituents'
      ));
    }

    function renderConfigUnavailable(err) {
      var host = $('gdt-picker-host');
      if (!host) return;
      clear(host);
      host.appendChild(el('div', { class: 'failsoft', role: 'alert' }, [
        el('h2', { class: 'pixel', text: GDT.TEXT.CONFIG_UNAVAILABLE }),
        para('The IDX30 company list could not be loaded, so there is nothing to choose from. ' +
             'No list is substituted: a hard-coded fallback would show companies this build ' +
             'cannot actually verify.'),
        para('The fixture demonstration selector below still works.'),
        el('p', { class: 'why', text: 'reason: ' + String(err && err.message ? err.message : err) })
      ]));
      var cta = $('gdt-run');
      if (cta) cta.disabled = true;
    }

    function renderResults(list) {
      app.filtered = list;
      var host = $('gdt-results');
      if (!host) return;
      clear(host);
      if (!list.length) {
        host.appendChild(el('li', null, [
          el('p', { class: 'results-empty', text: 'No IDX30 company matches that search.' })
        ]));
        announceCount(0);
        return;
      }
      list.forEach(function (c) {
        var selected = app.selected === c.ticker;
        var btn = el('button', {
          type: 'button', class: 'result-btn', 'data-ticker': c.ticker,
          role: 'option', 'aria-selected': selected ? 'true' : 'false',
          id: 'gdt-opt-' + c.ticker
        }, [
          el('span', { class: 'r-mark', 'aria-hidden': 'true' }),
          el('span', { class: 'r-body' }, [
            el('span', { class: 'r-ticker', text: c.ticker }),
            el('span', { class: 'r-name', text: c.name }),
            el('span', {
              class: 'r-meta',
              text: [c.sectorName || c.sectorCode || '', c.industryName || c.industryCode || '',
                     'COVERAGE ' + String(c.coverageStatus)].filter(Boolean).join(' · ')
            })
          ])
        ]);
        btn.addEventListener('click', function () { selectTicker(c.ticker); });
        host.appendChild(el('li', { role: 'presentation' }, [btn]));
      });
      announceCount(list.length);
    }

    function announceCount(n) {
      var live = $('gdt-results-count');
      if (live) live.textContent = n + (n === 1 ? ' company matches.' : ' companies match.');
    }

    function selectTicker(ticker) {
      app.selected = ticker;
      try { store.setItem('gdt.selectedTicker', ticker); } catch (e) { /* private mode */ }
      var host = $('gdt-results');
      if (host) {
        Array.prototype.forEach.call(host.querySelectorAll('.result-btn'), function (b) {
          b.setAttribute('aria-selected', b.getAttribute('data-ticker') === ticker ? 'true' : 'false');
        });
      }
      var cta = $('gdt-run');
      if (cta) {
        cta.disabled = false;
        var label = $('gdt-run-label');
        if (label) label.textContent = 'RUN THE NUMBERS — ' + ticker;
      }
    }
    app.selectTicker = selectTicker;

    function restoreSelection() {
      var remembered = null;
      try { remembered = store.getItem('gdt.selectedTicker'); } catch (e) { remembered = null; }
      if (!remembered) return;
      var known = app.constituents.some(function (c) { return c.ticker === remembered; });
      if (known) selectTicker(remembered);
    }

    /* ----------------------------------------------------------- loading */

    function renderLoading(stepIndex) {
      var host = $('gdt-loading-steps');
      if (!host) return;
      clear(host);
      GDT.LOADING_STEPS.forEach(function (label, i) {
        var state = i < stepIndex ? 'done' : (i === stepIndex ? 'active' : 'waiting');
        host.appendChild(el('li', { 'data-state': state, 'data-step': label }, [
          el('span', { class: 'lstate', text: state === 'done' ? 'OK' : state === 'active' ? 'READ' : 'WAIT' }),
          el('span', { text: label })
        ]));
      });
    }
    app.renderLoading = renderLoading;

    /* ---------------------------------------------------------- snapshot */

    function loadSnapshot(ticker) {
      showPage('loading');
      renderLoading(0);
      var path = GDT.SNAPSHOT_DIR + ticker + '.json';
      return getJson(path).then(function (json) {
        renderLoading(2);
        var report = GDT.validateSnapshot(json, ticker);
        if (!report.ok) throw new Error(report.errors.join('; '));
        renderLoading(GDT.LOADING_STEPS.length);
        renderSnapshot(json, { source: 'snapshot', path: path });
      }).catch(function (err) {
        renderSnapshotUnavailable(ticker, err);
      });
    }
    app.loadSnapshot = loadSnapshot;

    function loadFixture(file) {
      showPage('loading');
      renderLoading(0);
      var path = GDT.FIXTURE_DIR + file;
      return getJson(path).then(function (json) {
        renderLoading(2);
        var report = GDT.validateSnapshot(json, null);
        if (!report.ok) throw new Error(report.errors.join('; '));
        renderLoading(GDT.LOADING_STEPS.length);
        renderSnapshot(json, { source: 'fixture', path: path });
      }).catch(function (err) {
        renderSnapshotUnavailable(file, err);
      });
    }
    app.loadFixture = loadFixture;

    function renderSnapshotUnavailable(what, err) {
      showPage('result');
      var host = $('gdt-result-host');
      if (!host) return;
      clear(host);
      host.appendChild(el('div', { class: 'failsoft', role: 'alert' }, [
        el('h2', { class: 'pixel', text: GDT.TEXT.SNAPSHOT_UNAVAILABLE }),
        para('No research snapshot could be read for ' + String(what) + '.'),
        para('Nothing is estimated in its place. The company picker is still ' +
             'available, so another target can be chosen.'),
        el('p', { class: 'why', text: 'reason: ' + String(err && err.message ? err.message : err) })
      ]));
      host.appendChild(backToPicker());
    }

    function backToPicker() {
      var btn = el('button', { type: 'button', class: 'cta pixel' }, [
        el('span', { text: 'CHOOSE ANOTHER TARGET' })
      ]);
      btn.addEventListener('click', function () { showPage('select'); });
      return btn;
    }

    /* ======================================================================
       SNAPSHOT RENDERING
       ====================================================================== */

    function renderSnapshot(snapshot, meta) {
      app.snapshot = snapshot;
      app.index = GDT.recordIndex(snapshot);
      app.accordions = [];

      var fixture = GDT.isFixtureMode(snapshot);
      var stale = GDT.isStale(snapshot);
      setFixtureBanner(fixture, snapshot, meta);

      var host = $('gdt-result-host');
      if (!host) return;
      clear(host);

      host.appendChild(renderHead(snapshot, stale));
      host.appendChild(renderStateNotice(snapshot));
      host.appendChild(renderVerdictBlock(snapshot, stale));
      host.appendChild(renderAboveFold(snapshot, stale));
      host.appendChild(renderBulkControls());

      GDT.SECTIONS.forEach(function (section) {
        host.appendChild(renderSection(section, snapshot, stale));
      });

      host.appendChild(renderDisclaimers(snapshot));
      host.appendChild(backToPicker());

      showPage('result');
      var heading = $('gdt-result-heading');
      if (heading && heading.focus) heading.focus();
    }
    app.renderSnapshot = renderSnapshot;

    function setFixtureBanner(on, snapshot, meta) {
      var banner = $('gdt-fixture-banner');
      if (!banner) return;
      banner.classList.toggle('on', !!on);
      if (!on) { clear(banner); return; }
      clear(banner);
      banner.appendChild(el('span', { class: 'fb-badge pixel', text: GDT.TEXT.FIXTURE_L1 }));
      banner.appendChild(el('p', { class: 'fb-line', text: GDT.TEXT.FIXTURE_L2 }));
      banner.appendChild(el('p', {
        class: 'fb-sub',
        text: 'mode ' + String(snapshot.mode) + ' · source ' +
              (meta && meta.source === 'fixture' ? 'engine UI-state fixture' : 'published snapshot') +
              ' · this describes no real company and no real market.'
      }));
    }

    function renderHead(s, stale) {
      var head = el('header', { class: 'result-head' });
      head.appendChild(el('h2', {
        class: 'rh-ticker pixel', id: 'gdt-result-heading', tabindex: '-1', text: s.ticker
      }));
      head.appendChild(el('p', { class: 'rh-name', text: String((s.company && s.company.name) || '') }));

      var bar = el('div', { class: 'statebar' });
      bar.appendChild(chip('MODEL', String((s.company && s.company.modelFamily) || 'NONE')));
      bar.appendChild(chip('RESEARCH', String(s.researchStatus)));
      bar.appendChild(chip('UI STATE', String(s.uiState), uiStateTone(s.uiState)));
      bar.appendChild(chip('MODEL VER', String(s.modelVersion)));
      bar.appendChild(chip('DATA MODE', String(s.mode), s.mode === 'PRODUCTION' ? 'ok' : 'bad'));
      bar.appendChild(chip('QUALITY', String((s.quality && s.quality.status) || 'UNKNOWN'),
                           s.quality && s.quality.status === 'VALID' ? 'ok' : 'warn'));
      if (stale) bar.appendChild(chip('FRESHNESS', 'STALE', 'warn'));
      head.appendChild(bar);
      return head;
    }

    function uiStateTone(state) {
      if (state === 'FULL_RESEARCH') return 'ok';
      if (state === 'SUSPENDED' || state === 'STALE') return 'bad';
      return 'warn';
    }

    /* The per-state notice. Each carries its exact required wording. */
    var STATE_NOTICE = {
      MODEL_UNDER_VALIDATION: {
        title: 'MODEL UNDER VALIDATION',
        lines: ['Historical financial information may be available.',
                'A complete valuation is not published.']
      },
      ONBOARDING: {
        title: 'COVERAGE ONBOARDING',
        lines: ['Company configuration exists.',
                'The model family or required data contract is not yet available.']
      },
      STALE: {
        title: 'STALE RESEARCH',
        lines: ['A newer filing or freshness threshold requires review.',
                'The previous verified snapshot remains visible with its original timestamps.']
      },
      SUSPENDED: {
        title: 'MODEL SUSPENDED',
        lines: ['Research output is temporarily unavailable.',
                'See the model-audit section for the suspension reason.']
      },
      PARTIAL: {
        title: 'PARTIAL RESEARCH',
        lines: ['Some financial information is available.',
                'Required inputs are missing, so a complete valuation is not published.']
      }
    };

    function renderStateNotice(s) {
      var spec = STATE_NOTICE[s.uiState];
      if (!spec) return el('div', { hidden: true, 'data-state-notice': 'none' });
      var box = el('div', { class: 'failsoft', 'data-state-notice': s.uiState, role: 'note' });
      box.appendChild(el('h3', { class: 'pixel', text: spec.title }));
      spec.lines.forEach(function (line) { box.appendChild(para(line)); });

      if (s.uiState === 'PARTIAL' || s.uiState === 'MODEL_UNDER_VALIDATION') {
        var v = s.valuation || {};
        if (Array.isArray(v.missingInputs) && v.missingInputs.length) {
          box.appendChild(el('p', { class: 'why', text: 'missing inputs: ' + v.missingInputs.join(', ') }));
        }
        if (Array.isArray(v.failedGates) && v.failedGates.length) {
          box.appendChild(el('p', { class: 'why', text: 'failed gates: ' + v.failedGates.join(', ') }));
        }
      }
      if (s.uiState === 'STALE' && s.freshness) {
        box.appendChild(el('p', {
          class: 'why',
          text: 'financials through ' + String(s.freshness.newestPublishedAt || 'unknown') +
                ' · ' + String(s.freshness.ageDays) + ' days old at the ' + String(s.freshness.asOf) + ' cutoff'
        }));
      }
      if (s.uiState === 'SUSPENDED') {
        box.appendChild(el('p', {
          class: 'why',
          text: 'coverage status ' + String((s.coverage && s.coverage.coverageStatus) || 'unknown') +
                ' · refusal ' + String((s.valuation && s.valuation.reason) || 'unknown')
        }));
      }
      return box;
    }

    function renderVerdictBlock(s, stale) {
      var h = GDT.headline(s);
      var box = el('div', { class: 'verdict ' + (h.valued ? 'valued' : 'refused'),
                            'data-valuation': h.valued ? 'VALUED' : 'REFUSED' });

      if (!h.valued) {
        box.appendChild(el('p', { class: 'verdict-label pixel', text: 'VALUATION STATUS' }));
        box.appendChild(el('p', { class: 'verdict-value pixel', text: GDT.TEXT.VALUATION_NOT_PUBLISHED }));
        box.appendChild(kv([
          ['REFUSAL REASON', String(h.reason || 'UNKNOWN')],
          ['FAILED GATES', h.failedGates.length ? h.failedGates.join(', ') : 'none recorded'],
          ['MISSING INPUTS', h.missingInputs.length ? h.missingInputs.join(', ') : 'none recorded']
        ]));
        if (h.note) box.appendChild(el('p', { class: 'verdict-sub', text: h.note }));
        return box;
      }

      box.appendChild(el('p', { class: 'verdict-label pixel', text: 'BASE VALUE PER SHARE' }));
      var value = el('p', { class: 'verdict-value' }, [
        el('span', { class: 'unit', text: String(h.unit || '') }),
        figure(h.text, { ref: h.ref, raw: h.raw, class: 'v' })
      ]);
      if (stale) value.appendChild(el('span', { class: 'stale-mark pixel', text: 'STALE' }));
      box.appendChild(value);
      box.appendChild(el('p', {
        class: 'verdict-sub',
        text: 'Primary method ' + String(h.method) + '. Cross-checks are sensitivity checks, ' +
              'not an equal-weight second opinion, and no blended value is produced.'
      }));

      var range = el('div', { class: 'verdict-range' });
      h.order.forEach(function (name) {
        var sc = h.scenarios[name] || {};
        var ref = sc.primary && sc.primary.valuePerShare ? refOf(sc.primary.valuePerShare) : null;
        var shown = GDT.displayValue(sc.valuePerShare);
        range.appendChild(el('div', { class: 'vr' }, [
          el('span', { class: 'vr-k', text: name }),
          el('span', { class: 'vr-v' }, [
            figure(shown === null ? GDT.TEXT.NOT_PUBLISHED : shown,
                   { ref: ref, raw: sc.valuePerShare })
          ])
        ]));
      });
      box.appendChild(range);
      return box;
    }

    function renderAboveFold(s, stale) {
      var price = GDT.marketPrice(s);
      var panel = el('section', { class: 'panel', 'aria-labelledby': 'gdt-af-title' });
      panel.appendChild(el('h3', { class: 'panel-title pixel', id: 'gdt-af-title', text: 'AT A GLANCE' }));

      var priceNode = figure(price.text, { raw: price.raw });
      var quality = s.quality || {};
      var fresh = s.freshness || {};
      var thesisAvailable = s.thesis && s.thesis.status === 'PRODUCED';

      panel.appendChild(kv([
        ['CURRENT PRICE', priceNode],
        ['VALUATION STATUS', String((s.valuation && s.valuation.status) || 'UNKNOWN')],
        ['QUALITY STATUS', String(quality.status || 'UNKNOWN')],
        ['COMPLETENESS (0–1)', figure(GDT.displayValue(quality.completeness) || GDT.TEXT.NOT_PUBLISHED,
                                      { raw: quality.completeness })],
        ['METRICS MISSING', String((quality.missingCriticalMetrics || []).length)],
        ['THESIS', thesisAvailable ? 'PUBLISHED' : 'NOT PUBLISHED'],
        ['UNCERTAINTY', uncertaintyText(s)],
        ['FINANCIALS THROUGH', String(fresh.newestPublishedAt || GDT.TEXT.NOT_PUBLISHED) + (stale ? ' (STALE)' : '')],
        ['PRICE AS OF', price.available ? String(price.asOf || fresh.asOf) : GDT.TEXT.NOT_PUBLISHED],
        ['MODEL CALCULATED', String(s.generatedAt || GDT.TEXT.NOT_PUBLISHED)],
        ['POINT-IN-TIME CUTOFF', String(fresh.asOf || GDT.TEXT.NOT_PUBLISHED)]
      ]));

      if (!price.available) {
        panel.appendChild(el('p', {
          class: 'note',
          text: 'No price is published. ' + String(price.reason || '') +
                (price.rightsStatus ? ' Rights status: ' + price.rightsStatus + '.' : '') +
                ' A price is not required to value a business, so this does not block research.'
        }));
      }
      return panel;
    }

    function uncertaintyText(s) {
      var val = s.valuation || {};
      if (val.status !== 'VALUED') return 'NOT PUBLISHED — no valuation';
      var order = val.scenarioOrder || [];
      return 'scenario set ' + order.join(' / ') + ' — see the sensitivity grid';
    }

    /* ------------------------------------------------- section rendering */

    function renderSection(spec, s, stale) {
      var wrap = el('section', { class: 'section', 'data-section': spec.key });
      wrap.appendChild(el('h3', { class: 'section-head pixel', text: spec.uncle }));
      var body = el('div', { class: 'section-body' });
      UNCLE[spec.key](body, s, stale);
      wrap.appendChild(body);
      wrap.appendChild(accordion(spec, s, stale));
      return wrap;
    }

    function accordion(spec, s, stale) {
      var id = 'gdt-an-' + spec.key;
      var btnId = id + '-btn';
      var wrap = el('div', { class: 'analyst' });
      var btn = el('button', {
        type: 'button', class: 'analyst-toggle pixel', id: btnId,
        'aria-expanded': 'false', 'aria-controls': id
      }, [
        el('span', { text: spec.analyst }),
        el('span', { class: 'caret', 'aria-hidden': 'true', text: '+' })
      ]);
      var panel = el('div', {
        class: 'analyst-panel', id: id, role: 'region', 'aria-labelledby': btnId, hidden: true
      });

      var built = false;
      function build() {
        if (built) return;
        ANALYST[spec.key](panel, s, stale);
        built = true;
      }
      function setOpen(open) {
        if (open) build();
        btn.setAttribute('aria-expanded', open ? 'true' : 'false');
        panel.hidden = !open;
        var caret = btn.querySelector('.caret');
        if (caret) caret.textContent = open ? '−' : '+';
      }
      btn.addEventListener('click', function () {
        /* Scroll position is preserved by construction: the panel opens below
           the button and nothing above it moves, so the button stays where the
           reader's thumb left it. No scrollIntoView, which would move it. */
        var open = btn.getAttribute('aria-expanded') !== 'true';
        setOpen(open);
        if (open) pushDetailState();
      });

      app.accordions.push({ setOpen: setOpen, isOpen: function () {
        return btn.getAttribute('aria-expanded') === 'true'; } });

      wrap.appendChild(btn);
      wrap.appendChild(panel);
      return wrap;
    }

    function renderBulkControls() {
      var wrap = el('div', { class: 'bulk' });
      var expand = el('button', { type: 'button', class: 'pixel', id: 'gdt-expand-all',
                                  text: 'EXPAND ALL ANALYST DETAIL' });
      var collapse = el('button', { type: 'button', class: 'pixel', id: 'gdt-collapse-all',
                                    text: 'COLLAPSE ALL' });
      expand.addEventListener('click', function () {
        app.accordions.forEach(function (a) { a.setOpen(true); });
        pushDetailState();
      });
      collapse.addEventListener('click', function () {
        app.accordions.forEach(function (a) { a.setOpen(false); });
      });
      wrap.appendChild(expand);
      wrap.appendChild(collapse);
      return wrap;
    }

    /* Back closes open detail before it leaves the page — once, and only while
       something is actually open, so ordinary navigation is never hijacked. */
    function pushDetailState() {
      if (app.historyPushed) return;
      if (!global.history || !global.history.pushState) return;
      try {
        global.history.pushState({ gdt: 'analyst-detail' }, '');
        app.historyPushed = true;
      } catch (e) { /* file:// and sandboxed frames */ }
    }
    app.onPopState = function () {
      app.historyPushed = false;
      var anyOpen = app.accordions.some(function (a) { return a.isOpen(); });
      if (anyOpen) app.accordions.forEach(function (a) { a.setOpen(false); });
    };

    /* ------------------------------------------------------- UNCLE VIEW */

    var UNCLE = {
      verdict: function (body, s) {
        var view = s.uncleView;
        if (!view || view.status !== 'PRODUCED') {
          body.appendChild(para(notProducedReason(view,
            'Uncle has no verdict to give: no valuation was produced for this company.')));
          return;
        }
        (view.conclusions || []).forEach(function (c) {
          body.appendChild(el('div', { class: 'claim', 'data-record-id': c.id }, [
            el('span', { class: 'claim-rank pixel', 'data-rank': String(c.importance || c.severity || 'NOTE'),
                         text: String(c.type) + ' · ' + String(c.importance || c.severity || 'NOTE') }),
            el('p', { class: 'claim-text', text: String(c.statement) })
          ]));
        });
        (view.notes || []).forEach(function (n) {
          body.appendChild(el('p', { class: 'note', text: String(n) }));
        });
      },

      money: function (body, s) {
        var drivers = s.drivers;
        if (!drivers || drivers.status !== 'PRODUCED') {
          body.appendChild(para(notProducedReason(drivers,
            'The driver model is not published for this company.')));
          return;
        }
        body.appendChild(el('p', { class: 'uncle-say',
          text: 'A bank earns on what it lends, pays for what it borrows, and loses on what ' +
                'goes bad. Every figure below starts from one of those three.' }));
        var scenarios = drivers.scenarios || {};
        var baseline = scenarios.BASE || scenarios[Object.keys(scenarios)[0]] || [];
        baseline.slice(0, 6).forEach(function (a) {
          body.appendChild(el('div', { class: 'eq' }, [
            el('span', { class: 'eq-id', text: String(a.driverId) }),
            document.createTextNode(' = '),
            figure(GDT.displayValue(a.value) || GDT.TEXT.NOT_PUBLISHED, { raw: a.value }),
            el('span', { class: 'eq-form', text: String(a.formula || '') })
          ]));
        });
      },

      health: function (body, s) {
        var q = s.quality || {};
        body.appendChild(para(
          'Reported facts on file: ' + String((s.reported && s.reported.count) || 0) + '. ' +
          'Input quality is ' + String(q.status || 'UNKNOWN') + '. ' +
          ((q.missingCriticalMetrics || []).length
            ? String(q.missingCriticalMetrics.length) + ' metric(s) the model needs are absent.'
            : 'Every metric the model needs is present.')));
        if ((q.missingCriticalMetrics || []).length) {
          body.appendChild(el('p', { class: 'note', text: 'missing: ' + q.missingCriticalMetrics.join(', ') }));
        }
      },

      changed: function (body, s) {
        var bridge = s.valuation && s.valuation.bridge;
        if (!bridge) {
          body.appendChild(para(
            'No prior snapshot exists to compare against, so nothing has changed yet. ' +
            'Revisions appear here once a second snapshot has been published.'));
          return;
        }
        body.appendChild(para('The valuation bridge below attributes the move to declared ' +
                              'factors and reports whatever it cannot attribute.'));
      },

      worth: function (body, s, stale) {
        var h = GDT.headline(s);
        if (!h.valued) {
          body.appendChild(el('p', { class: 'claim-text', text: GDT.TEXT.VALUATION_NOT_PUBLISHED }));
          body.appendChild(el('p', { class: 'note',
            text: 'Reason ' + String(h.reason) + '. Nothing is estimated in its place.' }));
          return;
        }
        var grid = GDT.sensitivityGrid(s);
        body.appendChild(para('Three scenarios, three methods. Residual income is the primary ' +
                              'method; the other two are sensitivity checks.'));
        body.appendChild(sensitivityNode(grid, stale));
      },

      wrong: function (body, s) {
        var ct = s.counterThesis;
        if (!ct || ct.status !== 'PRODUCED') {
          body.appendChild(para(notProducedReason(ct,
            'No counter-thesis is published, because no thesis was published to argue with.')));
          return;
        }
        (ct.records || []).forEach(function (r) { body.appendChild(claimNode(r)); });
      },

      breaks: function (body, s) {
        var breakers = Array.isArray(s.breakers) ? s.breakers : [];
        if (!breakers.length) {
          body.appendChild(para('No thesis breakers are published, because no thesis is published.'));
          return;
        }
        body.appendChild(para('A breaker is not a worse number. It is the condition under which ' +
                              'there is no number at all.'));
        breakers.forEach(function (r) { body.appendChild(claimNode(r)); });
      },

      evidence: function (body, s) {
        var audit = s.modelAudit || {};
        body.appendChild(para(
          'Every figure on this page can be walked back to a reported fact. ' +
          String((s.evidence || []).length) + ' source records contributed.'));
        body.appendChild(kv([
          ['ENGINE VERSION', String(audit.engineVersion || 'unknown')],
          ['MODEL VERSION', String(audit.modelVersion || 'unknown')],
          ['FACT SOURCE', String(audit.factSource || 'unknown')],
          ['RULES FIRED', String((audit.rulesFired || []).length)]
        ]));
      }
    };

    /* ----------------------------------------------------- ANALYST VIEW */

    var ANALYST = {
      verdict: function (panel, s) {
        var th = s.thesis;
        panel.appendChild(el('h4', { class: 'pixel', text: 'THESIS RECORDS' }));
        if (!th || th.status !== 'PRODUCED') {
          panel.appendChild(para(notProducedReason(th, 'No thesis records were produced.')));
        } else {
          (th.records || []).forEach(function (r) { panel.appendChild(claimNode(r, true)); });
        }
        panel.appendChild(el('h4', { class: 'pixel', text: 'CATALYSTS' }));
        appendClaims(panel, s.catalysts, 'No catalysts are published.');
        panel.appendChild(el('h4', { class: 'pixel', text: 'RISKS' }));
        appendClaims(panel, s.risks, 'No risks are published.');
      },

      money: function (panel, s) {
        var drivers = s.drivers;
        panel.appendChild(el('h4', { class: 'pixel', text: 'DRIVER ASSUMPTIONS' }));
        if (!drivers || drivers.status !== 'PRODUCED') {
          panel.appendChild(para(notProducedReason(drivers, 'No driver model was produced.')));
          return;
        }
        var scenarios = drivers.scenarios || {};
        Object.keys(scenarios).forEach(function (name) {
          panel.appendChild(el('h4', { class: 'pixel', text: name + ' ASSUMPTIONS' }));
          var rows = scenarios[name].map(function (a) {
            return [a.driverId,
                    { text: GDT.displayValue(a.value) || GDT.TEXT.NOT_PUBLISHED, raw: a.value },
                    { text: GDT.displayValue(a.historicalAnchor) || GDT.TEXT.NOT_PUBLISHED,
                      raw: a.historicalAnchor },
                    String(a.reasonForChange || '')];
          });
          panel.appendChild(tableNode(['DRIVER', 'VALUE', 'ANCHOR', 'WHY'], rows, [1, 2]));
        });
      },

      health: function (panel, s) {
        panel.appendChild(el('h4', { class: 'pixel', text: 'REPORTED FACTS' }));
        var values = (s.reported && s.reported.values) || [];
        if (!values.length) { panel.appendChild(para('No reported facts are present.')); return; }
        panel.appendChild(lazyTable(
          ['METRIC', 'PERIOD', 'VALUE', 'UNIT', 'BASIS'],
          values.map(function (v) {
            return [String(v.metric), String(v.periodEnd),
                    v.value === null
                      ? { text: GDT.TEXT.NOT_PUBLISHED, raw: null, missing: String(v.missingReason || '') }
                      : { text: GDT.displayValue(v.value), raw: v.value },
                    String(v.unit || ''), String(v.basis || '')];
          }), [2]));
      },

      changed: function (panel, s) {
        panel.appendChild(el('h4', { class: 'pixel', text: 'ESTIMATE REVISIONS' }));
        var bridge = s.valuation && s.valuation.bridge;
        if (!bridge) {
          panel.appendChild(para(
            'No bridge is published. A bridge reconciles two snapshots of the same issuer, ' +
            'and only one snapshot exists.'));
          return;
        }
        var legs = bridge.legs || [];
        panel.appendChild(el('div', { class: 'cards' },
          legs.map(function (leg) {
            return el('div', { class: 'card' }, [
              el('span', { class: 'c-k pixel', text: String(leg.factor || leg.name || 'FACTOR') }),
              el('span', { class: 'c-v' }, [
                figure(GDT.displayValue(leg.contribution) || GDT.TEXT.NOT_PUBLISHED,
                       { raw: leg.contribution })
              ])
            ]);
          })));
      },

      worth: function (panel, s) {
        panel.appendChild(el('h4', { class: 'pixel', text: 'VALUATION MODEL' }));
        var val = s.valuation || {};
        if (val.status !== 'VALUED') {
          panel.appendChild(kv([
            ['STATUS', GDT.TEXT.VALUATION_NOT_PUBLISHED],
            ['REASON', String(val.reason || 'unknown')],
            ['FAILED GATES', (val.failedGates || []).join(', ') || 'none recorded'],
            ['MISSING INPUTS', (val.missingInputs || []).join(', ') || 'none recorded']
          ]));
          if (val.note) panel.appendChild(el('p', { class: 'note', text: String(val.note) }));
          return;
        }
        var order = val.scenarioOrder || [];
        order.forEach(function (name) {
          var sc = (val.scenarios || {})[name] || {};
          panel.appendChild(el('h4', { class: 'pixel', text: name }));
          var coe = sc.costOfEquity || {};
          panel.appendChild(kv([
            ['PRIMARY METHOD', String(sc.primary && sc.primary.method)],
            ['VALUE PER SHARE', figure(GDT.displayValue(sc.valuePerShare) || GDT.TEXT.NOT_PUBLISHED, {
              raw: sc.valuePerShare,
              ref: sc.primary && sc.primary.valuePerShare ? refOf(sc.primary.valuePerShare) : null
            })],
            ['EQUITY VALUE', figure(GDT.displayValue(sc.equityValue) || GDT.TEXT.NOT_PUBLISHED,
                                    { raw: sc.equityValue })],
            ['SUSTAINABLE ROE', figure(GDT.displayValue(sc.sustainableRoe) || GDT.TEXT.NOT_PUBLISHED,
                                       { raw: sc.sustainableRoe })],
            ['SUSTAINABLE GROWTH', figure(GDT.displayValue(sc.sustainableGrowth) || GDT.TEXT.NOT_PUBLISHED,
                                          { raw: sc.sustainableGrowth })],
            ['COST OF EQUITY', figure(GDT.displayValue(coe.rate) || GDT.TEXT.NOT_PUBLISHED,
                                      { raw: coe.rate })],
            ['RATE BASIS', String(coe.basis || 'unknown')]
          ]));
          (sc.crossChecks || []).forEach(function (c) {
            panel.appendChild(el('p', { class: 'note',
              text: String(c.method) + ': ' + String(c.note || '') }));
          });
        });
        panel.appendChild(el('h4', { class: 'pixel', text: 'METHOD COMPARISON' }));
        var mc = s.methodComparison;
        if (!mc || mc.status !== 'PRODUCED') {
          panel.appendChild(para(notProducedReason(mc, 'No method comparison was produced.')));
        } else {
          (mc.records || []).forEach(function (r) { panel.appendChild(claimNode(r, true)); });
        }
      },

      wrong: function (panel, s) {
        panel.appendChild(el('h4', { class: 'pixel', text: 'COUNTER-THESIS RECORDS' }));
        var ct = s.counterThesis;
        if (!ct || ct.status !== 'PRODUCED') {
          panel.appendChild(para(notProducedReason(ct, 'No counter-thesis records were produced.')));
          return;
        }
        (ct.records || []).forEach(function (r) { panel.appendChild(claimNode(r, true)); });
      },

      breaks: function (panel, s) {
        panel.appendChild(el('h4', { class: 'pixel', text: 'MONITORING RULES' }));
        var breakers = Array.isArray(s.breakers) ? s.breakers : [];
        if (!breakers.length) { panel.appendChild(para('No breakers are published.')); return; }
        breakers.forEach(function (r) { panel.appendChild(claimNode(r, true)); });
        var guards = s.valuation && s.valuation.guards;
        if (guards) {
          panel.appendChild(el('h4', { class: 'pixel', text: 'TERMINAL GUARDS' }));
          panel.appendChild(kv(Object.keys(guards).map(function (k) {
            return [k, figure(GDT.displayValue(guards[k]) || GDT.TEXT.NOT_PUBLISHED, { raw: guards[k] })];
          })));
        }
      },

      evidence: function (panel, s) {
        var audit = s.modelAudit || {};
        panel.appendChild(el('h4', { class: 'pixel', text: 'VERSIONS AND FORMULAS' }));
        panel.appendChild(kv([
          ['ENGINE VERSION', String(audit.engineVersion || 'unknown')],
          ['MODEL VERSION', String(audit.modelVersion || 'unknown')],
          ['SCHEMA VERSION', String(s.schemaVersion || 'unknown')],
          ['FORMULA REGISTRY HASH', String(audit.formulaRegistryHash || 'unknown')],
          ['FORMULA COUNT', String(audit.formulaCount === undefined ? 'unknown' : audit.formulaCount)],
          ['RULE REGISTRY HASH', String(audit.ruleRegistryHash || 'unknown')],
          ['RULE COUNT', String(audit.ruleCount === undefined ? 'unknown' : audit.ruleCount)],
          ['CONTENT HASH', String(s.contentHash || 'unknown')],
          ['FACT SOURCE', String(audit.factSource || 'unknown')]
        ]));

        panel.appendChild(el('h4', { class: 'pixel', text: 'GATES' }));
        panel.appendChild(tableNode(['GATE', 'PASSED', 'DETAIL'],
          (audit.gates || []).map(function (g) {
            return [String(g.gate), g.passed ? 'PASS' : 'FAIL', String(g.detail || '')];
          }), []));

        panel.appendChild(el('h4', { class: 'pixel', text: 'INPUT PROVENANCE' }));
        var prov = audit.inputProvenance || {};
        panel.appendChild(kv([
          ['MODE', String(prov.mode || 'unknown')],
          ['UNIVERSE AUTHORITATIVE', String(prov.universeAuthoritative)],
          ['PROVIDERS', (prov.providers || []).join(', ') || 'none']
        ]));
        (prov.reasons || []).forEach(function (r) {
          panel.appendChild(el('p', { class: 'note', text: String(r) }));
        });

        panel.appendChild(el('h4', { class: 'pixel', text: 'MACRO CONTEXT' }));
        var macro = audit.macroContext || [];
        if (!macro.length) {
          panel.appendChild(para('No macro series were selected at this cutoff.'));
        } else {
          panel.appendChild(tableNode(['SERIES', 'PERIOD', 'VALUE', 'USED IN CALCULATION'],
            macro.map(function (m) {
              return [String(m.seriesId), String(m.observationPeriod),
                      m.value === null ? { text: GDT.TEXT.NOT_PUBLISHED, raw: null }
                                       : { text: GDT.displayValue(m.value), raw: m.value },
                      m.usedInCalculation ? 'YES' : 'NO'];
            }), [2]));
        }

        panel.appendChild(el('h4', { class: 'pixel', text: 'SOURCE RECORDS' }));
        panel.appendChild(lazyEvidence(s.evidence || []));
      }
    };

    /* ------------------------------------------------------ node builders */

    function notProducedReason(section, fallback) {
      if (section && typeof section.reason === 'string' && section.reason) return section.reason;
      return fallback;
    }

    function claimNode(record, withCitations) {
      var node = el('div', { class: 'claim', 'data-record-id': String(record.id) }, [
        el('span', {
          class: 'claim-rank pixel',
          'data-rank': String(record.severity || record.importance || 'NOTE'),
          text: String(record.type) + ' · ' + String(record.severity || record.importance || 'NOTE')
        }),
        el('p', { class: 'claim-text', text: String(record.statement) })
      ]);
      if (withCitations) {
        node.appendChild(el('p', { class: 'claim-rule', text: 'rule: ' + String(record.ruleId) }));
        var refs = record.supportingRecords || [];
        refs.forEach(function (ref) {
          var resolved = GDT.resolveRecord(app.index, ref);
          node.appendChild(el('p', { class: 'claim-rule' }, [
            document.createTextNode(ref + ' → '),
            figure(resolved.text, { ref: ref, raw: resolved.raw })
          ]));
        });
        var ev = record.supportingEvidence || [];
        if (ev.length) {
          node.appendChild(el('p', { class: 'claim-rule', text: 'evidence: ' + ev.join(' · ') }));
        }
      }
      return node;
    }

    function appendClaims(panel, list, emptyText) {
      var items = Array.isArray(list) ? list : [];
      if (!items.length) { panel.appendChild(para(emptyText)); return; }
      items.forEach(function (r) { panel.appendChild(claimNode(r, true)); });
    }

    function cellNode(cell, numeric) {
      var td = el('td', { class: numeric ? 'num' : null });
      if (typeof cell === 'string') { td.textContent = cell; return td; }
      td.appendChild(figure(cell.text === null ? GDT.TEXT.NOT_PUBLISHED : cell.text,
                            { ref: cell.ref, raw: cell.raw }));
      if (cell.missing) td.appendChild(el('span', { class: 'note', text: ' ' + cell.missing }));
      return td;
    }

    function tableNode(headers, rows, numericCols) {
      var nums = numericCols || [];
      var table = el('table');
      var thead = el('thead');
      thead.appendChild(el('tr', null, headers.map(function (h, i) {
        return el('th', { scope: 'col', class: nums.indexOf(i) !== -1 ? 'num' : null, text: h });
      })));
      var tbody = el('tbody');
      rows.forEach(function (row) {
        tbody.appendChild(el('tr', null, row.map(function (cell, i) {
          return cellNode(cell, nums.indexOf(i) !== -1);
        })));
      });
      table.appendChild(thead);
      table.appendChild(tbody);
      return el('div', { class: 'tablewrap sticky' }, [table]);
    }

    /** Long tables render a window first. The rest arrives on request, so a
     *  phone is not asked to lay out a hundred rows nobody scrolled to. */
    function lazyTable(headers, rows, numericCols) {
      var wrap = el('div');
      var shown = Math.min(rows.length, GDT.EVIDENCE_PAGE);
      var mount = tableNode(headers, rows.slice(0, shown), numericCols);
      wrap.appendChild(mount);
      if (rows.length > shown) {
        var more = el('button', { type: 'button', class: 'more-btn pixel',
                                  text: 'SHOW ALL ' + rows.length + ' ROWS' });
        more.addEventListener('click', function () {
          wrap.replaceChildren(tableNode(headers, rows, numericCols));
        });
        wrap.appendChild(more);
      }
      return wrap;
    }

    function lazyEvidence(list) {
      var wrap = el('div');
      function paint(limit) {
        var ul = el('ul', { class: 'evidence-list' });
        list.slice(0, limit).forEach(function (e) {
          var li = el('li', null, [
            el('span', { class: 'ev-kind', text: String(e.kind || 'REF') }),
            document.createTextNode(String(e.ref))
          ]);
          if (e.sourceRef) {
            if (GDT.isSafeHttpUrl(e.sourceRef)) {
              li.appendChild(document.createTextNode(' '));
              li.appendChild(el('a', {
                href: e.sourceRef, rel: 'noopener noreferrer', target: '_blank',
                text: 'source'
              }));
            } else {
              /* Not an https URL, so it is a document reference, not a link.
                 Rendered as inert text — a snapshot must never be able to make
                 the page navigate somewhere of its choosing. */
              li.appendChild(document.createTextNode(' · ' + String(e.sourceRef)));
            }
          }
          if (e.publishedAt) li.appendChild(document.createTextNode(' · ' + String(e.publishedAt)));
          ul.appendChild(li);
        });
        wrap.replaceChildren(ul);
        if (list.length > limit) {
          var more = el('button', { type: 'button', class: 'more-btn pixel',
                                    text: 'SHOW ALL ' + list.length + ' SOURCE RECORDS' });
          more.addEventListener('click', function () { paint(list.length); });
          wrap.appendChild(more);
        }
      }
      paint(Math.min(list.length, GDT.EVIDENCE_PAGE));
      return wrap;
    }

    function sensitivityNode(grid, stale) {
      if (!grid) return para(GDT.TEXT.VALUATION_NOT_PUBLISHED);
      var box = el('div', { class: 'sens', role: 'table', 'aria-label': 'Value per share by scenario and method' });
      box.appendChild(el('span', { class: 'sh', role: 'columnheader', text: '' }));
      grid.methods.forEach(function (m) {
        box.appendChild(el('span', { class: 'sh', role: 'columnheader', text: shortMethod(m) }));
      });
      grid.rows.forEach(function (row) {
        box.appendChild(el('span', { class: 'sh', role: 'rowheader', text: row.scenario }));
        row.cells.forEach(function (cell, i) {
          var span = el('span', { class: 'sv' + (i === 0 ? ' primary' : ''), role: 'cell' }, [
            figure(cell.text, { ref: cell.ref, raw: cell.raw })
          ]);
          if (stale) span.appendChild(el('span', { class: 'stale-mark pixel', text: 'STALE' }));
          box.appendChild(span);
        });
      });
      return box;
    }

    function shortMethod(m) {
      if (m === 'RESIDUAL_INCOME') return 'RI (PRIMARY)';
      if (m === 'JUSTIFIED_PB') return 'P/B CHECK';
      if (m === 'DIVIDEND_DISCOUNT') return 'DDM CHECK';
      return String(m);
    }

    function renderDisclaimers(s) {
      var box = el('section', { class: 'disclosure', 'aria-labelledby': 'gdt-disc-title' });
      box.appendChild(el('h2', { class: 'pixel', id: 'gdt-disc-title', text: 'DISCLOSURE' }));
      (s.disclaimers || []).forEach(function (d) { box.appendChild(para(String(d))); });
      return box;
    }

    /* ---------------------------------------------------------- wiring */

    app.mount = function () {
      var search = $('gdt-search');
      if (search) {
        search.addEventListener('input', function () {
          renderResults(GDT.searchConstituents(app.constituents, search.value));
        });
        search.addEventListener('keydown', function (e) {
          if (e.key !== 'ArrowDown') return;
          var first = doc.querySelector('#gdt-results .result-btn');
          if (first) { e.preventDefault(); first.focus(); }
        });
      }

      var results = $('gdt-results');
      if (results) {
        /* Roving keyboard navigation across the option list. No hover-only
           behaviour anywhere: everything reachable by pointer is reachable by
           Tab and by the arrow keys. */
        results.addEventListener('keydown', function (e) {
          var buttons = Array.prototype.slice.call(results.querySelectorAll('.result-btn'));
          var at = buttons.indexOf(doc.activeElement);
          if (at === -1) return;
          var next = null;
          if (e.key === 'ArrowDown') next = buttons[Math.min(at + 1, buttons.length - 1)];
          if (e.key === 'ArrowUp') next = at === 0 ? search : buttons[at - 1];
          if (e.key === 'Home') next = buttons[0];
          if (e.key === 'End') next = buttons[buttons.length - 1];
          if (next) { e.preventDefault(); next.focus(); }
        });
      }

      var run = $('gdt-run');
      if (run) {
        run.addEventListener('click', function () {
          if (app.selected) loadSnapshot(app.selected);
        });
      }

      var fixtureSelect = $('gdt-fixture-select');
      if (fixtureSelect) {
        GDT.FIXTURE_FILES.forEach(function (f) {
          fixtureSelect.appendChild(el('option', { value: f.file, text: f.state }));
        });
      }
      var fixtureRun = $('gdt-fixture-run');
      if (fixtureRun && fixtureSelect) {
        fixtureRun.addEventListener('click', function () { loadFixture(fixtureSelect.value); });
      }

      var backToSelect = $('gdt-back-to-select');
      if (backToSelect) {
        backToSelect.addEventListener('click', function () { showPage('select'); });
      }

      if (global.addEventListener) {
        global.addEventListener('popstate', app.onPopState);
      }

      renderLoading(0);
      showPage('select');
      return loadUniverse();
    };

    return app;
  };

  function safeSessionStorage() {
    try {
      if (global.sessionStorage) {
        global.sessionStorage.setItem('gdt.probe', '1');
        global.sessionStorage.removeItem('gdt.probe');
        return global.sessionStorage;
      }
    } catch (e) { /* Safari private mode throws on write */ }
    var mem = Object.create(null);
    return {
      getItem: function (k) { return k in mem ? mem[k] : null; },
      setItem: function (k, v) { mem[k] = String(v); },
      removeItem: function (k) { delete mem[k]; }
    };
  }

  global.GohDipTong = GDT;
  if (typeof module === 'object' && module.exports) module.exports = GDT;

})(typeof globalThis !== 'undefined' ? globalThis : this);
