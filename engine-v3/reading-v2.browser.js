/* ============================================================================
   GOH POK TONG — DYNAMIC READING COMPOSER  (reading-v2)
   ============================================================================
   Replaces fixed per-section strings with fragments assembled at runtime from
   the signals the v3 engine already produces:

     Day Master · strength · season · dominant Ten God · roots ·
     branch clashes and WHICH pillar (life domain) they land on

   Position is meaning. The four pillars are four life domains:
     year  = roots, childhood, the face you show the world
     month = parents, career, the machine of your 20s and 30s
     day   = your inner self AND your spouse (the day branch is the marriage seat)
     hour  = children, old age, what you do when no one is watching

   Voice: sharp. Names contradictions, calls out self-sabotage, a little mean.
   Hard line held on purpose — NO deterministic doom about death, marriage
   ending, illness, or ruin. The uncle is brutal about who you ARE, never
   fatalistic about what will destroy you. That is the difference between
   dangerous and irresponsible.

   Everything is data-driven. To retune the voice, edit FRAG below. No logic
   changes needed. Exposed as window.GptReadingV2.
   ============================================================================ */

(function (root) {
  'use strict';

  var STEMS   = ['Jia','Yi','Bing','Ding','Wu','Ji','Geng','Xin','Ren','Gui'];
  var STEM_EL = ['Wood','Wood','Fire','Fire','Earth','Earth','Metal','Metal','Water','Water'];
  var STEM_YY = ['Yang','Yin','Yang','Yin','Yang','Yin','Yang','Yin','Yang','Yin'];
  var BRANCHES= ['Zi','Chou','Yin','Mao','Chen','Si','Wu','Wei','Shen','You','Xu','Hai'];

  /* branch -> season bucket (by the month branch) */
  var SEASON = {
    Yin:'spring', Mao:'spring', Chen:'spring',
    Si:'summer',  Wu:'summer',  Wei:'summer',
    Shen:'autumn',You:'autumn', Xu:'autumn',
    Hai:'winter', Zi:'winter',  Chou:'winter'
  };

  /* Collapse the 8 raw ten-gods into 5 readable drives */
  function godGroup(g){
    if(g==='Friend'||g==='RobWealth') return 'Companion';
    if(g==='EatingGod'||g==='HurtingOfficer') return 'Output';
    if(g==='DirectWealth'||g==='IndirectWealth') return 'Wealth';
    if(g==='DirectOfficer'||g==='SevenKillings') return 'Officer';
    if(g==='DirectResource'||g==='IndirectResource') return 'Resource';
    return 'Companion';
  }

  function topGodGroup(tg){
    var acc={Companion:0,Output:0,Wealth:0,Officer:0,Resource:0};
    Object.keys(tg).forEach(function(k){ acc[godGroup(k)] += tg[k]; });
    return Object.entries(acc).sort(function(a,b){return b[1]-a[1];})[0][0];
  }
  function secondGodGroup(tg){
    var acc={Companion:0,Output:0,Wealth:0,Officer:0,Resource:0};
    Object.keys(tg).forEach(function(k){ acc[godGroup(k)] += tg[k]; });
    return Object.entries(acc).sort(function(a,b){return b[1]-a[1];})[1][0];
  }

  function strengthBucket(cls){
    if(cls==='Very Weak'||cls==='Weak') return 'weak';
    if(cls==='Very Strong'||cls==='Strong') return 'strong';
    return 'balanced';
  }

  /* which pillar (life domain) a branch sits in */
  function branchSeat(pillars, branch){
    if(pillars.day.branch===branch)   return 'day';
    if(pillars.month.branch===branch) return 'month';
    if(pillars.hour.branch===branch)  return 'hour';
    if(pillars.year.branch===branch)  return 'year';
    return null;
  }

  /* ==========================================================================
     FRAGMENT LIBRARY — the whole voice lives here. Edit freely.
     Each fragment is a clause written to FOLLOW the one before it, so that
     concatenation reads as one thought. Leading spaces are intentional.
     ========================================================================== */
  var FRAG = {

    /* ---- opener: hook + name. seed-picked, name woven in ---- */
    openers: [
      "Sit, {name}. Don't fidget. Uncle already read half of you from the way you typed your own birthday.",
      "Ah, {name}. Machine's warm. Give me the date, keep the life story — uncle can see most of it anyway.",
      "{name}. You walked into an arcade to ask a cabinet who you are. That already tells uncle three things. Sit.",
      "So. {name}. Let's see what the sky was doing the day you showed up. Hm. Oh. Oh, that's you alright.",
      "Come, {name}, sit closer. Uncle only says the true part once and he doesn't repeat it for people at the back.",
      "{name}, is it. Uncle has read ten thousand charts and yours is not boring, which is either good news or a warning.",
      "Eh, {name}. Uncle looked at your pillars and sighed. Not a bad sigh. A 'yes, of course, that makes sense' sigh."
    ],

    /* ---- personality: dmCore + strength + season + drive ---- */
    dmCore: {
      Jia:"You're Yang Wood — a tree, not a shrub. You grow up, you grow straight, and you do not bend just to make a room comfortable.",
      Yi:"You're Yin Wood — a vine, not a trunk. You don't fight the wall, you climb it. People call it adaptable. Uncle calls it knowing exactly which way is up.",
      Bing:"You're Yang Fire — the sun, not a candle. You walk in and the whole room adjusts its brightness to yours, and you have never once noticed doing it.",
      Ding:"You're Yin Fire — a flame in the dark, not a bonfire. You don't flood a room, you draw the one person who needs the light. Quieter. Warmer. Harder to put out than people think.",
      Wu:"You're Yang Earth — a mountain. Solid, patient, unbothered. People shelter behind you. They rarely ask what it costs the mountain to never move.",
      Ji:"You're Yin Earth — a field, not a cliff. You take what's dropped on you and grow something from it. Everyone eats. Nobody asks who feeds the soil.",
      Geng:"You're Yang Metal — a blade, not a decoration. Direct, tempered, made to cut through nonsense. You've hurt people by 'just being honest' and you'd do it again.",
      Xin:"You're Yin Metal — a fine edge, jewelry not machinery. Precise, particular, quietly proud. You'd rather one thing done beautifully than ten done fast.",
      Ren:"You're Yang Water — the ocean, not a cup. Big, restless, always moving, impossible to hold. You start ten things. We will discuss the finishing rate later.",
      Gui:"You're Yin Water — mist and rain, not a river. Soft, everywhere, easy to underestimate. You soak into things. You feel the whole room before anyone speaks."
    },
    strength: {
      weak:" And right now your roots are shallow. You bend more than you let on, and you resent every inch of it — you'd rather be seen as immovable than admit you flexed.",
      balanced:" You're evenly built — enough spine to hold, enough give to bend. Your problem isn't strength, it's that you keep waiting for a clearer sign before you commit. It's not coming.",
      strong:" And you're firmly rooted — maybe too firmly. You call it principle. The people who love you have another word for it, and they've stopped saying it out loud."
    },
    season: {
      spring:" Born in the growing season, so pushing forward feels natural and stillness feels like death. Careful — not every season is for sprinting.",
      summer:" Born in the hot season, so you run warm: fast to light up, fast to burn out, then confused why you're tired.",
      autumn:" Born in the cutting season, when things ripen and get harvested. You learned early that soft doesn't survive, and you've been a little armored ever since.",
      winter:" Born in the still season, so you think before you move and mistrust anyone who doesn't. Deep water. Also cold, sometimes, to people who didn't earn it."
    },
    drive: {
      Companion:" Your chart is crowded with your own kind — lots of self, lots of will. You trust your own hands most. That's strength and that's exactly why you struggle to let anyone carry a corner.",
      Output:" You're built to express — to make, perform, say the thing out loud. Sitting on it makes you sick. You'd rather be judged for what you made than safe and silent.",
      Wealth:" You're wired toward the tangible — money, results, the thing you can hold. You measure days in what got done. Good instinct. Also the reason you can't rest.",
      Officer:" There's a ruler in your chart — duty, structure, the weight of doing it right. Authority shaped you early, and you're still arguing with it in your head at 2am.",
      Resource:" You're built to absorb — learning, support, the long study. You take things in deeply. The trap is preparing forever and calling it progress."
    },

    /* ---- career: primary drive + strength modifier ---- */
    careerCore: {
      Companion:"Work-wise, you're a founder's build — you need to own the outcome or you quietly rot. Bad employee for a micromanager. Put your name on something.",
      Output:"Work-wise, you belong where you're SEEN making things — building, performing, pitching, shipping. Bury you in a back office and you'll wilt on schedule.",
      Wealth:"Work-wise, you're a closer — deals, results, things that convert. You're bored by theory and alive at the finish line. Go where money is kept, not discussed.",
      Officer:"Work-wise, you thrive with real stakes and a clear structure — law, medicine, operations, command. You want the weight. Aimless creative chaos will eat you.",
      Resource:"Work-wise, you're the deep well — research, teaching, strategy, the craft that rewards years. Don't chase fast money; chase mastery and let the money follow."
    },
    careerMod: {
      weak:" But thin roots means don't solo it — pair with someone steadier and let them hold the floor while you do the sharp part. Your gift isn't stamina, it's aim.",
      balanced:" You've got the balance to lead OR support, which is exactly why you keep half-doing both. Pick the harder one for two years. Stop hedging.",
      strong:" You've got the horsepower to carry it alone — the risk is you'll refuse help you actually need and call the exhaustion 'commitment.'"
    },

    /* ---- love: yin/yang base + drive lens + optional clash-on-day-branch ---- */
    loveBase: {
      Yang:"In love you lead — you pursue, you decide, you set the temperature. You need someone who won't fold under you but won't fight you for the wheel either. Rare animal. When you find it, stop testing it.",
      Yin:"In love you receive — you sense, you wait to be chosen, and then quietly resent not being chosen harder. You feel enormously and show a thimble of it. Say the want out loud, once, and watch what happens."
    },
    loveDrive: {
      Companion:" You bring a lot of yourself into a room — strong, whole, self-sufficient. The danger is you're SO complete you forget to leave a door open. Let someone matter.",
      Output:" You love loud and expressive, all warmth and display. Just remember the quiet ones are reading you closely — perform less, show more.",
      Wealth:" You show love by doing, fixing, providing. Beautiful. Also people want your attention, not just your service. Sit still with them sometime.",
      Officer:" You take love seriously — loyal, dutiful, a bit heavy with it. Loosen the grip. Devotion and control wear the same coat and only one is welcome.",
      Resource:" You nurture, you absorb, you carry your person. Generous. But someone who's only ever the caregiver forgets how to be held. Let them feed you too."
    },
    loveClashDay:" And here's the thing uncle wasn't going to say: the sharpest tension in your chart sits in your day branch — the marriage seat. Whoever you pair with gets pulled into a fight that started long before them. Not doom. Just: choose someone who doesn't flinch, and don't hand them a war that was never theirs.",

    /* ---- luck: weakest element + timing gesture + hour-unknown note ---- */
    luckCore: {
      Wood:"What's thin in you right now is Wood — the starting energy, the nerve to plant something before you can see it grow. Life will keep poking exactly there until you plant anyway.",
      Fire:"What's low right now is Fire — visibility, warmth, the willingness to be seen wanting something. You keep your light banked. The next stretch asks you to let it show.",
      Earth:"What's thin is Earth — ground, routine, the boring structure that holds a life together. You scatter. The season ahead rewards the dull discipline you keep avoiding.",
      Metal:"What's low is Metal — the clean cut, the decision, the no. You let things drag because choosing feels like losing the other option. It isn't. Cut.",
      Water:"What's thin is Water — flow, patience, letting things move without forcing them. You push. The next while rewards the opposite: wait, and let it come to you."
    },
    luckTiming:" Uncle won't sell you a fake calendar — this cabinet reads the shape of your luck, not the date it turns. But the shape says the coming stretch pays patience over hustle. Build quietly. The loud money comes later than you want and lands better than you expect.",
    luckHourUnknown:" And {name} — you didn't know your birth hour, so uncle's reading three pillars, not four. The shape is right; the fine print on your later years, don't quote uncle on.",

    /* ---- closer: seed-picked, name woven, a parting cut ---- */
    closers: [
      "That's all uncle gives for free, {name}. The rest you already know and keep pretending you don't. Go do the thing you've been avoiding.",
      "Go on, {name}. Uncle's tired and you've got a chart to go argue with. You'll be fine. Mostly. The mostly is up to you.",
      "Remember, {name}: the chart is the weather, not the umbrella. Uncle told you what's coming. Whether you get wet is entirely your business.",
      "Screenshot it, {name}, ignore it, live your life. Come back in a year when you've done the exact opposite of everything uncle said. You know you will.",
      "Send this to the friend who needs it more than you, {name}. You know the one. They won't listen either, but at least they'll feel seen.",
      "Uncle said what he saw, {name}. If it stung a little — good. The readings that don't sting are the ones nobody remembers.",
      "Enough. Go eat something, {name}. Half of what you call a bad week is just an empty stomach and a chart you haven't made peace with yet."
    ]
  };

  /* ==========================================================================
     COMPOSERS
     ========================================================================== */
  function fillName(s, name){ return s.split('{name}').join(name || 'you'); }
  function pick(arr, seed){ return arr[Math.abs(seed) % arr.length]; }

  function weakestElement(elementScores){
    return Object.entries(elementScores).sort(function(a,b){return a[1]-b[1];})[0][0];
  }

  function compose(v3, opts){
    opts = opts || {};
    var name = opts.name || 'you';
    var hourKnown = opts.hourKnown !== false;
    var pillars = v3.pillars;

    var dmIndex = STEMS.indexOf(v3.dayMaster);
    var yy = STEM_YY[dmIndex];
    var strBucket = strengthBucket(v3.strength.classification);
    var season = SEASON[pillars.month.branch];
    var drive = topGodGroup(v3.tenGodScores);
    var seed = dmIndex*13 + BRANCHES.indexOf(pillars.day.branch) + BRANCHES.indexOf(pillars.year.branch);

    /* does any clash land on the day branch (marriage seat)? */
    var dayClash = v3.dynamics.some(function(d){
      return d.type==='Clash' && d.branches.indexOf(pillars.day.branch)!==-1;
    });

    /* opener */
    var opener = fillName(pick(FRAG.openers, seed), name);

    /* personality = dmCore + strength + season + drive */
    var personality = FRAG.dmCore[v3.dayMaster]
                    + FRAG.strength[strBucket]
                    + FRAG.season[season]
                    + FRAG.drive[drive];

    /* career = core(drive) + modifier(strength) */
    var career = FRAG.careerCore[drive] + FRAG.careerMod[strBucket];

    /* love = base(yy) + lens(drive) + optional day-branch clash */
    var love = FRAG.loveBase[yy] + FRAG.loveDrive[drive];
    if(dayClash){ love += FRAG.loveClashDay; }

    /* luck = weakest element + timing + optional hour-unknown */
    var weak = weakestElement(v3.elementScores);
    var luck = FRAG.luckCore[weak] + FRAG.luckTiming;
    if(!hourKnown){ luck += fillName(FRAG.luckHourUnknown, name); }

    /* closer */
    var closer = fillName(pick(FRAG.closers, seed+5), name);

    return {
      opener: opener,
      personality: personality,
      career: career,
      love: love,
      luck: luck,
      closer: closer,
      /* diagnostics for the dev panel */
      _selectors: {
        dayMaster: v3.dayMaster, yinYang: yy, strength: strBucket,
        season: season, drive: drive, secondary: secondGodGroup(v3.tenGodScores),
        weakestElement: weak, dayBranchClash: dayClash,
        seat: { drive: null }
      }
    };
  }

  root.GptReadingV2 = {
    compose: compose,
    FRAG: FRAG,
    topGodGroup: topGodGroup,
    strengthBucket: strengthBucket,
    VERSION: 'reading-v2-dynamic'
  };

})(typeof window !== 'undefined' ? window : globalThis);
