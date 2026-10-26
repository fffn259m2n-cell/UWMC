"""Misunderstanding insights: which instructions patients misread, and how.

Runs teach-back checks over a batch of explanations and summarises, per instruction,
how often a concern was raised and which kinds of concern were most common. Each
instruction is mapped to the HCAHPS domain it most affects, so a quality team can read
"discharge information scores are low" next to "patients misread these instructions".

  teachback insights attempts.json [--csv insights.csv] [--html insights.html]

Input (JSON): {"attempts": [{"plan": "hf-demo", "item": "med-furosemide", "text": "...",
                             "language": "en", "caregiver": false}]}

No explanation text is written to the outputs, only counts. The bundled
data/insights/synthetic_cohort.json is made from reviewer-written test cases, so it
over-represents mistakes on purpose; its rates say nothing about real patients.
"""

from __future__ import annotations

import csv
import html
import json
from collections import Counter, defaultdict
from importlib import resources
from pathlib import Path

from . import teachback
from .plans import load_plans

# HCAHPS domain each kind of discharge instruction most affects (labels match the
# Quality Signal Monitor's domains).
HCAHPS_DOMAIN = {
    "medication": ("medicines", "Communication about medicines"),
    "warning": ("symptoms", "Information about symptoms"),
    "instruction": ("discharge_information", "Discharge information"),
    "appointment": ("care_coordination", "Care coordination"),
    "test": ("care_coordination", "Care coordination"),
}
CHECK_LABELS = {
    "do_not_lost": "“do not” instruction restated without the “not”",
    "meaning_reversed": "required point stated the opposite way",
    "stop_or_skip": "stopping or skipping a medicine",
    "stop_condition_added": "a reason or time to stop that the plan does not give",
    "dose_added": "an extra or doubled dose",
    "doses_combined": "doses taken together",
    "number_changed": "a different number (dose, threshold, days)",
    "number_mismatch": "a different number (dose, threshold, days)",
    "tablet_count_changed": "a different number of tablets",
    "frequency_changed": "a different schedule",
    "time_of_day_changed": "a different time of day",
    "food_changed": "the food rule changed",
    "limit_direction": "a limit read the wrong way",
    "limit_loosened": "a limit treated as open-ended",
    "limit_reversed": "fluids restricted instead of encouraged",
    "period_changed": "a limit applied to the wrong period",
    "direction_changed": "weight change read the wrong way",
    "or_changed_to_and": "“or” read as “and”",
    "warning_normalised": "a warning sign treated as normal",
    "action_delayed": "waiting before calling",
    "instruction_dropped": "a visit or test treated as optional",
    "emergency_sign_not_with_911": "an emergency sign without calling 911",
    "alternative_to_911": "another option instead of 911",
    "medicine_not_in_instruction": "a medicine the instruction does not mention",
    "strength_swapped": "strengths swapped",
}


def label(check: str) -> str:
    if check.startswith("misconception:"):
        return "known misunderstanding: " + check.split(":", 1)[1].replace("-", " ")
    return CHECK_LABELS.get(check, check.replace("_", " "))


def bundled_cohort() -> list[dict]:
    path = resources.files("teachback").joinpath("data/insights/synthetic_cohort.json")
    return json.loads(path.read_text(encoding="utf-8"))["attempts"]


