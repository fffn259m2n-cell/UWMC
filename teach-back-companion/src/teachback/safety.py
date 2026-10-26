"""Conservative safety screen applied to everything a patient types, before any other logic.

This is a prototype safeguard, not validated triage. It errs toward sending people
to human help. It cannot detect or rule out an emergency, and the interface says so.

Levels: crisis (self-harm) > emergency > refer (medication change, diagnosis, own
results) > none. Emergency and crisis phrases are ignored only when clearly negated
("I don't have chest pain"); in teach-back, phrases inside a condition ("if I have
chest pain I call 911") describe the plan rather than a current symptom.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from . import text

# Broad, conservative vocabulary. Gaps of a few words are allowed because people write
# "my lips look kind of blue" or "a squeezing in my chest that goes down my arm".
EMERGENCY = (
    ("chest pain", r"\bchest\b[^.?!]{0,40}\b(pain|pains|pressure|tight|tightness|heavy|heaviness|hurts?|hurting|squeez\w*|crush\w*|elephant|burning|weight)\b"
                   r"|\b(pain|pressure|tightness|heaviness|weight|squeez\w*|elephant)\b[^.?!]{0,30}\b(in|on) (my|the) chest\b|(?<!give me a )(?<!gives me a )(?<!give you a )(?<!give him a )(?<!give her a )(?<!give us a )\bheart attack\b(?! over)(?![^.]{0,40}\b(haha|lol|lmao|jk)\b)"
                   r"|\bdolor de pecho\b|\bduele (mucho |muchisimo )?el pecho\b|\bme duele el corazon\b"),
    ("breathing", r"\b(can'?t|cant|cannot|can not|hard to|trouble|difficulty|struggling to|struggle to|unable to|barely|hardly|hurts to)\s+(breathe|breath|breathing|catch my breath|talk)\b"
                  r"|\b(can'?t|cant|cannot) get (enough )?(air|a breath)\b|\bout of breath\b[^.]{0,25}\b(sitting|resting|lying|doing nothing|at rest)\b"
                  r"|\bshort of breath\b[^.]{0,10}\b(while |at |when )?(resting|rest|sitting|lying)\b|\b(gasping|choking|suffocating|wheezing)\b"
                  r"|\bso (short of|out of) breath\b|\bcan'?t (even )?(talk|speak|finish|say) (a )?(full |whole )?sentences?\b|\bcan'?t (lie|lay) (down|flat)\b[^.]{0,30}\bbreath|\b(lips|fingers?|fingertips|face|skin)\b[^.?!]{0,25}\b(blue|gray|grey)\b|\bpink frothy\b|\bturning (gray|grey|blue|purple)\b|\b(lips|face)\b[^.]{0,20}\b(purple|morad\w*)\b|\b(can'?t|cannot|won'?t) stay awake\b|\bno (puedo|puede) respirar\b|\blabios (morados|azules|grises)\b|\bme falta el aire\b"),
    ("stroke signs", r"\b(face|mouth|smile)\b[^.?!]{0,20}\bdroop\w*|\bslurr\w*|\b(can'?t|cannot|trouble|hard to) (speak|talk|get my words out|move my)\b"
                     r"|\b(one side|left side|right side|my arm|my leg|arm|leg|half of my body|half my face)\b[^.]{0,15}\b(weak|numb|dead|tingl\w*|can'?t move|heavy)\b|\bstroke\b(?! of (luck|genius|good))"
                     r"|\b(face|arm|leg|hand|legs|arms)\b[^.]{0,15}\b(numb|weak and clumsy|clumsy)\b|\bnumb\b[^.]{0,15}\bone side\b"
                     r"|\b(can'?t|cannot|unable to) (lift|raise|move|feel) (my|his|her) ((right|left) )?(arm|leg|hand|legs|arms|face)\b"
                     r"|\b(can'?t|cannot) move (his|her|my|their) (left|right|whole) side\b|\b(face|mouth|smile)\b[^.]{0,20}\b(crooked|lopsided|uneven|sagging)\b|\bdrool\w* (on|out of|from) one side\b"
                     r"|\b(speech|words?|talking)\b[^.]{0,20}\b(garbled|slurred|jumbled|strange|wrong|weird)\b|\b(not|isn'?t|is not) making sense\b|\bgibberish\b|\b(can'?t|cannot) get (her|his|my|their) words out\b|\bcara caida\b|\bno (puede|puedo) hablar\b|\b(un|del) lado\b[^.]{0,25}\b(debil|dormid[oa]|entumid[oa]|caid[oa])\b"
                     r"|\b(can'?t|cannot) see (out of|with)\b|\b(sudden\w*|lost) (vision|sight)\b|\bblind in one eye\b"),
    ("fainting", r"\bunresponsive\b|\b(went|gone|is|goes) limp\b|\bslumped\b|\b(won'?t|will not|can'?t|doesn'?t|isn'?t|not) (wake|waking) (up|him|her)\b|\b(faint(ed|ing)?|pass(ed|ing)? out|black(ed|ing)? out|went black|unconscious|collaps(e|ed|ing)|keel(ed)? over)\b|\bgoing to (faint|pass out)\b|\b(me|se) desmay\w*|\bno (despierta|responde|reacciona)\b"),
    ("unresponsive", r"\b(he|she|they|my \w+|someone|somebody)\b[^.]{0,15}\b(is |isn'?t |'s |are |not )*(not breathing|isn'?t breathing|stopped breathing|not responding|unresponsive|won'?t wake up|not waking up|blue)\b"),
    ("bleeding", r"\b(vomit\w*|throw\w* up|threw up|cough\w* up)\b[^.]{0,15}\b(blood|coffee[- ]grounds?)\b|\bcoffee[- ]grounds?\b"
                 r"|\bblood\b[^.]{0,10}\b(in|from) (my )?(vomit|throw[- ]up|spit|mouth)\b"
                 r"|\bbleed\w*\b[^.]{0,40}\b(won'?t|wont|will not|doesn'?t|does not|can'?t|cannot|not) (stop|quit)\w*|\b(heavy|severe|a lot of|lots of) bleeding\b|\bbleed\w* a lot\b"
                 r"|\b(won'?t|wont|will not|can'?t|cannot|doesn'?t|does not) stop (the )?bleed\w*|\bbleed\w* (heavily|badly|nonstop|non-stop)\b|\bnot stopping\b[^.]{0,20}\bbleed"
                 r"|\bkeeps? bleeding\b|\bcough\w*\b[^.]{0,25}\bblood\b|\bblood\b[^.]{0,25}\bcough\w*|\b(pouring|gushing|soaking|spurting)\b[^.]{0,20}\bblood\b|\bblood\b[^.]{0,20}\b(pouring|gushing|soaking|spurting|everywhere)\b|\bstill bleeding\b|\bstill (pouring|gushing)\b|\bnose ?bleed\w*\b[^.]{0,30}\b(\d+ ?min\w*|pouring|won'?t stop|keeps going)\b|\bbleeding\b[^.]{0,40}\bkeeps? going\b"
                 r"|\b(a lot of|lots of|so much|bright red|tons of) blood\b|\bblood\b[^.]{0,60}\b(lightheaded|light-headed|dizzy|faint\w*|weak)\b|\b(cut|wound|nick\w*|gash)\b[^.]{0,40}\b(won'?t|wont|will not|doesn'?t|does not|can'?t|cannot) stop\b|\bbleeding (for |over )?(\d+|an?|half an?) (minutes?|mins?|hours?|hour)\b|\bnose ?bleed\w*\b[^.]{0,20}\b(\d+|an?|half an?) (minutes?|hours?|hour)\b"
                 r"|\bbleeding from (my|the) (rectum|bottom|butt|eye|ear)\b|\b(severe|worst|terrible|sudden|very bad|awful)\b[^.]{0,15}\bheadache\b"
                 r"|\b(hit|bumped|banged|struck) (my|his|her) head\b|\bhead injury\b|\bfell\b[^.]{0,40}\bhead\b|\bbleeding from (his|her|my|the) head\b"),
    ("confusion", r"\b(very |suddenly |really |so )?confused\b(?!\s*(about|on|by|with|as to|which|what|when|how|why|if|whether|,\s*(which|what|when|how|about)))|\bconfusion\b|\b(doesn'?t|don'?t|does not|do not) know where (i|she|he|they) (am|is|are)\b|\bconfundid[oa]\b|\bno sabe donde (esta|estoy)\b"),
    ("seizure", r"\bseizure|convuls|\bfit\b(?= (now|again))"),
    ("overdose", r"\b(took|taken|swallowed|had|ate)\b[^.]{0,20}\b(too many|too much|extra|double|2 doses|two doses|twice|the whole|all (of )?(my|the)|another (dose|pill))\b"
                 r"|\b(took|taken|swallowed|ate)\b[^.]{0,12}\b(like |about |maybe |around )?(\d+|two|three|four|five|six|seven|eight|nine|ten|several|a bunch of|a handful of)\b[^.]{0,10}\b(pills?|tablets?|doses?|eliquis|apixaban|tylenol|acetaminophen|lasix|furosemide|metoprolol|carvedilol|entresto|of (my|them))\b"
                 r"|\b(took|taken|had)\b[^.]{0,10}\b\d{4,}\s*mg\b|\bdouble[- ]?dos\w*\b|\boverdos\w*\b|\bby (accident|mistake)\b[^.]{0,20}\b(took|dose|pill)"
                 r"|\b(took|dose|pill|pills)\b[^.]{0,30}\bby (accident|mistake)\b|\baccidentally (took|taken|swallowed|ate)\b"
                 r"|\b(kid|child|son|daughter|baby|toddler|grandchild|grandkid|grandson|granddaughter|nephew|niece|dog|cat)\b[^.]{0,20}\b(ate|swallowed|got into|took|chewed)\b[^.]{0,40}\b(pills?|medicine|meds|tablets?|eliquis|apixaban|tylenol)\b"),
    ("allergic reaction", r"\b(throat|tongue|lips|face)\b[^.]{0,15}\b(swell\w*|swollen|closing|tight)\b|\banaphyla|\bhives all over\b"),
    ("dying", r"\bfeel(s|ing)? like (i'?m|i am) dying\b|\bi think i'?m dying\b"),
)
SELF_HARM = (r"\b(kill(ing)? myself|suicid\w*|end(ing)? my life|end(ing)? it( all)?|hurt(ing)? myself|self[- ]harm|overdos\w* on"
             r"|(don'?t|do not) want to (live|be alive|be here|wake up|go on)|want to die|wish i (was|were) dead|better off dead"
             r"|no reason to (live|go on)|can'?t go on|nothing to live for|take my (own )?life|want (it|this|everything)( all)? to (be over|end|stop)"
             r"|(go to )?sleep and (not|never) wake up|better off without me|(isn'?t|not|no longer) worth living|quiero morir|me quiero matar|suicidarme|no quiero vivir|no quiero seguir viviendo"
             r"|(take|taking|swallow\w*) (all|every one|the whole bottle) (of )?(my |the |of )?(pills|meds|medicine|tablets)|so (i|that i) (don'?t|won'?t|never) wake up"
             r"|done with (life|living|it all)|(saving|stockpil\w*|hoard\w*) (up )?(my |all my )?(pills|meds|medicine)|stockpil\w*"
             r"|cut(ting)? myself (again|on purpose|deliberately)|(no |the |see the )?point (in|of) (living|life|going on)|what'?s the point"
             r"|(cutting|burning|hurting) (my|his|her) (arms?|legs?|wrists?|skin)|(killing|hurting|harming) (himself|herself|themselves)|hacerme dan\w*|sin esperanza"
             r"|(would|i'?d) be relieved|(stopping|stop) (all )?(my|his|her) (meds|medicines|pills)\b[^.]{0,30}\bon purpose|driv\w* off the (road|bridge|cliff)|(started|start) cutting|cutting again|so it'?ll (just )?end|it'?d (all )?be over|wants? to die"
             r"|giv\w* (his|her|my|their|all|away) (stuff|things|belongings)|(to )?not wake up|(driv\w*|jump\w*) off (the|a) (bridge|roof|building)|(cut|hurt)(ting)? myself\b[^.]{0,60}\b(want|going|plan) to do it again|ending (things|everything)|end (things|everything)"
             r"|\bjust die\b|\ball be over\b|wish i (wouldn'?t|didn'?t|would not|did not|won'?t|could just not) wake up|want to (cut|hurt) (myself )?again|want to do it again tonight)\b")

# Medicine vocabulary used to recognise medication questions.
MED_WORDS = (r"\b(pills?|tablets?|capsules?|meds?|medicines?|medications?|doses?|dosage|prescriptions?|water pill|blood thinner"
             r"|antibiotics?|diuretics?|anticoagulantes?|supplements?|vitamins?|melatonin|sleeping pills?|sleep aids?|fish oil|turmeric|herbs?|herbal|garlic pills|ginkgo|st\.? john'?s wort|antibiotico|pastillas?|medicinas?|medicamentos?|apixaban|eliquis|metoprolol|toprol|furosemide|lasix|sacubitril|valsartan|entresto|carvedilol|coreg"
             r"|amoxicillin|augmentin|clavulanate|acetaminophen|tylenol|ibuprofen|advil|motrin|naproxen|aleve|aspirin|nsaids?"
             r"|warfarin|insulin|spironolactone|potassium)\b")
CHANGE_WORDS = (r"\b(switching|leftover|quitting|te de hierbas|start|starting|add|adding|begin|gave me|someone else'?s|(her|his|their) (pills|meds|medicine)|neighbou?r'?s?|friend'?s|dejar de|deje de|suspender|saltar|doble|stop|stopped|stopping|quit|skip|skipped|skipping|miss|missed|forgot|forget|ran out|run out|running out"
                r"|double|doubled|doubling|extra|another|half|halve|cut|split|crush|instead|change|changing|switch"
                r"|increase|decrease|lower|raise|reduce|adjust|mix|combine|together|along with"
                r"|take more|more (pills|doses|of)|2 \w+ today|two \w+ today|second (one|dose|pill)"
                r"|anymore|any more|going to stop|don'?t want to take|didn'?t take|did not take|don'?t take|do not take"
                r"|not take|not taking|without (my|the|taking)|leave (it|them) out|go off|come off|out of|twice|later|earlier|before (my |the )?(surgery|procedure|dental|dentist))\b")
ASKING_TO_TAKE = (r"\bpuedo (tomar|usar|mezclar|combinar|dejar)\b|\b(can|could|should|may) i (take|use|have|give|mix|drink)\b[^.?]*\b(with|and|if|instead|while|for|today|tonight|now|on)\b"
                  r"|\b(alcohol|beer|wine|liquor|grapefruit|cannabis|marijuana|supplements?)\b[^.?]*\b(with|on|and)\b"
                  r"|\b(can|could|should|may) i (take|use) (an? |some |any )?(ibuprofen|advil|motrin|naproxen|aleve|aspirin|nsaids?|tylenol|acetaminophen)\b"
                  r"|\b(is|are) (it|they|\w+) (ok|okay|safe|fine|alright|all right)\b|\b(is it|it's|is that) (ok|okay|safe|fine|alright|all right) (to|if)\b")
DIAGNOSIS = (r"\bdo i have\b", r"\bwhat'?s wrong with me\b", r"\bdiagnos(e|is) me\b",
             r"\bis (this|it|my \w+) (cancer|serious|normal|dangerous)\b", r"\bam i (dying|going to die|ok|okay)\b")
RESULTS = (r"\bmy (potassium|sodium|blood pressure|bp|heart rate|pulse|ef|ejection fraction|lab|labs|result|results|test|weight|oxygen) "
           r"(is|was|came back|reading|level)\b",)
EDUCATIONAL = r"^\s*(what (is|are|does)|what'?s|whats|tell me (about|more)|explain|how (do|does|can) (you|a|an|the|people)|what are the signs|signs of|describe)\b"
CONDITIONAL = r"\b(if|in case|should i (ever )?(get|have|feel))\b"
FIRST_PERSON = r"\b(i|i'm|im|my|i've|i'd|mine)\b"
PRESENT = r"\b(this|now|right now|currently|today|tonight|still|at the moment|keeps?|keep on|again)\b"
PAST_ONLY = (r"\b(\d+|a|one|two|few|several|many|some) (years?|months?|weeks?) ago\b|\blast (year|month|week|night)\b|\bin the past\b|\byears ago\b"
             r"|\byesterday\b[^.]*\b(gone|went away|better|fine now)\b|\b(went away|is gone|it'?s gone|has gone|stopped)\b"
             r"|\b(on|last) (monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b|\b(back )?in (19|20)\d\d\b|\bchecked (me|him|her) out\b|\b(been|feels?|felt) fine since\b|\bsent (him|her|me|them) home\b")


@dataclass
class SafetyResult:
    level: str                 # emergency | crisis | refer | none
    reason: str = ""
    message: str = ""
    caution: str = ""          # "" | emergency | crisis: the broad safety net (see CAUTION_*)

    def to_dict(self) -> dict:
        return asdict(self)


EMERGENCY_MESSAGE = ("If you think this may be an emergency, call 911 now. Do not wait for an answer here. "
                     "This companion cannot assess symptoms or tell whether something is an emergency.")
CRISIS_MESSAGE = ("If you are thinking about harming yourself, call or text 988 (Suicide & Crisis Lifeline) or "
                  "call 911. You deserve support right now from a person who can help.")
CAUTION_MESSAGE = ("If this is happening now, or someone may be in danger, call 911. If you are having thoughts of "
                   "suicide or self-harm, call or text 988. This companion cannot judge how serious something is.")
MEDICATION_MESSAGE = ("I can't advise on starting, stopping, skipping, doubling or changing a medicine, or on taking "
                      "other medicines with it. Here is exactly what your care plan says. For anything else, please "
                      "ask your pharmacist or care team.")


def _live_match(t: str, pattern: str, context: str) -> re.Match | None:
    """First match that is not a plain denial, a past event, or (in teach-back) a plan description.

    Missing a real emergency is worse than a false alarm, so only a negator that directly
    governs the symptom ("no chest pain", "I don't have chest pain") suppresses a match.
    """
    present = bool(re.search(PRESENT, t)) and not re.search(r"\b(gone|better|fine|good|resolved|over|ok|okay|stopped) now\b", t)
    for m in re.finditer(pattern, t):
        lead = t[max(0, m.start() - 25):m.start()]
        tail = t[m.end():m.end() + 30]
        if re.search(r"\b(no|not having|don'?t have|do not have|didn'?t have|without|never had|haven'?t had|not)\s+(any\s+)?$", lead) \
                and not re.search(r"\b(can'?t|cannot|barely|won'?t)\s*$", lead) \
                and not re.search(r"\b(like this|like that|this bad|before|until now|now)\b", tail):
            continue
        if re.search(PAST_ONLY, t) and not present:
            continue
        if context == "teachback":
            clause = re.split(r"[.;!?]", t[:m.start()])[-1]
            if re.search(CONDITIONAL, clause) and not present:
                continue
        return m
    return None


# Broad safety net. Specific patterns above decide when to stop and say "call 911 now";
# they miss new wording (see docs/evaluation_results.md). These wide word lists catch any
# message that so much as touches an emergency or self-harm topic, and add a 911 / 988
# box above the normal answer. A needless box costs little; a missed crisis costs a lot.
CAUTION_CRISIS = (r"\b(die|dying|death|kill\w*|suicid\w*|end (it|things|everything|my life|it all)|be over|(all )?over with"
                  r"|(not|never|don'?t|wouldn'?t|won'?t) wake up|bridge|jump\w* (off|from|in front)|overdos\w*|how many [a-z ]{0,25}(would it take|does it take|to)"
                  r"|giv\w* (his|her|my|their|all) (stuff|things|belongings) away|giv\w* away|cutting (again|myself)|started cutting|cut (myself|himself|herself)"
                  r"|hurt (myself|himself|herself)|self[- ]?harm|no point|a burden|hopeless|can'?t go on|give up on (life|everything)|nothing left"
                  r"|morir|muerte|matar\w*|no quiero vivir|(no |the )?point (in|of) (living|life|going on|anything)|what'?s the point|(would|i'?d) be relieved"
                  r"|(cutting|cut|burning|hurting|scratching) (my|his|her) (arms?|legs?|wrists?|skin|self)|to cope|killing (himself|herself|myself)"
                  r"|hurting (himself|herself|myself)|on purpose|worthless|giving up|tired of (living|life|everything|fighting|it all)|can'?t do (this|it) anymore"
                  r"|done with everything|hacerme dan\w*|sin esperanza|quitarme la vida|driv\w* off|desaparecer|gone forever|better off|(it'?ll|it will|it would|it all|so it) (just )?end)\b")
CAUTION_EMERGENCY = (r"\b(chest|pecho|breath\w*|breathe|breathing|respir\w*|bleed\w*|blood|sangr\w*|faint\w*|pass(ed)? out|collaps\w*"
                     r"|unresponsive|responding|wake|waking|gibberish|words out|speech|slurr?\w*|talk\w* (funny|weird|strange|right|wrong)"
                     r"|making sense|confus\w*|sleepy|drows\w*|numb\w*|weak\w*|droop\w*|crooked|seizure|convuls\w*|swallow\w*|too many"
                     r"|lips|blue|gray|grey|morad\w*|throat|tongue|heart attack|stroke|labios|desmay\w*|nosebleed|vomit\w*|throw\w* up"
                     r"|head|fell|fall|pounding|racing|dizzy|mareo\w*|duele|dolor|choking|ahog\w*)\b")
NOT_EMERGENCY_BLOOD = r"\bblood (thinners?|pressure|tests?|work|sugar|draw|count)\b|\bchest x-? ?rays?\b|\bwake up (time|call)\b|\bhead (doctor|nurse)\b"


def _caution(t: str) -> str:
    if re.search(CAUTION_CRISIS, t):
        return "crisis"
    stripped = re.sub(NOT_EMERGENCY_BLOOD, " ", t)
    educational = bool(re.search(EDUCATIONAL, t)) and not re.search(FIRST_PERSON, t)
    if re.search(CAUTION_EMERGENCY, stripped) and not educational and not (re.search(PAST_ONLY, t) and not re.search(PRESENT, t)):
        return "emergency"
    return ""


def screen(message: str, context: str = "chat") -> SafetyResult:
    r = _screen(message, context)
    if r.level not in ("emergency", "crisis"):
        c = _caution(text.normalize(message))
        # In teach-back, explanations name warning signs on purpose, so only the crisis net applies.
        r.caution = c if context == "chat" or c == "crisis" else ""
    return r


def _screen(message: str, context: str = "chat") -> SafetyResult:
    t = text.normalize(message)
    if re.search(SELF_HARM, t) or re.search(r"\b(want|going|plan\w*|thinking about|about) to overdose\b", t) and not re.search(r"\b(stop|quit) (hurting|killing) myself (with|by) (smoking|drinking)\b", t):
        return SafetyResult("crisis", "self-harm language", CRISIS_MESSAGE)
    educational = bool(re.search(EDUCATIONAL, t)) and not re.search(FIRST_PERSON, t) and not re.search(PRESENT, t)
    if not educational:
        med_question = "?" in t and re.search(r"\b(which|what|when|how)\b[^?]*\b(pill|pills|medicine|medicines|meds|dose|doses|take)\b", t)
        for label, pattern in EMERGENCY:
            if label == "confusion" and med_question:
                continue   # "which pills do I take in the morning? I'm confused" is about the schedule
            if _live_match(t, pattern, context):
                return SafetyResult("emergency", label, EMERGENCY_MESSAGE)
    if context == "chat" and re.search(MED_WORDS, t) and (re.search(CHANGE_WORDS, t) or re.search(ASKING_TO_TAKE, t)):
        return SafetyResult("refer", "medication change", MEDICATION_MESSAGE)
    if any(re.search(p, t) for p in DIAGNOSIS):
        return SafetyResult("refer", "diagnosis question",
                            "I can't diagnose or tell you what a symptom means for you. Please ask your care team. "
                            "I can explain the diagnoses already written in your care plan.")
    if any(re.search(p, t) for p in RESULTS):
        return SafetyResult("refer", "personal result",
                            "I can't interpret your own test results. Your care team can tell you what your numbers "
                            "mean for you. I can explain what a test is in general.")
    return SafetyResult("none")
