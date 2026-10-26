"""Teach-back: compare a patient's own explanation with the documented instruction.

The result says which documented points the explanation included, which it did
not mention, and where it may conflict with the instruction. It never grades
the patient, never says the explanation is "correct", and never adds advice:
every message points back to the original instruction or to the care team.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from . import consistency, text
from .models import CarePlan, Fact, Item

MAX_INPUT = 2000
# Durations compared in days, so "2 months" conflicts with "2 weeks".
DURATION_DAYS = {"days": 1, "weeks": 7, "months": 30, "years": 365}
SKIP_VERBS = ["skip", "stop taking", "quit taking", "miss", "leave it out", "leave out", "go without", "come off",
              "go off", "get off", "done with it", "leave the rest", "throw away", "throw out", "won't need it",
              "no longer need"]
EXTRA_DOSE = (r"\b(?:second|2nd|another|extra|additional|1 more|one more)\s+(?:\d+ mg\s+)?(?:one|1|dose|pill|tablet|capsule)s?\b"
              r"|\bdouble (?:up|the dose|my dose|it)\b|\btake (?:more|2|two|extra)\b")


READ_AGAIN = "Please read the instruction below again, and ask your care team if you are unsure."
PATIENT_MESSAGES = {
    "time_of_day_changed": "You mentioned a different time of day than your instructions give.",
    "frequency_changed": "How often you described taking it may not match your instructions.",
    "food_changed": "Your instructions say to take it with food.",
    "stop_condition_added": "Your instructions do not give a reason or a time to stop, skip or pause this medicine.",
    "dose_added": "Your instructions do not say to take extra.",
    "tablet_count_changed": "The number of tablets you mentioned may not match your instructions.",
    "doses_combined": "Your instructions say to take the doses separately, as written.",
    "strength_swapped": "The strength you mentioned may not match your instructions.",
    "warning_normalised": "Your instructions treat this as a reason to call, not as something normal.",
    "action_delayed": "Your instructions say to call when this happens, without waiting.",
    "instruction_dropped": "Your instructions ask you to do this; they do not make it optional.",
    "emergency_sign_not_with_911": "For this sign, your instructions say to call 911.",
    "alternative_to_911": "For these signs, your instructions say to call 911.",
    "limit_loosened": "Your instructions set a limit here.",
    "limit_reversed": "Your instructions say to drink plenty of fluids.",
    "direction_changed": "Your instructions are about your weight going up.",
    "period_changed": "The time period you mentioned for this limit may not match your instructions.",
    "or_changed_to_and": "Your instructions say that either one of these is a reason to call.",
}
# Checks that repeat what a plan-specific misunderstanding message already says.
OVERLAPPING = {"stop_condition_added", "emergency_sign_not_with_911", "alternative_to_911", "action_delayed", "dose_added"}


@dataclass
class Concern:
    fact_id: str
    kind: str            # misconception | contradiction | number_mismatch
    message: str
    original: str        # the documented instruction, verbatim
    severity: str


@dataclass
class TeachBackResult:
    item_id: str
    covered: list[dict] = field(default_factory=list)
    not_mentioned: list[dict] = field(default_factory=list)
    concerns: list[Concern] = field(default_factory=list)
    summary: str = ""
    follow_up: str = ""
    safety: dict | None = None
    limits: str = ("This is an automatic check of wording. It can miss misunderstandings and cannot confirm that "
                   "you understood. Please go over your instructions with your nurse, pharmacist or care team.")

    def to_dict(self) -> dict:
        return asdict(self)


def _fmt(v: float) -> str:
    return f"{v:,.0f}" if float(v).is_integer() else f"{v:g}"


def _unit_label(unit: str) -> str:
    return {"per_day": "time(s) a day", "mg": "mg", "bpm": "beats a minute", "fahrenheit": "°F",
            "tablets": "tablet(s)"}.get(unit, unit)


def _quantities_stated(fact: Fact, said: str) -> bool:
    """At least one of the fact's key numbers is stated with its unit (exact match)."""
    nums = text.numbers(said)
    return any(any(n.unit == q.unit and n.value == q.value for n in nums) for q in fact.quantities)


