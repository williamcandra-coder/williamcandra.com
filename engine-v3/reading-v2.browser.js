/* ============================================================================
   GOH POK TONG — DYNAMIC READING COMPOSER  (reading-v3, ten-section build)
   ============================================================================
   Composes ten sections from fragments chosen by v3 engine signals, weaving
   dated lines from the annual-pillar and luck-pillar systems.

   SECTION ORDER (arranged for the reader: hook, identity, then outward from
   self to world, ending on time and the parting shot):
     1  opener      Uncle's Opening Remark
     2  personality Who You Are        (+ physique tendency + trait cluster)
     3  fortune     Your Fortune       [dated]
     4  career      Career             [dated]
     5  love        Love & Spouse      [dated]
     6  people      Your People        (siblings + friends, merged)
     7  parents     Parents & Roots
     8  health      Health             (gentle tendencies only)
     9  luck        What's Coming      [dated]
     10 closer      Uncle's Parting Shot

   VOICE: plain and direct. Say the thing, then the twist. No riddles. Short
   sentences. The bite comes from being specific, not from being cryptic.

   HONESTY BOUNDARIES, enforced in code and copy:
   - Annual pillars EXACT; dated lines computed, never invented.
   - Decade marker uses SOFT TIME ("somewhere in your thirties") because
     luck-pillar start age needs solar terms to the hour and the engine has them
     to the day. Deliberate mystique over a real data limit, never fake precision.
   - NO verdicts. Dated weather, never dated fate.
   - HEALTH is written as tendencies to be mindful of. Never diagnosis, never
     naming a disease, never telling anyone they will fall ill. This engine is
     UNVALIDATED and health copy is held to the gentlest standard in the file.
   - PHYSIQUE is written as what the TYPE tends toward, never as a claim about
     the reader's actual body — the chart does not know their height.
   - "Special" = specific, not flattering.

   Voice lives in FRAG / YEAR / PAST_REFLECT / DECADE. Edit freely; logic stable.
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
  function groupScores(tg){
    var acc={Companion:0,Output:0,Wealth:0,Officer:0,Resource:0};
    Object.keys(tg).forEach(function(k){ acc[godGroupOfRaw(k)] += tg[k]; });
    return acc;
  }
  function topGodGroup(tg){
    var acc=groupScores(tg);
    return Object.entries(acc).sort(function(a,b){return b[1]-a[1];})[0][0];
  }
  /* v3's own classification puts 51% of all charts in "weak" — its thresholds
     (<46) sit well above the real median of 45. That is the same class of skew
     as the spouse star: the model's weighting showing through, not the charts
     speaking. Copy selection therefore bands on the measured tertiles of the
     diagnostic score (33rd = 39, 66th = 52) so the three voices are used
     roughly equally. v3's own label is left untouched for the dev panel. */
  function strengthBucket(cls, score){
    if(typeof score === 'number'){
      return score < 39 ? 'weak' : (score > 52 ? 'strong' : 'balanced');
    }
    if(cls==='Very Weak'||cls==='Weak') return 'weak';
    if(cls==='Very Strong'||cls==='Strong') return 'strong';
    return 'balanced';
  }

  /* Pick one phrasing from a cell that may be a string or an array of
     alternatives. The index comes from a chart feature chosen to vary
     INDEPENDENTLY of whatever selected the cell, so two people who share a
     bucket rarely share the sentence. */
  function variant(cell, idx){
    if(!cell) return '';
    return Array.isArray(cell) ? cell[Math.abs(idx) % cell.length] : cell;
  }
  /* is a god group notably present, thin, or middling in this chart? */
  function bandOf(acc, key){
    var vals=Object.values(acc), max=Math.max.apply(null,vals), min=Math.min.apply(null,vals);
    var v=acc[key], span=(max-min)||1;
    var t=(v-min)/span;
    return t>=0.66 ? 'high' : (t<=0.33 ? 'low' : 'mid');
  }

  /* ---- TRUE ELEMENT COUNT ----------------------------------------------
     What the page's "ELEMENT BALANCE" bar should have been showing all along.

     The engine's fiveFactors is NOT an element count: it weights each element
     by its relationship to the Day Master (Resource 3.0, Companion 2.5, Output
     2.0, Wealth 1.2, Control 1.2). A chart with almost no Water can therefore
     show a large Water bar, simply because Water happens to be that chart's
     Resource element. The bar was labelled "ELEMENT BALANCE" and was showing
     something else entirely.

     This counts what is actually present: four visible stems at full weight,
     plus every hidden stem at its own depth. No Day Master relationship enters
     it, because "how much Fire is in this chart" is not a question about the
     Day Master. */
  var HIDDEN = {
    Zi:  [['Gui',1]],
    Chou:[['Ji',0.6],['Gui',0.3],['Xin',0.1]],
    Yin: [['Jia',0.6],['Bing',0.3],['Wu',0.1]],
    Mao: [['Yi',1]],
    Chen:[['Wu',0.6],['Yi',0.3],['Gui',0.1]],
    Si:  [['Bing',0.6],['Wu',0.3],['Geng',0.1]],
    Wu:  [['Ding',0.7],['Ji',0.3]],
    Wei: [['Ji',0.6],['Ding',0.3],['Yi',0.1]],
    Shen:[['Geng',0.6],['Ren',0.3],['Wu',0.1]],
    You: [['Xin',1]],
    Xu:  [['Wu',0.6],['Xin',0.3],['Ding',0.1]],
    Hai: [['Ren',0.7],['Jia',0.3]]
  };
  function trueElements(pillars){
    var out = {Wood:0, Fire:0, Earth:0, Metal:0, Water:0};
    ['year','month','day','hour'].forEach(function(k){
      var p = pillars[k];
      if(!p) return;
      if(STEM_EL[p.stem]) out[STEM_EL[p.stem]] += 1;
      (HIDDEN[p.branch]||[]).forEach(function(h){
        if(STEM_EL[h[0]]) out[STEM_EL[h[0]]] += h[1];
      });
    });
    var tot=0; Object.keys(out).forEach(function(k){ tot+=out[k]; });
    var pct={};
    Object.keys(out).forEach(function(k){
      pct[k] = tot ? Math.round(out[k]/tot*1000)/10 : 0;
    });
    return { raw: out, percent: pct, total: Math.round(tot*100)/100 };
  }

  /* Band the spouse star on its SHARE of the chart, not on distance from the
     chart's own minimum. The engine weights Wealth and Officer at 1.2 against
     Resource 3.0 and Companion 2.5, so a relative banding puts ~51% of people
     in the bottom bucket — that isn't chart truth, it's the weighting showing
     through, and it would tell half of all readers their love life is thin.
     Thresholds are the measured 33rd/66th percentiles over a 540-chart sweep. */
  function spouseBand(acc, key){
    var tot=0; Object.keys(acc).forEach(function(k){ tot += acc[k]; });
    if(!tot) return 'mid';
    var share = acc[key]/tot;
    return share < 0.10 ? 'low' : (share > 0.213 ? 'high' : 'mid');
  }

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

  /* Branch pairs — same tables the engine uses. A future year whose branch
     clashes with the DAY branch (the self/marriage seat) is a genuinely
     pivotal year in the tradition; a combination is a smoother, partnering one.
     This is what makes "interesting years" real rather than decorative. */
  var CLASH_PAIRS = [['Zi','Wu'],['Chou','Wei'],['Yin','Shen'],['Mao','You'],['Chen','Xu'],['Si','Hai']];
  var COMBO_PAIRS = [['Zi','Chou'],['Yin','Hai'],['Mao','Xu'],['Chen','You'],['Si','Shen'],['Wu','Wei']];
  function pairHas(pairs, a, b){
    return pairs.some(function(p){ return (p[0]===a&&p[1]===b)||(p[1]===a&&p[0]===b); });
  }
  /* Scan forward for years whose branch clashes or combines with ANY of the four
     pillar seats. Each seat is a different area of life, so a clash on the month
     pillar (career) means something different from one on the day pillar (self
     and marriage).

     Note on why this scans all four seats: a branch has exactly ONE clash
     partner and ONE combination partner in the 12-branch cycle, so scanning a
     single seat over 12 years can only ever return two hits. Four seats gives a
     realistic spread of notable years inside a normal forecast window.

     Seat priority when two seats flag the same year: day > month > year > hour.
     Returns chronologically, nearest first, deduped by year. */
  var SEAT_RANK = { day:0, month:1, year:2, hour:3 };
  function notableYears(pillars, fromYear, span, limit, exclude){
    var skip = {};
    (exclude||[]).forEach(function(y){ skip[y]=true; });
    var hits = {};
    ['day','month','year','hour'].forEach(function(seat){
      var seatBranch = pillars[seat] && pillars[seat].branch;
      if(!seatBranch) return;
      for(var y=fromYear; y<fromYear+span; y++){
        if(skip[y]) continue;   // already narrated in detail above
        var b=annualPillar(y).branch, kind=null;
        if(pairHas(CLASH_PAIRS, b, seatBranch)) kind='clash';
        else if(pairHas(COMBO_PAIRS, b, seatBranch)) kind='combo';
        if(!kind) continue;
        var prev=hits[y];
        if(!prev || SEAT_RANK[seat] < SEAT_RANK[prev.seat]) hits[y]={year:y, kind:kind, seat:seat};
      }
    });
    return Object.keys(hits).map(function(k){ return hits[k]; })
      .sort(function(a,b){ return a.year-b.year; })
      .slice(0, limit);
  }

  /* ==========================================================================
     FRAGMENT LIBRARY — plain, direct, concise. Edit freely.
     ========================================================================== */
  var FRAG = {

    openers: [
      "Sit down, {name}. Uncle already learned something from how you typed that date. Quiet now.",
      "Ah, {name}. Machine's warm. Give uncle the day. Keep the rest — he can see it.",
      "{name}. You asked an arcade cabinet who you are. That tells uncle three things already.",
      "So. {name}. Let's see what the sky was doing that day. ...Ah. Yes. That's you.",
      "Come closer, {name}. Uncle says the true part once. He won't repeat it for the back row.",
      "{name}, is it. Ten thousand charts uncle has read. Yours is not boring.",
      "Eh, {name}. Uncle looked at this and sighed. Not a bad sigh. The 'of course' kind."
    ],

    /* WHO YOU ARE — core nature */
    dmCore: {
      Jia:"Yang Wood. You are a tree, {name} — you grow straight up and you don't bend to make a room comfortable.",
      Yi:"Yin Wood. You are a vine. You don't fight a wall, you climb it. People call that soft. Uncle calls it winning slowly.",
      Bing:"Yang Fire. You are the sun, {name}. You walk in and the room brightens, and you've never once noticed doing it.",
      Ding:"Yin Fire. You are a lamp, not a bonfire. You don't fill a room, you find the one person who needs light.",
      Wu:"Yang Earth. You are a mountain. Steady, patient, hard to move. People rest against you and forget mountains feel the weather too.",
      Ji:"Yin Earth. You are a field. Whatever gets dropped on you, you grow something from it. Everyone eats. Nobody asks who feeds the soil.",
      Geng:"Yang Metal. You are a blade, {name}. You cut, then wonder why people bleed. The sky made you sharp. It did not make you gentle.",
      Xin:"Yin Metal. You are a fine edge — jewellery, not machinery. Precise, proud, particular about small things nobody else notices.",
      Ren:"Yang Water. You are the ocean. Big, restless, hard to hold. You start ten things. We'll discuss the finishing later.",
      Gui:"Yin Water. You are rain and mist. Quiet, everywhere, easy to underestimate. You read a room before anyone speaks."
    },
    /* physique: TYPE tendency, never a claim about the reader's body */
    physique: {
      Wood:[" Wood types tend to run tall and lean, with long limbs and a straight back — the kind of build that looks taller than it measures.",
            " Wood types usually carry height in the frame rather than the weight: long bones, upright carriage, hands that talk while you do.",
            " The Wood build is lengthways — narrow through the shoulders, long in the leg, and slow to thicken with age."],
      Fire:[" Fire types tend toward sharp features and quick movement — expressive face, restless hands, warm colouring.",
            " Fire shows in the face first: mobile expression, bright eyes, colour that rises when you're animated or annoyed.",
            " The Fire build runs light and quick — you move before you decide to, and people read your mood off you at ten paces."],
      Earth:[" Earth types tend toward a solid, grounded build — broad through the middle, steady on their feet, a face people find easy to trust.",
             " Earth shows as substance: squarer frame, settled posture, the sort of face strangers ask directions from.",
             " The Earth build is built to stay put — sturdy through the torso, unhurried in movement, ages slowly and evenly."],
      Metal:[" Metal types tend toward clean, defined features — good bone structure, upright posture, a certain neatness even when dressed badly.",
             " Metal shows in the edges: defined jaw, straight back, a tidiness about you that survives a bad week.",
             " The Metal build is architectural — clear lines, contained movement, and a face that photographs better than it feels."],
      Water:[" Water types tend toward softer, rounder features and smooth movement — the kind of face that looks younger than the birth year says.",
             " Water shows as fluidity: rounder features, unhurried movement, and an age that people consistently guess wrong.",
             " The Water build is soft-edged and adaptable — nothing sharp, nothing fixed, and it keeps its youth longer than it should."]
    },
    /* trait cluster keyed by day-master, plain-spoken */
    traits: {
      Jia:" Traits: principled, stubborn, protective, slow to forgive, terrible at asking for help.",
      Yi:" Traits: adaptable, diplomatic, quietly ambitious, avoids direct conflict, remembers everything.",
      Bing:" Traits: generous, dramatic, impatient, warm to strangers, burns out and sulks about it.",
      Ding:" Traits: observant, private, loyal in small circles, moody, sharper than people expect.",
      Wu:" Traits: dependable, immovable, calm under pressure, resistant to change, hides worry well.",
      Ji:" Traits: nurturing, practical, self-sacrificing, quietly resentful when unnoticed, hard to say no.",
      Geng:" Traits: decisive, blunt, courageous, loyal, leaves damage behind while calling it honesty.",
      Xin:" Traits: refined, meticulous, image-conscious, sensitive to criticism, high standards for everyone.",
      Ren:" Traits: inventive, sociable, restless, generous with ideas, poor at finishing what excites them.",
      Gui:" Traits: intuitive, gentle, deeply feeling, conflict-avoidant, overthinks small things for years."
    },
    strength: {
      weak:[" Right now your support is thin. You bend more than you admit, and it annoys you that you do.",
            " Your chart gives you less backing than you'd like. You've compensated with effort, and called the tiredness normal.",
            " Support runs light in your chart. You've learned to carry things alone, and mistaken the habit for a preference."],
      balanced:[" You are evenly built — enough backbone to hold, enough give to bend. Your real problem is waiting for certainty before you move.",
                " Your chart is level. Neither brittle nor soft. Which means nothing external is stopping you, and you know it.",
                " You're built in proportion — you can push or yield as needed. The trouble is you keep choosing neither."],
      strong:[" You are heavily supported — maybe too much. You call it having principles. The people around you gave up arguing about it.",
              " Your chart gives you more backing than most. It makes you durable, and it makes you certain, and only one of those is always useful.",
              " You're strongly built, which is why you rarely doubt yourself. Doubt occasionally has good information in it."]
    },
    season: {
      spring:" You were born in the growing season, so sitting still makes you restless. Not every season is for pushing.",
      summer:" You were born in the hot season, so you run hot — quick to start, quick to burn out, then surprised you're tired.",
      autumn:" You were born in the cutting season, when things get harvested. You learned early that being soft costs you.",
      winter:" You were born in the cold season, so you think before you move and distrust people who don't."
    },
    drive: {
      Companion:" Your chart is full of your own element. You trust your own hands most — which is exactly why you won't let anyone help.",
      Output:" Your chart pushes you to make things and say them out loud. Keeping it inside makes you unwell.",
      Wealth:" Your chart points at results — the thing you can hold and count. Good instinct. Also why you can't sit still.",
      Officer:" Your chart carries authority in it. Rules shaped you early, and part of you is still arguing with them.",
      Resource:" Your chart is built to take things in — study, learn, absorb. The trap is preparing forever and calling it progress."
    },

    /* FORTUNE — overall luck shape */
    fortuneCore: {
      weak:["Your fortune builds slowly, {name}. Nothing lands in your lap. What you get, you get by outlasting people — and that turns out to be your actual advantage.",
            "Luck arrives late for you and it arrives earned. Nothing has ever simply been handed over. You've stopped expecting it, which is its own kind of strength.",
            "Your fortune is a slow build, {name} — no windfalls, no shortcuts. The people who started faster than you are not the ones still standing."],
      balanced:["Your fortune is steady rather than spectacular. Doors open at a normal speed, and the ones you push on open faster.",
                "Your luck is unremarkable in the best sense — it responds to effort and ignores wishing. What you put in, you roughly get back.",
                "Fortune neither favours nor obstructs you. That sounds dull. It means the outcome is genuinely yours, which is heavier than it sounds."],
      strong:["Your fortune runs strong, {name} — opportunities find you. The risk is you'll assume they always will, and stop preparing.",
              "Luck leans your way more than most. Useful, and quietly dangerous: people carried by luck rarely build the muscle for when it pauses.",
              "Your chart draws opportunity, {name}. The question was never whether chances would come. It's whether you were ready when they did."]
    },
    fortuneUseful: {
      Wood:[" Growth and new starts help you. Say yes to the thing that hasn't proven itself yet.",
            " Beginnings feed your luck. The unproven project, the early-stage thing — that's where your fortune turns.",
            " What lifts you is starting things. Momentum, not perfection. Plant before you're certain."],
      Fire:[" Visibility helps you. The more people who know what you do, the better your luck runs.",
            " Being seen improves your fortune. Hidden competence pays you badly; announced competence pays you well.",
            " Your luck follows attention. Not fame — just being known by the right handful of people for the right thing."],
      Earth:[" Stability helps you. Property, routine, long commitments — boring things pay you well.",
             " Fortune comes to you through what stays put: land, long contracts, habits you don't renegotiate.",
             " Your luck rewards the unglamorous — the standing arrangement, the thing you keep for years."],
      Metal:[" Clear decisions help you. Every time you cut something dead loose, your luck improves.",
             " Fortune follows your cuts. Ending the thing that stopped working is what actually moves you forward.",
             " Your luck sharpens when you choose. Ambiguity costs you more than a wrong decision would."],
      Water:[" Movement helps you. Travel, new networks, changing scenery — stagnation is what actually hurts you.",
             " Your fortune moves when you do. New rooms, new people, a change of ground.",
             " Luck reaches you through circulation — go where you aren't known and something loosens."]
    },
    /* CAREER */
    careerCore: {
      Companion:["You need your own name on the work, or you slowly stop caring. Bad fit under a controlling boss.",
                 "You work best when the result is visibly yours. Anonymous contribution drains you faster than long hours do.",
                 "Ownership is the thing for you — a stake, a title, a signature. Without it you go quietly flat."],
      Output:["You belong where the work is visible — building, presenting, performing, shipping. Hidden in a back office you go flat.",
              "You're made to produce and be seen producing. Work that never gets shown will make you restless and strange.",
              "Your work needs an audience — clients, users, a room. Craft in a vacuum doesn't hold you."],
      Wealth:["You're a closer. Theory bores you, finishing energises you. Work where money is handled, not discussed.",
              "You're built for the transaction — the deal, the delivery, the number that lands. Strategy meetings are your enemy.",
              "You want results you can count. Put yourself where outcomes are measured, not where intentions are described."],
      Officer:["You want real responsibility and a clear structure. Give you weight and you carry it. Give you chaos and it eats you.",
               "You do well with rank, rules and consequence. Loose creative environments will quietly wear you down.",
               "You need a chain of accountability — something to answer to and something answerable to you."],
      Resource:["You're the deep-knowledge type — the craft that pays after years, not months. Chase mastery, not quick money.",
                "You compound. Your value is in accumulated understanding, which means early years look unimpressive and later ones don't.",
                "You're built for depth over speed. Pick something worth ten years and stop shopping around."]
    },
    careerMod: {
      weak:[" Don't do it alone. Pair with someone steadier — your gift is precision, not endurance.",
            " Solo is your weak configuration. Find the partner with stamina and let them hold the floor.",
            " You need a structure around you. Freelancing into open space will exhaust you before it pays."],
      balanced:[" You can lead or support, which is why you keep half-doing both. Choose one for two years.",
                " You're capable either way, and that flexibility has become a way of avoiding commitment. Pick a lane.",
                " Being able to do both is why you've done neither properly. Two years, one direction."],
      strong:[" You can carry it alone, and you will refuse the help you need, and call the exhaustion loyalty.",
              " You have the capacity to do it all yourself. You will. And you'll resent the people who let you.",
              " Strength is your trap here — you'll take on what three people should, then wonder why nothing feels light."]
    },
    /* LOVE & SPOUSE */
    /* HOW LOVE ARRIVES — keyed by the spouse star: Wealth for men, Officer for
       women, which is the traditional reading. Six variants, and it leads the
       section because it varies far more than a yin/yang coin-flip does. */
    spouseStar: {
      male: {
        high:["Love has never been scarce for you, {name} — the chart is full of it. Options came early and often. Your difficulty was never finding someone; it was deciding, and then staying decided.",
              "There's no shortage of romance in your chart, {name}. People have always been available to you. What you lacked was not choice — it was the will to stop choosing."],
        mid:["Love comes to you at a normal rate — not thrown at you, not withheld. What you get has depended almost entirely on whether you showed up and said something.",
             "Your chart gives an ordinary supply of romance. Nothing lands in your lap, nothing is denied you. It has always come down to whether you spoke first."],
        low:["Love runs narrow in your chart, {name} — not absent, narrow. It arrives late, or slowly, or once and properly. You've spent time wondering what's wrong with you. Nothing is. A narrow supply is not an empty one.",
             "Romance is not the loudest thing in your chart, {name}. Fewer people, arriving later, staying longer. You read that as a shortage. It's closer to a filter."]
      },
      female: {
        high:["Attention has never been in short supply for you, {name}. The chart is crowded with it. The work was never attracting someone — it was telling the serious ones from the loud ones.",
              "Your chart draws people easily, {name}. There has always been interest. Sorting the genuine from the merely persistent is where your energy actually went."],
        mid:["Love comes to you at an ordinary pace. Nobody hands it over and nobody withholds it. It has always depended on whether you let the right person close enough.",
             "Your chart gives a normal share of partnership. It arrives when you allow it to, which is less often than you tell people."],
        low:["The chart runs narrow on partnership, {name} — not empty, narrow. Love arrives late, or quietly, or just once and properly. You've read that as a verdict on you. It isn't.",
             "Partnership is not the loudest thing in your chart, {name}. Fewer people, later, and they stay. You've called that bad luck. Uncle would call it a narrow gate, not a closed one."]
      }
    },
    /* WHO SUITS YOU — the spouse seat, twelve variants */
    spouseType: {
      Zi:" The partner who fits you is quick, adaptable, a little restless — someone who thinks fast and changes plans without panicking. Slow, heavy people wear you out.",
      Chou:" The partner who fits you is steady and patient — the sort who says little and follows through. Flashy attracts you briefly, then exhausts you.",
      Yin:" The partner who fits you has their own fire — ambitious, a bit bold, occasionally difficult. Someone too easy to please will bore you within a year.",
      Mao:" The partner who fits you is gentle, sociable, easy in company. You do badly with harshness, even the well-meant kind.",
      Chen:" The partner who fits you is capable and a little proud — someone with their own weather. You don't want managing, and you don't want to manage.",
      Si:" The partner who fits you is clever and self-contained, with a private side. You want someone with depth you have to earn access to.",
      Wu:" The partner who fits you is warm, direct, generous — no guessing games. Anyone who plays cold with you loses you faster than they expect.",
      Wei:" The partner who fits you is kind and home-minded, the sort who builds a nest. You need softness more than you admit in public.",
      Shen:" The partner who fits you is sharp, funny, quick on their feet. You need someone who can keep up in an argument and not hold it against you.",
      You:" The partner who fits you is precise, presentable, particular. You want standards. You also want someone who won't apply them all to you.",
      Xu:" The partner who fits you is loyal and protective — the kind who stays when it's dull. You test people for this, usually without telling them.",
      Hai:" The partner who fits you is generous and easygoing, slow to take offence. You need room to be difficult sometimes, and someone who won't score it."
    },
    /* HOW YOU APPROACH — demoted from the opener; still true, just no longer
       the first thing every second reader sees. */
    /* This was the flattest table in the reading — a straight yin/yang coin
       flip, so half of everyone read the identical sentence. Three phrasings
       each, indexed off the month branch so it varies independently. */
    loveApproach: {
      Yang:[" You lead — you pursue, you decide, you set the pace. You need someone who won't collapse under that and won't fight you for the wheel.",
            " You're the one who moves first. That works until you meet someone who also moves first, and then it's a negotiation you've never practised.",
            " You set the temperature in a relationship. Worth asking, occasionally, whether the other person was consulted."],
      Yin:[" You tend to wait to be chosen, then feel hurt you weren't chosen harder. Say the want out loud once, {name}.",
           " You let the other person move first, then read their hesitation as a verdict on you. It usually isn't. Speak.",
           " You'd rather be discovered than have to declare yourself. It's cost you at least one person who needed a signal, {name}."]
    },
    loveDrive: {
      Companion:[" You're so self-sufficient you forget to leave a door open. Let someone actually matter.",
                 " You handle everything yourself, then wonder why nobody offers. They did. You said you were fine.",
                 " You love people without ever quite needing them, and the ones who wanted to be needed felt it."],
      Output:[" You love expressively. The quiet ones are watching closely — show more, perform less.",
              " You give affection loudly and generously. Just check the person in front of you actually wants an audience.",
              " You court people with what you make and what you say. Charming. Occasionally exhausting."],
      Wealth:[" You show love by doing and fixing. They want your attention, not your service.",
              " You treat love like something to be earned and maintained. It also has to be enjoyed sometimes.",
              " You provide, you solve, you handle it. Sit still with them once without fixing anything."],
      Officer:[" You love seriously and hold on tight. Devotion and control look the same from outside. Loosen it.",
               " You take commitment gravely, which is rare and good, and you turn it into rules, which is not.",
               " You want love to be orderly. People aren't. That gap is where most of your arguments live."],
      Resource:[" You look after your person completely. But someone who only ever gives forgets how to receive.",
                " You nurture hard. Watch that caring for them doesn't quietly become deciding for them.",
                " You carry the people you love. Let one of them carry you occasionally — it's not weakness."]
    },
    spouseSeat: {
      clash:[" One more thing uncle wasn't going to mention: the sharpest tension in your chart sits right where marriage lives. Your partner inherits a friction that started before them. Not doom. Just pick someone who doesn't flinch.",
             " And the marriage part of your chart carries the hardest tension in it. Whoever you pair with walks into an argument that predates them. Choose someone steady, and don't hand them the whole war.",
             " Uncle will say the awkward part: partnership is where your chart grinds. Not a curse — a pattern. It goes better with someone who doesn't take the friction personally."],
      harmony:[" The marriage part of your chart sits in harmony with the rest of it. Partnership tends to steady you rather than stir you up.",
               " Marriage sits easily in your chart. Being with someone tends to settle you — which is why long stretches alone don't suit you as well as you claim.",
               " Your chart takes well to partnership. It calms rather than complicates you, and you're better company when someone's around."],
      plain:[" The marriage part of your chart is quiet. Your relationships take whatever shape you give them, which is more responsibility than it sounds.",
             " Nothing dramatic sits in your marriage house. No fated ease, no fated trouble — which means the outcome is mostly your own doing.",
             " Your chart is neutral about partnership. That's not nothing: it means nobody gets to blame the stars for how it goes."]
    },
    /* YOUR PEOPLE — siblings + friends, merged (Companion god) */
    people: {
      high:["Your chart is crowded with peers, {name}. You've never lacked people — brothers, sisters, a circle that shows up. The cost is that you compete with the ones closest to you, sometimes without noticing.",
            "There have always been people around you, {name} — siblings, friends, a crowd. What you've had to learn is that closeness and rivalry can live in the same person.",
            "Company is not something you've had to hunt for. Your chart is full of peers. The quiet difficulty is measuring yourself against them without meaning to."],
      mid:["A normal amount of company in your chart. A few real ones, a lot of acquaintances, and you can tell the difference — which is rarer than you think.",
           "Your circle is ordinary in size and unusually well-sorted. You've never confused a good time with a good friend.",
           "You have the usual number of people and an unusually clear sense of which ones count. That sorting instinct is worth more than a bigger circle."],
      low:["Your chart is light on peers. You've often felt like the one standing slightly apart, even in a full room. That built your independence and also your habit of not calling anyone when it's bad.",
           "Peers are thin in your chart, {name}. Fewer siblings, fewer real friends, more time alone than most. It made you self-sufficient and slightly hard to reach.",
           "You've spent more of your life on the edge of the group than in it. That's given you perspective, and a reflex of handling bad news privately."]
    },
    peopleMod: {
      weak:[" Lean on them more than you do. Asking is not losing.",
            " You under-use the people you have. Ask for something small and see what happens.",
            " The help is there. You just don't request it, and then feel unsupported."],
      balanced:[" You give and take about evenly here. Keep it that way.",
                " Your exchanges are roughly fair, which is harder than it sounds and worth protecting.",
                " You neither drain people nor avoid them. That balance is quietly one of your best features."],
      strong:[" You're usually the one others lean on. Check whether anyone is holding you up.",
              " You're the load-bearing one in most of your friendships. Ask yourself who you'd call at 3am.",
              " People come to you. That's a compliment and a workload — make sure the traffic runs both ways."]
    },
    /* PARENTS & ROOTS — Resource god + year/month pillar */
    parents: {
      high:["Strong support sits in your chart, {name}. Someone older backed you — a parent, a grandparent, a teacher. You got a foundation. The risk is staying comfortable on it too long.",
            "You were given a floor to stand on, {name} — someone older invested in you. That's a real advantage, and it can also become a reason not to jump.",
            "Your chart shows backing from the generation above. Whatever else was hard, you weren't starting from nothing."],
      mid:["Ordinary support — present, imperfect, enough. What you got was a start, not a guarantee, and you've known that since young.",
           "The support you had was real and limited. Enough to begin with, not enough to coast on. You worked that out early.",
           "Your roots gave you something, though not everything. You've never expected rescue, which has served you better than rescue would have."],
      low:["Your chart is thin on inherited support. You built more of yourself than most people had to. It made you capable and it made you wary of depending on anyone.",
           "There wasn't much backing behind you, {name}. You assembled yourself. That's why you're competent, and why you find it hard to be carried.",
           "Little came down to you from above — you made your own footing. It shows in how much you can handle and in how badly you take being helped."]
    },
    parentsSeason: {
      spring:" Early years pushed you forward fast.",
      summer:" Early years were loud and full — a lot happening around you.",
      autumn:" Early years asked you to grow up sooner than you should have.",
      winter:" Early years were quieter than most. You learned to entertain yourself."
    },

    /* HEALTH — gentle tendencies only, never diagnosis */
    /* Keyed on the chart's DOMINANT element, not the thinnest. What's Coming
       already speaks about what's thin; running health off the same selector
       made one signal narrate two sections and the reading repeated itself.
       Excess is as legitimate a health story in the tradition as deficiency.

       Written as tendencies with practical habits. Never a diagnosis, never a
       named disease, never a prediction of illness. */
    health: {
      Wood:["Your chart runs heavy on Wood, traditionally linked to the liver and the tendons — the body's stretch and its temper. Nothing to worry about, just where your type holds tension. Move often, and don't let irritation sit.",
            "Wood dominates your chart. The tradition ties that to the liver and the sinews, and to a temperament that tightens under frustration. Stretch, walk, say the annoying thing out loud.",
            "There's a lot of Wood in you — liver and tendons, in the old language. Your type stiffens when stuck, physically and otherwise. Keep moving and keep deciding."],
      Fire:["Your chart runs heavy on Fire, traditionally linked to the heart and circulation. Not a warning — a tendency. Your type burns hot and sleeps badly. Guard the sleep and let the pressure out somewhere.",
            "Fire dominates your chart. The old association is the heart and the blood, and a system that runs hot and fast. Cooling matters for you more than most: rest, water, quiet evenings.",
            "You're Fire-heavy. That maps to circulation and to a mind that won't switch off. Your type does well with a hard stop at the end of the day."],
      Earth:["Your chart runs heavy on Earth, traditionally linked to digestion and the stomach. Your type holds things — food, worry, other people's problems. Regular meals and fewer carried burdens.",
             "Earth dominates your chart. The tradition ties it to the spleen and stomach, and to a habit of absorbing what isn't yours. Eat on a schedule and put some things down.",
             "You're Earth-heavy — digestion, in the old language, and a tendency to sit with things too long. Move more than feels necessary and don't skip meals when busy."],
      Metal:["Your chart runs heavy on Metal, traditionally linked to the lungs and the skin — the body's boundary. Your type holds grief quietly and breathes shallowly under stress. Air, breath, and saying it.",
             "Metal dominates your chart. The association is the lungs and skin, and a temperament that keeps things sealed. Mind the air you spend your days in, and exhale properly.",
             "You're Metal-heavy. Lungs and boundary, in the tradition. Your type gets rigid before it gets tired — loosen the schedule before the body insists."],
      Water:["Your chart runs heavy on Water, traditionally linked to the kidneys and the body's reserves. Your type runs deep and drains slowly without noticing. Sleep is not optional for you.",
             "Water dominates your chart. The old association is the kidneys — the deep reserve. Your type overdraws quietly and calls it being busy. Rest before empty, not after.",
             "You're Water-heavy: reserves, in the tradition, and a habit of running on them. Warmth and sleep do more for you than effort does."]
    },
    healthStrength: {
      weak:[" With thinner support overall, recovery takes you longer than you'd like. Build rest in before you need it.",
            " Your reserves are on the light side, so you bounce back slowly. Plan the recovery, don't improvise it.",
            " You don't have deep reserves to raid. That means rest is maintenance for you, not reward."],
      balanced:[" Your overall balance is reasonable — most of your health comes down to habit, not fate.",
                " Nothing in your chart is working against you here. Which puts the whole thing in the hands of your routine.",
                " You're evenly built. No structural disadvantage, no free pass — just whatever you actually do each week."],
      strong:[" You have strong reserves, which is why you overspend them. Strong people ignore small signals longest.",
              " Your reserves are deep, and that's precisely the risk: you can push through warnings other people would stop for.",
              " You recover well, so you take liberties. The bill for that arrives later and all at once."]
    },

    /* WHAT'S COMING */
    luckCore: {
      Wood:["What's thin in you is Wood — the nerve to start something before you can see how it ends.",
            "Your chart is short on Wood: beginnings, and the willingness to plant without a guarantee.",
            "Wood runs low in you — the appetite for the unproven thing. That's the muscle life keeps asking for."],
      Fire:["What's thin is Fire — letting yourself be seen wanting something.",
            "Your chart is short on Fire: visibility, and the nerve to be caught caring.",
            "Fire runs low in you — you keep the light banked and then wonder why nobody noticed."],
      Earth:["What's thin is Earth — the dull structure that holds a life together. You scatter.",
             "Your chart is short on Earth: routine, ballast, the boring scaffolding. Things slip through.",
             "Earth runs low in you — the unglamorous structure. Without it your good ideas leak away."],
      Metal:["What's thin is Metal — the clean decision. You let things drag because choosing feels like losing the other option.",
             "Your chart is short on Metal: the cut, the no, the end of something. You let it run on instead.",
             "Metal runs low in you — decisiveness. You keep options open past the point where they're worth anything."],
      Water:["What's thin is Water — patience and flow. You push when waiting would work better.",
             "Your chart is short on Water: patience, and the sense of when to stop forcing.",
             "Water runs low in you — the ability to wait. You force outcomes that were arriving anyway."]
    },
    luckHourUnknown:" And {name} — you didn't know your birth hour, so uncle read three pillars instead of four. The shape is right. The fine detail about your later years, don't quote uncle on.",

    /* NEXT YEAR — the headline prediction, keyed by the incoming Ten God */
    nextYear: {
      Companion:"Next year, {y}, leans on your own element. Support thins out and you carry more yourself. Good year to back your own judgement — bad year to assume everyone agrees with it.",
      Output:"Next year, {y}, pushes what's inside you outward. Something you've been sitting on wants finishing. Ship it, {name}, even rough — that year rewards the visible.",
      Wealth:"Next year, {y}, puts something you want inside arm's reach. It is real. It also asks a price, and you'll be tempted to pretend it didn't.",
      Officer:"Next year, {y}, adds structure and someone to answer to. It will feel like pressure. Carried properly, it's the year people start taking you seriously.",
      Resource:"Next year, {y}, slows the pace and hands you time to learn instead of push. You'll want to force it. Don't — that year pays students, not soldiers."
    },
    /* Notable years. Named by what they touch in a life, not by which pillar
       they land on — "your month pillar" is engine vocabulary and means nothing
       to a reader. Movement and timing only, never a verdict. */
    notable: {
      clash: {
        day:" Then mark {y}, {name}. A pivot year, and a personal one — home, partner, the things you thought were settled. Not bad. Just moving. Don't sign anything lazily that year.",
        month:" {y} shakes your work loose. A role ends, a boss leaves, or a direction stops making sense. Prepared people call that an exit. Everyone else calls it bad luck.",
        year:" {y} stirs family and reputation — how you're seen, or something among the older generation. Have the conversation you keep postponing before that year, not after it.",
        hour:" {y} unsettles the long view — home, the shape you want your life to take. Quieter than the others, and harder to ignore once it starts."
      },
      combo: {
        day:" And {y} is one of the smoother years in the run. Partnership comes easily then. Whatever you need someone's help for, ask in that year, not before it.",
        month:" {y} opens doors at work that were stuck. Ask for the role that year, {name}. Don't wait and see.",
        year:" {y} brings old connections back — someone from earlier in your life turns up with something you need. Answer the message.",
        hour:" {y} settles things at home. A good year to plant something you intend to keep."
      }
    },

    closers: [
      "That's the free part, {name}. The rest you already know and keep pretending you don't. Go do the thing you're avoiding.",
      "Go on, {name}. Uncle's tired and you have a chart to go argue with. You'll be fine. Mostly. The mostly is your part.",
      "The chart is the weather, {name}, not the umbrella. Uncle told you what's coming. Getting wet is your own business.",
      "Screenshot it, {name}. Ignore it. Come back in a year having done the exact opposite. You will.",
      "Send this to the friend who needs it more than you, {name}. You know the one. They won't listen either.",
      "It stung a little? Good, {name}. The readings that don't sting are the ones nobody remembers.",
      "Enough. Go eat something, {name}. Half of a bad week is an empty stomach and a chart you haven't made peace with."
    ]
  };

  /* YEAR: dated lines, two phrasings per cell (chosen by year parity) so two
     adjacent years sharing a Ten God never read identically. */
  var YEAR = {
    fortune: {
      Companion:["{y} throws you back on your own resources — more will, fewer helpers. Useful, if you don't shut people out.",
                 "{y} is a year you carry yourself. Independence pays; isolation doesn't."],
      Output:["{y} rewards putting your work in front of people. Staying quiet that year costs you.",
              "{y} wants output. What you make gets noticed — if you actually finish it."],
      Wealth:["{y} brings the tangible within reach. Grab it, but check the price tag.",
              "{y} is a year of appetite. Real gains, real cost. Read the fine print."],
      Officer:["{y} adds weight — a duty, a rule, someone to answer to. Carry it well and it becomes standing.",
               "{y} tightens the structure around you. Uncomfortable, but it's how you get taken seriously."],
      Resource:["{y} slows down and asks you to learn instead of push. Rest is not laziness that year.",
                "{y} is a year of taking in. Study now; the output comes after."]
    },
    career: {
      Companion:["{y} — colleagues and rivals look alike; the right partnership doubles you, the wrong one drains you.",
                 "{y} — who you work with matters more than what you work on."],
      Output:["{y} — your work gets seen; the reward is real but arrives on its own schedule.",
              "{y} — recognition first, money second. Be patient with the gap."],
      Wealth:["{y} puts money centre stage, {name} — it's there, but it arrives with a fight attached.",
              "{y} is a money year with teeth. The gain is real and so is what it asks."],
      Officer:["{y} — responsibility outruns reward for a stretch; you hold the weight before you enjoy it.",
               "{y} — you earn the position before the pay. Late, not absent."],
      Resource:["{y} — invest in your own skill, not the market. Slow money, and worth it.",
                "{y} — the return that year is knowledge. Bank it; it pays out later."]
    },
    love: {
      Companion:["{y} shows you who is actually on your side. The ones still there, keep.",
                 "{y} sorts real from convenient. Watch who's left standing."],
      Output:["{y} — you draw people easily; keeping them is the harder skill.",
              "{y} — charm opens the door, follow-through decides if they stay."],
      Wealth:["{y} stirs wanting and its complications. Want carefully.",
              "{y} heats things up. Wanting is easy; choosing well is not."],
      Officer:["{y} asks for the commitment you've been dodging. The dodge stops working.",
               "{y} raises the question you keep avoiding, and answers it for you."],
      Resource:["{y} softens you. Someone gets close, or you find out what's blocking the door.",
                "{y} opens you a little. Let it."]
    }
  };

  var PAST_REFLECT = {
    Companion:"{y} was a year you leaned hard on yourself. Did that cost you the people who offered to help?",
    Output:"{y} pushed you to put something out into the world. Did you do it, {name} — or did you sit on it?",
    Wealth:"{y} put something you wanted within reach. Did the reaching cost more than the having?",
    Officer:"{y} handed you a weight you didn't ask for. You either carried it, or you're still annoyed you had to.",
    Resource:"{y} was a quieter year — one for taking in. Did you rest, or just call the hiding rest?"
  };

  var DECADE = {
    Companion:"And somewhere in {band}, {name}, a decade opens that runs on your own element — you'll either finally back yourself, or dig in so hard nobody can reach you.",
    Output:"Somewhere in {band} a long stretch opens where you're meant to build and be seen. You'll take it or hide from it. Uncle is curious which.",
    Wealth:"Around {band}, a decade of appetite arrives — money, wanting, reaching. It rewards discipline and punishes greed, and only you know which one you run on.",
    Officer:"Somewhere in {band} the real weight lands — a decade of being responsible for things and people. It builds you or it hardens you.",
    Resource:"Around {band}, a quieter decade of learning and support opens. Help arrives — so does the temptation to hide inside the studying."
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
  function strongestElement(es){ return Object.entries(es).sort(function(a,b){return b[1]-a[1];})[0][0]; }

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
    var dmEl = STEM_EL[dayStem];

    var dmIndex = STEMS.indexOf(dayStem);
    var yy = STEM_YY[dmIndex];
    var strBucket = strengthBucket(v3.strength.classification, v3.strength.diagnosticScore);
    var season = SEASON[pillars.month.branch];
    var acc = groupScores(v3.tenGodScores);
    var drive = topGodGroup(v3.tenGodScores);
    var seed = dmIndex*13 + BRANCHES.indexOf(pillars.day.branch) + BRANCHES.indexOf(pillars.year.branch);

    /* Independent indices. Each table picks its phrasing from a DIFFERENT
       chart feature than the one that selected the bucket, so two people who
       share a bucket rarely share the sentence. */
    var iDay   = BRANCHES.indexOf(pillars.day.branch);
    var iMonth = BRANCHES.indexOf(pillars.month.branch);
    var iYear  = BRANCHES.indexOf(pillars.year.branch);
    var iHour  = BRANCHES.indexOf(pillars.hour.branch);
    var iStem  = dmIndex;

    var dayClash = v3.dynamics.some(function(d){
      return d.type==='Clash' && d.branches.indexOf(pillars.day.branch)!==-1;
    });
    var dayHarmony = v3.dynamics.some(function(d){
      return d.type==='Combination' && d.branches.indexOf(pillars.day.branch)!==-1;
    });

    var now = new Date().getFullYear();
    var pastA = now-5, pastB = now-2, next1 = now+1, next2 = now+2, next3 = now+3;

    var thin   = weakestElement(v3.elementScores);   /* what's lacking */
    var strong = strongestElement(v3.elementScores); /* what dominates */

    /* 1. OPENER */
    var opener = fillName(pick(FRAG.openers, seed), name);

    /* 2. WHO YOU ARE */
    var pCore = fillName(FRAG.dmCore[dayStem], name)
              + variant(FRAG.strength[strBucket], iDay)
              + FRAG.season[season];
    var pPhysical = variant(FRAG.physique[dmEl], iMonth).replace(/^ /,'');
    var pTraits = FRAG.traits[dayStem].replace(/^ /,'').replace(/^Traits: /,'Traits — ')
                + FRAG.drive[drive];
    var pSelfYears = (yearLine('fortune', pastA, dayStem, name)
                    + yearLine('fortune', pastB, dayStem, name)).replace(/^ /,'');

    /* 3. FORTUNE */
    var fShape = fillName(variant(FRAG.fortuneCore[strBucket], iYear), name)
               + variant(FRAG.fortuneUseful[thin], iHour);
    var fYears = (yearLine('fortune', now, dayStem, name)).replace(/^ /,'');

    /* 4. CAREER */
    var cWork = variant(FRAG.careerCore[drive], iMonth) + variant(FRAG.careerMod[strBucket], iHour);
    var cYears = (yearLine('career', pastB, dayStem, name)
                + yearLine('career', next1, dayStem, name)
                + yearLine('career', next3, dayStem, name)).replace(/^ /,'');
    var lp = activeLuckPillar(pillars, gender, birthYear);
    var decGrp = tenGodGroup(dayStem, lp.stem);
    var cDecade = fillTokens(DECADE[decGrp], { band:lp.band, name:name });

    /* 5. LOVE & SPOUSE */
    var spouseGod = (gender==='female') ? 'Officer' : 'Wealth';
    var lArrives = fillName(FRAG.spouseStar[gender][spouseBand(acc, spouseGod)][iDay % 2], name);
    var lSuits   = FRAG.spouseType[pillars.day.branch].replace(/^ /,'');
    var lHow     = (fillName(variant(FRAG.loveApproach[yy], iMonth), name)
                  + FRAG.loveDrive[drive][iDay % 3]).replace(/^ /,'');
    var seatKey  = dayClash ? 'clash' : (dayHarmony ? 'harmony' : 'plain');
    var lSeat    = (variant(FRAG.spouseSeat[seatKey], iHour)
                  + yearLine('love', next2, dayStem, name)).replace(/^ /,'');

    /* 6. YOUR PEOPLE */
    var people = fillName(variant(FRAG.people[bandOf(acc,'Companion')], iHour), name)
               + variant(FRAG.peopleMod[strBucket], iYear);

    /* 7. PARENTS & ROOTS */
    var parents = fillName(variant(FRAG.parents[bandOf(acc,'Resource')], iYear), name)
                + FRAG.parentsSeason[season];

    /* 8. HEALTH — keyed on the DOMINANT element, so it doesn't restate
       What's Coming, which speaks about the thin one. */
    var hBody = variant(FRAG.health[strong], iMonth);
    var hReserve = variant(FRAG.healthStrength[strBucket], iStem).replace(/^ /,'');

    /* 9. WHAT'S COMING */
    var pastGrp = tenGodGroup(dayStem, annualPillar(pastA).stem);
    var nextGrp = tenGodGroup(dayStem, annualPillar(next1).stem);
    var kThin = variant(FRAG.luckCore[thin], iDay);
    var kPast = 'Look back — ' + fillTokens(PAST_REFLECT[pastGrp] || '{y} asked something of you.', {y:String(pastA),name:name});
    var kNext = (fillTokens(FRAG.nextYear[nextGrp], {y:String(next1), name:name})
               + yearLine('fortune', next2, dayStem, name)).replace(/^ /,'');
    var notable = notableYears(pillars, next1, 12, 4, [next1, next2]);
    var kNotable = notable.map(function(nb){
      var tmpl = FRAG.notable[nb.kind] && FRAG.notable[nb.kind][nb.seat];
      return tmpl ? fillTokens(tmpl, { y:String(nb.year), name:name }).replace(/^ /,'') : '';
    }).filter(Boolean);
    var kClose = 'Past that, the shape holds: build quietly, and the loud money lands later and better than you expect.';
    if(!hourKnown){ kClose += fillName(FRAG.luckHourUnknown, name); }

    /* 10. CLOSER */
    var closer = fillName(pick(FRAG.closers, seed+5), name);

    return {
      /* Sections that read as prose are returned as ARRAYS of paragraphs,
         grouped by the nature of the analysis: what you are, what you look
         like, how you behave, what the years say. The page renders each
         element as its own <p>. Opener and closer stay single strings — they
         are one spoken beat each.

         The classic fallback returns plain strings for every section, so the
         renderer accepts both. */
      opener: opener,
      personality: [
        pCore,          /* core nature: element, build of character, strength, season */
        pPhysical,      /* physical tendency of the type */
        pTraits,        /* personality traits + dominant drive */
        pSelfYears      /* what the years say about you */
      ],
      fortune: [ fShape, fYears ],
      career:  [ cWork, cYears, cDecade ],
      love:    [ lArrives, lSuits, lHow, lSeat ],
      people:  [ people ],
      parents: [ parents ],
      health:  [ hBody, hReserve ],
      luck:    [ kThin, kPast, kNext ].concat(kNotable).concat([ kClose ]).filter(Boolean),
      closer:  closer,
      _selectors: {
        dayMaster:dayStem, element:dmEl, yinYang:yy, strength:strBucket, season:season,
        drive:drive, usefulElement:thin, dominantElement:strong,
        dayBranchClash:dayClash, dayBranchHarmony:dayHarmony,
        spouseStar:{ god:(gender==='female'?'Officer':'Wealth'), band:spouseBand(acc, gender==='female'?'Officer':'Wealth') },
        spouseSeat:pillars.day.branch,
        bands:{ companion:bandOf(acc,'Companion'), resource:bandOf(acc,'Resource') },
        timeline: {
          past:[pastA,pastB], current:now, future:[next1,next2,next3],
          notable: notableYears(pillars, next1, 12, 4, [next1, next2]),
          decade:{ pillar:lp.stem+'-'+lp.branch, band:lp.band, tenGod:decGrp }
        }
      }
    };
  }

  root.GptReadingV2 = {
    compose: compose,
    FRAG: FRAG, YEAR: YEAR, PAST_REFLECT: PAST_REFLECT, DECADE: DECADE,
    annualPillar: annualPillar,
    trueElements: trueElements,
    tenGodGroup: tenGodGroup,
    SECTIONS: ['opener','personality','fortune','career','love','people','parents','health','luck','closer'],
    VERSION: 'reading-v3-ten-section'
  };

})(typeof window !== 'undefined' ? window : globalThis);
