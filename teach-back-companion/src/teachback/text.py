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
    "shan't", "avoid", "without", "neither", "nunca", "sin",
)
# Multi-word avoidance phrases, rewritten to "not" before counting.
NEGATOR_PHRASES = re.compile(
    r"\b(?:stay (?:off|away from)|keep (?:off|away from)|hold off(?: on)?|put off|instead of|rather than"
    r"|skip(?:ping)? (?=(?:911|calling|the call|the er|the hospital|going|the ibuprofen|the naproxen|the advil|the aleve|ibuprofen|naproxen|advil|aleve|nsaids)\b)|forget about (?=(?:911|calling)\b)"
    r"|wait (?:and see|to see)|steer clear of|stopp?(?:ed|ing|s)? (?=(?:taking|using|smoking|vaping|drinking|eating)\b)"
    r"|quit(?:s|ting)? (?=(?:taking|using|smoking|vaping|drinking)\b)|give up|gave up|stay clear of)")
# "tell you to stop", "unless your cardiologist says to stop": the action is someone else's decision.
AUTHORITY_BEFORE = re.compile(r"\b(?:tells?|told|asks?|asked|says?|said|lets?|instructs?)\s+(?:you|me|us|them|her|him)?\s*(?:to\s+)?$"
                              r"|\b(?:decides?|decided|chooses|says|tells me)\s+(?:if|when|whether)\s+(?:i|you|we)\s+(?:can\s+|should\s+)?$")
AUTHORITY_AFTER = re.compile(r"^\s*(?:it\s+|taking it\s+)?(?:if|when|unless)\s+(?:my|your|the)\s+(?:cardiologist|doctor|care team|heart doctor|provider|nurse)\s+(?:tells|says|asks)")
# Phrases that contain a negator but do not negate what follows.
NOT_NEGATING = re.compile(
    r"\b(?:no problem(?:s)?(?: with)?|not a problem|no issues?(?: with)?|no trouble(?: with)?|"
    r"(?:do|does|did)n'?t mind|(?:do|does|did) not mind|not only|can'?t wait to|cannot wait to|"
    r"never (?:have|had) (?:any )?(?:issues|problems|trouble)(?: with)?|no worries|no doubt|"
    r"no more than|not more than|not exceed|no later than|not sure|no matter|"
    r"(?:not|never|won'?t|don'?t|do not|wouldn'?t|will not|can'?t) (?:stop|quit)(?:ping|ped)? (?:taking|using)|"
    r"(?:do not|don't|dont|never|not)\s+(?:[a-z]+\s+){0,2}(?:more than|over|above|beyond|exceed)|"
    r"(?:do not|don't|never|not) let (?:it|this|your \w+) (?:go|get) (?:over|above)|"
    # a symptom, not a negated action: "if he can't talk right I dial 911"
    r"(?:can'?t|cannot|couldn'?t|isn'?t|is not|won'?t|not) (?:talk|speak|breathe|move|wake|feel|see|walk|stand|get (?:his|her|my|their) words))\b")
NEGATION_WINDOW = 5  # words before the target
LIST_WORDS = (r"(?:\bthe\b|\bany\b|\bor\b|\band\b|\bnor\b|\blike\b|\bsuch as\b|\bincluding\b|\bfor example\b|\be\.?g\.?|\bnsaids?\b"
              r"|\balso (?:sold|known) as\b|\balso called\b|\bknown as\b|\bwhich is\b|\bbrand names?\b|\bsold as\b|\bor any\b|[\s(),/:])")
# Negation that follows the target: "Smoking is not allowed", "crushing is not ok".
POST_NEGATION = re.compile(r"^\s*(?:it\s+|that\s+|them\s+)?(?:(?:or|and)\s+[a-z]+\s+)?(?:is|are)\s+(?:not\s*(?:$|[.,;!]|okay\b|ok\b|good\b|for me\b))|^\s*(?:it\s+|that\s+|them\s+)?(?:(?:or|and)\s+[a-z]+\s+)?(?:is|are)\s+(?:not\s+(?:allowed|ok|okay|safe|permitted|recommended)|forbidden|prohibited|unsafe)\b"
                           r"|^(?:\s*(?:,|and|or)?\s*[a-z]{2,15}){0,3}?\s+(?:are|is)\s+(?:a\s+)?(?:off[- ]limits|no[- ]go|no|out|bad for me|not safe)\b"
                           r"|^(?:\s*(?:,|and|or)?\s*[a-z]{2,15}){0,3}?\s*:\s*(?:never|no|nope|not for me)\b"
                           r"|^(?:\s*(?:,|and|or)?\s*[a-z]{2,15}){0,3}?\s+(?:i|you)\s+(?:must not|mustn'?t|can'?t|cannot|shouldn'?t|should not|won'?t|don'?t|do not|never)\s+(?:take|use|have)\b"
                           r"|^(?:\s*(?:,|and|or)?\s*[a-z]{2,15}){0,3}?\s+(?:no|nope|never)\s*(?:$|[.,;!])"
                           r"|^\s*(?:it\s+|that\s+)?(?:could|can|would|will|may|might)\s+(?:cause|raise|lead|give|increase|put)\b|^\s*(?:it\s+)?(?:is|are)\s+(?:dangerous|risky)\b")