def _fact_covered(fact: Fact, said: str) -> bool:
    concepts_ok = bool(fact.concepts) and all(text.group_present(said, g) for g in fact.concepts)
    if fact.coverage == "concepts":
        quantities_ok = _quantities_stated(fact, said) if fact.quantities else True
        if not fact.concepts:
            return quantities_ok
        return concepts_ok and quantities_ok
    negated_action = bool(fact.action) and any(
        neg for _, neg in text.action_mentions(said, fact.action.verbs, fact.action.objects))
    if fact.coverage == "negated_action":
        return negated_action
    return concepts_ok or negated_action


def _number_mismatches(item: Item, fact: Fact, said: str) -> list[Concern]:
    """Numbers the patient states, in a unit this fact uses, that appear nowhere in the instruction."""
    documented = {(n.unit, n.value) for n in text.numbers(item.original)}
    documented_days = {n.value * DURATION_DAYS[n.unit] for n in text.numbers(item.original) if n.unit in DURATION_DAYS}
    fact_units = {q.unit for q in fact.quantities}
    fact_has_duration = bool(fact_units & DURATION_DAYS.keys())
    out = []
    for n in text.numbers(said):
        if n.unit in DURATION_DAYS and fact_has_duration:
            if n.value * DURATION_DAYS[n.unit] in documented_days:
                continue
            expected = [f"{_fmt(q.value)} {q.unit}" for q in fact.quantities if q.unit in DURATION_DAYS]
        elif n.unit in fact_units and (n.unit, n.value) not in documented:
            expected = [f"{_fmt(v)} {_unit_label(n.unit)}" for v in sorted({q.value for q in fact.quantities if q.unit == n.unit})]
        else:
            continue
        out.append(Concern(
            fact.id, "number_mismatch",
            f"You mentioned {_fmt(n.value)} {_unit_label(n.unit)}. Your instructions say {' or '.join(expected)}. "
            "Please check the instruction below, and ask your care team or pharmacist if it is unclear.",
            item.original, fact.severity))
    return out


