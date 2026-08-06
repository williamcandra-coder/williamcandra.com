#!/usr/bin/env bash
# ============================================================================
# Goh Dip Tong — Stage 2 acceptance test (slices 1-3)
#
#   ./engine/goh_dip_tong/tests/acceptance_stage2.sh
#
# Slice 1: contracts, the formula registry, missing-value propagation, the
# input loader and point-in-time selection, the output schema, fixture
# provenance labelling, the valuation refusal framework, the canonical bank
# metric definitions and the segment contract correction.
#
# Slice 2: the BANK driver chain, the five-year forecast, bear/base/bull
# scenarios, residual income with two cross-checks, the terminal guards, the
# reverse-implied ROE solver, the valuation bridge, and the two views.
#
# Slice 3: the deterministic research package (thesis, counter-thesis,
# catalysts, risks, breakers, evidence and model-audit references, and the
# valuation-method comparison notes), the finalised Uncle and Analyst views,
# the six Stage 3 UI-state fixtures, and the publishing guarantees — byte
# stability, no churn on a later date, and an invalid snapshot never replacing
# a valid one.
#
# It does NOT verify any other model family. None is implemented, and an
# acceptance script that passed for absent functionality would be worse than
# no script at all.
#
# ISOLATION
# Read-only assertions run against the repository. Every operation that WRITES
# runs inside a throwaway sandbox under $(mktemp -d), removed on exit. The
# closing self-check fails the build if the repository tree moved, so this is
# safe to run in CI on a pull request and safe to run locally mid-work.
#
# EXIT CODE
#   0  every check passed
#   1  one or more checks failed (count printed in the summary)
# ============================================================================
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
export REPO
cd "$REPO"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

PASS=0
FAIL=0

hdr() { printf '\n\033[1m%s\033[0m\n%s\n' "$1" "$(printf '─%.0s' $(seq 1 78))"; }
ok()  { printf '  \033[32mPASS\033[0m  %s\n' "$1"; PASS=$((PASS + 1)); }
no()  { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; FAIL=$((FAIL + 1)); }
chk() { if [ "$1" = "0" ]; then ok "$2"; else no "$2"; fi; }
ev()  { printf '        %s\n' "$1"; }

py() { python3 -c "$1"; }

tree_hash() {
  find "$1" -type f ! -name '.gitkeep' -exec sha256sum {} \; | sed "s|$1||" \
    | sort | sha256sum | cut -d' ' -f1
}

mk_sandbox() {
  local dir="$WORK/$1"
  mkdir -p "$dir"
  (cd "$REPO" && tar --exclude=.git --exclude=__pycache__ \
                     --exclude=.pytest_cache -cf - .) | (cd "$dir" && tar -xf -)
  printf '%s' "$dir"
}

REPO_DATA_BEFORE="$(tree_hash "$REPO/data/goh-dip-tong")"
REPO_CONFIG_BEFORE="$(tree_hash "$REPO/config/goh-dip-tong")"

# ═══════════════════════════════════════════════════════════════════════════
hdr "1. Engine contracts"

py "
import sys; sys.path.insert(0,'$REPO')
from engine.goh_dip_tong.contracts.calculated import Calculated, Period
from pipeline.goh_dip_tong.contracts.enums import PeriodType
from pipeline.goh_dip_tong.contracts.records import ContractError, Measure
p = Period(PeriodType.FY, '2025-12-31')
try:
    Calculated(metric_id='x', measure=Measure.of(1.0, unit='IDR'), period=p,
               formula_id='', model_version='0', calculated_at='x')
except ContractError:
    raise SystemExit(0)
raise SystemExit(1)"
chk $? "a calculated value cannot exist without a formula ID"

py "
import sys; sys.path.insert(0,'$REPO')
from pipeline.goh_dip_tong.contracts.records import ContractError, Measure
try:
    Measure(value=None, unit='IDR')
except ContractError:
    raise SystemExit(0)
raise SystemExit(1)"
chk $? "a missing value cannot be constructed without a reason"

py "
import sys; sys.path.insert(0,'$REPO')
from engine.goh_dip_tong.contracts.enums import ResearchStatus
need = {'DISCOVERY','FINANCIALS_VALIDATED','MODEL_UNDER_VALIDATION',
        'FULL_RESEARCH','MODEL_SUSPENDED','STALE'}
raise SystemExit(0 if need == {str(s) for s in ResearchStatus} else 1)"
chk $? "the spec section 2.8 research-status vocabulary is complete"

# ═══════════════════════════════════════════════════════════════════════════
hdr "2. Formula registry"

