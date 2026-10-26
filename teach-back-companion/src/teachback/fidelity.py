"""Instruction Fidelity Evaluator.

Checks whether a rewritten version of a documented instruction (a plain-language
rewrite, an AI explanation, or a translation) still carries every critical fact:

  * numbers with their units (dose, frequency, duration, thresholds) are present and unchanged
  * "do not" instructions keep their negation
  * emergency instructions still say 911
  * medicine names in the source are still named, and no new medicine names are added
  * no numbers appear that the source does not contain
  * required concepts (e.g. "with food", "every morning") are still present (English only)

It reports issues by severity; it never certifies a text as safe. For non-English
text only language-independent checks run (numbers, 911, medicine names), and the
report says semantic checks need a qualified bilingual reviewer.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from . import readability, text
from .models import CarePlan, Item

# Medicine names the evaluator recognises when looking for *added* medicines.
# Plan medicine names are added automatically.
COMMON_DRUGS = {
    "aspirin", "warfarin", "coumadin", "heparin", "enoxaparin", "lovenox", "rivaroxaban", "xarelto",
    "dabigatran", "pradaxa", "edoxaban", "clopidogrel", "plavix", "ibuprofen", "advil", "motrin",
    "naproxen", "aleve", "acetaminophen", "tylenol", "metoprolol", "carvedilol", "atenolol",
    "diltiazem", "verapamil", "digoxin", "amiodarone", "flecainide", "sotalol", "furosemide", "lasix",
    "torsemide", "bumetanide", "spironolactone", "lisinopril", "losartan", "valsartan", "sacubitril",
    "entresto", "amlodipine", "atorvastatin", "metformin", "insulin", "prednisone", "amoxicillin",
    "augmentin", "azithromycin", "doxycycline", "levofloxacin", "ceftriaxone", "cefdinir", "ondansetron",
    "oxycodone", "hydrocodone", "tramadol", "potassium", "dapagliflozin", "empagliflozin", "eliquis",
}
ENGLISH_MARKERS = {"the", "and", "you", "your", "a", "an", "of", "to", "if", "or", "in", "is", "it", "on",
                   "take", "call", "day", "with", "for", "get", "do", "not", "this", "that", "be", "are", "after"}
SPANISH_MARKERS = {"el", "la", "los", "las", "de", "que", "y", "en", "un", "una", "tome", "llame", "día", "dia",
                   "veces", "por", "con", "si", "no", "su", "sus", "para", "cada", "semana", "horas"}
SEVERITY_ORDER = {"critical": 0, "major": 1, "minor": 2}
UNIT_WORDS = {"per_day": "times a day", "bpm": "beats a minute", "fahrenheit": "°F", "celsius": "°C"}


@dataclass
class Issue:
    severity: str
    check: str
    fact_id: str | None
    message: str


@dataclass
class FidelityReport:
    item_id: str
    language: str
    issues: list[Issue] = field(default_factory=list)
    facts_checked: int = 0
    readability_source: dict = field(default_factory=dict)
    readability_candidate: dict = field(default_factory=dict)
    not_assessed: list[str] = field(default_factory=list)

    @property
    def counts(self) -> dict:
        return {s: sum(i.severity == s for i in self.issues) for s in SEVERITY_ORDER}

    @property
    def verdict(self) -> str:
        c = self.counts
        if c["critical"]:
            return "do not use: critical issues found"
        if c["major"]:
            return "revise: major issues found"
        if self.not_assessed:
            return "no automated issues found in the checks that ran; human review still required"
        return "no automated issues found; clinician review still required"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["counts"], d["verdict"] = self.counts, self.verdict
        return d


def detect_language(s: str) -> str:
    """'en', 'es', or 'non-en'. Pass `language` explicitly when known; this is a heuristic."""
    words = re.findall(r"[a-záéíóúñü']+", s.lower())
    if not words:
        return "unknown"
    en = sum(w in ENGLISH_MARKERS for w in words)
    es = sum(w in SPANISH_MARKERS for w in words)
    if es > en:
        return "es"
    non_ascii = sum(1 for ch in s if ord(ch) > 127 and ch.isalpha()) / max(1, sum(ch.isalpha() for ch in s))
    if en == 0 and non_ascii > 0.3:
        return "non-en"
    return "en"


def _has_quantity(candidate_numbers, value, unit) -> bool:
    if unit == "per_day" and value == 2:
        # "every 12 hours" is the same frequency as "twice a day"
        if any(n.unit == "per_day" and n.value == 2 for n in candidate_numbers):
            return True
    return any(n.unit == unit and n.value == value for n in candidate_numbers)


def _digits(s: str) -> str:
    return text._words_to_digits(text.normalize(s))


def _threshold_periods(s: str) -> set[tuple[float, str]]:
    """Pairs such as (2, 'day') and (5, 'week') from "2 pounds in one day or 5 pounds in one week"."""
    t = _digits(s)
    pairs = set()
    for n in text.numbers(s):
        if n.unit == "pounds":
            m = re.match(r"^\s*(?:pounds?|lbs?)?\s*(?:or more\s+)?(?:in|per|within)\s+(?:1|a|an|one)\s+(day|week)", t[n.span[1]:])
            if m:
                pairs.add((n.value, m.group(1)))
    return pairs


def _sentences_with_live_911(s: str) -> list[str]:
    out = []
    for sent in re.split(r"(?<=[.!?;])\s+", text.normalize(s)):
        if any(not neg for neg in text.phrase_states(sent, "911")):
            out.append(sent)
    return out


def evaluate_item(plan: CarePlan, item: Item, candidate: str, language: str | None = None) -> FidelityReport:
    lang = language or detect_language(candidate)
    rep = FidelityReport(item_id=item.id, language=lang)
    src = item.original
    cand_nums = text.numbers(candidate)
    src_nums = text.numbers(src)
    cand_bare = text.bare_numbers(candidate)
    cand_norm = text.normalize(candidate)
    english = lang in ("en", "unknown")
    if not english:
        rep.not_assessed = ["required concepts", "negation of 'do not' instructions",
                            "meaning and tone (needs a qualified bilingual reviewer)", "readability"]

    def add(sev, check, fact_id, msg):
        if not any(i.check == check and i.fact_id == fact_id and i.message == msg for i in rep.issues):
            rep.issues.append(Issue(sev, check, fact_id, msg))

    live_911 = _sentences_with_live_911(candidate)
    for fact in item.facts:
        rep.facts_checked += 1
        for q in fact.quantities:
            ok = _has_quantity(cand_nums, q.value, q.unit) if english else q.value in cand_bare
            if not ok:
                add(fact.severity, "quantity_missing_or_changed", fact.id,
                    f"“{fact.statement}” — “{q.value:g} {UNIT_WORDS.get(q.unit, q.unit)}” is missing or changed.")
        if fact.emergency:
            if "911" not in cand_norm:
                add("critical", "emergency_action_missing", fact.id, f"“{fact.statement}” — the instruction to call 911 is missing.")
            elif not live_911:
                add("critical", "emergency_action_negated", fact.id,
                    f"“{fact.statement}” — the candidate mentions 911 but does not tell the reader to call it.")
            elif english:
                for g in fact.concepts:
                    if any("911" in p for p in g):
                        continue
                    for phrase in g:
                        if text.find_phrase(src, phrase) and text.find_phrase(candidate, phrase) \
                                and not any(text.find_phrase(sent, phrase) for sent in live_911):
                            add("critical", "emergency_sign_not_with_911", fact.id,
                                f"“{phrase}” is in the candidate, but not in a sentence that says to call 911.")
        if english and fact.action:
            mentions = text.action_mentions(candidate, fact.action.verbs, fact.action.objects)
            if any(not neg for _, neg in mentions):
                add(fact.severity, "negation_lost", fact.id, f"“{fact.statement}” — the candidate states the action without “do not”.")
            elif fact.coverage == "negated_action" and not mentions:
                add(fact.severity, "instruction_missing", fact.id, f"“{fact.statement}” — this “do not” instruction is missing.")
        if english:
            for g in fact.concepts:
                neg = text.group_only_negated(candidate, g)
                if neg:
                    add("critical" if fact.severity == "critical" else "major", "meaning_reversed", fact.id,
                        f"“{fact.statement}” — the candidate says not to “{neg}”.")
                elif fact.coverage == "concepts" and not text.group_present(candidate, g):
                    add("major" if fact.severity != "minor" else "minor", "concept_missing", fact.id,
                        f"“{fact.statement}” — no mention of: {', '.join(g[:4])}.")
            for mc in fact.misconceptions:
                m = re.search(mc.pattern, cand_norm)
                if m and not text.is_negated(cand_norm, m.start()):
                    add("critical", "contradicts_instruction", fact.id, f"“{fact.statement}” — {mc.message}")
        elif fact.action and re.search(r"(?<!\bno )\b(puede|pueden|podra|podria)\s+(dejar de|suspender|parar|dejarlo)", cand_norm):
            add("critical", "negation_possibly_lost", fact.id,
                f"“{fact.statement}” — the translation appears to allow stopping (“puede dejar de…”).")

    if item.kind == "medication":
        src_freq = {n.value for n in src_nums if n.unit == "per_day"} | {
            q.value for f in item.facts for q in f.quantities if q.unit == "per_day"}
        cand_freq = {n.value for n in cand_nums if n.unit == "per_day"}
        if src_freq and cand_freq - src_freq:
            add("critical", "frequency_changed", None,
                f"The candidate gives {', '.join(f'{v:g}' for v in sorted(cand_freq - src_freq))} time(s) a day; "
                f"the original says {', '.join(f'{v:g}' for v in sorted(src_freq))}.")
        src_tabs = {n.value for n in src_nums if n.unit == "tablets"} | {1.0}
        for n in cand_nums:
            if n.unit == "tablets" and n.value not in src_tabs:
                add("critical", "tablet_count_changed", None, f"“{n.value:g} tablet(s)” does not match the original.")
        dose_add = (r"\b(?:extra|additional|double|another|1 more|one more|second|2nd)\s+(?:\d+ mg\s+)?(?:doses?|pills?|tablets?|capsules?|ones?)\b"
                    r"|\bdouble (?:up|the dose|your dose|it)\b|\b(?:1|one) extra\b")
        if english and re.search(dose_add, _digits(candidate)) and not re.search(dose_add, _digits(src)):
            add("critical", "dose_added", None, "The candidate mentions an extra or additional dose that the original does not.")

    src_pairs, cand_pairs = _threshold_periods(src), _threshold_periods(candidate)
    if src_pairs and cand_pairs - src_pairs:
        add("critical", "threshold_period_changed", None,
            "A threshold is paired with a different time period than in the original "
            f"({', '.join(f'{v:g} pounds per {p}' for v, p in sorted(cand_pairs - src_pairs))}).")

    if english:
        for unit, value, got, want in text.direction_conflicts(src, candidate):
            add("critical", "direction_changed", None,
                f"“{value:g} {UNIT_WORDS.get(unit, unit)}” is described as a {'/'.join(sorted(got))} bound; "
                f"the original gives a {'/'.join(sorted(want))} bound.")

    # Medicine names: every source medicine still named; nothing new introduced.
    known = COMMON_DRUGS | plan.drug_names
    src_l = text.normalize(src)
    src_drugs = {d for d in known if re.search(rf"(?<![a-z]){re.escape(d)}(?![a-z])", src_l)}
    cand_drugs = {d for d in known if re.search(rf"(?<![a-z]){re.escape(d)}(?![a-z])", cand_norm)}
    if item.kind == "medication" and item.drug_names:
        names = {n.lower() for n in item.drug_names}
        if not names & cand_drugs and not any(n in cand_norm for n in names):
            add("critical", "medicine_name_missing", None, f"The medicine name ({item.drug_names[0]}) is missing.")
    for d in sorted(cand_drugs - src_drugs - {n.lower() for n in item.drug_names}):
        add("critical", "medicine_added", None, f"“{d}” is not in the original instruction.")

    # Numbers the source does not contain. "1" is ignored ("one day", "one pill"); tablet counts are checked above.
    src_bare = text.bare_numbers(src) | {float(q.value) for f in item.facts for q in f.quantities} | {1.0, 911.0}
    for n in sorted(cand_bare - src_bare):
        add("critical" if item.kind == "medication" else "major", "number_added", None,
            f"The number {n:g} does not appear in the original instruction.")

    if english:
        rep.readability_source = readability.stats(src)
        rep.readability_candidate = readability.stats(candidate)
        g = rep.readability_candidate.get("fk_grade")
        if g is not None and g > readability.TARGET_GRADE:
            add("minor", "reading_level", None, f"Estimated reading grade {g} is above the target of {readability.TARGET_GRADE:g}.")
    rep.issues.sort(key=lambda i: SEVERITY_ORDER[i.severity])
    return rep


def evaluate_plan_text(plan: CarePlan, candidates: dict[str, str], language: str | None = None) -> list[FidelityReport]:
    """Evaluate several rewritten items at once: {item_id: candidate_text}."""
    return [evaluate_item(plan, plan.item(i), c, language) for i, c in candidates.items()]