def check(plan: CarePlan, item_id: str, said: str) -> TeachBackResult:
    item = plan.item(item_id)
    said = (said or "")[:MAX_INPUT]
    res = TeachBackResult(item_id=item.id)
    norm = text.normalize(said)
    if len(re.findall(r"[a-z]{2,}", norm)) < 3 and not text.numbers(said):
        res.summary = "Try saying the instruction in your own words, in a sentence or two."
        res.not_mentioned = [{"fact_id": f.id, "statement": f.statement, "severity": f.severity} for f in item.facts]
        return res

    def concern(fact: Fact, kind: str, message: str) -> None:
        if not any(c.fact_id == fact.id and c.kind == kind and c.message == message for c in res.concerns):
            res.concerns.append(Concern(fact.id, kind, message, item.original, fact.severity))

    for fact in item.facts:
        # 1) Known misunderstandings for this instruction (unless the patient negated them).
        for mc in fact.misconceptions:
            m = re.search(mc.pattern, norm)
            if m and not text.is_negated(norm, m.start()):
                concern(fact, "misconception", mc.message)
        # 2) "Do not ..." instructions restated without the "not".
        if fact.action:
            for verb, negated in text.action_mentions(said, fact.action.verbs, fact.action.objects):
                if not negated and not any(c.fact_id == fact.id for c in res.concerns):
                    concern(fact, "contradiction",
                            f"Your explanation mentions “{verb}”, but the instruction says: “{fact.statement}” "
                            "Please read the instruction below again, and ask your care team if you are unsure.")
        # 3) A required point stated the opposite way ("never call 911", "without food").
        for g in fact.concepts:
            neg = text.group_only_negated(said, g)
            if neg:
                concern(fact, "contradiction",
                        f"Your explanation seems to say not to “{neg}”, but the instruction says: “{fact.statement}” "
                        "Please read the instruction below again, and ask your care team if you are unsure.")
        # 4) Numbers that do not match the instruction.
        for c in _number_mismatches(item, fact, said):
            concern(fact, c.kind, c.message)

    # 5) Skipping, stopping or adding doses of a medicine when the plan says nothing of the kind.
    if item.kind == "medication":
        f = item.facts[0]
        if not any(c.kind == "contradiction" for c in res.concerns):
            for verb, negated in text.action_mentions(said, SKIP_VERBS):
                if not negated and not re.search(rf"\b(if|when|in case) (i|you) {re.escape(verb)}", norm):
                    concern(f, "contradiction",
                            f"Your explanation mentions “{verb}”, but your instructions do not say to skip or stop "
                            "this medicine. Please check with your care team or pharmacist before changing how you take it.")
                    break
        digits = text._words_to_digits(norm)
        m = re.search(EXTRA_DOSE, digits)
        if m and not text.is_negated(digits, m.start()) and not re.search(EXTRA_DOSE, text._words_to_digits(text.normalize(item.original))):
            concern(f, "contradiction",
                    "Your explanation mentions an extra dose. Your instructions do not say to take extra. "
                    "Please ask your care team or pharmacist before taking more than prescribed.")

    # 6) A limit read the wrong way ("at least 2 liters" when 2 liters is the most allowed).
    for unit, value, got, want in text.direction_conflicts(item.original, said):
        f = next((fa for fa in item.facts if any(q.unit == unit and q.value == value for q in fa.quantities)), item.facts[0])
        concern(f, "number_mismatch",
                f"You described {_fmt(value)} {_unit_label(unit)} as a {'minimum' if 'lower' in got else 'maximum'}, "
                f"but in your instructions it is a {'maximum' if 'upper' in want else 'minimum'}. Please check the instruction below.")

    # 7) Meaning changes shared with the fidelity evaluator (time of day, food, stop
    #    conditions, emergency signs without 911, limits and periods), in patient wording.
    target = next((f for f in item.facts if f.emergency), None) or next(
        (f for f in item.facts if f.severity == "critical"), item.facts[0])
    already = bool(res.concerns)
    for ch in consistency.compare(item, said, patient=True):
        if already and ch.check in OVERLAPPING:
            continue   # a plan-specific message already covers this
        concern(target, "contradiction", f"{PATIENT_MESSAGES.get(ch.check, ch.message)} {READ_AGAIN}")
    # 8) Medicines this instruction does not mention.
    from .fidelity import COMMON_DRUGS
    src = text.normalize(item.original)
    known = COMMON_DRUGS | plan.drug_names
    # Brand and generic names of a medicine this instruction already names are not "new".
    for other in plan.items:
        names = {n.lower() for n in other.drug_names}
        if any(re.search(rf"(?<![a-z]){re.escape(n)}(?![a-z])", text.normalize(item.original)) for n in names):
            known -= names
    for d in sorted(known):
        if re.search(rf"(?<![a-z]){re.escape(d)}(?![a-z])", norm) and d not in src \
                and d not in {n.lower() for n in item.drug_names} and not text.is_negated(norm, norm.index(d)):
            concern(target, "contradiction",
                    f"You mentioned {d}. This instruction does not mention it. Please check with your care team "
                    "or pharmacist before taking any medicine that is not in your instructions.")
            break

    for fact in item.facts:
        flagged = any(c.fact_id == fact.id for c in res.concerns)
        entry = {"fact_id": fact.id, "statement": fact.statement, "severity": fact.severity}
        if _fact_covered(fact, said) and not flagged:
            res.covered.append(entry)
        elif not flagged:
            res.not_mentioned.append(entry)

    order = {"critical": 0, "major": 1, "minor": 2}
    res.concerns.sort(key=lambda c: order[c.severity])
    res.not_mentioned.sort(key=lambda f: order[f["severity"]])
    if res.concerns:
        res.summary = ("Some of what you said may not match your instructions. That is very common, and "
                       "it is exactly why we check. Please look at the points below.")
        res.follow_up = "Ask your care team about these points before you leave or at your next call."
    elif res.not_mentioned:
        res.summary = ("Thank you. The tool recognized some of the main points, and a few were not mentioned yet. "
                       "No conflicts were found automatically, but that does not mean there are none.")
        res.follow_up = "You can read the instruction again and try once more, or ask your care team."
    else:
        res.summary = ("Thank you. The tool recognized the main points of this instruction and found no conflicts "
                       "automatically. That does not confirm your understanding; please still review it with your care team.")
        res.follow_up = "If anything is still unclear, your care team is happy to go over it again."
    return res