# Permission that follows the target: "ibuprofen is fine", "Advil is OK for me".
POST_PERMISSION = re.compile(r"^\s*(?:is|are)\s+(?:also\s+|totally\s+|just\s+)?(?:fine|ok|okay|good|safe|allowed|alright|all right)\b|^\s*works\b"
                             r"|^\s*[:-]?\s*(?:ok|okay|fine|yes)\b")
# "I don't drink more than 8 cups": the negation belongs to the limit, not to drinking.
LIMIT_AFTER = re.compile(r"^\s*(?:[a-z]+\s+){0,2}?(?:more than|over|above|beyond|past)\b")


def normalize(text: str) -> str:
    """Lower-case, strip accents (apixabán -> apixaban), unify quotes and dashes, squeeze spaces."""
    t = unicodedata.normalize("NFKD", (text or "").lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = t.replace("’", "'").replace("–", "-").replace("—", "-")
    t = re.sub(r"\bnine[- ]one[- ]one\b", "911", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _words_to_digits(t: str) -> str:
    t = re.sub(r"\bovernight\b", "in 1 day", t)
    t = re.sub(r"\b(a|one) single\b", "1", t)
    t = re.sub(r"\b(for|in|within|after|over) (?:a|an|one) (day|week|month|year)\b", r"\1 1 \2", t)
    for w, n in sorted(WORD_NUMBERS.items(), key=lambda kv: -len(kv[0])):
        t = re.sub(rf"\b{w}\b", str(n), t)
    return t


# Frequency phrases -> doses per day. Weak forms ("every morning") count only when no
# stronger form is present, so "every morning and every night" reads as twice a day.
FREQUENCY = (
    (r"\b(?:once|1 time|one time)\s+(?:a|per|each|every)\s+day\b|\bonce daily\b|\b1 times? daily\b|\bonce a day\b|\b1 vez al dia\b", 1),
    (r"\b(?:twice|2 times|two times)\s+(?:a|per|each|every)\s+day\b|\b(?:1 )?with breakfast and (?:1 |again )?with (?:dinner|supper)\b|\b(?:twice|2 times) daily\b|\b2x\s*(?:a\s+)?day\b|\bbid\b"
     r"|\bevery 12 hours\b|\b(?:in the |every |each )?mornings? and (?:again )?(?:at |in the |every |each )?(?:nights?|evenings?|bedtime)\b"
     r"|\b1 in the morning and 1 (?:at night|in the evening|at bedtime)\b|\band again (?:at|in the) (?:night|evening|bedtime)\b"
     r"|\b(?:and|plus) (?:1|another|once|1 more) (?:at|in the) (?:night|evening|bedtime)\b|\b2 veces al dia\b"
     r"|\b(?:a )?(?:second|2nd) (?:one|1|dose|pill|tablet)\b", 2),
    (r"\b(?:three times|3 times|thrice)\s+(?:a|per|each|every)\s+day\b|\b3 times daily\b|\btid\b|\b3 veces al dia\b", 3),
    (r"\b(?:4 times|four times)\s+(?:a|per|each|every)\s+day\b|\b4 times daily\b|\bqid\b", 4),
)
WEAK_FREQUENCY = (
    # "every day" / "daily" say the medicine is continued, not how often, so they are not counted.
    (r"\b(?:every|each|a) day,? (?:in the morning|at night|at bedtime|in the evening)\b|\b(?:every|each) (?:morning|night|evening|bedtime)\b|\b1 (?:\d+ mg )?(?:pill|tablet|dose|capsule)s? (?:a|per|each) day\b", 1),
)
UNIT_PATTERNS = (
    ("mg", r"(\d[\d,]*(?:\.\d+)?)\s*(?:mg|milligrams?)\b"),
    ("mg", r"(\d[\d,]*(?:\.\d+)?)\s*(?:mg)?\s*/\s*\d[\d,]*(?:\.\d+)?\s*mg\b"),          # first of "24/26 mg"
    ("tablets", r"(?<![\d/.,])(\d{1,2})\s*(?:tablets?|pills?|capsules?|tabs?|tabletas?|pastillas?)\b"),
    ("hours", r"(\d+(?:\.\d+)?)\s*-?\s*(?:hours?|hrs?)\b"),
    ("minutes", r"(\d+)\s*(?:minutes?|mins?)\b"),
    ("days", r"(\d+)\s*(?:more\s+)?days?\b"),
    ("weeks", r"(\d+)\s*weeks?\b"),
    ("months", r"(\d+)\s*months?\b"),
    ("years", r"(\d+)\s*years?\b"),
    ("pounds", r"(\d+(?:\.\d+)?)\s*(?:pounds?|lbs?|libras?)\b"),
    ("liters", r"(\d+(?:\.\d+)?)\s*(?:liters?|litres?|l)\b"),
    ("cups", r"(\d+)\s*cups?\b"),
    ("bpm", r"(\d+)\s*(?:beats?\s*(?:a|per)\s*minute|bpm)\b"),
    ("bpm", r"\b(?:above|over|more than|below|under|less than|faster than|slower than)\s+(\d{2,3})\b(?=[^.]*\b(?:heart ?rate|pulse|beats))"),
    ("bpm", r"\b(?:heart ?rate|pulse)\b[^.\d]{0,30}?(\d{2,3})\b(?!\s*(?:mg|pounds?|lbs?|days?|°))"),
    ("fahrenheit", r"(\d+(?:\.\d+)?)\s*(?:°\s*f|degrees?\s*f(?:ahrenheit)?|°)(?![c\d])"),
    ("fahrenheit", r"\b(?:fever|temperature|temp)\b[^.\d]{0,25}?(9\d(?:\.\d)?|1[01]\d(?:\.\d)?)\b(?!\s*(?:°\s*c|mg|days?|hours?))"),
    ("celsius", r"(\d+(?:\.\d+)?)\s*°\s*c\b"),
    ("drinks", r"(\d+)\s*(?:alcoholic\s+)?(?:drinks?|beers?|glasses(?: of wine)?|shots?)\b"),
    ("drinks", r"(?<=\bhave )(\d+)(?: or \d+)?(?= on (?:saturday|sunday|friday|the weekend|weekends)\b)"),
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
    # Other units for the same quantity: "2 grams" = 2,000 mg, "2 gallons" = 7.6 liters
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(grams?|g)\b(?!\s*/)", t):
        out.append(Number(float(m.group(1)) * 1000, "mg", m.span(1)))
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*gallons?\b", t):
        out.append(Number(round(float(m.group(1)) * 3.785, 1), "liters", m.span(1)))
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


# Clauses end at sentence punctuation, at contrast words, and at a comma that starts a new
# clause ("…, I'll use Aleve"). Other commas (lists, asides, appositives) do not end a clause.
CLAUSE_BREAK = re.compile(
    r"[.;!?=]|->|→|\bso\b(?=\s*$|\s+(?:i|i'll|i'm|i will|i can|you|he|she|we|they)\b)|\bbut\b|\bunless\b|\buntil\b|\btill\b|\bexcept\b|\bhowever\b|\botherwise\b"
    r"|,\s*(?=(?:i|i'll|i'm|i'd|i've|i will|i can|you|we|it's|only|then|so|and then|and i|after that)\b)")


def is_negated(text: str, start: int, window: int = NEGATION_WINDOW) -> bool:
    """True if a negator appears in the same clause within `window` words before `start`.

    A negator carries across a list ("do not stop or skip", "no ibuprofen and no naproxen").
    "stop"/"quit" negate only directly before an action ("stop taking", "quit smoking").
    """
    t = normalize(text)
    clause = CLAUSE_BREAK.split(t[:start])[-1]
    clause = NOT_NEGATING.sub(" ", clause)
    if re.search(r"\b(?:stopp?(?:ed|ing|s)?|quit(?:s|ting)?|give up|gave up|cut out|skip(?:ping)?|forget about"
                 r"|hold off on|instead of|rather than|not bother(?: with| calling)?)\s*$", clause):
        return True   # "stop smoking", "skip 911": the target itself is being stopped or avoided
    clause = NEGATOR_PHRASES.sub(" not ", clause)
    words = re.findall(r"[a-z']+", clause)[-window:]
    return any(w in NEGATORS for w in words)


def phrase_states(text: str, phrase: str) -> list[bool]:
    """Negation state (True = negated) of each occurrence of a phrase."""
    t = normalize(text)
    states = []
    if re.match(r"(?:unless|until|till|except|but)\b", normalize(phrase)):
        return [False for _ in find_phrase(t, phrase)]   # a condition phrase is not itself negated
    for start, end in find_phrase(t, phrase):
        neg = is_negated(t, start)
        after = re.sub(r"\([^)]*\)", " ", t[end:])
        if POST_PERMISSION.match(after) or (neg and LIMIT_AFTER.match(after)):
            neg = False
        elif POST_NEGATION.match(after):
            neg = not neg
        states.append(neg)
    return states


def _numeric(phrase: str) -> bool:
    """Limits and thresholds such as "3,000" or "110" (but not "911", which is an action)."""
    return bool(re.search(r"\d", _words_to_digits(normalize(phrase)))) and "911" not in phrase


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
                after = re.sub(r"\([^)]*\)", " ", re.sub(r"^[^()]*\)", " ", t[m.end():]))
                if POST_PERMISSION.match(re.sub(r"^[^a-z]*(?:\([^)]*\))?", "", after)):
                    neg = False
                elif POST_NEGATION.match(after):
                    neg = True
                found.append((obj, neg))
        return found
    hits = []
    for verb in verbs:
        for m in re.finditer(rf"(?<![a-z]){re.escape(verb)}(?:s|ed|ing|ping|ped|d)?(?![a-z])", t):
            hits.append((m.start(), m.end(), verb))
    prev = None  # (end, negated) of the previous mention: "can't crush or chew" negates both
    for start, end, verb in sorted(hits):
        neg = is_negated(t, start) or bool(AUTHORITY_BEFORE.search(t[:start])) \
            or bool(re.search(r"\bonly\s*$", t[:start]) and AUTHORITY_AFTER.match(t[end:]))
        if POST_NEGATION.match(t[end:]):
            neg = True
        if prev and prev[1] and re.fullmatch(r"\s*(?:,|or|and|nor|, or|, and)\s*", t[prev[0]:start]):
            neg = True
        prev = (end, neg)
        found.append((verb, neg))
    return found


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]


# ---------------------------------------------------------------- limit and threshold direction
# A number's direction: an upper limit ("no more than 2 liters", "keep under 2,000 mg",
# "never go over"), a lower limit ("at least"), or a threshold ("above 110", "below 110").
# "upper" covers max limits and "below" thresholds; "lower" covers min limits and "above".
DIRECTION_BEFORE = (
    ("upper", r"(?:no more than|not more than|never (?:take |have |drink |eat |go |get )?(?:more than|over|above|beyond)"
              r"|(?:not|never|don'?t|do not)\b[^.]{0,25}\b(?:more than|over|above|exceed\w*|beyond)"
              r"|limit\w*\b.{0,30}?\bto|up to|at most|maximum(?: of)?|max\.?|not to exceed|keep\b.{0,30}?\b(?:to|under|below|less than)"
              r"|(?:the )?most (?:you can|you may|is)\b.{0,30})\s*$"),
    ("lower", r"(?:at least|minimum(?: of)?|no less than|no fewer than)\s*$"),
    ("above", r"(?:more than|above|over|greater than|higher than|exceeds?|faster than)\s*$"),
    ("below", r"(?:below|under|less than|lower than|fewer than|slower than)\s*$"),
)
DIRECTION_AFTER = (("upper", r"^[^.;]{0,45}?\b(?:or less|or fewer|or under|at most|or below|a day at most|is the (?:max|maximum|most|limit))\b"),
                   ("lower", r"^[^.;]{0,45}?\b(?:or more|or higher|or above|at least|is the (?:minimum|least))\b(?!\s+than)"))
DIRECTION_GROUP = {"upper": "upper", "below": "upper", "lower": "lower", "above": "lower"}
DIRECTIONAL_UNITS = {"mg", "liters", "cups", "bpm", "fahrenheit", "celsius", "pounds", "drinks"}


def directions(s: str) -> dict[tuple[str, float], set[str]]:
    """(unit, value) -> {"upper"/"lower"} direction groups stated around that number."""
    t = _words_to_digits(normalize(s))
    out: dict[tuple[str, float], set[str]] = {}
    for n in numbers(s):
        if n.unit not in DIRECTIONAL_UNITS:
            continue
        sentence_start = max(t.rfind(".", 0, n.span[0]), t.rfind(";", 0, n.span[0])) + 1
        before = t[max(sentence_start, n.span[0] - 60):n.span[0]]
        after = t[n.span[1]:n.span[1] + 60]
        if re.search(r"\(\s*(?:about|approximately|around|or|=)?\s*$", before) and out:
            # "2 liters (about 8 cups)": the bracketed amount is the same limit
            prev = [k for k in out if k[1] != n.value]
            if prev:
                out.setdefault((n.unit, n.value), set()).update(out[prev[-1]])
        for label, pat in DIRECTION_BEFORE:
            if re.search(pat, before):
                out.setdefault((n.unit, n.value), set()).add(DIRECTION_GROUP[label])
                break
        for label, pat in DIRECTION_AFTER:
            if re.search(pat, after):
                out.setdefault((n.unit, n.value), set()).add(label)
    return out


def direction_conflicts(source: str, candidate: str) -> list[tuple[str, float, set, set]]:
    src, cand = directions(source), directions(candidate)
    return [(k[0], k[1], labels, src[k]) for k, labels in cand.items() if k in src and labels and not labels & src[k]]
