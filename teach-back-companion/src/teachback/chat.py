"""Ask Companion: grounded, deterministic answers.

Every answer is built from labelled blocks:
  care_plan  - text copied from the patient's documented plan (verbatim)
  education  - general text from the curated library, with its source
  companion  - short connecting text that adds no medical content
When neither source covers a question, the companion says so and points to the
care team. Nothing is generated; an optional LLM layer (llm.py) can rephrase
answers only if its output passes the fidelity checks.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import date

from . import knowledge, safety, text
from .models import CarePlan

MAX_MESSAGE = 1000
LEVEL_ORDER = ("simple", "standard", "detailed")


@dataclass
class Block:
    source: str
    text: str
    label: str = ""
    ref: str = ""
    url: str = ""


@dataclass
class Answer:
    blocks: list[Block] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    safety: dict | None = None
    topic: str | None = None
    level: str = "standard"

    def to_dict(self) -> dict:
        return asdict(self)


def _plan_topics(plan: CarePlan) -> set[str]:
    return {d.education_topic for d in plan.diagnoses} | {i.education_topic for i in plan.items if i.education_topic}


def _item_blocks(plan: CarePlan, items) -> list[Block]:
    return [Block("care_plan", i.original, label=i.title, ref=i.id) for i in items]


def _education(topic: dict, level: str) -> Block:
    src = topic["sources"][0] if topic["sources"] else {}
    return Block("education", topic["levels"][level], label=topic["title"],
                 ref=topic["id"], url=src.get("url", ""))


def _simpler(level: str) -> str:
    i = LEVEL_ORDER.index(level) if level in LEVEL_ORDER else 1
    return LEVEL_ORDER[max(0, i - 1)]


def _items_for_drug(plan: CarePlan, message: str):
    return [i for i in plan.items if i.kind == "medication"
            and any(text.find_phrase(message, n) for n in i.drug_names)]


def answer(plan: CarePlan, message: str, level: str = "standard", last_topic: str | None = None,
           today: date | None = None) -> Answer:
    message = (message or "")[:MAX_MESSAGE]
    level = level if level in LEVEL_ORDER else "standard"
    ans = Answer(level=level)
    msg = text.normalize(message)

    s = safety.screen(message)
    if s.level in ("emergency", "crisis"):
        ans.safety = s.to_dict()
        ans.blocks.append(Block("companion", s.message, label="Get help now"))
        warnings = [i for i in plan.items if i.kind == "warning"]
        ans.blocks += _item_blocks(plan, warnings)
        return ans
    if s.level == "refer":
        ans.safety = s.to_dict()
        ans.blocks.append(Block("companion", s.message, label="Please ask your care team"))
        drug_items = _items_for_drug(plan, message)
        ans.blocks += _item_blocks(plan, drug_items)
        ans.blocks += [Block("care_plan", f"{c.role}: {c.contact}", label="Your care team") for c in plan.care_team]
        return ans

    allowed = _plan_topics(plan)

    # "Simpler, please" / "explain again"
    if re.search(r"\b(simpler|simply|more simple|easier|plain(er)? (words|language)|don'?t understand|do not understand|(explain|say) (that|it) again)\b", msg):
        t = knowledge.topic(last_topic) if last_topic else None
        if t:
            new = _simpler(level)
            ans.level, ans.topic = new, t["id"]
            ans.blocks.append(_education(t, new))
            ans.suggestions = [f"What questions should I ask about {t['title']}?", "Can you give me more detail?"]
            return ans

    if re.search(r"\b(more detail|tell me more|in more depth)\b", msg) and last_topic and knowledge.topic(last_topic):
        t = knowledge.topic(last_topic)
        new = LEVEL_ORDER[min(2, LEVEL_ORDER.index(level) + 1)]
        ans.level, ans.topic = new, t["id"]
        ans.blocks.append(_education(t, new))
        return ans

    # Questions to ask
    if re.search(r"\b(what )?(questions?)\b.*\b(ask|bring)\b|\bwhat should i ask\b", msg):
        topics = [knowledge.topic(t) for t in sorted(allowed)]
        t = knowledge.find_topic(message, allowed) or (knowledge.topic(last_topic) if last_topic else None)
        chosen = [t] if t else [x for x in topics if x and x["kind"] == "condition"]
        for x in chosen:
            ans.blocks.append(Block("education", " • ".join(x["questions_to_ask"]),
                                    label=f"Questions you could ask about {x['title']}", ref=x["id"]))
        ans.suggestions = ["When is my next appointment?", "What are my warning signs?"]
        return ans

    # Appointments and follow-up
    if re.search(r"\b(appointment|follow[- ]?up|visit|when do i see|x-?ray|blood test|lab)\b", msg):
        discharge = plan.discharge_date(today)
        items = [i for i in plan.items if i.kind in ("appointment", "test")]
        for i in items:
            when = i.appointment.when(discharge) if i.appointment else None
            date_txt = f" Planned date: {when:%A %B %d}" + (f" at {when:%H:%M}." if i.appointment.time else ".") if when else ""
            ans.blocks.append(Block("care_plan", i.original + date_txt, label=i.title, ref=i.id))
        ans.suggestions = ["Can I set a reminder?", "What should I ask at my visit?"]
        return ans

    # Warning signs
    if re.search(r"\b(warning signs?|when (should|do) i call|call 911|emergency|worry)\b", msg):
        ans.blocks += _item_blocks(plan, [i for i in plan.items if i.kind == "warning"])
        ans.suggestions = ["Explain my diagnosis", "What are my medicines for?"]
        return ans

    # A specific medicine in the plan
    drug_items = _items_for_drug(plan, message)
    if drug_items:
        ans.blocks += _item_blocks(plan, drug_items)
        for i in drug_items:
            t = knowledge.topic(i.education_topic) if i.education_topic else None
            if t:
                ans.blocks.append(_education(t, level))
                ans.topic = t["id"]
        ans.suggestions = ["Can you explain that more simply?", "What questions should I ask my pharmacist?"]
        return ans

    # A topic in this plan, or a glossary term
    t = knowledge.find_topic(message, allowed)
    if t:
        ans.topic = t["id"]
        ans.blocks.append(_education(t, level))
        dx = [d for d in plan.diagnoses if d.education_topic == t["id"]]
        for d in dx:
            ans.blocks.append(Block("care_plan", d.documented_note, label=d.name, ref=d.id))
        ans.suggestions = ["Can you explain that more simply?", "What questions should I ask?"]
        return ans
    g = knowledge.find_term(message)
    if g:
        ans.blocks.append(Block("education", g["definition"], label=f"What “{g['term']}” means", ref=g["term"]))
        ans.suggestions = ["Explain my diagnosis", "What are my warning signs?"]
        return ans

    ans.blocks.append(Block(
        "companion",
        "I don't have information about that in your care plan or in this education library, so I "
        "won't guess. Please ask your care team. You can also try asking about your diagnosis, a "
        "medicine on your list, your appointments or your warning signs.", label="Not covered"))
    ans.suggestions = ["Explain my diagnosis", "What are my medicines for?", "When is my next appointment?"]
    return ans
