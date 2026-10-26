"""Digest HTML and machine-readable outputs for one run."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from . import __version__, extraction
from .review import PRIORITY_ORDER, QUEUE_COLUMNS
from .storage import Store

DISCLAIMER = ("This tool supports research surveillance and literature organization. It does not "
              "perform a systematic review, provide medical advice, or establish clinical practice "
              "recommendations.")


def _write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("; ".join(map(str, r[k])) if isinstance(r.get(k), list)
                            else ("" if r.get(k) is None else r[k])) for k in columns})


def build_rows(result, store: Store) -> dict:
    topic = result.topic.key
    reviews = store.reviews(topic)
    new = set(result.new_pmids)
    updated = set(result.updated_pmids)
    articles, queue, extraction_rows, evidence_rows = [], [], [], []
    seen = set()
    for a in result.fetch.articles:
        if a.pmid not in result.screenings or a.pmid in seen:
            continue
        seen.add(a.pmid)
        s = result.screenings[a.pmid]
        ex = result.extractions.get(a.pmid, [])
        status = "new" if a.pmid in new else "updated" if a.pmid in updated else "seen before"
        rv = reviews.get(a.pmid, {})
        row = {"pmid": a.pmid, "title": a.title, "journal": a.journal, "pub_date": a.pub_date,
               "entrez_date": a.entrez_date, "doi": a.doi, "url": a.url, "doi_url": a.doi_url,
               "first_author": a.authors[0] if a.authors else "", "status": status,
               "scope": s.scope, "categories": s.categories, "study_design": s.study_design,
               "priority": s.priority, "uncertain": s.uncertain, "has_abstract": bool(a.abstract),
               "publication_types": a.publication_types, "reasons": s.reasons,
               "matched_terms": "; ".join(f"{k}: {', '.join(v)}" for k, v in s.matched_terms.items()),
               "extraction": extraction.summary_row(a, ex), "evidence": [e.to_dict() for e in ex],
               "reviewer_decision": rv.get("reviewer_decision", "")}
        articles.append(row)
        queue.append({"source_id": a.pmid, "title": a.title, "url": a.url, "topic": topic,
                      "suggested_priority": s.priority, "scope": s.scope, "categories": s.categories,
                      "study_design": s.study_design, "classification_reason": " | ".join(s.reasons),
                      "reviewer_decision": rv.get("reviewer_decision", ""),
                      "reviewer_notes": rv.get("reviewer_notes", "")})
        extraction_rows.append(row["extraction"])
        evidence_rows.extend(e.to_dict() for e in ex)
    key = lambda r: (PRIORITY_ORDER.get(r["priority"], 9), r["status"] != "new", r["pmid"])  # noqa: E731
    articles.sort(key=key)
    queue.sort(key=lambda r: (PRIORITY_ORDER.get(r["suggested_priority"], 9), r["source_id"]))

    trials = store.all_trials(topic)
    new_trials = set(result.new_trials)
    changed = {}
    for c in result.trial_changes:
        changed.setdefault(c["nct_id"], []).append(c)
    for t in trials:
        t["url"] = f"https://clinicaltrials.gov/study/{t['nct_id']}"
        missing = any(c["field"] == "record" for c in changed.get(t["nct_id"], []))
        t["status_this_run"] = ("not returned by registry" if missing else
                                "new" if t["nct_id"] in new_trials else
                                "changed" if t["nct_id"] in changed else "unchanged")
        t["changes"] = changed.get(t["nct_id"], [])
        t["substantive_change"] = any(c["kind"] == "substantive" for c in t["changes"])
    trials.sort(key=lambda t: ({"changed": 0, "not returned by registry": 0, "new": 1}.get(t["status_this_run"], 2),
                               not t["substantive_change"], t["nct_id"]))
    # Trials mentioned in abstracts, linked to the registry view.
    mentions = {}
    for e in evidence_rows:
        if e["field"] == "trial_registration":
            mentions.setdefault(e["value"], []).append(e["pmid"])
    return {"articles": articles, "queue": queue, "extraction": extraction_rows,
            "evidence": evidence_rows, "trials": trials, "changes": result.trial_changes,
            "trial_mentions": mentions}


def write_outputs(result, store: Store, out_dir: Path) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = build_rows(result, store)
    paths = {k: out / v for k, v in {
        "digest": "ep_research_digest.html", "articles": "articles.csv",
        "extractions": "evidence_extraction.csv", "evidence": "evidence_quotes.csv",
        "trials": "trials.csv", "trial_changes": "trial_changes.csv",
        "review_queue": "review_queue.csv", "changes": "changes.json", "metadata": "run_metadata.json",
    }.items()}

    _write_csv(paths["articles"], rows["articles"],
               ["pmid", "title", "journal", "pub_date", "entrez_date", "doi", "url", "status", "scope",
                "priority", "categories", "study_design", "publication_types", "has_abstract",
                "matched_terms", "reviewer_decision"])
    _write_csv(paths["extractions"], rows["extraction"],
               ["pmid", "title", "url", "evidence_source", *extraction.FIELDS, "notes"])
    _write_csv(paths["evidence"], rows["evidence"],
               ["pmid", "field", "value", "evidence", "method", "source", "note",
                "reviewer_correct", "reviewer_notes"])
    _write_csv(paths["trials"], rows["trials"],
               ["nct_id", "brief_title", "overall_status", "study_type", "phases", "enrollment",
                "enrollment_type", "interventions", "primary_outcomes", "sponsor", "start_date",
                "primary_completion_date", "last_update_posted", "has_results", "washington_sites",
                "status_this_run", "url"])
    _write_csv(paths["trial_changes"],
               [dict(c, old=json.dumps(c["old"]), new=json.dumps(c["new"])) for c in rows["changes"]],
               ["nct_id", "kind", "label", "field", "old", "new"])
    _write_csv(paths["review_queue"], rows["queue"], QUEUE_COLUMNS)

    run = store.run(result.run_id)
    n_articles = run["pubmed_retrieved"] if run and run["pubmed_retrieved"] is not None else len(result.fetch.articles)
    n_trials = run["trials_retrieved"] if run and run["trials_retrieved"] is not None else len(result.fetch.trials)
    meta = {
        "tool": "ep-research-copilot", "version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "synthetic_data": result.synthetic, "mode": result.fetch.mode,
        "provenance": result.fetch.details.get("provenance", "direct API retrieval"),
        "fields_unavailable": result.fetch.details.get("fields_unavailable", {}),
        "run_id": result.run_id, "topic": result.topic.key,
        "pubmed": {"query": result.topic.pubmed_query, "date_field": "Entrez date (EDAT)",
                   "window_start": result.fetch.window_start.isoformat(),
                   "window_end": result.fetch.window_end.isoformat(),
                   "total_reported": result.fetch.pubmed_total, "retrieved": n_articles,
                   "unique_retrieved": len({a.pmid for a in result.fetch.articles}),
                   "endpoint": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"},
        "clinicaltrials": {"condition": result.topic.trial_condition,
                           "intervention": result.topic.trial_intervention,
                           "statuses": result.topic.trial_statuses,
                           "total_reported": result.fetch.trials_total,
                           "retrieved": n_trials, "truncated": result.fetch.trials_truncated,
                           "endpoint": "https://clinicaltrials.gov/api/v2/studies"},
        "run": dict(run) if run else {},
        "counts": {"new_articles": len(result.new_pmids), "updated_articles": len(result.updated_pmids),
                   "duplicate_pmids_in_fetch": result.duplicate_pmids,
                   "new_trials": len(result.new_trials),
                   "trials_with_changes": len({c["nct_id"] for c in result.trial_changes})},
    }
    paths["metadata"].write_text(json.dumps(meta, indent=2, default=str))
    paths["changes"].write_text(json.dumps({
        "run_id": result.run_id, "new_pmids": result.new_pmids, "updated_pmids": result.updated_pmids,
        "new_trials": result.new_trials, "trial_changes": rows["changes"]}, indent=2, default=str))

    env = Environment(loader=PackageLoader("ep_copilot", "templates"), autoescape=select_autoescape())
    html = env.get_template("digest.html.j2").render(
        meta=meta, topic=result.topic, rows=rows, disclaimer=DISCLAIMER, fields=extraction.FIELDS,
        first_run=store.db.execute("SELECT COUNT(*) FROM runs WHERE topic=? AND status='success'",
                                   (result.topic.key,)).fetchone()[0] == 1)
    paths["digest"].write_text(html, encoding="utf-8")
    return paths
