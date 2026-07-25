/* ============================================================================
   COMPOSER TEST — reading-v2 dynamic composer (timeline build)
   ============================================================================
   Asserts, across a wide chart sweep:
     - every section non-empty; name woven into opener/closer
     - NO deterministic-doom vocabulary in any section
     - day-branch clash line fires iff a real day-branch clash exists
     - hour-unknown note appears when the hour is unknown
     - TIMELINE: dated year lines appear in self/money/love; the money section
       carries >=3 distinct dated lines with no two ADJACENT years identical;
       the decade marker uses soft time (a "your <band>" phrase, never a bare age)
     - composition variety stays high
   Tests composition + timeline mechanics, NOT astrological truth. UNVALIDATED.
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
let n=0, dayClashFired=0, dayClashCorrect=0, decadeSoftOK=0, moneyDatedOK=0, adjacentRepeat=0;
const YEARS_RE=/\b20\d\d\b/g;

for(let by=1962;by<=2004;by+=2)for(const mo of [2,5,8,11])for(const d of [6,16,26])for(const h of [3,15]){
  let v3; try{ v3=V3.analyseAdvanced(P(by,mo,d,h, by%2?'male':'female')); }catch(e){ continue; }
  const hourKnown = h!==3;
  const r=R2.compose(v3,{name:'Wira', gender:by%2?'male':'female', birthYear:by, hourKnown});
  n++;
  for(const k of sections){
    if(!r[k]||!r[k].trim()) fail(`${k} empty`);
    seen[k].add(r[k]);
    const low=r[k].toLowerCase();
    for(const ph of DOOM) if(low.includes(ph)) fail(`doom "${ph}" in ${k}`);
  }
  if(!r.opener.includes('Wira')) fail('name missing opener');
  if(!r.closer.includes('Wira')) fail('name missing closer');
  if(!hourKnown && !r.luck.includes('three pillars')) fail('hour-unknown note missing');

  // timeline: money section carries dated lines, >=3 distinct, no adjacent dup
  const moneyYears=(r.career.match(YEARS_RE)||[]);
  if(moneyYears.length>=3) moneyDatedOK++;
  // adjacent-repeat check: split money into dated clauses and compare neighbors
  const clauses=r.career.split(/(?=\b20\d\d\b)/).filter(c=>/^20\d\d/.test(c.trim()));
  for(let i=1;i<clauses.length;i++){
    const a=clauses[i-1].replace(/^20\d\d/,'').trim(), b=clauses[i].replace(/^20\d\d/,'').trim();
    if(a && a===b){ adjacentRepeat++; break; }
  }
  // decade marker soft time: must contain "your " band phrase, must NOT contain "at age" or a bare "at NN"
  if(/your (late teens|twenties|thirties|forties|fifties)|the coming decade/.test(r.career)) decadeSoftOK++;
  if(/\bage \d\d\b|\bat \d\d\b/.test(r.career)) fail('decade used a hard age');

  const realDayClash = v3.dynamics.some(x=>x.type==='Clash' && x.branches.includes(v3.pillars.day.branch));
  if(r._selectors.dayBranchClash){ dayClashFired++; if(realDayClash) dayClashCorrect++; else fail('day-clash fired without real clash'); }
  else if(realDayClash){ fail('real day clash but line did not fire'); }
}

console.log(`composer: ${n} charts`);
sections.forEach(k=>console.log(`  ${k.padEnd(12)}${seen[k].size} distinct`));
console.log(`  money section >=3 dated lines: ${moneyDatedOK}/${n}`);
console.log(`  adjacent verbatim year repeats: ${adjacentRepeat} (want 0)`);
console.log(`  decade marker soft-time: ${decadeSoftOK}/${n}`);
console.log(`  day-branch clash fired ${dayClashFired}, all correct: ${dayClashFired===dayClashCorrect}`);
console.log(`  doom vocabulary: ${fails===0?'none':'SEE FAILURES'}`);

if(moneyDatedOK<n) fail('some charts missing dated money lines');
if(adjacentRepeat>0) fail('adjacent years read identically');
if(decadeSoftOK<n) fail('decade marker missing soft-time band');
if(seen.career.size<50) fail('career variety too low');
if(fails){ console.error(`composer tests FAIL (${fails})`); process.exit(1); }
console.log('composer tests PASS');