RH_DECLARED=$(py "
import sys; sys.path.insert(0,'$REPO')
from engine.goh_dip_tong import FORMULA_REGISTRY_HASH; print(FORMULA_REGISTRY_HASH)")
RH_ACTUAL=$(python3 -m engine.goh_dip_tong.cli registry-hash)
[ "$RH_DECLARED" = "$RH_ACTUAL" ]
chk $? "the formula registry hash matches the declared constant"
ev "declared: ${RH_DECLARED:0:32}…"

py "
import sys; sys.path.insert(0,'$REPO')
from engine.goh_dip_tong.common import arithmetic
from engine.goh_dip_tong.contracts.registry import REGISTRY
raise SystemExit(0 if all(REGISTRY.get(f).doc for f in REGISTRY.ids()) else 1)"
chk $? "every registered formula is documented"

py "
import sys; sys.path.insert(0,'$REPO')
from engine.goh_dip_tong.contracts.registry import FormulaRegistry
r = FormulaRegistry()
try:
    @r.formula('bad', inputs=('a','b'), output_metric='x')
    def bad(a): return a
except Exception:
    raise SystemExit(0 if len(r) == 0 else 1)
raise SystemExit(1)"
chk $? "a formula whose signature disagrees with its declaration is rejected"

# ═══════════════════════════════════════════════════════════════════════════
hdr "3. Missing-value propagation"

py "
import sys; sys.path.insert(0,'$REPO')
from engine.goh_dip_tong.common.arithmetic import safe_div
from pipeline.goh_dip_tong.contracts.enums import MissingReason
from pipeline.goh_dip_tong.contracts.records import Measure
r = safe_div(Measure.of(10, unit='IDR'), Measure.of(0, unit='IDR'))
raise SystemExit(0 if r.value is None and
                 r.missing_reason == MissingReason.UNDEFINED_DENOMINATOR else 1)"
chk $? "a zero denominator returns UNDEFINED_DENOMINATOR, not zero or infinity"

py "
import sys, json; sys.path.insert(0,'$REPO')
from engine.goh_dip_tong.common.arithmetic import safe_div
from pipeline.goh_dip_tong.contracts.records import Measure
for a, b in ((1e308, 1e-308), (1, 0), (0, 0)):
    json.dumps(safe_div(Measure.of(a, unit='IDR'), Measure.of(b, unit='IDR')).value,
               allow_nan=False)
raise SystemExit(0)"
chk $? "no derived value can serialise as NaN or Infinity"

py "
import sys; sys.path.insert(0,'$REPO')
from engine.goh_dip_tong.contracts.calculated import Calculated, Period
from engine.goh_dip_tong.contracts.registry import FormulaRegistry
from pipeline.goh_dip_tong.contracts.enums import MissingReason, PeriodType
from pipeline.goh_dip_tong.contracts.records import Measure
seen = []
r = FormulaRegistry()
@r.formula('w', inputs=('a',), output_metric='x')
def w(a):
    seen.append(a); return Measure.of(0.0, unit='RATIO')
p = Period(PeriodType.FY, '2025-12-31')
c = Calculated(metric_id='a',
               measure=Measure.missing(MissingReason.NOT_REPORTED, unit='IDR'),
               period=p, formula_id='source.fact', model_version='0',
               calculated_at='x')
out = r.compute('w', p, {'a': c}, model_version='0', calculated_at='x')
raise SystemExit(0 if not seen and out.value is None else 1)"
chk $? "no formula body is ever invoked with a missing input"

grep -q "UNDEFINED_DENOMINATOR" "$REPO/config/goh-dip-tong/metrics.yml"
chk $? "UNDEFINED_DENOMINATOR is declared in the canonical metrics registry"

# ═══════════════════════════════════════════════════════════════════════════
hdr "4. Input loader and point-in-time selection"

PIT=$(py "
import sys; sys.path.insert(0,'$REPO')
from engine.goh_dip_tong.inputs import loader
from engine.goh_dip_tong.settings import get_engine_settings
s = get_engine_settings()
def np(d):
    ei = loader.load(s, 'BBCA', as_of=d, model_version='0.1.0', calculated_at='x')
    for c in ei.facts:
        if c.metric_id == 'net_profit' and str(c.period.period_type) == 'FY':
            return c.value, str(c.basis)
print(np('2026-07-25'), np('2026-07-29'))")
echo "$PIT" | grep -q "54800000000000.0, 'REPORTED'"
chk $? "a cutoff before the restatement returns the originally reported figure"
echo "$PIT" | grep -q "53950000000000.0, 'RESTATED'"
chk $? "a cutoff after the restatement returns the revision"
ev "$PIT"

py "
import sys; sys.path.insert(0,'$REPO')
from engine.goh_dip_tong.inputs import point_in_time as pit
rows = [{'factKey':'X','revision':1,'source':{'publishedAt':'2030-01-01T00:00:00Z'}}]
sel = pit.select_facts(rows, '2026-07-31')
raise SystemExit(0 if sel.rows == [] and sel.excluded_future == 1 else 1)"
chk $? "a record published after the cutoff never reaches the selected set"

py "
import sys; sys.path.insert(0,'$REPO')
from engine.goh_dip_tong.inputs import point_in_time as pit
sel = pit.select_facts([{'factKey':'X','revision':1,'source':{}}], '2026-07-31')
raise SystemExit(0 if sel.rows == [] and sel.excluded_undated == 1 else 1)"
chk $? "an undated record is never assumed to have been known"

py "
import sys; sys.path.insert(0,'$REPO')
from engine.goh_dip_tong.inputs import loader
from engine.goh_dip_tong.settings import get_engine_settings
s = get_engine_settings()
def cpi(d):
    ei = loader.load(s, 'BBCA', as_of=d, model_version='0.1.0', calculated_at='x')
    return [r['value'] for r in ei.macro
            if r['seriesId'] == 'BPS_CPI_YOY' and r['observationPeriod'] == '2026-05']
raise SystemExit(0 if cpi('2026-06-15') == [2.41] and cpi('2026-07-25') == [2.38] else 1)"
chk $? "a revised macro print is used only once its release vintage has passed"

# ═══════════════════════════════════════════════════════════════════════════
hdr "5. Output schema"

py "
import sys; sys.path.insert(0,'$REPO')
from pipeline.goh_dip_tong.settings import get_settings
from pipeline.goh_dip_tong.validation.schema import SCHEMA_FILES, validate_all_schemas
r = validate_all_schemas(get_settings())
raise SystemExit(0 if r.ok and 'research-snapshot' in SCHEMA_FILES else 1)"
chk $? "research-snapshot.schema.json is registered and is a legal Draft 2020-12 schema"

[ -f "$REPO/schemas/goh-dip-tong/research-snapshot.schema.json" ] && \
[ -f "$REPO/schemas/goh-dip-tong/research-input.schema.json" ]
chk $? "engine input and engine output are separate contracts"

SB=$(mk_sandbox schema)
(cd "$SB" && python3 -m engine.goh_dip_tong.cli research-build --all >/dev/null 2>&1)
chk $? "every available issuer builds and validates against the output schema"

py "
import sys; sys.path.insert(0,'$REPO')
from pipeline.goh_dip_tong.validation.schema import get_validator
v = get_validator('research-snapshot')
raise SystemExit(0 if list(v.iter_errors({'schemaVersion':'1.0.0','ticker':'BBCA'})) else 1)"
chk $? "a document without a mode fails validation"

# ═══════════════════════════════════════════════════════════════════════════
hdr "6. Fixture provenance labelling"

SB=$(mk_sandbox label)
(cd "$SB" && python3 -m engine.goh_dip_tong.cli research-build --all \
             --write-mode commit >/dev/null 2>&1)

MODES=$(py "
import json, pathlib
root = pathlib.Path('$SB/data/goh-dip-tong/research-snapshots')
docs = [json.loads(p.read_text()) for p in sorted(root.rglob('*/*/*.json'))]
print(len(docs), sorted({d['mode'] for d in docs}))")
echo "$MODES" | grep -q "FIXTURE_TEST_ONLY"
chk $? "every generated snapshot is labelled FIXTURE_TEST_ONLY"
echo "$MODES" | grep -qv "PRODUCTION"
chk $? "no generated snapshot is labelled PRODUCTION"
ev "$MODES"

py "
import json, pathlib
root = pathlib.Path('$SB/data/goh-dip-tong/research-snapshots')
for p in sorted(root.rglob('*/*/*.json')):
    d = json.loads(p.read_text())
    assert d['mode'] == 'FIXTURE_TEST_ONLY'
    assert 'FIXTURE_TEST_ONLY' in d['quality']['flags']
    assert d['disclaimers'][0].startswith('FIXTURE_TEST_ONLY')
    assert d['modelAudit']['inputProvenance']['mode'] == 'FIXTURE_TEST_ONLY'
raise SystemExit(0)"
chk $? "the label appears in all four independent carriers"

py "
import sys; sys.path.insert(0,'$REPO')
from engine.goh_dip_tong.contracts.enums import EngineMode
from engine.goh_dip_tong.inputs.provenance import assess
from engine.goh_dip_tong.settings import get_engine_settings
from pipeline.goh_dip_tong.publishing.writers import read_json
s = get_engine_settings()
u = dict(read_json(s.pipeline.idx30_current))
u['authoritative'] = True; u['provenance'] = 'LIVE'
p = assess(s, u, {'quality': {'flags': []}})
raise SystemExit(0 if p.mode == EngineMode.FIXTURE_TEST_ONLY and p.reasons else 1)"
chk $? "PRODUCTION mode is unreachable — no single flag reaches it"

! grep -rl "EngineMode.PRODUCTION" "$REPO/engine" --include="*.py" \
  | grep -v "provenance.py\|enums.py\|tests/" | grep -q .
chk $? "only provenance.assess may decide the mode"

# ═══════════════════════════════════════════════════════════════════════════
hdr "7. Valuation refusal framework"

REF=$(py "
import json, pathlib
root = pathlib.Path('$SB/data/goh-dip-tong/research-snapshots')
out = []
for p in sorted(root.rglob('*/*/*.json')):
    d = json.loads(p.read_text())
    out.append((d['ticker'], d['valuation']['status'], d['valuation']['reason'],
                len(d['valuation']['missingInputs'])))
print(out)")
echo "$REF" | grep -qv "VALUED"
chk $? "no issuer produced a valuation"
[ "$(echo "$REF" | grep -o "REFUSED" | wc -l)" -ge 3 ]
chk $? "every issuer produced a structured refusal"
ev "$REF"

py "
import json, pathlib
root = pathlib.Path('$SB/data/goh-dip-tong/research-snapshots')
for p in sorted(root.rglob('*/*/*.json')):
    v = json.loads(p.read_text())['valuation']
    assert v['note'], 'a refusal must explain itself'
    assert v['failedGates'], 'a refusal must name the gates that failed'
    assert 'VALIDATED_RISK_FREE_RATE' in v['failedGates']
    assert 'MARKET_DATA_AVAILABLE' in v['failedGates']
raise SystemExit(0)"
chk $? "every refusal names its failed gates, including the risk-free rate"

py "
import sys; sys.path.insert(0,'$REPO')
from engine.goh_dip_tong.contracts.enums import ValuationMethod
from engine.goh_dip_tong.contracts.refusal import MethodNotPermitted
from engine.goh_dip_tong.models.bank import BankModel
for m in (ValuationMethod.EV_EBITDA, ValuationMethod.ENTERPRISE_DCF,
          ValuationMethod.FCF_YIELD):
    try:
        BankModel().assert_method_permitted(m)
    except MethodNotPermitted:
        continue
    raise SystemExit(1)
raise SystemExit(0)"
chk $? "enterprise-value methods raise for a bank rather than being unselected"

py "
import sys; sys.path.insert(0,'$REPO')
from engine.goh_dip_tong.models.registry import build_registry
from engine.goh_dip_tong.settings import get_engine_settings
cfg = get_engine_settings().pipeline.models()
reg = build_registry(cfg)
raise SystemExit(0 if set(reg) == set(cfg['model_families']) else 1)"
chk $? "every declared family is registered"

py "
import ast, sys
text = open('$REPO/engine/goh_dip_tong/cli.py').read()
bad = [n for n in ast.walk(ast.parse(text))
       if isinstance(n, ast.keyword) and n.arg == 'allow_synthetic_cost_of_equity'
       and isinstance(n.value, ast.Constant) and n.value.value is True]
raise SystemExit(0 if not bad else 1)"
chk $? "the CLI never permits a synthetic cost of equity"

py "
import yaml
c = yaml.safe_load(open('$REPO/engine/goh_dip_tong/config/cost-of-capital.yml'))
ids = {r['id'] for r in c['risk_free']['rejected_substitutes']}
raise SystemExit(0 if c['risk_free']['validated'] is False
                 and c['synthetic']['usable_in_production'] is False
                 and 'BI_7DRR' in ids else 1)"
chk $? "BI_7DRR is recorded as a rejected risk-free substitute"

py "
import json, pathlib
root = pathlib.Path('$SB/data/goh-dip-tong/research-snapshots')
for p in sorted(root.rglob('*/*/*.json')):
    for row in json.loads(p.read_text())['modelAudit']['macroContext']:
        assert row['usedInCalculation'] is False
raise SystemExit(0)"
chk $? "no macro series feeds any calculation"

# ═══════════════════════════════════════════════════════════════════════════
hdr "8. Canonical bank metric definitions"

py "
import sys, yaml; sys.path.insert(0,'$REPO')
from engine.goh_dip_tong.models.bank import BANK_REQUIRED_METRICS
defined = set(yaml.safe_load(open('$REPO/config/goh-dip-tong/metrics.yml'))['metrics'])
missing = sorted(set(BANK_REQUIRED_METRICS) - defined)
if missing: print('undefined:', missing)
raise SystemExit(0 if not missing else 1)"
chk $? "every metric the bank model requires is defined in metrics.yml"

py "
import sys; sys.path.insert(0,'$REPO')
from engine.goh_dip_tong.models.bank import BANK_REQUIRED_METRICS
raise SystemExit(0 if len(BANK_REQUIRED_METRICS) == 17 == len(set(BANK_REQUIRED_METRICS)) else 1)"
chk $? "the bank model declares 17 distinct required metrics"

py "
import yaml
m = yaml.safe_load(open('$REPO/config/goh-dip-tong/metrics.yml'))['metrics']
raise SystemExit(0 if 'BANK' in m['net_debt']['not_applicable_to_model_families'] else 1)"
chk $? "net_debt remains not applicable to banks"

py "
import yaml
m = yaml.safe_load(open('$REPO/config/goh-dip-tong/metrics.yml'))['metrics']
derived = ['roe','bvps','eps','nim','payout_ratio','cost_of_credit',
           'npl_ratio_gross','npl_coverage_ratio','casa_ratio',
           'capital_adequacy_ratio','cost_to_income_ratio','sustainable_growth',
           'net_interest_income','roa']
bad = [d for d in derived if m.get(d, {}).get('basis') != 'DERIVED']
if bad: print('not labelled DERIVED:', bad)
raise SystemExit(0 if not bad else 1)"
chk $? "every new ratio is labelled DERIVED, not REPORTED"

# ═══════════════════════════════════════════════════════════════════════════
hdr "9. Segment contract correction"

py "
import json
s = json.load(open('$REPO/schemas/goh-dip-tong/research-input.schema.json'))
raise SystemExit(0 if 'segment' in s['\$defs']['snapshotFact']['properties'] else 1)"
chk $? "research-input.schema.json carries an optional segment field"

py "
import json
d = json.load(open('$REPO/data/goh-dip-tong/research-snapshots/sample/BBCA.json'))
rev = [f for f in d['facts'] if f['metric'] == 'revenue' and f['periodType'] == 'FY']
segs = {f['segment'] for f in rev}
raise SystemExit(0 if len(rev) == 2 and None in segs and 'WHOLESALE_BANKING' in segs else 1)"
chk $? "consolidated and segment facts are distinguishable in the sample snapshot"

py "
import json
d = json.load(open('$REPO/data/goh-dip-tong/research-snapshots/sample/BBCA.json'))
raise SystemExit(0 if d['quality']['missingCriticalMetrics'] == [] else 1)"
chk $? "a segment-level null no longer reports a present consolidated metric as missing"

# ═══════════════════════════════════════════════════════════════════════════
hdr "10. Synthetic data never enters the published tree"

py "
import hashlib, pathlib
def h(root):
    return {hashlib.sha256(p.read_bytes()).hexdigest(): str(p)
            for p in sorted(root.rglob('*')) if p.is_file()}
fx = h(pathlib.Path('$REPO/engine/goh_dip_tong/fixtures'))
for tree in ('$REPO/data/goh-dip-tong', '$SB/data/goh-dip-tong'):
    overlap = set(fx) & set(h(pathlib.Path(tree)))
    if overlap: print(tree, sorted(overlap)); raise SystemExit(1)
raise SystemExit(0)"
chk $? "no published file shares a hash with any engine fixture"

! grep -rl "SYNTHETIC" "$REPO/data/goh-dip-tong" "$SB/data/goh-dip-tong" 2>/dev/null | grep -q .
chk $? "no published document carries the SYNTHETIC flag"

py "
import pathlib, sys; sys.path.insert(0,'$REPO')
from engine.goh_dip_tong.publishing.ui_states import FIXTURE_TICKERS
bad = []
for tree in ('$REPO/data/goh-dip-tong', '$SB/data/goh-dip-tong'):
    root = pathlib.Path(tree)
    if not root.is_dir(): continue
    for path in sorted(root.rglob('*.json')):
        text = path.read_text(encoding='utf-8')
        bad += [(str(path), t) for t in FIXTURE_TICKERS if t in text]
        bad += [(str(path), path.stem) for t in FIXTURE_TICKERS if path.stem == t]
if bad: print(bad[:5])
raise SystemExit(0 if not bad else 1)"
chk $? "no synthetic ticker appears anywhere in the published tree"
ev "checked SYNB, SYNM, SYNO, SYNP, SYNS, SYNX"

py "
import json, sys; sys.path.insert(0,'$REPO')
from engine.goh_dip_tong.publishing.ui_states import FIXTURE_TICKERS
u = json.load(open('$REPO/config/goh-dip-tong/idx30.current.json'))
live = {c['ticker'] for c in u['constituents']}
raise SystemExit(0 if not (set(FIXTURE_TICKERS) & live) else 1)"
chk $? "no synthetic ticker is in the IDX30 universe"

# ═══════════════════════════════════════════════════════════════════════════
hdr "11. Determinism and no churn"

SB=$(mk_sandbox determinism)
(cd "$SB" && python3 -m engine.goh_dip_tong.cli research-build --all \
             --as-of 2026-07-31 --write-mode commit >/dev/null 2>&1)
D1="$(tree_hash "$SB/data/goh-dip-tong/research-snapshots")"
(cd "$SB" && python3 -m engine.goh_dip_tong.cli research-build --all \
             --as-of 2026-07-31 --write-mode commit >/dev/null 2>&1)
D2="$(tree_hash "$SB/data/goh-dip-tong/research-snapshots")"
[ "$D1" = "$D2" ]
chk $? "rebuilding the same inputs writes nothing new"

for D in 2026-08-01 2026-12-31 2027-03-14 2027-07-31; do
  (cd "$SB" && python3 -m engine.goh_dip_tong.cli research-build --all \
               --as-of "$D" --write-mode commit >/dev/null 2>&1)
done
D3="$(tree_hash "$SB/data/goh-dip-tong/research-snapshots")"
[ "$D1" = "$D3" ]
chk $? "rebuilding on four later calendar dates deposits nothing"
ev "date sweep: 2026-08-01, 2026-12-31, 2027-03-14, 2027-07-31 → tree unmoved"

H1=$(PYTHONHASHSEED=0 python3 -m engine.goh_dip_tong.cli registry-hash)
H2=$(PYTHONHASHSEED=12345 python3 -m engine.goh_dip_tong.cli registry-hash)
[ "$H1" = "$H2" ]
chk $? "the registry hash does not depend on the process hash seed"

# ═══════════════════════════════════════════════════════════════════════════
hdr "12. BANK forecast and valuation (slice 2)"

SB=$(mk_sandbox bankmodel)
rm -f "$SB"/data/goh-dip-tong/research-snapshots/sample/*.json
cp "$REPO/engine/goh_dip_tong/fixtures/synthetic-bank/SYNB.json" \
   "$SB/data/goh-dip-tong/research-snapshots/sample/SYNB.json"

SYNB=$(cd "$SB" && py "
import json, sys
sys.path.insert(0, '.')
from engine.goh_dip_tong.settings import get_engine_settings
from engine.goh_dip_tong.tests.conftest_bank import evaluate
r = evaluate(get_engine_settings())
print(json.dumps({
    'status': r.to_json()['status'],
    'method': str(r.method),
    'coe': r.base.cost_of_equity.basis,
    'values': {s: r.scenarios[s].primary.value_per_share.value
               for s in r.scenario_order},
}))")

echo "$SYNB" | grep -q '"status": "VALUED"'
chk $? "the synthetic bank is valued"
echo "$SYNB" | grep -q '"coe": "SYNTHETIC"'
chk $? "its discount rate is labelled SYNTHETIC"
echo "$SYNB" | grep -q '"method": "RESIDUAL_INCOME"'
chk $? "residual income is the primary method"
ev "$(echo "$SYNB" | cut -c1-140)"

echo "$SYNB" | py "
import json, sys
d = json.load(sys.stdin)['values']
raise SystemExit(0 if d['BEAR'] <= d['BASE'] <= d['BULL'] else 1)"
chk $? "bear <= base <= bull"

py "
import sys; sys.path.insert(0,'$REPO')
from engine.goh_dip_tong.valuation import methods
from engine.goh_dip_tong.valuation.guards import TerminalGuards
r = methods.steady_state_value(1000.0, 0.15, 0.5, 0.12, TerminalGuards())
ok = (abs(r['JUSTIFIED_PB'] - r['RESIDUAL_INCOME']) < 1e-9
      and abs(r['DIVIDEND_DISCOUNT'] - r['RESIDUAL_INCOME']) < 1e-9)
raise SystemExit(0 if ok else 1)"
chk $? "residual income, justified P/B and DDM reconcile on a steady state"

py "
import sys; sys.path.insert(0,'$REPO')
from engine.goh_dip_tong.valuation.guards import TerminalAssumptionInvalid, TerminalGuards
g = TerminalGuards()
for r, gr in ((0.12, 0.12), (0.12, 0.115), (0.12, 0.15)):
    try:
        g.check_spread(r, gr)
    except TerminalAssumptionInvalid:
        continue
    raise SystemExit(1)
raise SystemExit(0)"
chk $? "the r-g guard refuses at, inside and beyond the minimum spread"

py "
import sys; sys.path.insert(0,'$REPO')
from engine.goh_dip_tong.valuation.guards import TerminalAssumptionInvalid, TerminalGuards
g = TerminalGuards()
for omega in (1.0, 1.5, -0.1):
    try:
        g.check_persistence(omega)
    except TerminalAssumptionInvalid:
        continue
    raise SystemExit(1)
raise SystemExit(0)"
chk $? "an invalid persistence factor is refused"

py "
import sys; sys.path.insert(0,'$REPO')
from engine.goh_dip_tong.expectations import reverse_solver
from engine.goh_dip_tong.valuation import methods
from engine.goh_dip_tong.valuation.guards import TerminalGuards
G = TerminalGuards(); BOOK, SH, PAY, RATE = 200e12, 1.2e11, 0.5, 0.12
def at(roe):
    try:
        return methods.steady_state_value(BOOK, roe, PAY, RATE, G)['RESIDUAL_INCOME']/SH
    except Exception:
        return None
br = reverse_solver.admissible_bracket(RATE, PAY, G)
r = reverse_solver.solve_implied_roe(at, at(0.17), 0.17, at(0.17), bracket=br)
raise SystemExit(0 if abs(r.implied_sustainable_roe - 0.17) < 1e-6 else 1)"
chk $? "the reverse solver round-trips to the ROE it was given"

py "
import sys; sys.path.insert(0,'$REPO')
from engine.goh_dip_tong.common.solvers import NoRootInBracket
from engine.goh_dip_tong.expectations import reverse_solver
from engine.goh_dip_tong.valuation import methods
from engine.goh_dip_tong.valuation.guards import TerminalGuards
G = TerminalGuards(); BOOK, SH, PAY, RATE = 200e12, 1.2e11, 0.5, 0.12
def at(roe):
    try:
        return methods.steady_state_value(BOOK, roe, PAY, RATE, G)['RESIDUAL_INCOME']/SH
    except Exception:
        return None
br = reverse_solver.admissible_bracket(RATE, PAY, G)
try:
    reverse_solver.solve_implied_roe(at, 1e12, 0.15, at(0.15), bracket=br)
except NoRootInBracket:
    raise SystemExit(0)
raise SystemExit(1)"
chk $? "an unreachable price refuses instead of extrapolating"

py "
import sys; sys.path.insert(0,'$REPO')
from engine.goh_dip_tong.models.bank import build_bridge
from engine.goh_dip_tong.valuation.guards import TerminalGuards
G = TerminalGuards()
prev = dict(sustainable_roe=0.15, payout=0.5, cost_of_equity=0.12,
            opening_book=200e12, shares=1.2e11)
inside = dict(prev, sustainable_roe=0.17, cost_of_equity=0.11, opening_book=218e12)
outside = dict(inside, payout=0.6)
a = build_bridge(200e12, 1.2e11, 0.5, 0.12, G, prev, inside, tolerance=1e-9)
b = build_bridge(200e12, 1.2e11, 0.5, 0.12, G, prev, outside, tolerance=1e-9)
raise SystemExit(0 if a.reconciles and not b.reconciles and b.unexplained != 0 else 1)"
chk $? "the bridge reconciles on declared factors and reports the rest as unexplained"

py "
import ast
src = open('$REPO/engine/goh_dip_tong/narration/views.py').read()
bad = [type(n.op).__name__ for n in ast.walk(ast.parse(src))
       if isinstance(n, ast.BinOp)
       and type(n.op).__name__ in {'Add','Sub','Mult','Div','Pow'}]
raise SystemExit(0 if not bad else 1)"
chk $? "the narration layer contains no arithmetic"

py "
import sys; sys.path.insert(0,'$REPO')
from engine.goh_dip_tong.models.registry import build_registry
from engine.goh_dip_tong.settings import get_engine_settings
reg = build_registry(get_engine_settings().pipeline.models())
raise SystemExit(0 if sorted(f for f, m in reg.items() if m.implemented) == ['BANK'] else 1)"
chk $? "only BANK implements valuation mathematics"

# ═══════════════════════════════════════════════════════════════════════════
hdr "13. Research package, views and UI states (slice 3)"

py "
import sys; sys.path.insert(0,'$REPO')
from engine.goh_dip_tong import RESEARCH_RULE_REGISTRY_HASH
from engine.goh_dip_tong.research.rules import RULES
print('        declared: ' + RESEARCH_RULE_REGISTRY_HASH[:32] + '…')
raise SystemExit(0 if RULES.registry_hash() == RESEARCH_RULE_REGISTRY_HASH else 1)"
chk $? "the research-rule registry hash matches the declared constant"

py "
import ast, pathlib
BAD = {'Add','Sub','Mult','Div','Pow','FloorDiv','Mod'}
mods = ['engine/goh_dip_tong/research/rules.py',
        'engine/goh_dip_tong/research/records.py',
        'engine/goh_dip_tong/research/package.py',
        'engine/goh_dip_tong/narration/views.py']
bad = []
for m in mods:
    src = (pathlib.Path('$REPO') / m).read_text(encoding='utf-8')
    bad += [m + ':' + str(n.lineno) for n in ast.walk(ast.parse(src))
            if isinstance(n, ast.BinOp) and type(n.op).__name__ in BAD]
if bad: print(bad[:5])
raise SystemExit(0 if not bad else 1)"
chk $? "no narrative module contains arithmetic"

py "
import json, pathlib
d = json.loads((pathlib.Path('$REPO')
    / 'engine/goh_dip_tong/fixtures/ui_states/FULL_RESEARCH.json')
    .read_text(encoding='utf-8'))
known = set()
for r in d['researchRefs']['evidence'] + d['researchRefs']['modelAudit']:
    known.update(r['supportingEvidence'])
bad = [r['id'] for r in d['thesis']['records']
       if not r['supportingEvidence']
       or not set(r['supportingEvidence']) <= known]
if bad: print(bad)
raise SystemExit(0 if d['thesis']['records'] and not bad else 1)"
chk $? "every thesis statement references registered evidence"

py "
import json, pathlib
d = json.loads((pathlib.Path('$REPO')
    / 'engine/goh_dip_tong/fixtures/ui_states/FULL_RESEARCH.json')
    .read_text(encoding='utf-8'))
known = set()
for r in d['researchRefs']['evidence'] + d['researchRefs']['modelAudit']:
    known.update(r['supportingEvidence'])
bad = [r['id'] for r in d['counterThesis']['records']
       if not r['supportingEvidence']
       or not set(r['supportingEvidence']) <= known]
if bad: print(bad)
raise SystemExit(0 if d['counterThesis']['records'] and not bad else 1)"
chk $? "every counter-thesis statement references registered evidence"

py "
import json, pathlib
d = json.loads((pathlib.Path('$REPO')
    / 'engine/goh_dip_tong/fixtures/ui_states/FULL_RESEARCH.json')
    .read_text(encoding='utf-8'))
items = d['catalysts'] + d['risks'] + d['breakers']
ids = [r['id'] for r in items]
ok = bool(items) and len(ids) == len(set(ids)) and all(
    r['id'].startswith('SYNB.') and r['ruleId'] in r['id'] for r in items)
print('        catalysts %d  risks %d  breakers %d' % (
    len(d['catalysts']), len(d['risks']), len(d['breakers'])))
raise SystemExit(0 if ok else 1)"
chk $? "every catalyst, risk and breaker has a stable unique ID"

py "
import json, pathlib
d = json.loads((pathlib.Path('$REPO')
    / 'engine/goh_dip_tong/fixtures/ui_states/FULL_RESEARCH.json')
    .read_text(encoding='utf-8'))
items = d['catalysts'] + d['risks'] + d['breakers']
bad = [r['id'] for r in items
       if not r['supportingEvidence'] or not r['supportingRecords']
       or not (r.get('severity') or r.get('importance'))]
if bad: print(bad)
raise SystemExit(0 if items and not bad else 1)"
chk $? "every catalyst, risk and breaker is cited and ranked"

py "
import sys; sys.path.insert(0,'$REPO')
from engine.goh_dip_tong.research.records import (
    RecordType, ResearchRecord, UnsupportedClaim)
base = dict(record_id='X.THESIS.r.ALL', record_type=RecordType.THESIS,
            statement='A claim.', rule_id='r',
            supporting_records=('a',), supporting_evidence=('b',),
            importance='HIGH')
cases = [dict(base, supporting_evidence=()),
         dict(base, supporting_records=()),
         dict(base, statement='This one is undervalued.'),
         dict(base, rule_id='')]
for case in cases:
    try:
        ResearchRecord(**case)
    except UnsupportedClaim:
        continue
    raise SystemExit(1)
raise SystemExit(0)"
chk $? "an unsupported or uncited claim is rejected at construction"

py "
import json, pathlib
d = json.loads((pathlib.Path('$REPO')
    / 'engine/goh_dip_tong/fixtures/ui_states/FULL_RESEARCH.json')
    .read_text(encoding='utf-8'))
uncle = {i['ref']: json.dumps(i['value']) for i in d['uncleView']['items']}
analyst = {i['ref']: json.dumps(i['value']) for i in d['analystView']['items']}
shared = set(uncle) & set(analyst)
ok = bool(shared) and set(uncle) <= set(analyst) and all(
    uncle[r] == analyst[r] for r in shared)
print('        uncle %d items, analyst %d items, %d shared refs' % (
    len(uncle), len(analyst), len(shared)))
raise SystemExit(0 if ok else 1)"
chk $? "Uncle and Analyst views share calculated-record IDs and identical numbers"

py "
import json, pathlib
d = json.loads((pathlib.Path('$REPO')
    / 'engine/goh_dip_tong/fixtures/ui_states/FULL_RESEARCH.json')
    .read_text(encoding='utf-8'))
u = {c['id']: c['statement'] for c in d['uncleView']['conclusions']}
a = {c['id']: c['statement'] for c in d['analystView']['conclusions']}
ok = bool(u) and set(u) <= set(a) and all(u[i] == a[i] for i in u)
raise SystemExit(0 if ok else 1)"
chk $? "both views project the same research records"

py "
import json, pathlib, sys; sys.path.insert(0,'$REPO')
from engine.goh_dip_tong.publishing.ui_states import UI_STATE_CASES
from engine.goh_dip_tong.settings import get_engine_settings
from pipeline.goh_dip_tong.validation.schema import validate_document
s = get_engine_settings()
root = pathlib.Path('$REPO') / 'engine/goh_dip_tong/fixtures/ui_states'
bad = []
for case in UI_STATE_CASES:
    d = json.loads((root / case.filename).read_text(encoding='utf-8'))
    r = validate_document('research-snapshot', d, subject=d['ticker'],
                          settings=s.pipeline)
    if not r.ok or d['uiState'] != str(case.state):
        bad.append(case.filename)
if bad: print(bad)
raise SystemExit(0 if len(UI_STATE_CASES) == 6 and not bad else 1)"
chk $? "all six UI-state fixtures exist and validate against the output schema"
ev "FULL_RESEARCH, MODEL_UNDER_VALIDATION, ONBOARDING, STALE, SUSPENDED, PARTIAL"

py "
import json, pathlib
root = pathlib.Path('$REPO') / 'engine/goh_dip_tong/fixtures/ui_states'
bad = []
for p in sorted(root.glob('*.json')):
    d = json.loads(p.read_text(encoding='utf-8'))
    if (d['mode'] != 'FIXTURE_TEST_ONLY'
            or 'FIXTURE_TEST_ONLY' not in d['quality']['flags']
            or not d['disclaimers'][0].startswith('FIXTURE_TEST_ONLY')
            or 'not live, current or authoritative' not in d['disclaimers'][0]):
        bad.append(p.name)
if bad: print(bad)
raise SystemExit(0 if not bad else 1)"
chk $? "every UI fixture is FIXTURE_TEST_ONLY and carries a visible disclaimer"

py "
import json, pathlib
root = pathlib.Path('$REPO') / 'engine/goh_dip_tong/fixtures/ui_states'
bad = []
for p in sorted(root.glob('*.json')):
    d = json.loads(p.read_text(encoding='utf-8'))
    if not (d.get('freshness') and d.get('quality') and d.get('evidence')
            and d['researchRefs']['status'] == 'PRODUCED'
            and d['modelAudit'].get('ruleRegistryHash')
            and d['modelAudit'].get('formulaRegistryHash')):
        bad.append(p.name)
if bad: print(bad)
raise SystemExit(0 if not bad else 1)"
chk $? "every UI fixture carries freshness, quality, evidence and model audit"

py "
import json, pathlib
root = pathlib.Path('$REPO') / 'engine/goh_dip_tong/fixtures/ui_states'
valued = {}
for p in sorted(root.glob('*.json')):
    d = json.loads(p.read_text(encoding='utf-8'))
    if d['valuation']['status'] == 'VALUED':
        valued[p.stem] = d['ticker']
print('        valued: ' + repr(valued))
raise SystemExit(0 if valued == {'FULL_RESEARCH': 'SYNB'} else 1)"
chk $? "only the synthetic bank is valued, and no fixture names a real issuer"

SB=$(mk_sandbox uifixtures)
(cd "$SB" && python3 -m engine.goh_dip_tong.cli ui-fixtures \
             --write-mode commit >/dev/null 2>&1)
py "
import pathlib
a = pathlib.Path('$REPO') / 'engine/goh_dip_tong/fixtures/ui_states'
b = pathlib.Path('$SB') / 'engine/goh_dip_tong/fixtures/ui_states'
bad = [p.name for p in sorted(a.glob('*.json'))
       if p.read_bytes() != (b / p.name).read_bytes()]
if bad: print(bad)
raise SystemExit(0 if not bad else 1)"
chk $? "regenerating every UI fixture reproduces it byte for byte"

SB=$(mk_sandbox realissuers)
(cd "$SB" && python3 -m engine.goh_dip_tong.cli research-build --all \
             --as-of 2026-07-31 --write-mode commit >/dev/null 2>&1)
py "
import json, pathlib
root = pathlib.Path('$SB') / 'data/goh-dip-tong/research-snapshots'
bad = []
seen = 0
for p in sorted(root.rglob('*/*/*.json')):
    d = json.loads(p.read_text(encoding='utf-8'))
    seen += 1
    text = json.dumps(d)
    if (d['valuation']['status'] != 'REFUSED'
            or d['marketImplied']['available'] is not False
            or d['marketImplied']['cases'] != {}
            or 'valuePerShare' in text or 'targetPrice' in text
            or d['thesis']['status'] != 'NOT_PRODUCED'
            or d['catalysts'] or d['risks'] or d['breakers']):
        bad.append(d['ticker'])
print('        issuers checked: %d' % seen)
if bad: print(bad)
raise SystemExit(0 if seen and not bad else 1)"
chk $? "every real issuer refuses, with no target price and no market-implied case"

py "
import json, pathlib
root = pathlib.Path('$SB') / 'data/goh-dip-tong/research-snapshots'
bad = [p.name for p in sorted((root / 'current').glob('*.json'))
       if not json.loads(p.read_text(encoding='utf-8')).get('uiState')]
if bad: print(bad)
states = sorted({json.loads(p.read_text(encoding='utf-8'))['uiState']
                 for p in sorted((root / 'current').glob('*.json'))})
print('        pointer uiState: ' + repr(states))
raise SystemExit(0 if not bad else 1)"
chk $? "every current pointer names the state a UI would render"

py "
import copy, json, sys; sys.path.insert(0,'$SB')
from engine.goh_dip_tong.contracts.model import ModelContext
from engine.goh_dip_tong.inputs import loader
from engine.goh_dip_tong.models.registry import model_for
from engine.goh_dip_tong.publishing import snapshot as snap
from engine.goh_dip_tong.settings import EngineSettings
from engine.goh_dip_tong import MODEL_VERSION
from pipeline.goh_dip_tong.settings import Settings
s = EngineSettings(pipeline=Settings(repo_root='$SB'))
ei = loader.load(s, 'BBCA', as_of='2026-07-31',
                 model_version=MODEL_VERSION, calculated_at='x')
m = model_for(s.pipeline.models(), ei.identity.get('modelFamily'))
doc = snap.build(s, ei, m, ModelContext(models_config=s.pipeline.models()), 'x')
path = s.output_snapshot('BBCA', doc['asOf'], doc['modelVersion'])
pointer = s.output_current / 'BBCA.json'
before = (path.read_bytes(), pointer.read_bytes())
corrupt = copy.deepcopy(doc)
corrupt['researchStatus'] = 'NOT_A_STATUS'
corrupt['contentHash'] = 'a' * 64
try:
    snap.write(s, corrupt)
except snap.InvalidSnapshot:
    after = (path.read_bytes(), pointer.read_bytes())
    raise SystemExit(0 if after == before else 1)
raise SystemExit(1)"
chk $? "an invalid snapshot cannot replace the last valid one"

# ═══════════════════════════════════════════════════════════════════════════
hdr "14. Boundaries"

! grep -rlw "BBCA" "$REPO/engine" --include="*.py" | grep -qv tests/
chk $? "no ticker is hard-coded in engine source (tests excluded)"

git diff --quiet HEAD -- index.html goh-pok-tong.html _config.yml CNAME
chk $? "index.html, goh-pok-tong.html, _config.yml and CNAME are untouched"

git diff --quiet HEAD -- config/goh-dip-tong/schedules.yml config/goh-dip-tong/sources.yml
chk $? "schedules.yml and sources.yml are unchanged — nothing enabled"

py "
import yaml
p = yaml.safe_load(open('$REPO/config/goh-dip-tong/sources.yml'))['providers']
live = [k for k, v in p.items() if v.get('kind') != 'fixture' and v.get('enabled')]
raise SystemExit(0 if not live else 1)"
chk $? "no live provider is enabled"

# Stage 3 has now built goh-dip-tong.html. What must remain true is that the
# ENGINE does not build it: the engine produces JSON the UI reads, and a
# calculation stage that emitted markup would have crossed a boundary that
# keeps the two independently testable.
py "
import pathlib
bad = [str(p.relative_to('$REPO')) for p in sorted(pathlib.Path('$REPO/engine').rglob('*.py'))
       if 'tests' not in p.parts and 'goh-dip-tong.html' in p.read_text(encoding='utf-8')]
if bad: print(bad)
raise SystemExit(0 if not bad else 1)"
chk $? "the engine does not build or write the Stage 3 UI page"

py "
import ast, pathlib
bad = []
for p in sorted(pathlib.Path('$REPO/pipeline').rglob('*.py')):
    for n in ast.walk(ast.parse(p.read_text())):
        if isinstance(n, ast.Import):
            bad += [a.name for a in n.names if a.name.split('.')[0] == 'engine']
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            if n.module.split('.')[0] == 'engine': bad.append(n.module)
raise SystemExit(0 if not bad else 1)"
chk $? "no Stage 1 module imports the engine — the dependency stays one-way"

# ═══════════════════════════════════════════════════════════════════════════
hdr "Isolation self-check"

REPO_DATA_AFTER="$(tree_hash "$REPO/data/goh-dip-tong")"
REPO_CONFIG_AFTER="$(tree_hash "$REPO/config/goh-dip-tong")"
[ "$REPO_DATA_BEFORE" = "$REPO_DATA_AFTER" ] && \
[ "$REPO_CONFIG_BEFORE" = "$REPO_CONFIG_AFTER" ]
chk $? "this acceptance run left generated datasets and config byte-identical"
ev "data/   ${REPO_DATA_BEFORE:0:24}… → ${REPO_DATA_AFTER:0:24}…"
ev "config/ ${REPO_CONFIG_BEFORE:0:24}… → ${REPO_CONFIG_AFTER:0:24}…"
ev "every write went to a throwaway sandbox under \$(mktemp -d), now removed"

# ═══════════════════════════════════════════════════════════════════════════
printf '\n\033[1m%s\033[0m\n%s\n' "RESULT" "$(printf '─%.0s' $(seq 1 78))"
printf "  checks passed: %d\n  checks failed: %d\n" "$PASS" "$FAIL"
if [ "$FAIL" = "0" ]; then
  printf "  \033[32mSTAGE 2 SLICES 1-3 ACCEPTANCE: PASS\033[0m\n"
  exit 0
fi
printf "  \033[31mSTAGE 2 SLICES 1-3 ACCEPTANCE: FAIL\033[0m\n"
exit 1
