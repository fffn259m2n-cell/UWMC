"""Load and validate the bundled synthetic care plans and education library."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib import resources
from pathlib import Path

from .models import CarePlan

# Text that looks like instructions to an AI system has no place in clinical content.
INJECTION = re.compile(
    r"ignore (?:all |any |the )?(?:previous|prior|above) instructions|disregard (?:the )?(?:system|previous)"
    r"|you are now|system prompt|act as (?:a|an) |<\s*/?\s*(?:script|system)\b", re.I)


class ContentError(ValueError):
    pass


def check_content(where: str, *texts: str) -> None:
    for t in texts:
        if t and INJECTION.search(t):
            raise ContentError(f"{where}: text looks like an embedded instruction to an AI system; refusing to load.")


def _plan_texts(plan: CarePlan):
    yield plan.notice
    for d in plan.diagnoses:
        yield d.documented_note
    for i in plan.items:
        yield i.original
        yield i.plain
        for f in i.facts:
            yield f.statement
            for m in f.misconceptions:
                yield m.message


def load_plan_file(path: Path) -> CarePlan:
    plan = CarePlan(**json.loads(Path(path).read_text(encoding="utf-8")))
    if not plan.synthetic:
        raise ContentError(f"{path}: only plans marked synthetic may be loaded in this prototype.")
    check_content(str(path), *_plan_texts(plan))
    for i in plan.items:
        for f in i.facts:
            for m in f.misconceptions:
                try:
                    re.compile(m.pattern)
                except re.error as exc:
                    raise ContentError(f"{path}: bad misconception pattern {m.id}: {exc}") from exc
    return plan


@lru_cache(maxsize=1)
def load_plans() -> dict[str, CarePlan]:
    folder = resources.files("teachback").joinpath("data/plans")
    plans = {}
    for entry in sorted(folder.iterdir(), key=lambda e: e.name):
        if entry.name.endswith(".json"):
            p = load_plan_file(Path(str(entry)))
            plans[p.id] = p
    return plans
