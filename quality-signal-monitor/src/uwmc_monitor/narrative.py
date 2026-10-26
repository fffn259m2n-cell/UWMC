"""Plain-English narrative: deterministic templates by default, optional LLM adapter.

The LLM path is disabled unless a caller supplies a completion function. It
receives only the aggregate facts built by `build_facts` (published hospital-level
percentages, never patient data), and its output is checked so that every number
and measure ID it mentions appears in those facts. All narrative is a draft for
human review.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Protocol

from .signals import HIGHER


def fmt_pp(x: float) -> str:
    """Signed percentage-point text; zero is shown without a sign."""
    if x == 0:
        return "0"
    return f"{x:+.0f}" if float(x).is_integer() else f"{x:+.1f}"


def build_facts(result) -> dict:
    """Aggregate, verified facts that any narrative may draw on."""
    comp = result.comparison
    comparable = comp[comp["comparable"]] if not comp.empty else comp
    top_box = (comparable[(comparable["direction"] == HIGHER) & ~comparable["retired_measure"]]
               if not comp.empty else comp)
    facts = {
        "facility_id": result.current.hospital.get("facility_id"),
        "facility_name": result.current.hospital.get("facility_name"),
        "release": result.current.label,
        "synthetic_data": bool(result.current.provenance.get("synthetic")),
        "measures_total": int(len(comp)),
        "measures_comparable": int(len(comparable)),
        "measures_not_comparable": int(len(comp) - len(comparable)),
        "top_box_above_national": int((top_box["gap_pp"] > 0).sum()) if len(top_box) else 0,
        "top_box_below_national": int((top_box["gap_pp"] < 0).sum()) if len(top_box) else 0,
        "focus_measures": [
            {
                "measure_id": r.hcahps_measure_id,
                "domain": r.domain,
                "answer": r.hcahps_answer_description,
                "uwmc_percent": None if r.uwmc_percent != r.uwmc_percent else float(r.uwmc_percent),
                "national_percent": None if r.national_percent != r.national_percent else float(r.national_percent),
                "gap_pp": None if r.gap_pp != r.gap_pp else float(r.gap_pp),
                "comparable": bool(r.comparable),
                "retired": bool(r.retired_measure),
            }
            for r in comp.itertuples() if r.focus_domain and r.direction == HIGHER
        ] if not comp.empty else [],
        "signals": [
            {
                "measure_id": s.hcahps_measure_id,
                "question": s.hcahps_question,
                "answer": s.hcahps_answer_description,
                "uwmc_percent": float(s.uwmc_percent),
                "national_percent": float(s.national_percent),
                "gap_pp": float(s.gap_pp),
                "gap_band": s.gap_band,
                "within_rounding": bool(s.within_rounding),
                "confidence": s.confidence,
                "persistence": s.persistence,
                "reporting_window": f"{s.start_date} to {s.end_date}",
            }
            for s in result.signals.head(5).itertuples()
        ],
        "data_quality": {
            sev: int(sum(1 for f in result.findings if f.severity == sev))
            for sev in ("failure", "anomaly", "info")
        },
    }
    return facts


class Narrator(Protocol):
    def summarize(self, facts: dict) -> dict:
        """Return {'paragraphs': [...], 'method': str, 'review_required': bool, 'problems': [...]}."""


class TemplateNarrator:
    """Rule-based narrative. Every sentence is filled from `facts`; nothing is inferred."""

    method = "deterministic template"

    def summarize(self, facts: dict) -> dict:
        p = []
        if facts["measures_comparable"] == 0:
            p.append(
                f"No patient-experience measure for facility {facts['facility_id']} could be "
                "matched to a national benchmark covering the same reporting period and response "
                "category. This report is therefore limited to data availability and quality.")
            return self._wrap(p)
        p.append(
            f"Of {facts['measures_total']} HCAHPS rows published for facility {facts['facility_id']} "
            f"in release {facts['release']}, {facts['measures_comparable']} could be compared with a "
            f"matched national value. Among the favorable-response (top-box) measures, "
            f"{facts['top_box_above_national']} are above and {facts['top_box_below_national']} are "
            "below the national figure.")
        focus = [f for f in facts["focus_measures"] if f["comparable"] and not f["retired"]]
        if focus:
            parts = [f"{f['measure_id']} ({f['domain'].lower()}) {f['uwmc_percent']:.0f}% vs "
                     f"{f['national_percent']:.0f}% ({fmt_pp(f['gap_pp'])} pp)" for f in focus]
            p.append("Discharge and care-transition focus, favorable responses: " + "; ".join(parts) + ".")
        else:
            p.append("No current discharge or care-transition measure could be compared with a "
                     "matched national value in this release.")
        for s in facts["signals"][:3]:
            side = "above" if s["gap_pp"] > 0 else "below" if s["gap_pp"] < 0 else "equal to"
            caveat = (" This difference is within whole-number rounding and may not be a real gap."
                      if s["within_rounding"] else "")
            conf = ("" if s["confidence"] == "standard"
                    else f" CMS footnotes or survey counts put this result at '{s['confidence']}' confidence.")
            trend = ("" if s["persistence"] == "no comparable prior release"
                     else f" Since the prior release: {s['persistence']}.")
            p.append(
                f"{s['measure_id']} ({s['answer'] or s['question']}): {s['uwmc_percent']:.0f}% vs "
                f"{s['national_percent']:.0f}% nationally, {fmt_pp(s['gap_pp'])} percentage points "
                f"({side} national; {s['gap_band']} descriptive gap) for {s['reporting_window']}."
                f"{caveat}{conf}{trend}")
        p.append(
            "These are descriptive differences in publicly reported, adjusted survey percentages. "
            "They are not tests of statistical significance and do not by themselves indicate "
            "causes or the quality of care for any individual patient.")
        return self._wrap(p)

    def _wrap(self, paragraphs: list[str]) -> dict:
        return {"paragraphs": paragraphs, "method": self.method,
                "review_required": True, "problems": []}


LLM_INSTRUCTIONS = """You are drafting a short summary of publicly reported hospital patient-survey
results for a hospital quality-improvement team. Use ONLY the JSON facts provided.
Rules:
- Do not introduce any number, measure, or claim that is not in the facts.
- Cite the exact CMS measure ID for every result you mention.
- Describe observed differences first. If you mention possible explanations, label them
  clearly as hypotheses to verify, never as findings.
