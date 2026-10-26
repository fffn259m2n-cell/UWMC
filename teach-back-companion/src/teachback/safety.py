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

EMERGENCY = (
    ("chest pain", r"\bchest\b[^.]{0,25}\b(pain|pains|pressure|tight|tightness|heavy|heaviness|hurts?|hurting|squeez\w*|crush\w*)\b"
                   r"|\b(pain|pressure|tightness|heaviness|weight)\b[^.]{0,20}\b(in|on) (my|the) chest\b|\bheart attack\b"),
    ("breathing", r"\b(can'?t|cannot|can not|hard to|trouble|difficulty|struggling to|struggle to|unable to|barely|hurts to)\s+(breathe|breath|breathing|catch my breath)\b"
                  r"|\b(gasping|choking|suffocating)\b|\bshort of breath\b[^.]{0,20}\b(resting|rest|lying|worse|bad|severe)\b"
                  r"|\b(lips|fingers?|fingertips|face) (are |is |look |looks |turning |turned )?(blue|gray|grey)\b"),
    ("stroke signs", r"\b(face|mouth|smile)\b[^.]{0,15}\bdroop\w*|\bslurr\w*|\b(can'?t|cannot|trouble|hard to) (speak|talk|get my words out|move my)\b"
                     r"|\b(one side|left side|right side|my arm|my leg|arm|leg|half of my body)\b[^.]{0,15}\b(weak|numb|dead|tingl\w*|can'?t move)\b|\bstroke\b"),
    ("fainting", r"\b(faint(ed|ing)?|pass(ed|ing)? out|black(ed|ing)? out|unconscious|collaps(e|ed|ing)|keel(ed)? over)\b|\bgoing to (faint|pass out)\b"),
    ("bleeding", r"\b(vomit\w*|throw\w* up|threw up|cough\w* up)\b[^.]{0,10}\bblood\b|\bblood\b[^.]{0,10}\b(in|from) (my )?(vomit|throw[- ]up|spit|mouth|stool)\b"
                 r"|\bbleed\w*\b[^.]{0,40}\b(won'?t|will not|doesn'?t|does not|can'?t|cannot|not) stop\w*|\b(heavy|severe|a lot of|lots of) bleeding\b|\bbleed\w* a lot\b"
                 r"|\b(severe|worst|terrible|sudden|very bad|awful)\b[^.]{0,15}\bheadache\b"),
    ("confusion", r"\b(very |suddenly |really )?confused\b|\bconfusion\b|\bdon'?t know where i am\b"),
    ("seizure", r"\bseizure|convuls|\bfit\b(?= (now|again))"),
    ("overdose", r"\b(took|taken|swallowed|had)\b[^.]{0,20}\b(too many|too much|extra|double|2 doses|two doses|twice|the whole|all (of )?(my|the)|another (dose|pill))\b"
                 r"|\boverdose\w*\b|\bby (accident|mistake)\b[^.]{0,20}\b(took|dose|pill)|\b(took|dose|pill)\b[^.]{0,30}\bby (accident|mistake)\b"),
    ("allergic reaction", r"\b(throat|tongue|lips|face)\b[^.]{0,10}\b(swell\w*|swollen|closing|tight)\b|\banaphyla|\bhives all over\b"),
)
SELF_HARM = (r"\b(kill(ing)? myself|suicid\w*|end(ing)? my life|end(ing)? it( all)?|hurt(ing)? myself|self[- ]harm"
             r"|(don'?t|do not) want to (live|be alive|be here)|want to die|wish i (was|were) dead|better off dead)\b")

# Medicine vocabulary used to recognise medication questions.
MED_WORDS = (r"\b(pills?|tablets?|capsules?|meds?|medicines?|medications?|doses?|dosage|prescriptions?|water pill|blood thinner"
             r"|antibiotics?|apixaban|eliquis|metoprolol|toprol|furosemide|lasix|sacubitril|valsartan|entresto|carvedilol|coreg"
             r"|amoxicillin|augmentin|clavulanate|acetaminophen|tylenol|ibuprofen|advil|motrin|naproxen|aleve|aspirin|nsaids?"
             r"|warfarin|insulin|spironolactone|potassium)\b")
