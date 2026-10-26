"""Score the rule-based checks against a labelled evaluation set.

  teachback evaluate-set eval/dev_set.json [--show-misses]

Teach-back: a dangerous explanation is caught if any concern is raised; a correct
one is a false alarm if any concern is raised. Fidelity: a dangerous rewrite is
caught if any critical or major issue is raised; a faithful one is a false alarm
if any is raised. Safety: E needs emergency or crisis, C needs crisis, M needs
referral (or stricter), N must not raise emergency or crisis; A is not scored.

File format (JSON; every section is optional):

  {"teachback": [{"plan": "afib-demo", "item": "med-apixaban", "label": "dangerous" | "correct", "text": "..."}],
   "fidelity":  [{"plan": "hf-demo", "item": "med-furosemide", "label": "dangerous" | "faithful", "text": "...",
                  "language": "en" | "es"}],
   "safety":    [{"context": "chat", "text": "...", "expect": "E" | "C" | "M" | "N" | "A"}]}

Plan and item ids are in src/teachback/data/plans/*.json.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import safety, teachback
from .fidelity import evaluate_item
from .plans import load_plans


def _rate(hit: int, n: int) -> float | None:
    return round(hit / n, 3) if n else None


def score(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    plans = load_plans()
    out: dict = {"set": str(path), "misses": {"teachback": [], "fidelity": [], "safety": []},
                 "false_alarms": {"teachback": [], "fidelity": [], "safety": []}}

    d = c = d_hit = c_fa = 0
    for case in data.get("teachback", []):
        r = teachback.check(plans[case["plan"]], case["item"], case["text"])
        flagged = bool(r.concerns)
        if case["label"] == "dangerous":
            d += 1
            d_hit += flagged
            if not flagged:
                out["misses"]["teachback"].append(case)
        else:
            c += 1
            c_fa += flagged
            if flagged:
                out["false_alarms"]["teachback"].append({**case, "concerns": [x.kind for x in r.concerns]})
    out["teachback"] = {"dangerous": d, "caught": d_hit, "sensitivity": _rate(d_hit, d),
                        "correct": c, "false_alarms": c_fa, "specificity": _rate(c - c_fa, c)}

    d = c = d_hit = c_fa = 0
    for case in data.get("fidelity", []):
        plan = plans[case["plan"]]
        rep = evaluate_item(plan, plan.item(case["item"]), case["text"], case.get("language"))
        flagged = any(i.severity in ("critical", "major") for i in rep.issues)
        if case["label"] == "dangerous":
            d += 1
            d_hit += flagged
            if not flagged:
                out["misses"]["fidelity"].append(case)
        else:
            c += 1
            c_fa += flagged
            if flagged:
                out["false_alarms"]["fidelity"].append({**case, "issues": [i.check for i in rep.issues if i.severity != "minor"]})
    out["fidelity"] = {"dangerous": d, "caught": d_hit, "sensitivity": _rate(d_hit, d),
                       "faithful": c, "false_alarms": c_fa, "specificity": _rate(c - c_fa, c)}

    # Two views of the safety screen. "Strict": the specific patterns stopped and said
    # "call 911 now" / "call or text 988". "With safety net": the patient also counts as
    # reached if the broad net added the 911 / 988 box above the normal answer.
    need = {"E": {"emergency", "crisis"}, "C": {"crisis"}, "M": {"refer", "emergency", "crisis"}}
    counts = {k: [0, 0] for k in ("E", "C", "M", "N")}
    net = {"E": 0, "C": 0, "N_box": 0}
    for case in data.get("safety", []):
        exp = case["expect"]
        if exp == "A":
            continue
        res = safety.screen(case["text"], case.get("context", "chat"))
        level = res.level
        if exp == "E":
            net["E"] += level in need["E"] or bool(res.caution)
        elif exp == "C":
            net["C"] += level == "crisis" or bool(res.caution)   # the box always includes 988
        elif exp == "N":
            net["N_box"] += bool(res.caution)
        counts[exp][0] += 1
        ok = (level not in ("emergency", "crisis")) if exp == "N" else level in need[exp]
        counts[exp][1] += ok
        if not ok:
            (out["false_alarms"] if exp == "N" else out["misses"])["safety"].append({**case, "got": level})
    out["safety"] = {k: {"n": n, "correct": ok, "rate": _rate(ok, n)} for k, (n, ok) in counts.items()}
    out["safety_net"] = {"E_reached": _rate(net["E"], counts["E"][0]), "C_reached": _rate(net["C"], counts["C"][0]),
                         "N_shown_box": _rate(net["N_box"], counts["N"][0])}
    return out
