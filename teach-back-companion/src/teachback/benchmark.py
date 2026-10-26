"""Run the fidelity evaluator against the synthetic benchmark and report detection performance.

For each case with expected checks, a detection counts when every expected
check is reported. For clean cases, any critical or major issue is a false alarm.
These numbers describe the evaluator on synthetic perturbations only.
"""

from __future__ import annotations

import json
from importlib import resources

from .fidelity import evaluate_item
from .plans import load_plans


def load_cases() -> list[dict]:
    return json.loads(resources.files("teachback").joinpath("data/benchmark/cases.json").read_text(encoding="utf-8"))["cases"]


def run(cases: list[dict] | None = None) -> dict:
    plans = load_plans()
    rows = []
    for c in cases or load_cases():
        plan = plans[c["plan"]]
        rep = evaluate_item(plan, plan.item(c["item"]), c["candidate"], c.get("language"))
        found = {i.check for i in rep.issues if i.severity in ("critical", "major")}
        expected = set(c["expect"])
        if expected:
            outcome = "detected" if expected <= found else "missed"
        else:
            outcome = "false_alarm" if found else "clean_ok"
        rows.append({"id": c["id"], "expected": sorted(expected), "found": sorted(found), "outcome": outcome,
                     "verdict": rep.verdict})
    seeded = [r for r in rows if r["expected"]]
    clean = [r for r in rows if not r["expected"]]
    return {
        "cases": len(rows),
        "seeded_errors": len(seeded),
        "detected": sum(r["outcome"] == "detected" for r in seeded),
        "clean_cases": len(clean),
        "false_alarms": sum(r["outcome"] == "false_alarm" for r in clean),
        "rows": rows,
        "note": "Synthetic perturbations of synthetic plans; not evidence of real-world accuracy.",
    }
