"""Plain-text analysis shared by teach-back checking and the fidelity evaluator.

Deliberately simple and transparent: lower-casing, word-number conversion,
unit-aware number extraction, phrase matching, and a short same-clause
negation test that counts negators (so "not stop" reads as an affirmation of
the following action) and ignores phrases such as "no problem" or
"don't mind" that sound negative but are not.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

WORD_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20,
    "twenty-four": 24, "thirty": 30, "forty": 40, "fifty": 50, "hundred": 100,
    # Spanish, so number checks also work on translations
    "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
    "ocho": 8, "nueve": 9, "diez": 10, "doce": 12, "veinticuatro": 24,
}
NEGATORS = (
    "not", "never", "no", "none", "nothing", "nor", "don't", "dont", "doesn't", "doesnt", "didn't",
    "didnt", "shouldn't", "shouldnt", "can't", "cant", "cannot", "mustn't", "mustnt", "won't", "wont",
    "wouldn't", "wouldnt", "isn't", "isnt", "aren't", "arent", "wasn't", "couldn't", "needn't",
    "shan't", "avoid", "without", "stop", "quit", "nunca", "sin",
)
# Phrases that contain a negator but do not negate what follows.
NOT_NEGATING = re.compile(
    r"\b(?:no problem(?:s)?(?: with)?|not a problem|no issues?(?: with)?|no trouble(?: with)?|"
    r"(?:do|does|did)n'?t mind|(?:do|does|did) not mind|not only|can'?t wait to|cannot wait to|"
    r"never (?:have|had) (?:any )?(?:issues|problems|trouble)(?: with)?|no worries|no doubt|"
    r"no more than|not more than|not exceed|no later than|not sure|no matter|"
    r"(?:do not|don't|dont|never|not)\s+(?:take|use|have|drink|eat|go|give)?\s*(?:more than|over|above|beyond|exceed)|"
    r"(?:do not|don't|never|not) let (?:it|this|your \w+) (?:go|get) (?:over|above))\b")
NEGATION_WINDOW = 5  # words before the target
LIST_WORDS = r"(?:\bor\b|\band\b|\blike\b|\bsuch as\b|\bincluding\b|\bfor example\b|\be\.?g\.?|\bnsaids?\b|[\s(),/:])"
# Negation that follows the target: "Smoking is not allowed", "crushing is not ok".
POST_NEGATION = re.compile(r"^\s*(?:(?:or|and)\s+[a-z]+\s+)?(?:is|are)\s+(?:not\s+(?:allowed|ok|okay|safe|permitted|recommended)|forbidden|prohibited|unsafe)\b")
# Permission that follows the target: "ibuprofen is fine", "Advil is OK for me".
POST_PERMISSION = re.compile(r"^\s*(?:is|are)\s+(?:also\s+|totally\s+|just\s+)?(?:fine|ok|okay|good|safe|allowed|alright|all right)\b|^\s*works\b")


def normalize(text: str) -> str:
    """Lower-case, strip accents (apixabán -> apixaban), unify quotes and dashes, squeeze spaces."""
    t = unicodedata.normalize("NFKD", (text or "").lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = t.replace("’", "'").replace("–", "-").replace("—", "-")
    t = re.sub(r"\bnine[- ]one[- ]one\b", "911", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _words_to_digits(t: str) -> str:
    for w, n in sorted(WORD_NUMBERS.items(), key=lambda kv: -len(kv[0])):
        t = re.sub(rf"\b{w}\b", str(n), t)
    return t


# Frequency phrases -> doses per day. Weak forms ("every morning") count only when no
# stronger form is present, so "every morning and every night" reads as twice a day.
FREQUENCY = (
    (r"\b(?:once|1 time|one time)\s+(?:a|per|each|every)\s+day\b|\bonce daily\b|\b1 times? daily\b|\bonce a day\b|\b1 vez al dia\b", 1),
    (r"\b(?:twice|2 times|two times)\s+(?:a|per|each|every)\s+day\b|\b(?:twice|2 times) daily\b|\b2x\s*(?:a\s+)?day\b|\bbid\b"
     r"|\bevery 12 hours\b|\b(?:in the |every |each )?mornings? and (?:again )?(?:at |in the |every |each )?(?:nights?|evenings?|bedtime)\b"
     r"|\b1 in the morning and 1 (?:at night|in the evening|at bedtime)\b|\band again (?:at|in the) (?:night|evening|bedtime)\b"
     r"|\b(?:and|plus) (?:1|another|once|1 more) (?:at|in the) (?:night|evening|bedtime)\b|\b2 veces al dia\b", 2),
    (r"\b(?:three times|3 times|thrice)\s+(?:a|per|each|every)\s+day\b|\b3 times daily\b|\btid\b|\b3 veces al dia\b", 3),
    (r"\b(?:4 times|four times)\s+(?:a|per|each|every)\s+day\b|\b4 times daily\b|\bqid\b", 4),
)
WEAK_FREQUENCY = (
    # "every day" / "daily" say the medicine is continued, not how often, so they are not counted.
    (r"\b(?:every|each) (?:morning|night|evening|bedtime)\b|\b1 (?:\d+ mg )?(?:pill|tablet|dose|capsule)s? (?:a|per|each) day\b", 1),
)
UNIT_PATTERNS = (
    ("mg", r"(\d[\d,]*(?:\.\d+)?)\s*(?:mg|milligrams?)\b"),
    ("mg", r"(\d[\d,]*(?:\.\d+)?)\s*(?:mg)?\s*/\s*\d[\d,]*(?:\.\d+)?\s*mg\b"),          # first of "24/26 mg"
    ("tablets", r"(\d+)\s*(?:tablets?|pills?|capsules?|tabs?)\b"),
    ("hours", r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\b"),
    ("minutes", r"(\d+)\s*(?:minutes?|mins?)\b"),
    ("days", r"(\d+)\s*(?:more\s+)?days?\b"),
    ("weeks", r"(\d+)\s*weeks?\b"),
    ("months", r"(\d+)\s*months?\b"),
    ("pounds", r"(\d+(?:\.\d+)?)\s*(?:pounds?|lbs?)\b"),
    ("liters", r"(\d+(?:\.\d+)?)\s*(?:liters?|litres?|l)\b"),
    ("cups", r"(\d+)\s*cups?\b"),
    ("bpm", r"(\d+)\s*(?:beats?\s*(?:a|per)\s*minute|bpm)\b"),
    ("bpm", r"\b(?:above|over|more than|below|under|less than|faster than|slower than)\s+(\d{2,3})\b(?=[^.]*\b(?:heart ?rate|pulse|beats))"),
    ("bpm", r"\b(?:heart ?rate|pulse)\b[^.\d]{0,30}?(\d{2,3})\b(?!\s*(?:mg|pounds?|lbs?|days?|°))"),
    ("fahrenheit", r"(\d+(?:\.\d+)?)\s*(?:°\s*f|degrees?\s*f(?:ahrenheit)?|°)(?![c\d])"),
    ("fahrenheit", r"\b(?:fever|temperature|temp)\b[^.\d]{0,25}?(9\d(?:\.\d)?|1[01]\d(?:\.\d)?)\b(?!\s*(?:°\s*c|mg|days?|hours?))"),
    ("celsius", r"(\d+(?:\.\d+)?)\s*°\s*c\b"),
    ("drinks", r"(\d+)\s*(?:alcoholic\s+)?(?:drinks?|beers?|glasses(?: of wine)?|shots?)\b"),
)


@dataclass(frozen=True)
class Number:
    value: float
    unit: str
    span: tuple[int, int]


def numbers(text: str) -> list[Number]:
    """Unit-tagged numbers (doses per day, mg, tablets, hours, pounds, ...)."""
    t = _words_to_digits(normalize(text))
    out: list[Number] = []
    strong = []
    for pattern, n in FREQUENCY:
        for m in re.finditer(pattern, t):
            strong.append(Number(float(n), "per_day", m.span()))
    out += strong
    if not strong:
        for pattern, n in WEAK_FREQUENCY:
            for m in re.finditer(pattern, t):
                out.append(Number(float(n), "per_day", m.span()))
    seen = set()
    for unit, pattern in UNIT_PATTERNS:
        for m in re.finditer(pattern, t):
            raw = next(g for g in m.groups() if g)
            key = (unit, m.start(1))
            if key in seen:
                continue
            seen.add(key)
            out.append(Number(float(raw.replace(",", "")), unit, m.span(1)))
    # "24/26 mg": also record the second strength
    for m in re.finditer(r"\d[\d,]*(?:\.\d+)?\s*(?:mg)?\s*/\s*(\d[\d,]*(?:\.\d+)?)\s*mg\b", t):
        if ("mg", m.start(1)) not in seen:
            out.append(Number(float(m.group(1).replace(",", "")), "mg", m.span(1)))
    return sorted(set(out), key=lambda n: n.span)


def bare_numbers(text: str) -> set[float]:
    """Every number in the text regardless of unit (used to spot added numbers)."""
    t = _words_to_digits(normalize(text))
    return {float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", t)}


def _phrase_regex(phrase: str) -> re.Pattern:
    p = re.escape(normalize(phrase)).replace(r"\ ", r"\s+")
    # stems such as "confus" or "recurren" match word starts; full words match whole words
    return re.compile(rf"(?<![a-z0-9]){p}")


def find_phrase(text: str, phrase: str) -> list[tuple[int, int]]:
    t = normalize(text)
    return [m.span() for m in _phrase_regex(phrase).finditer(t)]


CLAUSE_BREAK = re.compile(r"[.;!?,]|\bbut\b|\bunless\b|\buntil\b|\bexcept\b|\bso\b|\bthen\b|\bhowever\b|\binstead\b")


def is_negated(text: str, start: int, window: int = NEGATION_WINDOW) -> bool:
    """True if an odd number of negators appears in the same clause within `window` words before `start`.

    Clauses end at punctuation and at "but / unless / until / so / then".
    "not stop" counts two negators and so reads as affirming what follows.
    """
    t = normalize(text)
    clause = CLAUSE_BREAK.split(t[:start])[-1]
    clause = NOT_NEGATING.sub(" ", clause)
    words = re.findall(r"[a-z']+", clause)[-window:]
    count = sum(1 for w in words if w in NEGATORS)
    return count % 2 == 1


def phrase_states(text: str, phrase: str) -> list[bool]:
    """Negation state (True = negated) of each occurrence of a phrase."""
    t = normalize(text)
    states = []
    for start, end in find_phrase(t, phrase):
        neg = is_negated(t, start)
        if POST_NEGATION.match(t[end:]):
            neg = not neg
        states.append(neg)
    return states


def _numeric(phrase: str) -> bool:
    """Limits and thresholds such as "3,000" or "110" (but not "911", which is an action)."""
    return bool(re.search(r"\d", phrase)) and "911" not in phrase


def group_present(text: str, group: list[str], allow_negated: bool = False) -> str | None:
    """Return the first phrase of the synonym group found in text (un-negated unless allowed).

    Purely numeric phrases ("3,000", "110") are limits or thresholds, never negated.
    """
    for phrase in group:
        for neg in phrase_states(text, phrase):
            if allow_negated or not neg or _numeric(phrase):
                return phrase
    return None


def group_only_negated(text: str, group: list[str]) -> str | None:
    """A phrase of the group that appears, but only in negated form ("never call 911")."""
    found_negated, found_plain = None, False
    for phrase in (p for p in group if not _numeric(p)):
        for neg in phrase_states(text, phrase):
            if neg:
                found_negated = found_negated or phrase
            else:
                found_plain = True
    return None if found_plain else found_negated


def action_mentions(text: str, verbs: list[str], objects: list[str] | None = None) -> list[tuple[str, bool]]:
    """(term, negated) for each mention of a "do not" action.

    Without objects, each verb mention is tested ("stop", "crush"). With objects
    ("do not take ibuprofen"), each object mention is tested instead, using the
    words before it, after removing only an immediately preceding list of the other
    objects: "do not take ibuprofen (Advil) or naproxen" negates every item, while
    "No Tylenol, ibuprofen is fine" does not negate ibuprofen.
    """
    t = normalize(text)
    found = []
    if objects:
        names = sorted({o.lower() for o in objects}, key=len, reverse=True)
        name_re = r"(?<![a-z])(?:" + "|".join(map(re.escape, names)) + r")(?![a-z])"
        trailing_list = re.compile(rf"(?:{name_re}|{LIST_WORDS})+$")
        for obj in objects:
            for m in re.finditer(rf"(?<![a-z]){re.escape(obj.lower())}(?![a-z])", t):
                before = t[:m.start()]
                stripped = trailing_list.sub(" ", before)
                # A list joined by commas belongs to the preceding clause, so drop list commas only.
                neg = is_negated(stripped, len(stripped))
                after = t[m.end():]
                if POST_PERMISSION.match(re.sub(r"^[^a-z]*(?:\([^)]*\))?", "", after)):
                    neg = False
                elif POST_NEGATION.match(after):
                    neg = True
                found.append((obj, neg))
        return found
    for verb in verbs:
        for m in re.finditer(rf"(?<![a-z]){re.escape(verb)}(?:s|ed|ing|ping|ped|d)?(?![a-z])", t):
            neg = is_negated(t, m.start())
            if POST_NEGATION.match(t[m.end():]):
                neg = True
            found.append((verb, neg))
    return found


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]