def run(attempts: list[dict]) -> dict:
    plans = load_plans()
    per_item: dict[tuple[str, str], dict] = {}
    checks: dict[tuple[str, str], Counter] = defaultdict(Counter)
    by_language: Counter = Counter()
    flagged_language: Counter = Counter()
    for a in attempts:
        plan = plans.get(a.get("plan", ""))
        if plan is None or a.get("item") not in {i.id for i in plan.items}:
            continue
        item = plan.item(a["item"])
        key = (plan.id, item.id)
        row = per_item.setdefault(key, {"plan": plan.id, "item": item.id, "title": item.title, "kind": item.kind,
                                        "hcahps_domain": HCAHPS_DOMAIN[item.kind][0],
                                        "hcahps_label": HCAHPS_DOMAIN[item.kind][1], "attempts": 0, "flagged": 0})
        r = teachback.check(plan, item.id, a.get("text", ""))
        row["attempts"] += 1
        lang = a.get("language", "en")
        by_language[lang] += 1
        if r.concerns:
            row["flagged"] += 1
            flagged_language[lang] += 1
            for c in {c.check or c.kind for c in r.concerns}:
                checks[key][c] += 1
    rows = []
    for key, row in per_item.items():
        row["flagged_rate"] = round(row["flagged"] / row["attempts"], 3) if row["attempts"] else 0.0
        row["top_concerns"] = [{"check": c, "label": label(c), "count": n} for c, n in checks[key].most_common(3)]
        rows.append(row)
    rows.sort(key=lambda r: (-r["flagged_rate"], -r["flagged"]))
    domains: dict[str, dict] = {}
    for r in rows:
        d = domains.setdefault(r["hcahps_domain"], {"domain": r["hcahps_domain"], "label": r["hcahps_label"],
                                                   "attempts": 0, "flagged": 0, "items": []})
        d["attempts"] += r["attempts"]
        d["flagged"] += r["flagged"]
        d["items"].append(r["title"])
    for d in domains.values():
        d["flagged_rate"] = round(d["flagged"] / d["attempts"], 3) if d["attempts"] else 0.0
    return {"attempts": sum(r["attempts"] for r in rows), "items": rows,
            "domains": sorted(domains.values(), key=lambda d: -d["flagged_rate"]),
            "languages": {k: {"attempts": v, "flagged": flagged_language[k]} for k, v in by_language.items()},
            "note": "Counts from automated checks, not a measure of real understanding. No explanation text is kept."}


def write_csv(result: dict, path: Path, synthetic: bool = True) -> None:
    """One row per instruction; the Quality Signal Monitor reads this file (--teachback-insights)."""
    with Path(path).open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["plan", "item", "title", "hcahps_domain", "hcahps_label", "attempts", "flagged",
                    "flagged_rate", "top_concern_1", "top_concern_2", "top_concern_3", "synthetic"])
        for r in result["items"]:
            tops = [f"{t['label']} ({t['count']})" for t in r["top_concerns"]] + ["", "", ""]
            w.writerow([r["plan"], r["item"], r["title"], r["hcahps_domain"], r["hcahps_label"], r["attempts"],
                        r["flagged"], r["flagged_rate"], *tops[:3], "yes" if synthetic else "no"])


def to_html(result: dict, synthetic: bool = True) -> str:
    e = html.escape
    banner = ("<p style='background:#fdecea;color:#b3261e;padding:.6rem;border-radius:8px'><b>SYNTHETIC DATA.</b> "
              "Made from reviewer-written test cases that over-represent mistakes. Not real patients.</p>") if synthetic else ""
    out = ["<!doctype html><meta charset='utf-8'><title>Teach-back insights</title>",
           "<style>body{font-family:system-ui,sans-serif;max-width:62rem;margin:2rem auto;padding:0 1rem}"
           "td,th{border-bottom:1px solid #ddd;padding:.4rem;text-align:left;vertical-align:top}table{border-collapse:collapse;width:100%}"
           ".bar{background:#b3261e;height:.6rem;border-radius:3px}</style>",
           "<h1>Which instructions are misunderstood, and how</h1>", banner,
           f"<p>{result['attempts']} teach-back explanations checked. {e(result['note'])}</p>",
           "<h2>By HCAHPS domain</h2><table><tr><th>Domain</th><th>Explanations flagged</th><th>Instructions</th></tr>"]
    for d in result["domains"]:
        out.append(f"<tr><td>{e(d['label'])}</td><td>{d['flagged']} of {d['attempts']} ({d['flagged_rate']:.0%})</td>"
                   f"<td>{e('; '.join(d['items']))}</td></tr>")
    out.append("</table><h2>By instruction (most often flagged first)</h2><table><tr><th>Instruction</th><th>Flagged</th>"
               "<th></th><th>Most common concerns</th><th>HCAHPS domain</th></tr>")
    for r in result["items"]:
        tops = "".join(f"<li>{e(t['label'])} ({t['count']})</li>" for t in r["top_concerns"]) or "none"
        out.append(f"<tr><td>{e(r['title'])}<br><small>{e(r['plan'])}</small></td><td>{r['flagged']} / {r['attempts']}</td>"
                   f"<td style='width:8rem'><div class='bar' style='width:{int(r['flagged_rate'] * 100)}%'></div></td>"
                   f"<td><ul>{tops}</ul></td><td>{e(r['hcahps_label'])}</td></tr>")
    out.append("</table><p>Use: rewrite the instructions at the top first, then check whether teach-back concerns fall. "
               "Independent prototype; not affiliated with or endorsed by UW Medicine.</p>")
    return "\n".join(out)
