"""Conservative safety screen applied to everything a patient types, before any other logic.

This is a prototype safeguard, not validated triage. It errs toward sending people
to human help. It cannot detect or rule out an emergency, and the interface says so.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from . import text

EMERGENCY = (
    ("chest pain", r"\bchest (pain|pressure|tightness|hurts?)\b|\b(my )?chest (is )?(hurting|tight)\b|\bheart attack\b"),
    ("breathing", r"\b(can'?t|cannot|can not|hard to|trouble|struggling to|unable to) (breathe|breath|catch my breath)\b|\bchoking\b|\b(lips|fingers?|fingertips) (are |look |turning |turned )?(blue|gray|grey)\b"),
    ("stroke signs", r"\b(face|mouth) (is )?droop|\bslurred? speech\b|\b(can'?t|cannot) (speak|talk|move my)\b|\b(one side|left side|right side|arm|leg) (is |feels |went )?(weak|numb)\b|\bstroke\b"),
    ("fainting", r"\b(faint(ed|ing)?|passed out|passing out|blacked out|unconscious)\b"),
    ("bleeding", r"\b(vomit(ing|ed)?|throwing up|threw up|coughing up) blood\b|\bbleeding (that )?(won'?t|will not|doesn'?t|does not) stop\b|\b(heavy|severe) bleeding\b"),
    ("confusion", r"\b(very |suddenly )?confused\b|\bconfusion\b"),
    ("seizure", r"\bseizure|convuls"),
    ("overdose", r"\b(took|taken|swallowed) (too many|too much|extra|the whole|all (of )?(my|the))\b|\boverdose\b"),
    ("allergic reaction", r"\b(throat|tongue|lips|face) (is )?(swelling|swollen)\b|\banaphyla"),
)
SELF_HARM = r"\b(kill myself|suicid|end my life|hurt myself|self[- ]harm|don'?t want to (live|be alive))\b"

MEDICATION_CHANGE = (
    r"\b(can|should|could|may) i (stop|quit|skip|double|halve|cut|split|crush|reduce|increase|lower|raise|change)\b",
    r"\b(take|use) (more|less|extra|another|a double|double|half)\b",
    r"\b(missed|forgot|skipped) (a |my |the )?(dose|pill|tablet|medicine|medication)\b",
    r"\b(change|adjust|lower|raise|increase|decrease) (my|the) (dose|dosage|medicine|medication)\b",
    r"\binstead of (my|the)\b",
    r"\b(is it|is it ok(ay)?|safe) to (stop|skip|mix|combine|take .* with)\b",
)
DIAGNOSIS = (
    r"\bdo i have\b", r"\bwhat'?s wrong with me\b", r"\bdiagnos(e|is) me\b",
    r"\bis (this|it|my \w+) (cancer|serious|normal|dangerous)\b", r"\bam i (dying|going to die|ok)\b",
)
RESULTS = (r"\bmy (potassium|sodium|blood pressure|heart rate|pulse|ef|ejection fraction|lab|labs|result|test) (is|was|came back)\b",)


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


def screen(message: str) -> SafetyResult:
    t = text.normalize(message)
    if re.search(SELF_HARM, t):
        return SafetyResult("crisis", "self-harm language", CRISIS_MESSAGE)
    for label, pattern in EMERGENCY:
        if re.search(pattern, t):
            return SafetyResult("emergency", label, EMERGENCY_MESSAGE)
    if any(re.search(p, t) for p in MEDICATION_CHANGE):
        return SafetyResult("refer", "medication change",
                            "I can't advise changing, stopping, skipping or doubling a medicine. Here is exactly "
                            "what your care plan says. For anything else, please ask your pharmacist or care team.")
    if any(re.search(p, t) for p in DIAGNOSIS):
        return SafetyResult("refer", "diagnosis question",
                            "I can't diagnose or tell you what a symptom means for you. Please ask your care team. "
                            "I can explain the diagnoses already written in your care plan.")
    if any(re.search(p, t) for p in RESULTS):
        return SafetyResult("refer", "personal result",
                            "I can't interpret your own test results. Your care team can tell you what your numbers "
                            "mean for you. I can explain what a test is in general.")
    return SafetyResult("none")
