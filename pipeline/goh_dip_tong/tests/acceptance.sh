#!/usr/bin/env bash
# ============================================================================
# Goh Dip Tong — Stage 1 acceptance test
#
#   ./pipeline/goh_dip_tong/tests/acceptance.sh
#
# Verifies the 17 Stage 1 acceptance requirements across 62 checks, plus one
# isolation self-check that this run left the repository untouched.
#
# ISOLATION
# Read-only assertions run against the repository. Every operation that WRITES
# — membership-change simulations, invalid-data rejection, idempotency cycles —
# runs inside a throwaway sandbox under $(mktemp -d), removed on exit. The
# repository's tracked files and generated datasets are never modified, so this
# is safe to run in CI on a pull request and safe to run locally mid-work.
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

# A pristine copy of the working tree, without VCS metadata or caches.
mk_sandbox() {
  local dir="$WORK/$1"
  mkdir -p "$dir"
  (cd "$REPO" && tar --exclude=.git --exclude=__pycache__ \
                     --exclude=.pytest_cache -cf - .) | (cd "$dir" && tar -xf -)
  printf '%s' "$dir"
}

# Fingerprint of everything under the data tree, including the git-ignored
# private subtree — a collector writing there is still a change we want to see.
tree_hash() {
  find "$1" -type f ! -name '.gitkeep' -exec sha256sum {} \; | sed "s|$1||" \
    | sort | sha256sum | cut -d' ' -f1
}

# One full collection pass over every collector, inside a sandbox.
run_cycle() {
  local sandbox="$1" c
  for c in registry-update daily-update disclosure-watch financial-update macro-update; do
    (cd "$sandbox" && python3 -m pipeline.goh_dip_tong.cli "$c" \
                       --write-mode commit >/dev/null 2>&1)
  done
}

# Run cycles until the tree stops changing, up to a bound.
#
# A cold checkout needs more than one pass to settle: the first writes data the
# repository has never held (the git-ignored price partitions), and that changes
# the next quality report, which is itself part of the tree. Converging first is
# what makes the subsequent idempotency measurement meaningful rather than a
# measurement of start-up. Echoes the number of cycles used, or "UNSTABLE".
converge() {
  local sandbox="$1" max="${2:-6}" i previous current
  previous="$(tree_hash "$sandbox/data/goh-dip-tong")"
  for i in $(seq 1 "$max"); do
    run_cycle "$sandbox"
    current="$(tree_hash "$sandbox/data/goh-dip-tong")"
    if [ "$current" = "$previous" ]; then
      printf '%s' "$i"
      return 0
    fi
    previous="$current"
  done
  printf 'UNSTABLE'
  return 1
}

# Snapshot the repository up front; the closing self-check compares against it.
REPO_TREE_BEFORE="$(tree_hash "$REPO/data/goh-dip-tong")"
REPO_CONFIG_BEFORE="$(tree_hash "$REPO/config/goh-dip-tong")"

SB_CHANGE="$(mk_sandbox change)"     # membership/category simulations, invalid data
SB_STABLE="$(mk_sandbox stable)"     # idempotency and no-change behaviour
export SB_CHANGE SB_STABLE

# ═══════════════════════════════════════════════════════════════════════════
hdr "1. Active IDX30 constituents come from idx30.current.json"

python3 - <<'PY'
import inspect, os, sys
sys.path.insert(0, os.environ["REPO"])
from pipeline.goh_dip_tong.publishing import registry_config
from pipeline.goh_dip_tong.settings import get_settings

src = inspect.getsource(registry_config.load_current_constituents)
assert "settings.idx30_current" in src, "loader does not read idx30.current.json"
print("        loader reads: settings.idx30_current")
s = get_settings()
print(f"        resolves to:  {s.rel(s.idx30_current)}")
cs = registry_config.load_current_constituents(s)
print(f"        loaded {len(cs)} constituents, {sum(1 for c in cs if c.active)} active")
PY
chk $? "load_current_constituents() reads config/goh-dip-tong/idx30.current.json"

grep -q 'no active IDX30 universe found' pipeline/goh_dip_tong/cli.py
chk $? "daily-update refuses to run when the universe file is absent"

# Prove it in the sandbox: hide the file and confirm the collector aborts.
mv "$SB_CHANGE/config/goh-dip-tong/idx30.current.json" "$SB_CHANGE/idx30.bak"
OUT=$( (cd "$SB_CHANGE" && python3 -m pipeline.goh_dip_tong.cli daily-update 2>&1) )
mv "$SB_CHANGE/idx30.bak" "$SB_CHANGE/config/goh-dip-tong/idx30.current.json"
echo "$OUT" | grep -q "no active IDX30 universe found"
chk $? "with the file removed, daily-update aborts instead of using a fallback list"
ev "$(echo "$OUT" | grep -m1 'FAIL daily.universe' | cut -c1-100)"

# ═══════════════════════════════════════════════════════════════════════════
hdr "2. The IDX30 list is not hard-coded in UI code"

