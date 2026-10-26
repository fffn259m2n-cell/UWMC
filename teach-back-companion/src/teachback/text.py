"""Plain-text analysis shared by teach-back checking and the fidelity evaluator.

Deliberately simple and transparent: lower-casing, word-number conversion,
unit-aware number extraction, phrase matching, and a short-window negation test.
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
NEGATORS = ("not", "never", "no", "don't", "dont", "doesn't", "doesnt", "didn't", "shouldn't",
            "shouldnt", "can't", "cant", "cannot", "mustn't", "won't", "wont", "avoid", "without",
            "nunca", "no debe", "no tome", "no deje")
NEGATION_WINDOW = 4  # words before the target


def normalize(text: str) -> str:
    """Lower-case, strip accents (apixabán -> apixaban), unify quotes and dashes, squeeze spaces."""
    t = unicodedata.normalize("NFKD", (text or "").lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = t.replace("’", "'").replace("–", "-").replace("—", "-")
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _words_to_digits(t: str) -> str:
    for w, n in sorted(WORD_NUMBERS.items(), key=lambda kv: -len(kv[0])):
        t = re.sub(rf"\b{w}\b", str(n), t)
    return t


# Frequency phrases -> doses per day. "every 12 hours" is captured as hours, not per_day.
FREQUENCY = (
    (r"\b(once|1 time|one time)\s+(a|per|each)\s+day\b|\bonce daily\b|\bonce a day\b", 1),
    (r"\b(twice|2 times|two times)\s+(a|per|each)\s+day\b|\btwice daily\b|\btwice a day\b|\b2x\s*(a\s+)?day\b|\bbid\b", 2),
    (r"\b(three times|3 times|thrice)\s+(a|per|each)\s+day\b|\btid\b", 3),
    (r"\b(4 times|four times)\s+(a|per|each)\s+day\b|\bqid\b", 4),
)
UNIT_PATTERNS = (
    ("mg", r"(\d[\d,]*(?:\.\d+)?)\s*(?:mg|milligrams?)\b"),
    ("hours", r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\b"),
    ("minutes", r"(\d+)\s*(?:minutes?|mins?)\b"),
    ("days", r"(\d+)\s*(?:more\s+)?days?\b"),
    ("weeks", r"(\d+)\s*weeks?\b"),
    ("pounds", r"(\d+(?:\.\d+)?)\s*(?:pounds?|lbs?)\b"),
    ("liters", r"(\d+(?:\.\d+)?)\s*(?:liters?|litres?|l)\b"),
    ("cups", r"(\d+)\s*cups?\b"),
    ("bpm", r"(\d+)\s*(?:beats?\s*(?:a|per)\s*minute|bpm)\b|\b(?:above|over|more than)\s+(\d{2,3})\b(?=[^.]*\b(?:heart rate|pulse|beats))"),
    ("fahrenheit", r"(\d+(?:\.\d+)?)\s*(?:°\s*f|degrees?\s*f(?:ahrenheit)?|°)(?![c\d])"),
    ("celsius", r"(\d+(?:\.\d+)?)\s*°\s*c\b"),
    ("drinks", r"(\d+)\s*(?:alcoholic\s+)?drinks?\b"),
)


@dataclass(frozen=True)
class Number:
    value: float
    unit: str
    span: tuple[int, int]


def numbers(text: str) -> list[Number]:
    """Unit-tagged numbers. Week/day/hour spans that belong to a frequency phrase are skipped."""
    t = _words_to_digits(normalize(text))
    out: list[Number] = []
    for pattern, n in FREQUENCY:
        for m in re.finditer(pattern, t):
            out.append(Number(float(n), "per_day", m.span()))
    for unit, pattern in UNIT_PATTERNS:
        for m in re.finditer(pattern, t):
            raw = next(g for g in m.groups() if g)
            value = float(raw.replace(",", ""))
            out.append(Number(value, unit, m.span()))
    # "in 24 hours" after a mg limit is a real quantity; "a day" inside frequency is not a day count.
    return sorted(out, key=lambda n: n.span)


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


def is_negated(text: str, start: int, window: int = NEGATION_WINDOW) -> bool:
    """True if a negator appears within `window` words before position `start`."""
    t = normalize(text)
    clause = re.split(r"[.;!?]|,\s*(?:and|so|then)\b|\bbut\b|\bunless\b|\buntil\b", t[:start])[-1]
    words = re.findall(r"[a-z']+", clause)[-window:]
    joined = " ".join(words)
    return any(re.search(rf"(?<![a-z']){re.escape(n)}(?![a-z'])", joined) for n in NEGATORS)


def group_present(text: str, group: list[str], allow_negated: bool = True) -> str | None:
    """Return the first phrase of the synonym group found in text (optionally un-negated only)."""
    for phrase in group:
        for start, _ in find_phrase(text, phrase):
            if allow_negated or not is_negated(text, start):
                return phrase
    return None


def action_mentions(text: str, verbs: list[str], objects: list[str] | None = None) -> list[tuple[str, bool]]:
    """(term, negated) for each mention of a "do not" action.

    Without objects, each verb mention is tested ("stop", "crush"). With objects
    ("do not take ibuprofen"), each object mention is tested instead, using the
    words before it: "take Tylenol but not ibuprofen" negates ibuprofen.
    """
    t = normalize(text)
    found = []
    if objects:
        # Drop the other objects and list punctuation so "do not take ibuprofen (Advil, Motrin)
        # or naproxen" negates every item in the list.
        names = sorted({o.lower() for o in objects}, key=len, reverse=True)
        strip = re.compile(r"(?<![a-z])(?:" + "|".join(map(re.escape, names)) + r")(?![a-z])|[(),/]|\bor\b|\band\b")
        for obj in objects:
            for m in re.finditer(rf"(?<![a-z]){re.escape(obj.lower())}(?![a-z])", t):
                before = strip.sub(" ", t[:m.start()])
                found.append((obj, is_negated(before, len(before), window=NEGATION_WINDOW)))
        return found
    for verb in verbs:
        for m in re.finditer(rf"(?<![a-z]){re.escape(verb)}(?:s|ed|ing|ping|ped)?(?![a-z])", t):
            found.append((verb, is_negated(t, m.start())))
    return found


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]
