/* ============================================================================
   GOH POK TONG — DYNAMIC READING COMPOSER  (reading-v2, timeline build)
   ============================================================================
   Composes each section from fragments chosen by the signals v3 produces, and
   WEAVES DATED LINES into the prose using the luck-pillar and annual-pillar
   systems.

   Timeline per reading: 2 past anchors + current year + next 3 years + one
   decade marker, distributed across sections (money/career gets the most).

   HONESTY BOUNDARIES, enforced in code and copy:
   - Annual pillars are EXACT. Dated year lines are computed, not invented, and
     interpreted by that year's Ten God relationship to the Day Master — so
     every chart, and every section, reads differently.
   - The decade marker is the luck pillar. DIRECTION and SEQUENCE are exact; the
     START AGE needs solar terms to the hour and the engine has them to the day.
     So the decade line uses SOFT TIME ("somewhere in your thirties") — mystique,
     not fake precision.
   - NO verdicts. Dated weather, never dated fate. Enforced by composer-test.mjs.
   - "Special" = specific, not flattering.

   Voice: chaotic-mystic, concise. Whole voice lives in FRAG + YEAR + DECADE.
   Exposed as window.GptReadingV2.
   ============================================================================ */

(function (root) {
  'use strict';

  var STEMS   = ['Jia','Yi','Bing','Ding','Wu','Ji','Geng','Xin','Ren','Gui'];
  var STEM_YY = ['Yang','Yin','Yang','Yin','Yang','Yin','Yang','Yin','Yang','Yin'];
  var BRANCHES= ['Zi','Chou','Yin','Mao','Chen','Si','Wu','Wei','Shen','You','Xu','Hai'];

  var SEASON = {
    Yin:'spring', Mao:'spring', Chen:'spring',
    Si:'summer',  Wu:'summer',  Wei:'summer',
    Shen:'autumn',You:'autumn', Xu:'autumn',
    Hai:'winter', Zi:'winter',  Chou:'winter'
  };

  var STEM_EL = {Jia:'Wood',Yi:'Wood',Bing:'Fire',Ding:'Fire',Wu:'Earth',Ji:'Earth',Geng:'Metal',Xin:'Metal',Ren:'Water',Gui:'Water'};
  var PRODUCES= {Wood:'Fire',Fire:'Earth',Earth:'Metal',Metal:'Water',Water:'Wood'};
  var CONTROLS= {Wood:'Earth',Earth:'Water',Water:'Fire',Fire:'Metal',Metal:'Wood'};

  function tenGodGroup(dayStem, otherStem){
    var a=STEM_EL[dayStem], b=STEM_EL[otherStem];
    if(a===b) return 'Companion';
    if(PRODUCES[a]===b) return 'Output';
    if(CONTROLS[a]===b) return 'Wealth';
    if(CONTROLS[b]===a) return 'Officer';
    if(PRODUCES[b]===a) return 'Resource';
    return 'Companion';
  }
  function godGroupOfRaw(g){
    if(g==='Friend'||g==='RobWealth') return 'Companion';
    if(g==='EatingGod'||g==='HurtingOfficer') return 'Output';
    if(g==='DirectWealth'||g==='IndirectWealth') return 'Wealth';
    if(g==='DirectOfficer'||g==='SevenKillings') return 'Officer';
    if(g==='DirectResource'||g==='IndirectResource') return 'Resource';
    return 'Companion';
  }
  function topGodGroup(tg){
    var acc={Companion:0,Output:0,Wealth:0,Officer:0,Resource:0};
    Object.keys(tg).forEach(function(k){ acc[godGroupOfRaw(k)] += tg[k]; });
    return Object.entries(acc).sort(function(a,b){return b[1]-a[1];})[0][0];
  }
  function strengthBucket(cls){
    if(cls==='Very Weak'||cls==='Weak') return 'weak';
    if(cls==='Very Strong'||cls==='Strong') return 'strong';
    return 'balanced';
  }

  /* annual pillar: exact. 1984 = Jia-Zi (index 0) */
  function annualPillar(year){
    var idx=(((year-1984)%60)+60)%60;
    return { stem:STEMS[idx%10], branch:BRANCHES[idx%12] };
  }

  function sexIndex(stem,branch){
    var s=STEMS.indexOf(stem), b=BRANCHES.indexOf(branch);
    for(var i=0;i<60;i++) if(i%10===s && i%12===b) return i;
    return -1;
  }
  function luckDirectionForward(yearStem, gender){
    var yang = STEMS.indexOf(yearStem)%2===0;
    return (yang && gender==='male') || (!yang && gender==='female');
  }
  /* Active luck decade by SOFT age band. Start age unknown to the hour, so no
     year is claimed — pillar + soft band only. */
  function activeLuckPillar(pillars, gender, birthYear){
    var forward = luckDirectionForward(pillars.year.stem, gender);
    var idx = sexIndex(pillars.month.stem, pillars.month.branch);
    var approxAge = (new Date().getFullYear() - birthYear);
    var decadeNo = Math.max(1, Math.min(5, Math.floor((approxAge - 3) / 10) + 1));
    var stepIdx = idx;
    for(var i=0;i<decadeNo;i++) stepIdx = forward ? (stepIdx+1)%60 : (stepIdx+59)%60;
    var band = ['','your late teens','your twenties','your thirties','your forties','your fifties'][decadeNo] || 'the coming decade';
    return { stem:STEMS[stepIdx%10], branch:BRANCHES[stepIdx%12], band:band, forward:forward };
  }

  /* ==========================================================================
     FRAGMENT LIBRARY — concise chaotic-mystic. Edit freely.
     ========================================================================== */
  var FRAG = {
    openers: [
      "Sit, {name}. Uncle read half of you from how you typed the date. Quiet now.",
      "Ah, {name}. The machine's warm. Give me the day. Keep the rest — uncle sees it.",
      "{name}. You asked a cabinet who you are. That already told uncle three things.",
      "So. {name}. Let's see what the sky was doing. ...Mm. Yes. That's you.",
      "Come closer, {name}. Uncle says the true part once. He won't repeat it for the back row.",
      "{name}, is it. Ten thousand charts, and yours isn't boring. Could be good. Could be a warning.",
      "Eh, {name}. Uncle looked and sighed. Not a bad sigh. A 'of course' sigh."
    ],
    dmCore: {
      Jia:"Yang Wood — a tree, not a shrub. You grow straight and won't bend to make a room comfortable.",
      Yi:"Yin Wood — a vine. You don't fight the wall, you climb it. Some call it soft. Uncle calls it winning quietly.",
      Bing:"Yang Fire — the sun, {name}. You walk in, the room adjusts to your light, and you've never noticed doing it.",
      Ding:"Yin Fire — a lamp in the dark. You don't flood, you draw the one who needs you. Quiet. Harder to put out than they think.",
      Wu:"Yang Earth — a mountain. Solid, patient, unbothered. People shelter behind you and forget the mountain feels weather too.",
      Ji:"Yin Earth — a field. You grow things from whatever's dropped on you. Everyone eats. Nobody asks who feeds the soil.",
      Geng:"Yang Metal — a blade, {name}. You cut, then wonder why people bleed. The sky made you sharp. Gentle was not included.",
      Xin:"Yin Metal — a fine edge. Precise, proud, particular. One thing done beautifully beats ten done fast, and you'll die on that hill.",
      Ren:"Yang Water — the ocean. Big, restless, impossible to hold. You start ten things. We'll discuss the finishing later.",
      Gui:"Yin Water — mist and rain. Soft, everywhere, easy to underestimate. You feel the whole room before anyone speaks."
    },
    strength: {
      weak:" Roots shallow right now — you bend more than you admit, and hate that you do.",
      balanced:" Evenly built. Your problem isn't spine, it's waiting for a sign that isn't coming.",
      strong:" Rooted deep — maybe too deep. You call it principle. They've stopped calling it anything out loud."
    },
    season: {
      spring:" Born in the growing season, so stillness feels like dying. Careful — not every season is for sprinting.",
      summer:" Born in the heat, so you run hot: quick to light, quick to burn, then puzzled you're tired.",
      autumn:" Born in the cutting season. You learned early that soft doesn't survive. Armored ever since.",
      winter:" Born in the still cold. You think before you move and mistrust those who don't. Deep — and cold, sometimes, to people who didn't earn it."
    },
    drive: {
      Companion:" Your chart's crowded with your own kind. You trust your own hands most — which is exactly why you can't let anyone hold a corner.",
      Output:" You're built to make, to say it out loud. Sitting on it makes you sick. Rather be judged than silent.",
      Wealth:" You're wired to the tangible — results, the thing you can hold. Good instinct. Also why you can't rest.",
      Officer:" There's a ruler in your chart. Authority shaped you early, and you're still arguing with it at 2am.",
      Resource:" You're built to absorb — study, take it all in. The trap is preparing forever and calling it progress."
    },
    careerCore: {
      Companion:"Work: your name goes on it or you rot. Terrible under a micromanager. Own something.",
      Output:"Work: you belong where you're SEEN making things. Bury you in a back office and you wilt on schedule.",
      Wealth:"Work: you're a closer. Bored by theory, alive at the finish. Go where money is kept, not discussed.",
      Officer:"Work: you want real weight — structure, stakes, command. Aimless chaos will eat you.",
      Resource:"Work: you're the deep well — the craft that pays in years. Don't chase fast money. Chase mastery."
    },
    careerMod: {
      weak:" Thin roots — don't solo it. Pair with someone steadier; your gift is aim, not stamina.",
      balanced:" Balanced enough to lead or support, which is why you half-do both. Pick the harder one.",
      strong:" Horsepower to carry it alone — and you'll refuse the help you need, and call the exhaustion loyalty."
    },
    loveBase: {
      Yang:"Love: you lead, you chase, you set the temperature. You need someone who won't fold and won't fight you for the wheel. Rare. Stop testing it when you find it.",
      Yin:"Love: you wait to be chosen, then resent not being chosen harder. You feel a flood, show a thimble. Say the want out loud once, {name}. Watch what happens."
    },
    loveDrive: {
      Companion:" You're so complete you forget to leave a door open. Let someone matter.",
      Output:" You love loud. The quiet ones are reading you closely — perform less, show more.",
      Wealth:" You love by doing and fixing. They want your attention, not your service. Sit still with them.",
      Officer:" You love heavy — loyal, but the grip. Devotion and control wear the same coat. Loosen it.",
      Resource:" You carry your person. Generous — but the one who only gives forgets how to be held. Let them feed you."
    },
    loveClashDay:" And this uncle wasn't going to say: the sharpest tension sits in your day branch — the marriage seat. Whoever you pair with inherits a fight older than them. Not doom. Just — pick someone who doesn't flinch.",
    luckCore: {
      Wood:"What's thin is Wood — the nerve to plant before you can see it grow. Life keeps poking there.",
      Fire:"What's low is Fire — letting yourself be seen wanting something. You keep the light banked.",
      Earth:"What's thin is Earth — the dull structure that holds a life. You scatter.",
      Metal:"What's low is Metal — the clean cut, the no. You let things drag because choosing feels like losing.",
      Water:"What's thin is Water — flow, patience. You push when you should wait."
    },
    luckHourUnknown:" And {name} — no birth hour, so uncle reads three pillars. Shape's right. Fine print on the late years, don't quote uncle.",
    closers: [
      "That's the free part, {name}. The rest you know and keep pretending you don't. Go do the thing you're avoiding.",
      "Go on, {name}. Uncle's tired and you've a chart to go argue with. You'll be fine. Mostly. The mostly's on you.",
      "The chart's the weather, {name}, not the umbrella. Uncle told you what's coming. Getting wet is your business.",
      "Screenshot it, {name}. Ignore it. Come back in a year having done the exact opposite. You will.",
      "Send it to the friend who needs it more, {name}. You know the one. They won't listen either.",
      "It stung a little? Good, {name}. The readings that don't sting are the ones nobody remembers.",
      "Enough. Go eat, {name}. Half a bad week is an empty stomach and a chart you haven't made peace with."
    ]
  };

  /* YEAR: keyed by the year's Ten God group to the Day Master, colored by
     section. Two phrasings per cell, chosen by year parity, so two adjacent
     years that share a Ten God don't read word-for-word identical. */
  var YEAR = {
    self: {
      Companion:["{y} hands you back to yourself — more will, more spine. Useful, if you don't wall people out with it.",
                 "{y} doubles down on you — your own stubbornness, amplified. Ride it, don't let it isolate you."],
      Output:["{y} wants you loud — make it, say it. Bottling it that year costs you.",
              "{y} pushes what's in you to the surface. The work wants out. Let it."],
      Wealth:["{y} pulls you toward the tangible — you chase, you grip. Don't confuse busy with alive.",
              "{y} sharpens the appetite — you want the concrete thing. Fine, if you don't lose the rest chasing it."],
      Officer:["{y} puts weight on you — a rule to answer to. You grow a spine or an ulcer.",
               "{y} hands you responsibility you didn't ask for. Carry it well and it becomes authority."],
      Resource:["{y} slows you to absorb. Rest isn't lazy that year. Learn to believe it.",
                "{y} is a year to take in, not push out. Study. The output comes later."]
    },
    money: {
      Companion:["{y} — allies and rivals wear the same face; money moves through people or leaks through them.",
                 "{y} — partnerships decide the year; the right hands multiply you, the wrong ones drain you."],
      Output:["{y} — your work gets seen; the payoff is real but arrives on its own schedule.",
              "{y} — what you make finally shows; be patient, the money trails the recognition."],
      Wealth:["{y} drags money center stage — it's there, {name}, but it shows up wearing a fight.",
              "{y} is a money year with teeth — the gain is real, so is the cost. Read the fine print."],
      Officer:["{y} — responsibility outruns reward a while; you hold the purse before you enjoy it.",
               "{y} — you earn the weight before the wallet; the reward is late, not absent."],
      Resource:["{y} — you invest in yourself, not the market. Slow money that year, and worth it.",
                "{y} — the return is knowledge, not cash. Bank it; it pays out later."]
    },
    love: {
      Companion:["{y} tests who's actually on your side; the ones who stay, keep.",
                 "{y} sorts the real from the convenient; pay attention to who's left standing."],
      Output:["{y} — magnetic and messy; charm opens doors, follow-through keeps them.",
              "{y} — you draw people easily this year; keeping them is the harder art."],
      Wealth:["{y} stirs desire and its complications; want carefully.",
              "{y} heats things up; wanting is easy, choosing wisely is not."],
      Officer:["{y} asks for the commitment you've been dodging; the dodge stops working.",
               "{y} calls the question you keep avoiding; this year it answers itself."],
      Resource:["{y} softens you; you let someone close, or learn why you don't.",
                "{y} opens you a crack; someone gets in, or you find out what's blocking the door."]
    }
  };

  /* PAST_REFLECT: the "did you feel it?" callback in What's Coming. Distinct
     from YEAR.self so the past year never reads identically in two sections. */
  var PAST_REFLECT = {
    Companion:"{y} was a year you leaned hard on yourself. Did it cost you the people who offered to help?",
    Output:"{y} pushed you to put something out into the world. Did you, {name} — or did you sit on it?",
    Wealth:"{y} put something you wanted within reach. Did the reaching cost more than the having?",
    Officer:"{y} handed you a weight. You either carried it or you're still resenting that you had to.",
    Resource:"{y} was quieter — a year of taking in. Did you rest, or just call the hiding rest?"
  };

  /* DECADE: soft time. Keyed by luck-pillar Ten God group. */
  var DECADE = {
    Companion:"And somewhere in {band}, {name}, the ground turns to your own element — a decade you finally back yourself, or dig in so hard nobody reaches you.",
    Output:"Somewhere in {band} a long season opens where you're made to create and be seen — you bloom in it or hide from it. Uncle's watching which.",
    Wealth:"Around {band}, a decade of appetite arrives — money, wanting, reaching. Rewards the disciplined, punishes the greedy. Only you know which you are.",
    Officer:"Somewhere in {band} the weight lands for real — a decade of being counted on. It makes you or it hardens you.",
    Resource:"Around {band}, a quiet decade of learning and shelter opens — support comes, so does the urge to hide inside the studying. Don't."
  };

  /* ==========================================================================
     COMPOSERS
     ========================================================================== */
  function fillTokens(s, map){
    Object.keys(map).forEach(function(k){ s = s.split('{'+k+'}').join(map[k]); });
    return s;
  }
  function fillName(s, name){ return s.split('{name}').join(name || 'you'); }
  function pick(arr, seed){ return arr[Math.abs(seed) % arr.length]; }
  function weakestElement(es){ return Object.entries(es).sort(function(a,b){return a[1]-b[1];})[0][0]; }

  function yearLine(flavor, year, dayStem, name){
    var ap = annualPillar(year);
    var grp = tenGodGroup(dayStem, ap.stem);
    var cell = YEAR[flavor] && YEAR[flavor][grp];
    if(!cell) return '';
    var tmpl = Array.isArray(cell) ? cell[year % 2] : cell;
    return ' ' + fillTokens(tmpl, { y:String(year), name:name });
  }

  function compose(v3, opts){
    opts = opts || {};
    var name = opts.name || 'you';
    var hourKnown = opts.hourKnown !== false;
    var gender = opts.gender==='female' ? 'female' : 'male';
    var birthYear = opts.birthYear || (new Date().getFullYear() - 30);
    var pillars = v3.pillars;
    var dayStem = v3.dayMaster;

    var dmIndex = STEMS.indexOf(dayStem);
    var yy = STEM_YY[dmIndex];
    var strBucket = strengthBucket(v3.strength.classification);
    var season = SEASON[pillars.month.branch];
    var drive = topGodGroup(v3.tenGodScores);
    var seed = dmIndex*13 + BRANCHES.indexOf(pillars.day.branch) + BRANCHES.indexOf(pillars.year.branch);

    var dayClash = v3.dynamics.some(function(d){
      return d.type==='Clash' && d.branches.indexOf(pillars.day.branch)!==-1;
    });

    var now = new Date().getFullYear();
    var pastA = now-5, pastB = now-2, next1 = now+1, next2 = now+2, next3 = now+3;

    var opener = fillName(pick(FRAG.openers, seed), name);

    var personality = fillName(FRAG.dmCore[dayStem], name)
                    + FRAG.strength[strBucket] + FRAG.season[season] + FRAG.drive[drive]
                    + yearLine('self', pastA, dayStem, name)
                    + yearLine('self', next2, dayStem, name);

    var career = FRAG.careerCore[drive] + FRAG.careerMod[strBucket]
               + yearLine('money', pastB, dayStem, name)
               + yearLine('money', now, dayStem, name)
               + yearLine('money', next1, dayStem, name)
               + yearLine('money', next3, dayStem, name);
    var lp = activeLuckPillar(pillars, gender, birthYear);
    var decGrp = tenGodGroup(dayStem, lp.stem);
    career += ' ' + fillTokens(DECADE[decGrp], { band:lp.band, name:name });

    var love = FRAG.loveBase[yy] + FRAG.loveDrive[drive];
    if(dayClash){ love += FRAG.loveClashDay; }
    love = fillName(love, name) + yearLine('love', next1, dayStem, name);

    var weak = weakestElement(v3.elementScores);
    var pastGrp = tenGodGroup(dayStem, annualPillar(pastB).stem);
    var pastReflect = PAST_REFLECT[pastGrp] || '{y} asked something of you. You remember.';
    var luck = FRAG.luckCore[weak]
             + ' Look back — ' + fillTokens(pastReflect, {y:String(pastB),name:name})
             + ' The next stretch pays patience over noise: build quiet, the loud money lands later and better than you expect.';
    if(!hourKnown){ luck += fillName(FRAG.luckHourUnknown, name); }

    var closer = fillName(pick(FRAG.closers, seed+5), name);

    return {
      opener:opener, personality:personality, career:career, love:love, luck:luck, closer:closer,
      _selectors: {
        dayMaster:dayStem, yinYang:yy, strength:strBucket, season:season, drive:drive,
        weakestElement:weak, dayBranchClash:dayClash,
        timeline: {
          past:[pastA,pastB], current:now, future:[next1,next2,next3],
          decade:{ pillar:lp.stem+'-'+lp.branch, band:lp.band, tenGod:decGrp }
        }
      }
    };
  }

  root.GptReadingV2 = {
    compose: compose,
    FRAG: FRAG, YEAR: YEAR, DECADE: DECADE,
    annualPillar: annualPillar,
    tenGodGroup: tenGodGroup,
    VERSION: 'reading-v2-timeline'
  };

})(typeof window !== 'undefined' ? window : globalThis);
