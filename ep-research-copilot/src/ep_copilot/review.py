"""Human review queue and screening-performance evaluation.

Reviewer decisions live in their own table and CSV columns. They are never
overwritten by automated screening. Precision and recall are computed only
from decisions a person actually recorded.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from .storage import Store

QUEUE_COLUMNS = ["source_id", "title", "url", "topic", "suggested_priority", "scope", "categories",
                 "study_design", "classification_reason", "reviewer_decision", "reviewer_notes"]
DECISIONS = {"include", "exclude", "unsure"}
PRIORITY_ORDER = {"high": 0, "review": 1, "medium": 2, "low": 3}


def import_decisions(store: Store, topic: str, path: Path) -> tuple[int, list[str]]:
    """Load reviewer_decision/reviewer_notes from a filled-in review_queue.csv."""
    problems, n = [], 0
    with Path(path).open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with store.transaction() as db:
        for i, r in enumerate(rows, start=2):
            decision = (r.get("reviewer_decision") or "").strip().lower()
            if not decision:
                continue
            if decision not in DECISIONS:
                problems.append(f"line {i}: '{decision}' is not one of {sorted(DECISIONS)}")
                continue
            db.execute("INSERT OR REPLACE INTO reviews VALUES (?,?,?,?,?)",
                       (r["source_id"], topic, decision, r.get("reviewer_notes", ""), now))
            n += 1
    return n, problems


def evaluate(store: Store, topic: str) -> dict:
    """Compare automated in-scope labels with reviewer include/exclude decisions."""
    import json
    reviews = store.reviews(topic)
    auto = {r["pmid"]: json.loads(r["data"])["scope"] == "in_scope"
            for r in store.db.execute("SELECT pmid, data FROM screenings WHERE topic=?", (topic,))}
    tp = fp = fn = tn = 0
    fps, fns = [], []
    for sid, rv in reviews.items():
        if rv["reviewer_decision"] == "unsure" or sid not in auto:
            continue
        truth, pred = rv["reviewer_decision"] == "include", auto[sid]
        if truth and pred:
            tp += 1
        elif pred and not truth:
            fp += 1
            fps.append(sid)
        elif truth and not pred:
            fn += 1
            fns.append(sid)
        else:
            tn += 1
    labelled = tp + fp + fn + tn
    return {
        "labelled_records": labelled,
        "true_positives": tp, "false_positives": fp, "false_negatives": fn, "true_negatives": tn,
        "precision": round(tp / (tp + fp), 3) if tp + fp else None,
        "recall": round(tp / (tp + fn), 3) if tp + fn else None,
        "false_positive_pmids": fps, "false_negative_pmids": fns,
        "note": ("No reviewer decisions recorded yet; screening accuracy is unmeasured."
                 if not labelled else "Computed from human reviewer decisions only."),
    }


def extraction_accuracy(path: Path) -> dict:
    """Per-field accuracy from a filled-in evidence_quotes.csv (reviewer_correct = yes/no)."""
    per_field: dict[str, dict[str, int]] = {}
    with Path(path).open(newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            v = (r.get("reviewer_correct") or "").strip().lower()
            if v not in ("yes", "no"):
                continue
            f = per_field.setdefault(r["field"], {"correct": 0, "incorrect": 0})
            f["correct" if v == "yes" else "incorrect"] += 1
    for f in per_field.values():
        f["accuracy"] = round(f["correct"] / (f["correct"] + f["incorrect"]), 3)
    total = sum(f["correct"] + f["incorrect"] for f in per_field.values())
    return {"reviewed_items": total, "by_field": per_field,
            "note": "No reviewed items yet." if not total else "Computed from human reviewer judgments only."}