CHANGE_WORDS = (r"\b(stop|stopped|stopping|quit|skip|skipped|skipping|miss|missed|forgot|forget|ran out|run out|running out"
                r"|double|doubled|doubling|extra|another|more|less|half|halve|cut|split|crush|instead|change|changing|switch"
                r"|increase|decrease|lower|raise|reduce|adjust|mix|combine|together|with my|along with|2 \w+ today|two \w+ today"
                r"|anymore|any more|going to stop|don'?t want to take|didn'?t take|did not take|don'?t take|do not take|not take)\b")
ASKING_TO_TAKE = (r"\b(can|could|should|may|do) i (take|use|have|give)\b|\b(is|are) (it|they|\w+) (ok|okay|safe|fine|alright|all right)\b"
                  r"|\b(is it|it's|is that) (ok|okay|safe|fine|alright|all right) (to|if)\b")
DIAGNOSIS = (r"\bdo i have\b", r"\bwhat'?s wrong with me\b", r"\bdiagnos(e|is) me\b",
             r"\bis (this|it|my \w+) (cancer|serious|normal|dangerous)\b", r"\bam i (dying|going to die|ok|okay)\b")
RESULTS = (r"\bmy (potassium|sodium|blood pressure|bp|heart rate|pulse|ef|ejection fraction|lab|labs|result|results|test|weight|oxygen) "
           r"(is|was|came back|reading|level)\b",)
EDUCATIONAL = r"^\s*(what (is|are|does)|tell me about|explain|how (do|does|can)|what are the signs|signs of|describe)\b"
CONDITIONAL = r"\b(if|when|whenever|in case|should i (ever )?(get|have|feel))\b"
FIRST_PERSON = r"\b(i|i'm|im|my|me|i've|i'd)\b"


@dataclass
class SafetyResult:
    level: str                 # emergency | crisis | refer | none
    reason: str = ""
    message: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


EMERGENCY_MESSAGE = ("If you think this may be an emergency, call 911 now. Do not wait for an answer here. "
                     "This companion cannot assess symptoms or tell whether something is an emergency.")
CRISIS_MESSAGE = ("If you are thinking about harming yourself, call or text 988 (Suicide & Crisis Lifeline) or "
                  "call 911. You deserve support right now from a person who can help.")
MEDICATION_MESSAGE = ("I can't advise on starting, stopping, skipping, doubling or changing a medicine, or on taking "
                      "other medicines with it. Here is exactly what your care plan says. For anything else, please "
                      "ask your pharmacist or care team.")


def _live_match(t: str, pattern: str, context: str) -> re.Match | None:
    """First match that is not negated (and, in teach-back, not inside a condition)."""
    for m in re.finditer(pattern, t):
        clause = text.CLAUSE_BREAK.split(t[:m.start()])[-1]
        if text.is_negated(t, m.start()) and not re.search(r"\b(can'?t|cannot|barely|won'?t)\s*$", t[:m.start()]):
            continue
        if re.search(r"\b(no|not|don'?t have|do not have|without|never had)\b[^.]{0,12}$", clause):
            continue
        if context == "teachback" and re.search(CONDITIONAL, clause):
            continue
        return m
    return None


def screen(message: str, context: str = "chat") -> SafetyResult:
    t = text.normalize(message)
    if re.search(SELF_HARM, t) and not re.search(r"\b(stop|quit) (hurting|killing) myself (with|by) (smoking|drinking)\b", t):
        return SafetyResult("crisis", "self-harm language", CRISIS_MESSAGE)
    educational = bool(re.search(EDUCATIONAL, t)) and not re.search(FIRST_PERSON, t)
    if not educational:
        for label, pattern in EMERGENCY:
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
