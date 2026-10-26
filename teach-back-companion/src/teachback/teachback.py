"""Teach-back: compare a patient's own explanation with the documented instruction.

The result says which documented points the explanation included, which it did
not mention, and where it may conflict with the instruction. It never grades
the patient, never says the explanation is "correct", and never adds advice:
every message points back to the original instruction or to the care team.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from . import text
from .models import CarePlan, Fact, Item

MAX_INPUT = 2000
# Durations compared in days, so "2 months" conflicts with "2 weeks".
DURATION_DAYS = {"days": 1, "weeks": 7, "months": 30}
SKIP_VERBS = ["skip", "stop taking", "stop", "quit", "miss"]


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
    if len(re.findall(r"[a-z]{2,}", norm)) < 3:
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

    # 5) Skipping or stopping a medicine when the plan says nothing of the kind.
    if item.kind == "medication" and not any(f.action for f in item.facts):
        for verb, negated in text.action_mentions(said, SKIP_VERBS):
            if not negated:
                f = item.facts[0]
                concern(f, "contradiction",
                        f"Your explanation mentions “{verb}”, but your instructions do not say to skip or stop "
                        "this medicine. Please check with your care team or pharmacist before changing how you take it.")
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
        res.summary = "Thank you. You covered some of the main points. A few were not mentioned yet."
        res.follow_up = "You can read the instruction again and try once more, or ask your care team."
    else:
        res.summary = "Thank you. Your explanation included the main points of this instruction."
        res.follow_up = "If anything is still unclear, your care team is happy to go over it again."
    return res