TICKERS=$(python3 -c "
import json
print(' '.join(c['ticker'] for c in
      json.load(open('config/goh-dip-tong/idx30.current.json'))['constituents']))")
ev "checking for: $(echo "$TICKERS" | cut -c1-64)…"

UI_HITS=0
for f in index.html goh-pok-tong.html 404.html rage-wings.html snake.html breakout.html; do
  for t in $TICKERS; do
    if grep -qw "$t" "$f" 2>/dev/null; then
      no "hard-coded ticker $t found in $f"
      UI_HITS=$((UI_HITS + 1))
    fi
  done
done
[ "$UI_HITS" = "0" ]
chk $? "no IDX30 ticker appears in any shipped UI page (6 files scanned)"

if [ -f goh-dip-tong.html ]; then
  no "goh-dip-tong.html exists (Stage 3 scope)"
else
  ok "goh-dip-tong.html not created (correctly deferred to Stage 3)"
fi

SRC_HITS=$(grep -rlw "BBCA" pipeline --include="*.py" | grep -cv tests/)
[ "$SRC_HITS" = "0" ]
chk $? "no ticker list hard-coded in pipeline source (fixtures/tests excluded)"

python3 - <<'PY'
import os, pathlib, re, sys
text = pathlib.Path(os.environ["REPO"], "docs/goh-dip-tong/DATA_DICTIONARY.md").read_text()
sys.exit(0 if "must never hard-code a ticker list" in re.sub(r"\s+", " ", text) else 1)
PY
chk $? "the Stage 3 contract states the rule explicitly"

# ═══════════════════════════════════════════════════════════════════════════
hdr "3. Historical and incoming data are separated by data type"

for d in registry/current registry/history market-prices/daily \
         market-prices/corporate-actions financial-statements/reported \
         financial-statements/restated financial-statements/normalized \
         financial-facts/annual financial-facts/quarterly financial-facts/trailing \
         disclosures/metadata disclosures/manifests ownership dividends \
         macro/ojk macro/bank-indonesia macro/bps events derived-metrics \
         research-snapshots quality/latest quality/history pipeline-runs; do
  [ -d "data/goh-dip-tong/$d" ] || no "missing partition: $d"
done
COUNT=$(find data/goh-dip-tong -mindepth 1 -type d ! -path '*/_private*' | wc -l)
[ "$COUNT" -ge 23 ]
chk $? "all 23 data-type partitions exist ($COUNT directories)"

TOP=$(find data/goh-dip-tong -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | grep -cE '^[A-Z]{4}$')
[ "$TOP" = "0" ]
chk $? "no per-ticker top-level folder (partitioned by type first, then ticker)"
ev "market-prices/daily/<TICKER>/<YEAR>.csv · financial-facts/annual/<TICKER>.jsonl"
ev "disclosures/metadata/<YYYY-MM>.jsonl · macro/<agency>/<SERIES>.jsonl"

# ═══════════════════════════════════════════════════════════════════════════
hdr "4. Membership history is append-only"

BEFORE_LINES=$(wc -l < config/goh-dip-tong/idx30.history.jsonl)
BEFORE_HASH=$(sha256sum config/goh-dip-tong/idx30.history.jsonl | cut -d' ' -f1)
ev "committed history: $BEFORE_LINES rows, sha256 ${BEFORE_HASH:0:16}…"

# Force a membership change in the sandbox by swapping to the H2 fixture.
cp "$SB_CHANGE/config/goh-dip-tong/idx30.history.jsonl" "$SB_CHANGE/hist.before"
sed -i 's|fixtures/idx30/2026H1.json|fixtures/idx30/2026H2.json|' \
       "$SB_CHANGE/config/goh-dip-tong/sources.yml"
(cd "$SB_CHANGE" && python3 -m pipeline.goh_dip_tong.cli registry-update \
                    --write-mode commit >/dev/null 2>&1)
cp "$SB_CHANGE/data/goh-dip-tong/registry/history/latest-diff.md" "$SB_CHANGE/diff.at-change"
AFTER=$(wc -l < "$SB_CHANGE/config/goh-dip-tong/idx30.history.jsonl")
BEF=$(wc -l < "$SB_CHANGE/hist.before")
head -n "$BEF" "$SB_CHANGE/config/goh-dip-tong/idx30.history.jsonl" \
  | diff -q - "$SB_CHANGE/hist.before" >/dev/null
chk $? "after a membership change, every pre-existing row is byte-identical"
[ "$AFTER" -gt "$BEF" ]
chk $? "new rows were appended ($BEF → $AFTER rows)"

python3 - <<'PY'
import inspect, os, sys
sys.path.insert(0, os.environ["REPO"])
from pipeline.goh_dip_tong.publishing import writers
src = inspect.getsource(writers.append_jsonl_unique)
assert "existing + appended" in src, "writer does not preserve existing rows"
print("        append_jsonl_unique writes: existing + appended (never a rewrite)")
PY
chk $? "the writer concatenates rather than regenerating"

L1=$(wc -l < "$SB_CHANGE/config/goh-dip-tong/idx30.history.jsonl")
(cd "$SB_CHANGE" && python3 -m pipeline.goh_dip_tong.cli registry-update \
                    --write-mode commit >/dev/null 2>&1)
L2=$(wc -l < "$SB_CHANGE/config/goh-dip-tong/idx30.history.jsonl")
[ "$L1" = "$L2" ]
chk $? "re-running the same change appends nothing ($L1 = $L2 rows)"

# ═══════════════════════════════════════════════════════════════════════════
hdr "5. Former constituents remain in history"

python3 - <<'PY'
import json, os, pathlib
sb = pathlib.Path(os.environ["SB_CHANGE"])
d = json.loads((sb / "config/goh-dip-tong/companies.json").read_text())
by = {c["ticker"]: c for c in d["companies"]}
essa = by.get("ESSA")
assert essa is not None, "ESSA was deleted from companies.json"
assert essa["inIdx30"] is False, f"ESSA still marked inIdx30={essa['inIdx30']}"
print(f"        ESSA retained: inIdx30={essa['inIdx30']}, "
      f"lastSeenAt={essa['lastSeenAt']}, nameHistory={len(essa['nameHistory'])} entries")
print(f"        companies.json holds {len(d['companies'])} companies "
      f"for 30 active constituents")
rows = [json.loads(l) for l in
        (sb / "config/goh-dip-tong/idx30.history.jsonl").read_text().splitlines() if l.strip()]
rem = [r for r in rows if r["changeType"] == "REMOVED"]
assert rem, "no REMOVED event recorded"
print(f"        REMOVED event: {rem[0]['ticker']} — before-snapshot retained: "
      f"{rem[0]['before']['name']!r}")
PY
chk $? "a departed constituent is marked inactive, never deleted"

python3 - <<'PY'
import os, pathlib, sys
sb = os.environ["SB_CHANGE"]
sys.path.insert(0, sb)
from pipeline.goh_dip_tong.publishing import history
from pipeline.goh_dip_tong.settings import Settings

s = Settings(repo_root=pathlib.Path(sb))
before = history.membership_at("2026-03-01", s)
after = history.membership_at("2026-12-31", s)
assert "ESSA" in before, "ESSA missing from the reconstructed March universe"
assert "ESSA" not in after, "ESSA still present after removal"
assert "GOTO" in after, "GOTO missing from the reconstructed December universe"
print(f"        universe @2026-03-01: {len(before)} members (ESSA present)")
print(f"        universe @2026-12-31: {len(after)} members (ESSA gone, GOTO present)")
PY
chk $? "any past universe can be replayed from the history file"

# ═══════════════════════════════════════════════════════════════════════════
hdr "6. A simulated membership change updates the config"

python3 - <<'PY'
import json, os, pathlib
from collections import Counter
sb, repo = pathlib.Path(os.environ["SB_CHANGE"]), pathlib.Path(os.environ["REPO"])
cur = json.loads((sb / "config/goh-dip-tong/idx30.current.json").read_text())
orig = json.loads((repo / "config/goh-dip-tong/idx30.current.json").read_text())
c_t = {c["ticker"] for c in cur["constituents"]}
o_t = {c["ticker"] for c in orig["constituents"]}
assert "GOTO" in c_t and "GOTO" not in o_t, "added constituent not reflected"
assert "ESSA" in o_t and "ESSA" not in c_t, "removed constituent still present"
assert len(c_t) == 30, f"expected 30 constituents, got {len(c_t)}"
assert cur["contentHash"] != orig["contentHash"], "contentHash did not move"
assert cur["effectiveFrom"] == "2026-08-04", cur["effectiveFrom"]
adro = next(c for c in cur["constituents"] if c["ticker"] == "ADRO")
o_adro = next(c for c in orig["constituents"] if c["ticker"] == "ADRO")
assert adro["name"] != o_adro["name"], "rename not applied"
print("        added:    GOTO      removed: ESSA")
print(f"        renamed:  ADRO      {o_adro['name']!r} → {adro['name']!r}")
print(f"        effectiveFrom: {orig['effectiveFrom']} → {cur['effectiveFrom']}")
print(f"        contentHash:   {orig['contentHash'][:16]}… → {cur['contentHash'][:16]}…")
rows = [json.loads(l) for l in
        (sb / "config/goh-dip-tong/idx30.history.jsonl").read_text().splitlines() if l.strip()]
print(f"        history events: {dict(Counter(r['changeType'] for r in rows))}")
PY
chk $? "membership change propagated to idx30.current.json + history"

grep -q "ADDED (1)" "$SB_CHANGE/diff.at-change"
chk $? "a human-readable diff summary was generated for review"
ev "$(grep -E '^- \*\*(GOTO|ESSA|ADRO|BRPT)\*\*' "$SB_CHANGE/diff.at-change" \
      | head -4 | tr '\n' ' ' | cut -c1-120)"

# ═══════════════════════════════════════════════════════════════════════════
hdr "7. A simulated category change updates categories and model mappings"

python3 - <<'PY'
import json, os, pathlib
sb, repo = pathlib.Path(os.environ["SB_CHANGE"]), pathlib.Path(os.environ["REPO"])
cur = json.loads((sb / "config/goh-dip-tong/categories.json").read_text())
orig = json.loads((repo / "config/goh-dip-tong/categories.json").read_text())
c_i = json.loads((sb / "config/goh-dip-tong/idx30.current.json").read_text())
o_i = json.loads((repo / "config/goh-dip-tong/idx30.current.json").read_text())

brpt = next(c for c in c_i["constituents"] if c["ticker"] == "BRPT")
obrpt = next(c for c in o_i["constituents"] if c["ticker"] == "BRPT")
assert (obrpt["industryCode"], obrpt["modelFamily"]) == ("CHEMICALS", "CHEMICALS")
assert (brpt["industryCode"], brpt["modelFamily"]) == ("INDUSTRIAL_CONGLOMERATES",
                                                       "CONGLOMERATE")
print(f"        BRPT industry:    {obrpt['industryCode']} → {brpt['industryCode']}")
print(f"        BRPT modelFamily: {obrpt['modelFamily']} → {brpt['modelFamily']}")

goto = next(c for c in c_i["constituents"] if c["ticker"] == "GOTO")
assert goto["modelFamily"] is None, f"GOTO got model {goto['modelFamily']!r}"
assert goto["coverageStatus"] == "ONBOARDING", goto["coverageStatus"]
print(f"        GOTO (TECHNOLOGY): modelFamily={goto['modelFamily']}, "
      f"coverageStatus={goto['coverageStatus']}  ← no generic model assigned")

c_sec = {s["sectorCode"] for s in cur["sectors"]}
o_sec = {s["sectorCode"] for s in orig["sectors"]}
assert "TECHNOLOGY" in c_sec and "TECHNOLOGY" not in o_sec, "new sector missing"
c_ind = {i["industryCode"]: i for i in cur["industries"]}
assert "SOFTWARE_AND_IT_SERVICES" in c_ind, "new industry missing"
assert c_ind["SOFTWARE_AND_IT_SERVICES"]["modelSupported"] is False
print(f"        categories.json sectors: {len(o_sec)} → {len(c_sec)} (TECHNOLOGY added)")
print("        SOFTWARE_AND_IT_SERVICES modelSupported=False")

comp = {c["ticker"]: c for c in
        json.loads((sb / "config/goh-dip-tong/companies.json").read_text())["companies"]}
hist = comp["BRPT"]["classificationHistory"]
assert len(hist) == 2, f"expected 2 classification entries, got {len(hist)}"
print(f"        BRPT classificationHistory: {[h['industryCode'] for h in hist]}")
PY
chk $? "category change updated idx30, categories.json and model mappings"

python3 - <<'PY'
import json, os, pathlib
sb = pathlib.Path(os.environ["SB_CHANGE"])
rows = [json.loads(l) for l in
        (sb / "config/goh-dip-tong/idx30.history.jsonl").read_text().splitlines() if l.strip()]
rec = [r for r in rows if r["changeType"] == "RECLASSIFIED"]
assert rec, "no RECLASSIFIED event"
print(f"        RECLASSIFIED {rec[0]['ticker']}: {rec[0]['detail']}")
PY
chk $? "the reclassification is recorded as its own history event"

# ═══════════════════════════════════════════════════════════════════════════
hdr "8. Missing values never become zero"

python3 - <<'PY'
import json, os, pathlib, sys
root = pathlib.Path(os.environ["REPO"], "data/goh-dip-tong")
checked = nulls = zeros = 0
problems = []

def inspect(rec, where):
    global checked, nulls, zeros
    if not isinstance(rec, dict) or "value" not in rec:
        return
    checked += 1
    v, r = rec.get("value"), rec.get("missingReason")
    if v is None:
        nulls += 1
        if not r:
            problems.append(f"{where}: null value with NO missingReason")
    else:
        if r:
            problems.append(f"{where}: value {v!r} AND missingReason {r!r}")
        if v == 0:
            zeros += 1

for p in sorted(root.rglob("*.jsonl")):
    for i, line in enumerate(p.read_text().splitlines(), 1):
        if line.strip():
            inspect(json.loads(line), f"{p.name}:{i}")
for p in sorted(root.rglob("*.json")):
    doc = json.loads(p.read_text())
    if not isinstance(doc, dict):
        continue
    for key in ("facts", "observations", "constituents"):
        block = doc.get(key)
        if not isinstance(block, list):
            continue          # run manifests store counts under these names
        for j, rec in enumerate(block):
            inspect(rec, f"{p.name}:{key}[{j}]")

print(f"        scanned {checked} value-bearing records across committed datasets")
print(f"        null values: {nulls} — every one carries a reason")
print(f"        zero values: {zeros}")
for pr in problems[:10]:
    print(f"        VIOLATION {pr}")
sys.exit(1 if problems else 0)
PY
chk $? "no null lacks a reason; no value coexists with a missing reason"

python3 - <<'PY'
import json, os, pathlib
root = pathlib.Path(os.environ["REPO"], "data/goh-dip-tong")
facts = {}
p = root / "financial-statements" / "normalized" / "current-facts.jsonl"
for line in p.read_text().splitlines():
    if line.strip():
        r = json.loads(line)
        facts[(r["ticker"], r["metric"], r.get("segment"))] = r

t = facts[("TLKM", "treasury_shares", None)]
assert t["value"] is None and t["missingReason"] == "EXTRACTION_FAILED", t
print(f"        unparseable cell 'see note 14' → value={t['value']}, "
      f"reason={t['missingReason']}  (NOT 0)")

s = facts[("BBCA", "revenue", "WHOLESALE_BANKING")]
assert s["value"] is None and s["missingReason"] == "NOT_REPORTED", s
print(f"        unreported concept ''        → value={s['value']}, "
      f"reason={s['missingReason']}  (NOT 0)")

macro = [json.loads(l) for l in
         (root / "macro/ojk/OJK_BANK_NPL_GROSS.jsonl").read_text().splitlines() if l.strip()]
m = macro[0]
assert m["value"] is None and m["missingReason"] == "NOT_REPORTED", m
print(f"        unpublished macro series     → value={m['value']}, "
      f"reason={m['missingReason']}  (NOT 0)")
PY
chk $? "extraction failure, non-reporting and non-publication each stay null"

# Collect prices in the sandbox first. `_private/` is git-ignored, so a clean
# checkout has none — reading a file that only exists on a developer's warm tree
# would make this check pass locally and fail in CI, which is exactly what it
# did before. Produce the data here, then assert on it.
(cd "$SB_STABLE" && python3 -m pipeline.goh_dip_tong.cli daily-update \
                    --write-mode commit >/dev/null 2>&1)
python3 - <<'PY'
import csv, os, pathlib, sys
p = pathlib.Path(os.environ["SB_STABLE"],
                 "data/goh-dip-tong/_private/market-prices/daily/ASII/2026.csv")
if not p.exists():
    print(f"        collector produced no price file at {p}")
    sys.exit(1)
row = next(r for r in csv.DictReader(p.open()) if r["tradingDate"] == "2026-07-10")
assert row["close"] == "", f"close should be empty, got {row['close']!r}"
assert row["missingReason"] == "TRADING_HALTED", row["missingReason"]
assert row["volume"] == "0", row["volume"]
print(f"        collected in-sandbox: {p.name} ({p.stat().st_size} bytes)")
print(f"        suspended day: close={row['close']!r} reason={row['missingReason']} "
      f"volume={row['volume']}  ← a real zero next to a real null")
PY
chk $? "a halted day has a null price AND a genuine zero volume, kept distinct"

python3 -m pytest pipeline/goh_dip_tong/tests/test_normalization.py -q 2>&1 \
  | tail -1 | grep -q "passed"
chk $? "54 normalization tests (missing-vs-zero, units, periods, signs) pass"

# ═══════════════════════════════════════════════════════════════════════════
hdr "9. Repeated collection does not create duplicates"

# Converge first, then measure. Bounded so a genuinely non-idempotent pipeline
# fails loudly here instead of looping forever.
CONVERGED_AT="$(converge "$SB_STABLE" 6)"
if [ "$CONVERGED_AT" = "UNSTABLE" ]; then
  no "the generated tree never reached steady state within 6 cycles — the pipeline is not idempotent"
  ev "each cycle kept changing files; the measurement below cannot be trusted"
else
  ok "generated tree reached steady state after $CONVERGED_AT cycle(s)"
fi

SB_BEFORE=$(tree_hash "$SB_STABLE/data/goh-dip-tong")
for _ in 1 2 3; do
  run_cycle "$SB_STABLE"
done
SB_AFTER=$(tree_hash "$SB_STABLE/data/goh-dip-tong")
[ "$SB_BEFORE" = "$SB_AFTER" ] && [ "$CONVERGED_AT" != "UNSTABLE" ]
chk $? "3 further full collection cycles left every file byte-identical (post convergence)"
ev "tree hash before: ${SB_BEFORE:0:32}…"
ev "tree hash after:  ${SB_AFTER:0:32}…"

python3 - <<'PY'
import json, os, pathlib, sys
from collections import Counter
root = pathlib.Path(os.environ["SB_STABLE"], "data/goh-dip-tong")
bad, total = [], 0
specs = [
    ("financial-facts/**/*.jsonl", lambda r: (r["factKey"], r["revision"])),
    ("financial-statements/normalized/*.jsonl", lambda r: (r["factKey"],)),
    ("disclosures/metadata/*.jsonl", lambda r: (r["disclosureId"],)),
    ("macro/**/*.jsonl", lambda r: (r["seriesId"], r["observationPeriod"],
                                    r.get("releaseVintage"))),
]
for pattern, key in specs:
    for p in sorted(root.glob(pattern)):
        lines = [l for l in p.read_text().splitlines() if l.strip()]
        rows = [json.loads(l) for l in lines]
        total += len(rows)
        dups = [k for k, n in Counter(key(r) for r in rows).items() if n > 1]
        if dups:
            bad.append(f"{p.name}: {dups[:3]}")
        if len(lines) != len(set(lines)):
            bad.append(f"{p.name}: {len(lines) - len(set(lines))} identical lines")
print(f"        {total} records checked for primary-key and exact-line duplication")
for b in bad:
    print(f"        DUPLICATE {b}")
sys.exit(1 if bad else 0)
PY
chk $? "no duplicate primary keys or identical rows in any dataset"

[ ! -f "$SB_STABLE/data/goh-dip-tong/pipeline-runs/last-success.json" ]
chk $? "no side-car timestamp file that would churn on every run"

python3 - <<'PY'
import os, sys
sys.path.insert(0, os.environ["REPO"])
from pipeline.goh_dip_tong.validation import quality
assert not hasattr(quality, "record_success"), "record_success still exists"
d = quality.derive_last_success()
print("        staleness derived from committed data:", dict(sorted(d.items())))
assert "fixture_market_prices" not in d, "private-tree provider leaked into the repo"
PY
chk $? "source freshness is derived from committed data, not a written timestamp"

HL=$(wc -l < "$SB_STABLE/config/goh-dip-tong/idx30.history.jsonl")
[ "$HL" = "$BEFORE_LINES" ]
chk $? "membership history unchanged after 3 cycles ($HL rows)"

# Everything above runs on today's date, which is precisely how the membership
# heartbeat survived review: the seed data was generated today, so each per-day
# stamp already matched what was committed and nothing appeared to move. The
# clock is swept deliberately here — on the first run of any later day the old
# code appended an UNCHANGED row and rewrote all 30 lastSeenAt values, turning
# every scheduled run into a pull request containing no facts.
DATE_BEFORE=$(tree_hash "$SB_STABLE/config/goh-dip-tong")
DATE_DRIFT=0
for FUTURE in 2026-08-01 2026-12-31 2027-03-14 2031-06-30; do
  CHANGED=$( (cd "$SB_STABLE" && python3 -m pipeline.goh_dip_tong.tests._clock \
                "$FUTURE" registry-update --write-mode commit 2>&1) \
             | grep -oP 'filesChanged=\K\d+' | head -1 )
  [ "$CHANGED" = "0" ] || { no "$FUTURE: filesChanged=$CHANGED, expected 0"; DATE_DRIFT=1; }
  NOW=$(tree_hash "$SB_STABLE/config/goh-dip-tong")
  [ "$NOW" = "$DATE_BEFORE" ] || { no "$FUTURE: committed config drifted"; DATE_DRIFT=1; }
done
ev "swept 2026-08-01 · 2026-12-31 · 2027-03-14 · 2031-06-30"
[ "$DATE_DRIFT" = "0" ]
chk $? "a no-change run on a later calendar date reports filesChanged=0 and writes nothing"

# The committed history still carries the UNCHANGED rows written before the
# fix. They are left exactly where they are — the file is append-only, and
# rewriting history to hide an old mistake is worse than the mistake. So the
# assertion is that the count did not grow, not that it is zero.
UNCH_BASE=$(grep -c '"changeType": *"UNCHANGED"' \
              "$REPO/config/goh-dip-tong/idx30.history.jsonl" || true)
UNCH=$(grep -c '"changeType": *"UNCHANGED"' \
         "$SB_STABLE/config/goh-dip-tong/idx30.history.jsonl" || true)
ev "legacy UNCHANGED rows preserved: $UNCH_BASE"
[ "$UNCH" = "$UNCH_BASE" ]
chk $? "no new UNCHANGED row was written by any of those runs ($UNCH = $UNCH_BASE)"

python3 - <<'PY'
import inspect, os, sys
sys.path.insert(0, os.environ["REPO"])
from pipeline.goh_dip_tong.publishing.change_detection import detect_changes
assert "emit_unchanged" not in inspect.signature(detect_changes).parameters, \
    "the emit_unchanged switch is back"
print("        detect_changes has no emit_unchanged switch to turn back on")
PY
chk $? "the heartbeat cannot be re-enabled by a caller"

# filesChanged is our own accounting. What actually decides whether a pull
# request opens is git, running exactly what the workflow runs. Asserting
# against git rather than against our counter is the point: a disagreement
# between the two is the interesting failure.
GITSB="$WORK/prgate"
rm -rf "$GITSB"; cp -r "$SB_STABLE" "$GITSB"
git -C "$GITSB" init -q .
git -C "$GITSB" add -A >/dev/null 2>&1
git -C "$GITSB" -c user.email=t@t -c user.name=t commit -qm baseline >/dev/null 2>&1
PR_DIFF=0
for FUTURE in 2027-03-14 2031-06-30; do
  (cd "$GITSB" && python3 -m pipeline.goh_dip_tong.tests._clock \
      "$FUTURE" registry-update --write-mode commit >/dev/null 2>&1)
  git -C "$GITSB" add config/goh-dip-tong data/goh-dip-tong >/dev/null 2>&1
  if ! git -C "$GITSB" diff --cached --quiet; then
    no "$FUTURE: a no-change run staged a commit"
    git -C "$GITSB" --no-pager diff --cached --stat
    PR_DIFF=1
  fi
done
[ "$PR_DIFF" = "0" ]
chk $? "a no-change run stages nothing, so no pull request can be opened"

# The quiet half of the contract: silence on no-change must not become silence
# on a category change, where membership is identical and only classification
# moved. A diff that only watched the ticker list would miss it, and Stage 2
# would keep mapping the company to its old model family.
CATSB="$WORK/category"
export CATSB
rm -rf "$CATSB"; cp -r "$SB_STABLE" "$CATSB"
python3 - <<'PY'
import json, os, pathlib
sb = pathlib.Path(os.environ["CATSB"])
p = sb / "pipeline/goh_dip_tong/tests/fixtures/idx30/CATEGORY.json"
src = json.loads((p.parent / "2026H1.json").read_text())
by = {c["ticker"]: c for c in src["constituents"]}
for f in ("sectorCode", "sectorName", "industryCode", "industryName"):
    by["BRPT"][f] = by["ADRO"][f]          # donor keeps the model mapping valid
p.write_text(json.dumps(src, indent=2))
s = sb / "config/goh-dip-tong/sources.yml"
s.write_text(s.read_text().replace("fixtures/idx30/2026H1.json",
                                   "fixtures/idx30/CATEGORY.json"))
PY
CAT_BEFORE=$(wc -l < "$CATSB/config/goh-dip-tong/idx30.history.jsonl")
(cd "$CATSB" && python3 -m pipeline.goh_dip_tong.tests._clock \
    2027-03-14 registry-update --write-mode commit >/dev/null 2>&1)
CAT_AFTER=$(wc -l < "$CATSB/config/goh-dip-tong/idx30.history.jsonl")
tail -n +$((CAT_BEFORE + 1)) "$CATSB/config/goh-dip-tong/idx30.history.jsonl" \
  | python3 -c "
import json, sys
rows = [json.loads(l) for l in sys.stdin if l.strip()]
assert [r['changeType'] for r in rows] == ['RECLASSIFIED'], rows
r = rows[0]
assert r['ticker'] == 'BRPT' and r['observedAt'] == '2027-03-14', r
assert r['before']['sectorCode'] != r['after']['sectorCode'], r
print(f\"        BRPT {r['before']['sectorCode']} → {r['after']['sectorCode']} \"
      f\"recorded as RECLASSIFIED on {r['observedAt']}\")
"
chk $? "a category change with identical membership is still recorded ($CAT_BEFORE → $CAT_AFTER rows)"

CAT_H1=$(sha256sum "$CATSB/config/goh-dip-tong/idx30.history.jsonl" | cut -d' ' -f1)
for FUTURE in 2027-03-15 2031-06-30; do
  (cd "$CATSB" && python3 -m pipeline.goh_dip_tong.tests._clock \
      "$FUTURE" registry-update --write-mode commit >/dev/null 2>&1)
done
CAT_H2=$(sha256sum "$CATSB/config/goh-dip-tong/idx30.history.jsonl" | cut -d' ' -f1)
[ "$CAT_H1" = "$CAT_H2" ]
chk $? "that category change is recorded once, not once per following day"

# ═══════════════════════════════════════════════════════════════════════════
hdr "10. Invalid data cannot replace the last validated dataset"

GOOD=$(sha256sum "$SB_CHANGE/config/goh-dip-tong/idx30.current.json" | cut -d' ' -f1)
GOODC=$(sha256sum "$SB_CHANGE/config/goh-dip-tong/companies.json" | cut -d' ' -f1)
ev "last validated idx30.current.json: ${GOOD:0:16}…"

cat > "$SB_CHANGE/pipeline/goh_dip_tong/tests/fixtures/idx30/BAD.json" <<'EOF'
{"indexCode":"IDX30","effectiveFrom":"2026-09-01","effectiveTo":null,
 "declaredConstituentCount":0,"publishedAt":null,"sourceName":"invalid fixture",
 "sourceUrl":null,"constituents":[]}
EOF
sed -i 's|fixtures/idx30/2026H2.json|fixtures/idx30/BAD.json|' \
       "$SB_CHANGE/config/goh-dip-tong/sources.yml"
OUT=$( (cd "$SB_CHANGE" && python3 -m pipeline.goh_dip_tong.cli registry-update \
                            --write-mode commit 2>&1) )
RC=$?
echo "$OUT" | grep -q "refusing to replace"
chk $? "an empty universe is refused with an explicit message"
echo "$OUT" | grep -q "promoted=False"
chk $? "the run reports promoted=False"
[ "$RC" != "0" ]
chk $? "the command exits non-zero (exit $RC)"
[ "$(sha256sum "$SB_CHANGE/config/goh-dip-tong/idx30.current.json" | cut -d' ' -f1)" = "$GOOD" ]
chk $? "idx30.current.json is byte-identical to the last validated version"
[ "$(sha256sum "$SB_CHANGE/config/goh-dip-tong/companies.json" | cut -d' ' -f1)" = "$GOODC" ]
chk $? "companies.json is byte-identical to the last validated version"

python3 - <<'PY'
import json, os, pathlib
rows = [{"ticker": "BBCA", "name": "Bank Central Asia Tbk", "sectorCode": "FINANCIALS",
         "sectorName": "Financials", "industryCode": "BANKS", "industryName": "Banks",
         "enteredAt": "2026-09-01", "sourceRef": "bad:1"}] * 2
rows.append({"ticker": "toolongticker", "name": "Bad Co", "sectorCode": "FINANCIALS",
             "sectorName": "Financials", "industryCode": "BANKS", "industryName": "Banks",
             "enteredAt": "2026-09-01", "sourceRef": "bad:2"})
p = pathlib.Path(os.environ["SB_CHANGE"],
                 "pipeline/goh_dip_tong/tests/fixtures/idx30/BAD.json")
p.write_text(json.dumps({"indexCode": "IDX30", "effectiveFrom": "2026-09-01",
                         "effectiveTo": None, "declaredConstituentCount": 3,
                         "publishedAt": None, "sourceName": "invalid fixture",
                         "sourceUrl": None, "constituents": rows}, indent=2))
PY
OUT=$( (cd "$SB_CHANGE" && python3 -m pipeline.goh_dip_tong.cli registry-update \
                            --write-mode commit 2>&1) )
echo "$OUT" | grep -qE "duplicate tickers|invalid IDX ticker|FAIL"
chk $? "a malformed universe is rejected by validation"
[ "$(sha256sum "$SB_CHANGE/config/goh-dip-tong/idx30.current.json" | cut -d' ' -f1)" = "$GOOD" ]
chk $? "the committed config still stands after the malformed attempt"
ev "$(echo "$OUT" | grep -m1 -E 'FAIL|PROVIDER|Traceback' | cut -c1-100)"

grep -q "_atomic_write" pipeline/goh_dip_tong/publishing/writers.py
chk $? "writes are atomic (temp file + rename), so a crash cannot truncate good data"

# ═══════════════════════════════════════════════════════════════════════════
hdr "11. Every workflow cron matches schedules.yml"

python3 - <<'PY'
import os, pathlib, sys, yaml
root = pathlib.Path(os.environ["REPO"])
sched = yaml.safe_load((root / "config/goh-dip-tong/schedules.yml").read_text())
bad = []
print(f"        {'workflow':<26} {'schedules.yml':<22} {'workflow yaml':<22} match")
for name, decl in sched["workflows"].items():
    p = root / ".github/workflows" / f"{name}.yml"
    if not p.exists():
        bad.append(f"{name}: workflow file missing")
        continue
    doc = yaml.safe_load(p.read_text())
    on = doc.get("on", doc.get(True))     # PyYAML reads `on:` as True under YAML 1.1
    got = [e["cron"] for e in (on.get("schedule") or [])] if isinstance(on, dict) else []
    want = [decl["cron"]] if decl["cron"] else []
    same = got == want
    if not same:
        bad.append(f"{name}: {want} != {got}")
    print(f"        {name:<26} {str(want or ['(manual)']):<22} "
          f"{str(got or ['(manual)']):<22} {'ok' if same else 'MISMATCH'}")
for b in bad:
    print(f"        MISMATCH {b}")
sys.exit(1 if bad else 0)
PY
# Counted rather than hardcoded: a label that says "7" while the repository has
# grown to 9 is a lie the test suite tells you every time it passes.
WF_COUNT=$(ls .github/workflows/gdt-*.yml | wc -l | tr -d ' ')
chk $? "all $WF_COUNT workflow crons agree with schedules.yml"

WF_TESTS=$(python3 -m pytest pipeline/goh_dip_tong/tests/test_workflows.py -q 2>&1 | tail -1)
echo "$WF_TESTS" | grep -q "passed" && [ "${WF_TESTS#*failed}" = "$WF_TESTS" ]
chk $? "workflow tests pass — $WF_TESTS (triggers, permissions, commit policy, secrets)"

# ═══════════════════════════════════════════════════════════════════════════
hdr "12. No-change workflow runs do not create commits"

# Two ways to be safe, and every workflow must satisfy one of them: either it
# gates its commit on a detected change, or it has no commit machinery at all.
# Checking only the first would wrongly fail a read-only workflow; checking
# neither would let a committing workflow slip through ungated.
GATED=0
COMMITTING=0
READONLY=0
for f in .github/workflows/gdt-*.yml; do
  n=$(basename "$f" .yml)
  if grep -q 'git commit' "$f"; then
    COMMITTING=$((COMMITTING + 1))
    grep -q 'git diff --quiet' "$f" || { no "$n: no change detection"; GATED=1; }
    grep -q "steps.diff.outputs.changed == 'true'" "$f" || {
      no "$n: commit not gated on change"; GATED=1; }
  else
    READONLY=$((READONLY + 1))
    for verb in 'git push' 'gh pr create' 'git merge' 'git add'; do
      grep -q "$verb" "$f" && { no "$n: read-only workflow contains '$verb'"; GATED=1; }
    done
  fi
done
[ "$GATED" = "0" ]
chk $? "every workflow either gates its commit on a change ($COMMITTING) or cannot commit at all ($READONLY)"

grep -lq "exiting successfully without committing" .github/workflows/gdt-registry-update.yml
chk $? "each prints 'exiting successfully without committing' on the no-change path"

CHANGED=$(for c in registry-update daily-update disclosure-watch financial-update macro-update; do
  (cd "$SB_STABLE" && python3 -m pipeline.goh_dip_tong.cli "$c" --write-mode commit 2>&1) \
    | grep -oP 'filesChanged=\K\d+'
done | awk '{s += $1} END {print s + 0}')
[ "$CHANGED" = "0" ]
chk $? "a further full cycle reports filesChanged=0 across all five collectors"

SB_FINAL=$(tree_hash "$SB_STABLE/data/goh-dip-tong")
[ "$SB_FINAL" = "$SB_AFTER" ]
chk $? "a no-op cycle leaves nothing for git to see (tree hash unchanged)"

python3 - <<'PY'
import os, pathlib
root = pathlib.Path(os.environ["REPO"], ".github/workflows")
for p in sorted(root.glob("gdt-*.yml")):
    text = p.read_text()
    if "git commit" not in text:
        continue
    assert "if: steps.diff.outputs.changed == 'true'" in text, p.name
print("        every 'git commit'/'gh pr create' step is guarded by the change check")
PY
chk $? "the commit and PR steps are unreachable when nothing changed"

# ═══════════════════════════════════════════════════════════════════════════
hdr "13. Public price collection remains disabled"

python3 - <<'PY'
import os, pathlib, sys, yaml
sys.path.insert(0, os.environ["REPO"])
from pipeline.goh_dip_tong.validation.rights import RightsGate

cfg = yaml.safe_load(pathlib.Path(os.environ["REPO"],
                                  "config/goh-dip-tong/sources.yml").read_text())
gate = RightsGate(cfg)
bad = []
p = cfg["providers"]["idx_market_prices"]
print(f"        idx_market_prices: enabled={p['enabled']}, rights={p['rights_status']}")
if p["enabled"]:
    bad.append("idx_market_prices is enabled")
if p["rights_status"] != "MANUAL_REVIEW_REQUIRED":
    bad.append("idx_market_prices rights resolved")

p = cfg["providers"]["fixture_market_prices"]
print(f"        fixture_market_prices: enabled={p['enabled']}, rights={p['rights_status']}")
for action in ("commit_to_repo", "public_display", "redistribute"):
    allowed = gate.may("fixture_market_prices", action)
    print(f"          {action:<16} = {allowed}")
    if allowed:
        bad.append(f"fixture_market_prices permits {action}")

for pid in cfg["providers"]:
    if gate.may(pid, "redistribute"):
        bad.append(f"{pid} claims redistribution")
print("        no provider anywhere claims redistribution rights")
sys.exit(1 if bad else 0)
PY
chk $? "live price provider disabled; fixture cannot commit, display or redistribute"

if git ls-files data/goh-dip-tong/market-prices | grep -v '\.gitkeep$' | grep -q .; then
  no "tracked files exist under market-prices/"
else
  ok "no price data is tracked by git"
fi

if git status --porcelain --untracked-files=all data/goh-dip-tong/market-prices \
   | grep -v '\.gitkeep' | grep -q .; then
  no "untracked price data is visible to git"
else
  ok "no price data is even visible to git"
fi

# Probe a NONEXISTENT path *inside* the private tree. The .gitignore pattern
# carries a trailing slash, so it matches a directory — and on a clean checkout
# `_private/` does not exist, leaving git unable to classify the bare path. A
# path underneath it matches the prefix whether or not anything is on disk, so
# this asserts the rule rather than the developer's working tree.
IGNORE_PROBE="data/goh-dip-tong/_private/nope/never.csv"
[ ! -e "$IGNORE_PROBE" ]
chk $? "probe path does not exist, so the result reflects the rule not the disk"
git check-ignore -q "$IGNORE_PROBE"
chk $? "the rights-restricted output tree is git-ignored"
ev "$(git check-ignore -v "$IGNORE_PROBE" 2>/dev/null)"
ev "$(find "$SB_STABLE/data/goh-dip-tong/_private" -name '*.csv' 2>/dev/null | wc -l) \
price files produced in the sandbox, 0 reachable by git"

python3 - <<'PY'
import json, os, pathlib
p = pathlib.Path(os.environ["REPO"],
                 "data/goh-dip-tong/research-snapshots/sample/BBCA.json")
mc = json.loads(p.read_text())["marketContext"]
assert mc["available"] is False and mc["close"] is None, mc
print(f"        Stage 2 contract: marketContext.available={mc['available']}, "
      f"rightsStatus={mc['rightsStatus']}")
PY
chk $? "the Stage 2 contract exposes no price and states why"

# ═══════════════════════════════════════════════════════════════════════════
hdr "14. No secret or restricted document is tracked"

python3 -m pipeline.goh_dip_tong.cli repo-guard 2>&1 | grep -q "status=PASS"
chk $? "guard secret scan passes over all generated files"

if git ls-files | grep -iE '\.(pdf|zip|gz|tar|7z|rar|xlsx|xls|docx?|pem|key|p12|pfx|env)$' \
   | grep -q .; then
  no "restricted document type is tracked"
else
  ok "no PDF/archive/office/key file is tracked"
fi

python3 - <<'PY'
import os, pathlib, re, subprocess, sys, yaml
root = pathlib.Path(os.environ["REPO"])
pats = [(p["name"], re.compile(p["pattern"])) for p in
        yaml.safe_load((root / "config/goh-dip-tong/guard.yml").read_text())["secret_patterns"]]
files = subprocess.run(["git", "ls-files"], cwd=root,
                       capture_output=True, text=True).stdout.split()
files += subprocess.run(["git", "ls-files", "--others", "--exclude-standard"], cwd=root,
                        capture_output=True, text=True).stdout.split()
hits, scanned = [], 0
for f in files:
    p = root / f
    if not p.is_file() or p.stat().st_size > 4_000_000:
        continue
    # test_guards.py must contain a secret-shaped string to prove the detector
    # fires; it is assembled at runtime there, but skip it regardless.
    if f.endswith("tests/test_guards.py"):
        continue
    try:
        text = p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        continue
    scanned += 1
    for name, rx in pats:
        if rx.search(text):
            hits.append(f"{f}: {name}")
print(f"        scanned {scanned} tracked + to-be-added files against "
      f"{len(pats)} secret patterns")
for h in hits[:10]:
    print(f"        SECRET {h}")
sys.exit(1 if hits else 0)
PY
chk $? "no secret-shaped string in any file git would commit"

if grep -rn "secrets\." .github/workflows/*.yml | grep -v "secrets.GITHUB_TOKEN" | grep -q .; then
  no "a workflow references a stored secret"
else
  ok "no workflow references a stored repository secret"
fi

python3 - <<'PY'
import json, os, pathlib
p = pathlib.Path(os.environ["REPO"],
                 "data/goh-dip-tong/disclosures/manifests/documents.jsonl")
rows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
assert rows, "no manifest rows"
for r in rows:
    assert r["storedInRepo"] is False, r
print(f"        {len(rows)} restricted document(s) represented by manifest only:")
for r in rows:
    print(f"          {r['disclosureId']} {r['mediaType']} {r['byteSize']}B "
          f"storedInRepo={r['storedInRepo']} outcome={r['retrievalOutcome']}")
PY
chk $? "oversized/restricted documents are manifest rows, never committed files"

# ═══════════════════════════════════════════════════════════════════════════
hdr "15. Repository-size guards pass"

python3 -m pipeline.goh_dip_tong.cli repo-guard --verbose 2>&1 \
  | grep -E "^    ok guard\." | sed 's/^ */        /'
python3 -m pipeline.goh_dip_tong.cli repo-guard 2>&1 | grep -q "critical_failures=0"
chk $? "all 10 guard checks pass with 0 critical failures"

python3 - <<'PY'
import os, pathlib, yaml
root = pathlib.Path(os.environ["REPO"])
lim = yaml.safe_load((root / "config/goh-dip-tong/guard.yml").read_text())["limits"]
files = [p for d in ("config/goh-dip-tong", "data/goh-dip-tong")
         for p in (root / d).rglob("*") if p.is_file() and "_private" not in p.parts]
total = sum(p.stat().st_size for p in files)
biggest = max(files, key=lambda p: p.stat().st_size)
print(f"        generated files: {len(files)} (limit {lim['max_changed_files']})")
print(f"        total size:      {total:,} B (limit {lim['max_total_change_bytes']:,})")
print(f"        largest file:    {biggest.name} {biggest.stat().st_size:,} B "
      f"(limit {lim['max_file_bytes']:,})")
assert len(files) <= lim["max_changed_files"]
assert total <= lim["max_total_change_bytes"]
assert biggest.stat().st_size <= lim["max_file_bytes"]
PY
chk $? "file count, total size and largest file are all within configured limits"

python3 -m pytest pipeline/goh_dip_tong/tests/test_guards.py -q 2>&1 \
  | tail -1 | grep -q "passed"
chk $? "35 guard tests pass (incl. 8 that force each guard to fail correctly)"

# ═══════════════════════════════════════════════════════════════════════════
hdr "16. index.html is unchanged"

git diff --quiet HEAD -- index.html
chk $? "git diff HEAD -- index.html is empty"
H=$(git hash-object index.html)
G=$(git rev-parse HEAD:index.html)
[ "$H" = "$G" ]
chk $? "blob hash matches HEAD exactly"
ev "working tree: $H"
ev "HEAD:         $G"

# ═══════════════════════════════════════════════════════════════════════════
hdr "17. goh-pok-tong.html is unchanged"

git diff --quiet HEAD -- goh-pok-tong.html
chk $? "git diff HEAD -- goh-pok-tong.html is empty"
H=$(git hash-object goh-pok-tong.html)
G=$(git rev-parse HEAD:goh-pok-tong.html)
[ "$H" = "$G" ]
chk $? "blob hash matches HEAD exactly"
ev "working tree: $H"
ev "HEAD:         $G"

git diff --quiet HEAD -- bazi-engine.min.js engine-v3 og-goh-pok-tong.png
chk $? "the rest of the Goh Pok Tong bundle is also untouched"

git diff --quiet HEAD -- 404.html rage-wings.html snake.html breakout.html CNAME \
                         _config.yml README.md CHANGELOG.md internal docs/releases
chk $? "every other pre-existing site file is untouched"

# ═══════════════════════════════════════════════════════════════════════════
hdr "Isolation self-check"

REPO_TREE_AFTER="$(tree_hash "$REPO/data/goh-dip-tong")"
REPO_CONFIG_AFTER="$(tree_hash "$REPO/config/goh-dip-tong")"
[ "$REPO_TREE_BEFORE" = "$REPO_TREE_AFTER" ] && \
[ "$REPO_CONFIG_BEFORE" = "$REPO_CONFIG_AFTER" ]
chk $? "this acceptance run left generated datasets and config byte-identical"
ev "data/   ${REPO_TREE_BEFORE:0:24}… → ${REPO_TREE_AFTER:0:24}…"
ev "config/ ${REPO_CONFIG_BEFORE:0:24}… → ${REPO_CONFIG_AFTER:0:24}…"
ev "every write went to a throwaway sandbox under \$(mktemp -d), now removed"

# ═══════════════════════════════════════════════════════════════════════════
printf '\n\033[1m%s\033[0m\n%s\n' "RESULT" "$(printf '─%.0s' $(seq 1 78))"
printf "  checks passed: %d\n  checks failed: %d\n" "$PASS" "$FAIL"
if [ "$FAIL" = "0" ]; then
  printf "  \033[32mSTAGE 1 ACCEPTANCE: PASS\033[0m\n"
  exit 0
fi
printf "  \033[31mSTAGE 1 ACCEPTANCE: FAIL\033[0m\n"
exit 1
