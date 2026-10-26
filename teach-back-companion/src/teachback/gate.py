"""Safety gate for AI-generated (or any rewritten) patient text.

Before a drafted discharge summary, patient message or translation reaches a patient,
run every rewritten instruction through the Instruction Fidelity Evaluator. Anything
with a critical or major issue is held for a person to fix; everything else is still
marked "needs clinician review", because an absence of flags is not evidence of safety.

  teachback gate drafts.json [--html report.html]      # exit 1 if anything is held

Input (JSON): {"drafts": [{"id": "msg-1", "plan": "afib-demo", "item": "med-apixaban",
                           "text": "...", "language": "en"}]}
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from .fidelity import evaluate_item
from .plans import load_plans

HELD, REVIEW = "held: fix before sending", "passed automated checks: clinician review still required"


def run(drafts: list[dict]) -> dict:
    plans = load_plans()
    rows = []
    for i, d in enumerate(drafts):
        plan = plans.get(d.get("plan", ""))
        did = str(d.get("id") or i + 1)
        if plan is None or d.get("item") not in {it.id for it in plan.items}:
            rows.append({"id": did, "status": HELD, "issues": [{"severity": "critical", "check": "unknown_item",
                         "message": "Unknown plan or item; nothing to compare against."}]})
            continue
        rep = evaluate_item(plan, plan.item(d["item"]), str(d.get("text", ""))[:4000], d.get("language"))
        blocking = [i.__dict__ for i in rep.issues if i.severity in ("critical", "major")]
        rows.append({"id": did, "plan": plan.id, "item": d["item"], "status": HELD if blocking else REVIEW,
                     "verdict": rep.verdict, "issues": [i.__dict__ for i in rep.issues],
                     "not_assessed": rep.not_assessed, "original": plan.item(d["item"]).original})
    held = sum(r["status"] == HELD for r in rows)
    return {"total": len(rows), "held": held, "passed_checks": len(rows) - held, "rows": rows,
            "note": "Automated checks only. Every draft, held or not, still needs clinician review before use."}


def to_html(result: dict) -> str:
    e = html.escape
    out = ["<!doctype html><meta charset='utf-8'><title>AI draft safety gate</title>",
           "<style>body{font-family:system-ui,sans-serif;max-width:60rem;margin:2rem auto;padding:0 1rem}"
           ".held{color:#b3261e}.ok{color:#1d5e2f}td,th{border-bottom:1px solid #ddd;padding:.4rem;text-align:left;vertical-align:top}"
           "table{border-collapse:collapse;width:100%}</style>",
           "<h1>AI draft safety gate</h1>",
           f"<p><b>{result['held']}</b> of {result['total']} drafts held; {result['passed_checks']} passed the automated checks. "
           f"{e(result['note'])}</p><table><tr><th>Draft</th><th>Status</th><th>Issues</th><th>Documented original</th></tr>"]
    for r in result["rows"]:
        cls = "held" if r["status"] == HELD else "ok"
        issues = "".join(f"<li>{e(i['severity'])}: {e(i['message'])}</li>" for i in r["issues"] if i["severity"] != "minor") or "none flagged"
        out.append(f"<tr><td>{e(r['id'])}</td><td class='{cls}'>{e(r['status'])}</td><td><ul>{issues}</ul></td>"
                   f"<td>{e(r.get('original', ''))}</td></tr>")
    out.append("</table><p>Synthetic demonstration. Not a medical device; not clinically validated.</p>")
    return "\n".join(out)


def run_file(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return run(data["drafts"] if isinstance(data, dict) else data)
