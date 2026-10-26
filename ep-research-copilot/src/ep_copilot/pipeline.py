"""One monthly run: fetch -> store -> screen -> extract -> track trial changes.

Fetching happens first and completely. Only if every source succeeds are the
results written, in one database transaction.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from . import changes, extraction, screening
from .clinical_trials import TrialsClient
from .config import Topic
from .models import Article, Trial
from .pubmed import PubMedClient
from .storage import Store, dumps

DEFAULT_DAYS = 30
OVERLAP_DAYS = 1  # re-check the last day of the previous window; dedup makes this safe


@dataclass
class FetchResult:
    mode: str                         # live | offline-fixture | imported
    window_start: date
    window_end: date
    articles: list[Article]
    pubmed_total: int
    trials: list[Trial]
    trials_total: int
    trials_truncated: bool
    rechecked_trials: list[Trial] = field(default_factory=list)   # tracked trials not in this search
    missing_trials: list[str] = field(default_factory=list)       # tracked trials no longer found at all
    details: dict = field(default_factory=dict)


@dataclass
class RunResult:
    run_id: int
    topic: Topic
    fetch: FetchResult
    new_pmids: list[str]
    updated_pmids: list[str]
    duplicate_pmids: list[str]
    screenings: dict[str, screening.Screening]
    extractions: dict[str, list[extraction.Extracted]]
    new_trials: list[str]
    trial_changes: list[dict]
    synthetic: bool


def choose_window(store: Store, topic: Topic, days: int | None, today: date) -> tuple[date, date]:
    if days is not None:
        if days < 1:
            raise ValueError("--days must be at least 1")
        return today - timedelta(days=days), today
    last = store.last_successful_run(topic.key)
    if last and last["window_end"]:
        start = date.fromisoformat(last["window_end"]) - timedelta(days=OVERLAP_DAYS)
        return min(start, today), today
    return today - timedelta(days=DEFAULT_DAYS), today


def fetch_live(topic: Topic, start: date, end: date, store: Store,
               pubmed: PubMedClient | None = None, trials: TrialsClient | None = None) -> FetchResult:
    pubmed = pubmed or PubMedClient()
    trials = trials or TrialsClient()
    pmids, total = pubmed.search(topic.pubmed_query, start, end)
    articles = pubmed.fetch(pmids)
    found, ttotal, truncated = trials.search(topic.trial_condition, topic.trial_intervention,
                                             topic.trial_statuses, topic.trial_max_records)
    seen = {t.nct_id for t in found}
    rechecked, missing = [], []
    for nct in store.tracked_trial_ids(topic.key):
        if nct not in seen:
            t = trials.get(nct)
            (rechecked.append(t) if t else missing.append(nct))
    return FetchResult("live", start, end, articles, total, found, ttotal, truncated, rechecked, missing,
                       {"pmids_returned": len(pmids)})


def load_snapshot(folder: Path, mode: str) -> FetchResult:
    """Load pre-captured records (fixtures, or records imported from another retrieval)."""
    folder = Path(folder)
    manifest = json.loads((folder / "snapshot.json").read_text(encoding="utf-8"))
    articles = [Article.from_dict(a) for a in manifest.get("articles", [])]
    trials = [Trial.from_dict(t) for t in manifest.get("trials", [])]
    w = manifest["window"]
    return FetchResult(mode, date.fromisoformat(w["start"]), date.fromisoformat(w["end"]), articles,
                       int(manifest.get("pubmed_total", len(articles))), trials,
                       int(manifest.get("trials_total", len(trials))), bool(manifest.get("trials_truncated")),
                       [Trial.from_dict(t) for t in manifest.get("rechecked_trials", [])],
                       list(manifest.get("missing_trials", [])),
                       {k: manifest[k] for k in ("synthetic", "provenance", "retrieved_at", "fields_unavailable")
                        if k in manifest})


def store_run(store: Store, topic: Topic, fetched: FetchResult, started: str, synthetic: bool) -> RunResult:
    """Write a completed fetch in one transaction and compute what is new or changed."""
    new_pmids, updated, dupes = [], [], []
    screenings, extractions = {}, {}
    new_trials, trial_changes = [], []
    with store.transaction() as db:
        cur = db.execute(
            "INSERT INTO runs (topic, started_at, status, mode, pubmed_query, window_start, window_end,"
            " pubmed_total, pubmed_retrieved, trials_total, trials_retrieved, trials_truncated, details)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (topic.key, started, "running", fetched.mode, topic.pubmed_query,
             fetched.window_start.isoformat(), fetched.window_end.isoformat(), fetched.pubmed_total,
             len(fetched.articles), fetched.trials_total, len(fetched.trials),
             int(fetched.trials_truncated),
             dumps(dict(fetched.details, pmids=[a.pmid for a in fetched.articles],
                        rechecked_trials=[t.nct_id for t in fetched.rechecked_trials],
                        missing_trials=fetched.missing_trials))))
        run_id = cur.lastrowid

        seen = set()
        for a in fetched.articles:
            if not a.pmid.isdigit():
                continue
            if a.pmid in seen:
                dupes.append(a.pmid)
                continue
            seen.add(a.pmid)
            fp = a.fingerprint()
            row = store.article(a.pmid, topic.key)
            if row is None:
                new_pmids.append(a.pmid)
                db.execute("INSERT INTO articles VALUES (?,?,?,?,?,?,?)",
                           (a.pmid, topic.key, dumps(a.to_dict()), fp, run_id, run_id, run_id))
                db.execute("INSERT INTO article_events VALUES (?,?,?,?)", (run_id, topic.key, a.pmid, "new"))
            elif row["fingerprint"] != fp:
                updated.append(a.pmid)
                db.execute("UPDATE articles SET data=?, fingerprint=?, last_seen_run=?, last_changed_run=?"
                           " WHERE pmid=? AND topic=?", (dumps(a.to_dict()), fp, run_id, run_id, a.pmid, topic.key))
                db.execute("INSERT INTO article_events VALUES (?,?,?,?)", (run_id, topic.key, a.pmid, "updated"))
            else:
                db.execute("UPDATE articles SET last_seen_run=? WHERE pmid=? AND topic=?", (run_id, a.pmid, topic.key))
            s = screening.screen(a, topic)
            ex = extraction.extract(a)
            screenings[a.pmid], extractions[a.pmid] = s, ex
            db.execute("INSERT OR REPLACE INTO screenings VALUES (?,?,?,?)",
                       (a.pmid, topic.key, run_id, dumps(s.__dict__)))
            db.execute("INSERT OR REPLACE INTO extractions VALUES (?,?,?,?)",
                       (a.pmid, topic.key, run_id, dumps([e.to_dict() for e in ex])))

        tseen = set()
        for t in fetched.trials + fetched.rechecked_trials:
            if not t.nct_id.startswith("NCT") or t.nct_id in tseen:
                continue
            tseen.add(t.nct_id)
            fp = t.fingerprint()
            row = store.latest_trial(t.nct_id, topic.key)
            if row is None:
                new_trials.append(t.nct_id)
                db.execute("INSERT INTO trials VALUES (?,?,?,?,?,?)",
                           (t.nct_id, topic.key, dumps(t.to_dict()), fp, run_id, run_id))
                db.execute("INSERT INTO trial_snapshots VALUES (?,?,?,?,?)",
                           (t.nct_id, topic.key, run_id, dumps(t.to_dict()), fp))
                continue
            if row["fingerprint"] != fp:
                for d in changes.diff_trials(Trial.from_dict(json.loads(row["data"])), t):
                    d["nct_id"] = t.nct_id
                    trial_changes.append(d)
                    db.execute("INSERT INTO trial_changes VALUES (?,?,?,?,?,?,?)",
                               (run_id, topic.key, t.nct_id, d["field"], dumps(d["old"]), dumps(d["new"]), d["kind"]))
                db.execute("INSERT INTO trial_snapshots VALUES (?,?,?,?,?)",
                           (t.nct_id, topic.key, run_id, dumps(t.to_dict()), fp))
            db.execute("UPDATE trials SET data=?, fingerprint=?, last_seen_run=? WHERE nct_id=? AND topic=?",
                       (dumps(t.to_dict()), fp, run_id, t.nct_id, topic.key))
        for nct in fetched.missing_trials:
            last = db.execute("SELECT field FROM trial_changes WHERE topic=? AND nct_id=? ORDER BY rowid DESC LIMIT 1",
                              (topic.key, nct)).fetchone()
            if last and last["field"] == "record":
                continue  # already reported missing; do not repeat every run
            trial_changes.append({"nct_id": nct, "field": "record", "label": "Registry record",
                                  "old": "tracked", "new": "not returned by ClinicalTrials.gov",
                                  "kind": "substantive"})
            db.execute("INSERT INTO trial_changes VALUES (?,?,?,?,?,?,?)",
                       (run_id, topic.key, nct, "record", dumps("tracked"),
                        dumps("not returned by ClinicalTrials.gov"), "substantive"))

        db.execute("UPDATE runs SET status='success', finished_at=? WHERE id=?",
                   (datetime.now(UTC).isoformat(timespec="seconds"), run_id))
    return RunResult(run_id, topic, fetched, new_pmids, updated, dupes, screenings, extractions,
                     new_trials, trial_changes, synthetic)


def run(store: Store, topic: Topic, *, days: int | None = None, snapshot: Path | None = None,
        mode: str = "live", today: date | None = None, pubmed=None, trials=None) -> RunResult:
    started = datetime.now(UTC).isoformat(timespec="seconds")
    try:
        if snapshot is not None:
            fetched = load_snapshot(snapshot, mode)
        else:
            start, end = choose_window(store, topic, days, today or date.today())
            fetched = fetch_live(topic, start, end, store, pubmed, trials)
    except Exception as exc:
        store.record_failure(topic.key, started, datetime.now(UTC).isoformat(timespec="seconds"),
                             mode, str(exc))
        raise
    synthetic = bool(fetched.details.get("synthetic"))
    store.check_kind(synthetic)
    return store_run(store, topic, fetched, started, synthetic)


def load_result(store: Store, topic: Topic, run_id: int | None = None, rescreen: bool = False) -> RunResult:
    """Rebuild a run's result from the database (for `report` and `screen`).

    With rescreen=True, screening and extraction are recomputed with the current
    configuration and saved, without fetching anything.
    """
    row = store.run(run_id) if run_id else store.last_successful_run(topic.key)
    if row is None or row["status"] != "success":
        raise ValueError(f"No successful run found for topic '{topic.key}'. Run `ep-copilot run` first.")
    run_id = row["id"]
    details = json.loads(row["details"] or "{}")
    articles = []
    for pmid in details.get("pmids", []):
        a = store.article(pmid, topic.key)
        if a:
            articles.append(Article.from_dict(json.loads(a["data"])))
    events = {r["pmid"]: r["event"] for r in store.db.execute(
        "SELECT pmid, event FROM article_events WHERE run_id=? AND topic=?", (run_id, topic.key))}
    screenings, extractions = {}, {}
    if rescreen:
        with store.transaction() as db:
            for a in articles:
                screenings[a.pmid] = screening.screen(a, topic)
                extractions[a.pmid] = extraction.extract(a)
                db.execute("INSERT OR REPLACE INTO screenings VALUES (?,?,?,?)",
                           (a.pmid, topic.key, run_id, dumps(screenings[a.pmid].__dict__)))
                db.execute("INSERT OR REPLACE INTO extractions VALUES (?,?,?,?)",
                           (a.pmid, topic.key, run_id, dumps([e.to_dict() for e in extractions[a.pmid]])))
    else:
        for a in articles:
            srow = store.db.execute("SELECT data FROM screenings WHERE pmid=? AND topic=?",
                                    (a.pmid, topic.key)).fetchone()
            erow = store.db.execute("SELECT data FROM extractions WHERE pmid=? AND topic=?",
                                    (a.pmid, topic.key)).fetchone()
            screenings[a.pmid] = screening.Screening(**json.loads(srow["data"]))
            extractions[a.pmid] = [extraction.Extracted(**e) for e in json.loads(erow["data"])]
    changes_rows = [
        {"nct_id": r["nct_id"], "field": r["field"], "old": json.loads(r["old"]), "new": json.loads(r["new"]),
         "kind": r["kind"],
         "label": {**changes.SUBSTANTIVE, **changes.ADMINISTRATIVE}.get(r["field"], "Registry record")}
        for r in store.db.execute("SELECT * FROM trial_changes WHERE run_id=? AND topic=?", (run_id, topic.key))]
    new_trials = [r["nct_id"] for r in store.db.execute(
        "SELECT nct_id FROM trials WHERE topic=? AND first_seen_run=?", (topic.key, run_id))]
    fetched = FetchResult(row["mode"], date.fromisoformat(row["window_start"]), date.fromisoformat(row["window_end"]),
                          articles, row["pubmed_total"] or 0, [], row["trials_total"] or 0,
                          bool(row["trials_truncated"]), details={k: v for k, v in details.items()
                                                                  if k in ("synthetic", "provenance", "retrieved_at",
                                                                            "fields_unavailable")})
    return RunResult(run_id, topic, fetched, [p for p, e in events.items() if e == "new"],
                     [p for p, e in events.items() if e == "updated"], [], screenings, extractions,
                     new_trials, changes_rows, store.is_synthetic())
