/* ============================================================================
   COMPOSER TEST — reading-v2 dynamic composer
   ============================================================================
   Loads the browser composer + v3 engine in a vm realm and asserts:
     - every section is non-empty for a wide sweep of charts
     - the name is woven into opener/closer
     - NO deterministic-doom vocabulary appears in any section
     - the day-branch clash conditional fires and only on real day clashes
     - fragment selection is data-driven (variant count well above the
       number of hand-written fragments)
   This tests COMPOSITION, not astrological correctness. The engine stays
   UNVALIDATED.
   ============================================================================ */
import fs from 'node:fs'; import vm from 'node:vm';
const B = new URL('../../engine-v3/', import.meta.url);
const sb={console,Object,Array,String,Math,JSON,Date}; sb.window=sb; sb.globalThis=sb; vm.createContext(sb);
vm.runInContext(fs.readFileSync(new URL('../../bazi-engine.min.js',import.meta.url),'utf8'),sb);
vm.runInContext(fs.readFileSync(new URL('engine-v3.browser.js',B),'utf8'),sb);
vm.runInContext(fs.readFileSync(new URL('reading-v2.browser.js',B),'utf8'),sb);
const C=sb.BaziCalculator, V3=sb.BaziV3, R2=sb.GptReadingV2;

const CN_S={'甲':0,'乙':1,'丙':2,'丁':3,'戊':4,'己':5,'庚':6,'辛':7,'壬':8,'癸':9};
const CN_B={'子':0,'丑':1,'寅':2,'卯':3,'辰':4,'巳':5,'午':6,'未':7,'申':8,'酉':9,'戌':10,'亥':11};
const STEMS=['Jia','Yi','Bing','Ding','Wu','Ji','Geng','Xin','Ren','Gui'];
const BRANCHES=['Zi','Chou','Yin','Mao','Chen','Si','Wu','Wei','Shen','You','Xu','Hai'];
const pf=s=>({stem:STEMS[CN_S[s[0]]],branch:BRANCHES[CN_B[s[1]]]});
const P=(y,mo,d,h,g)=>{const f=new C(y,mo,d,h,g).getCompleteAnalysis(),M=f.mainPillars;
  return {year:pf(M.year.chinese),month:pf(M.month.chinese),day:pf(M.day.chinese),hour:pf(M.time.chinese)};};

let fails=0; const fail=(m)=>{fails++; console.error('  FAIL '+m);};
const DOOM=['will die','die alone','get cancer','will divorce','marriage will fail','never marry',
  'never find love','you are doomed','you are cursed','it is fatal','will be ruined','die young'];

const sections=['opener','personality','career','love','luck','closer'];
const seen={}; sections.forEach(k=>seen[k]=new Set());
let n=0, dayClashFired=0, dayClashCorrect=0;

for(let y=1961;y<=2019;y++)for(const mo of [2,5,8,11])for(const d of [6,16,26])for(const h of [3,15]){
  let v3; try{ v3=V3.analyseAdvanced(P(y,mo,d,h,'male')); }catch(e){ continue; }
  const hourKnown = h!==3;
  const r=R2.compose(v3,{name:'Wira',hourKnown});
  n++;
  for(const k of sections){
    if(!r[k] || !r[k].trim()) fail(`${k} empty at ${y}-${mo}-${d} ${h}h`);
    seen[k].add(r[k]);
    const low=r[k].toLowerCase();
    for(const ph of DOOM) if(low.includes(ph)) fail(`doom "${ph}" in ${k} at ${y}-${mo}-${d}`);
  }
  if(!r.opener.includes('Wira')) fail('name missing from opener');
  if(!r.closer.includes('Wira')) fail('name missing from closer');
  if(!hourKnown && !r.luck.includes('three pillars')) fail('hour-unknown note missing');

  // day-branch clash: fired iff a real Clash lands on the day branch
  const realDayClash = v3.dynamics.some(x=>x.type==='Clash' && x.branches.includes(v3.pillars.day.branch));
  if(r._selectors.dayBranchClash){
    dayClashFired++;
    if(realDayClash) dayClashCorrect++; else fail('day-clash line fired without a real day-branch clash');
  } else if(realDayClash){
    fail('real day-branch clash present but line did not fire');
  }
}

console.log(`composer: ${n} charts`);
sections.forEach(k=>console.log(`  ${k.padEnd(12)}${seen[k].size} distinct`));
const space=seen.personality.size*seen.career.size*seen.love.size*seen.luck.size;
console.log(`  reading space (self x career x love x luck): ${space.toLocaleString()}`);
console.log(`  day-branch clash fired: ${dayClashFired} (all correct: ${dayClashFired===dayClashCorrect})`);
console.log(`  doom vocabulary: ${fails===0?'none':'SEE FAILURES'}`);

if(seen.personality.size < 50) fail('personality variety too low — composition may be broken');
if(fails){ console.error(`composer tests FAIL (${fails})`); process.exit(1); }
console.log('composer tests PASS');
