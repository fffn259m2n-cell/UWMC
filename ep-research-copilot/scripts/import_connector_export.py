"""Convert PubMed / ClinicalTrials.gov connector exports (JSON) into a snapshot folder.

Use this when records were retrieved through a separate connector (for example
the PubMed and ClinicalTrials.gov MCP connectors) instead of `ep-copilot run`.
Records are copied field by field; nothing is edited or inferred. Fields the
connector does not provide are listed in the snapshot as unavailable.

  python scripts/import_connector_export.py OUT_DIR --window 2026-10-19 2026-10-26 \
      --pubmed-total 26 --articles a.json [b.json ...] --trials t1.json [t2.json ...]

Then:  ep-copilot --db data/ep_copilot_imported.sqlite run --snapshot OUT_DIR
"""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def article(a: dict) -> dict:
    d = a.get("publication_date") or {}
    month = str(d.get("month") or "")
    if month and not month.isdigit():
        month = str(MONTHS.get(month[:3].lower(), ""))
    parts = [str(d.get("year") or ""), month, str(d.get("day") or "") if month else ""]
    pub = "-".join(p.zfill(2) if i else p for i, p in enumerate(parts) if p)
    return {
        "pmid": str(a["identifiers"]["pmid"]),
        "title": a.get("title") or "",
        "abstract": a.get("abstract") or "",
        "authors": [" ".join(x for x in (au.get("fore_name"), au.get("last_name")) if x)
                    for au in a.get("authors") or []],
        "journal": (a.get("journal") or {}).get("title", ""),
        "pub_date": pub,
        "entrez_date": "",
        "doi": a.get("doi") or (a.get("identifiers") or {}).get("doi", "") or "",
        "publication_types": a.get("article_types") or [],
        "mesh_terms": [],
        "keywords": a.get("keywords") or [],
        "language": a.get("language") or "",
    }


def trial(t: dict) -> dict:
    return {
        "nct_id": t["nct_id"],
        "brief_title": t.get("title") or "",
        "overall_status": t.get("status") or "",
        "study_type": t.get("study_type") or "",
        "phases": t.get("phase") or [],
        "conditions": t.get("conditions") or [],
        "interventions": t.get("interventions") or [],
        "enrollment": t.get("enrollment"),
        "sponsor": t.get("sponsor") or "",
        "start_date": t.get("start_date") or "",
        "primary_completion_date": t.get("primary_completion_date") or "",
        "locations_count": t.get("locations_count") or 0,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("out", type=Path)
    p.add_argument("--window", nargs=2, required=True, metavar=("START", "END"))
    p.add_argument("--pubmed-total", type=int)
    p.add_argument("--trials-total", type=int)
    p.add_argument("--articles", nargs="*", type=Path, default=[])
    p.add_argument("--trials", nargs="*", type=Path, default=[])
    p.add_argument("--provenance", default="PubMed and ClinicalTrials.gov connector exports")
    a = p.parse_args()

    arts = {}
    for f in a.articles:
        for rec in json.loads(f.read_text())["articles"]:
            x = article(rec)
            arts.setdefault(x["pmid"], x)
    trials = {}
    for f in a.trials:
        for rec in json.loads(f.read_text())["items"]:
            trials.setdefault(rec["nct_id"], trial(rec))
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "snapshot.json").write_text(json.dumps({
        "synthetic": False,
        "provenance": a.provenance,
        "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "window": {"start": a.window[0], "end": a.window[1]},
        "pubmed_total": a.pubmed_total or len(arts),
        "trials_total": a.trials_total or len(trials),
        "fields_unavailable": {
            "articles": ["entrez_date", "mesh_terms"],
            "trials": ["official_title", "primary_outcomes", "enrollment_type", "completion_date",
                       "first_posted", "last_update_posted", "has_results", "washington_sites"]},
        "articles": list(arts.values()),
        "trials": list(trials.values()),
    }, indent=2, ensure_ascii=False))
    print(f"{len(arts)} articles, {len(trials)} trials -> {a.out / 'snapshot.json'}")


if __name__ == "__main__":
    main()
