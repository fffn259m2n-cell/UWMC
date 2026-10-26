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
    return any(n.unit == unit and n.value == value for n in candidate_numbers)


def evaluate_item(plan: CarePlan, item: Item, candidate: str, language: str | None = None) -> FidelityReport:
    lang = language or detect_language(candidate)
    rep = FidelityReport(item_id=item.id, language=lang)
    src = item.original
    cand_nums = text.numbers(candidate)
    cand_bare = text.bare_numbers(candidate)
    english = lang in ("en", "unknown")
    if not english:
        rep.not_assessed = ["required concepts", "negation of 'do not' instructions",
                            "meaning and tone (needs a qualified bilingual reviewer)", "readability"]

    for fact in item.facts:
        rep.facts_checked += 1
        for q in fact.quantities:
            if english:
                ok = _has_quantity(cand_nums, q.value, q.unit)
            else:
                ok = q.value in cand_bare  # units are language-specific; check the number itself
            if not ok:
                rep.issues.append(Issue(fact.severity, "quantity_missing_or_changed", fact.id,
                                        f"“{fact.statement}” — “{q.value:g} {UNIT_WORDS.get(q.unit, q.unit)}” "
                                        "is missing or changed."))
        if fact.emergency and "911" not in candidate:
            rep.issues.append(Issue("critical", "emergency_action_missing", fact.id,
                                    f"“{fact.statement}” — the instruction to call 911 is missing."))
        if english and fact.action:
            mentions = text.action_mentions(candidate, fact.action.verbs, fact.action.objects)
            if any(not neg for _, neg in mentions):
                rep.issues.append(Issue(fact.severity, "negation_lost", fact.id,
                                        f"“{fact.statement}” — the candidate states the action without “do not”."))
            elif fact.coverage == "negated_action" and not mentions:
                rep.issues.append(Issue(fact.severity, "instruction_missing", fact.id,
                                        f"“{fact.statement}” — this “do not” instruction is missing."))
        if english and fact.concepts and fact.coverage == "concepts":
            for g in fact.concepts:
                if not text.group_present(candidate, g):
                    rep.issues.append(Issue("major" if fact.severity != "minor" else "minor", "concept_missing",
                                            fact.id, f"“{fact.statement}” — no mention of: {', '.join(g[:4])}."))

    # Medicine names: every source medicine still named; nothing new introduced.
    known = COMMON_DRUGS | plan.drug_names
    src_l, cand_l = text.normalize(src), text.normalize(candidate)
    src_drugs = {d for d in known if re.search(rf"(?<![a-z]){re.escape(d)}(?![a-z])", src_l)}
    cand_drugs = {d for d in known if re.search(rf"(?<![a-z]){re.escape(d)}(?![a-z])", cand_l)}
    if item.kind == "medication" and item.drug_names:
        names = {n.lower() for n in item.drug_names}
        if not names & cand_drugs and not any(n in cand_l for n in names):
            rep.issues.append(Issue("critical", "medicine_name_missing", None,
                                    f"The medicine name ({item.drug_names[0]}) is missing."))
    for d in sorted(cand_drugs - src_drugs - {n.lower() for n in item.drug_names}):
        rep.issues.append(Issue("critical", "medicine_added", None,
                                f"“{d}” is not in the original instruction."))

    # Numbers the source does not contain (allowing simple equivalents such as 12 hours <-> twice a day).
    src_bare = text.bare_numbers(src) | {float(q.value) for f in item.facts for q in f.quantities}
    for n in sorted(cand_bare - src_bare):
        rep.issues.append(Issue("critical" if item.kind == "medication" else "major", "number_added", None,
                                f"The number {n:g} does not appear in the original instruction."))

    if english:
        rep.readability_source = readability.stats(src)
        rep.readability_candidate = readability.stats(candidate)
        g = rep.readability_candidate.get("fk_grade")
        if g is not None and g > readability.TARGET_GRADE:
            rep.issues.append(Issue("minor", "reading_level", None,
                                    f"Estimated reading grade {g} is above the target of {readability.TARGET_GRADE:g}."))
    rep.issues.sort(key=lambda i: SEVERITY_ORDER[i.severity])
    return rep


def evaluate_plan_text(plan: CarePlan, candidates: dict[str, str], language: str | None = None) -> list[FidelityReport]:
    """Evaluate several rewritten items at once: {item_id: candidate_text}."""
    return [evaluate_item(plan, plan.item(i), c, language) for i, c in candidates.items()]