- Note limitations: descriptive gaps only, no significance testing, rounding, footnotes.
- Do not give clinical advice or recommend interventions.
- Write 3 short paragraphs of plain English.
Facts:
"""


def verify_narrative(text: str, facts: dict) -> list[str]:
    """Return problems: numbers or measure IDs in `text` that do not appear in `facts`."""
    blob = json.dumps(facts)
    known_ids = set(re.findall(r"H_[A-Z0-9_]+", blob))
    problems = [f"Unknown measure ID: {m}" for m in sorted(set(re.findall(r"H_[A-Z0-9_]+", text)) - known_ids)]
    stripped = re.sub(r"H_[A-Z0-9_]+", " ", text)
    known_numbers = {float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", blob)}
    known_numbers |= {abs(n) for n in known_numbers}
    for n in re.findall(r"\d+(?:\.\d+)?", stripped):
        if float(n) not in known_numbers:
            problems.append(f"Number not in verified facts: {n}")
    return problems


class LLMNarrator:
    """Adapter for any text-completion function: `complete(prompt: str) -> str`.

    No provider SDK is bundled. Output that fails `verify_narrative` is replaced
    by the template narrative, and the problems are reported.
    """

    method = "LLM draft (verified against facts)"

    def __init__(self, complete: Callable[[str], str], fallback: Narrator | None = None):
        self.complete = complete
        self.fallback = fallback or TemplateNarrator()

    def summarize(self, facts: dict) -> dict:
        text = self.complete(LLM_INSTRUCTIONS + json.dumps(facts, indent=2))
        problems = verify_narrative(text, facts)
        if problems:
            out = self.fallback.summarize(facts)
            out["problems"] = problems
            out["method"] += " (LLM draft rejected by fact check)"
            return out
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        return {"paragraphs": paragraphs, "method": self.method, "review_required": True,
                "problems": []}
