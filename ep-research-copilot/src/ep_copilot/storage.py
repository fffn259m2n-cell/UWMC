"""Local SQLite store: articles, trial snapshots, screening, extraction, reviewer decisions.

Writes for a run happen in one transaction after all fetching has succeeded,
so a failed or partial fetch never overwrites the previous good data.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, topic TEXT, started_at TEXT, finished_at TEXT,
    status TEXT, mode TEXT, pubmed_query TEXT, window_start TEXT, window_end TEXT,
    pubmed_total INTEGER, pubmed_retrieved INTEGER, trials_total INTEGER,
    trials_retrieved INTEGER, trials_truncated INTEGER, error TEXT, details TEXT);
CREATE TABLE IF NOT EXISTS articles (
    pmid TEXT, topic TEXT, data TEXT, fingerprint TEXT,
    first_seen_run INTEGER, last_seen_run INTEGER, last_changed_run INTEGER,
    PRIMARY KEY (pmid, topic));
CREATE TABLE IF NOT EXISTS article_events (run_id INTEGER, topic TEXT, pmid TEXT, event TEXT);
CREATE TABLE IF NOT EXISTS screenings (pmid TEXT, topic TEXT, run_id INTEGER, data TEXT,
    PRIMARY KEY (pmid, topic));
CREATE TABLE IF NOT EXISTS extractions (pmid TEXT, topic TEXT, run_id INTEGER, data TEXT,
    PRIMARY KEY (pmid, topic));
CREATE TABLE IF NOT EXISTS trials (
    nct_id TEXT, topic TEXT, data TEXT, fingerprint TEXT,
    first_seen_run INTEGER, last_seen_run INTEGER, PRIMARY KEY (nct_id, topic));
CREATE TABLE IF NOT EXISTS trial_snapshots (nct_id TEXT, topic TEXT, run_id INTEGER,
    data TEXT, fingerprint TEXT);
CREATE TABLE IF NOT EXISTS trial_changes (run_id INTEGER, topic TEXT, nct_id TEXT,
    field TEXT, old TEXT, new TEXT, kind TEXT);
CREATE TABLE IF NOT EXISTS reviews (source_id TEXT, topic TEXT, reviewer_decision TEXT,
    reviewer_notes TEXT, imported_at TEXT, PRIMARY KEY (source_id, topic));
"""


class StoreError(RuntimeError):
    pass


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.db = sqlite3.connect(self.path, isolation_level=None)  # explicit BEGIN/COMMIT
            self.db.row_factory = sqlite3.Row
            self.db.executescript(SCHEMA)
            self.db.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.DatabaseError as exc:
            raise StoreError(f"Database {self.path} is unreadable or corrupt ({exc}). "
                             "Move it aside and re-run; a fresh baseline will be built.") from exc

    def close(self) -> None:
        self.db.close()

    @contextmanager
    def transaction(self):
        try:
            self.db.execute("BEGIN")
            yield self.db
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    # ---- data kind guard: never mix synthetic fixtures with real records
    def check_kind(self, synthetic: bool) -> None:
        row = self.db.execute("SELECT value FROM meta WHERE key='synthetic'").fetchone()
        want = "1" if synthetic else "0"
        if row is None:
            self.db.execute("INSERT INTO meta VALUES ('synthetic', ?)", (want,))
            self.db.commit()
        elif row["value"] != want:
            kind = "synthetic fixture" if row["value"] == "1" else "real"
            raise StoreError(f"{self.path} holds {kind} data; use a different --db for this run.")

    def is_synthetic(self) -> bool:
        row = self.db.execute("SELECT value FROM meta WHERE key='synthetic'").fetchone()
        return bool(row and row["value"] == "1")

    # ---- runs
    def last_successful_run(self, topic: str):
        return self.db.execute(
            "SELECT * FROM runs WHERE topic=? AND status='success' ORDER BY id DESC LIMIT 1",
            (topic,)).fetchone()

    def run(self, run_id: int):
        return self.db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()

    def record_failure(self, topic: str, started: str, finished: str, mode: str, error: str) -> int:
        cur = self.db.execute(
            "INSERT INTO runs (topic, started_at, finished_at, status, mode, error) VALUES (?,?,?,?,?,?)",
            (topic, started, finished, "failed", mode, error))
        self.db.commit()
        return cur.lastrowid

    # ---- reads
    def article(self, pmid: str, topic: str):
        return self.db.execute("SELECT * FROM articles WHERE pmid=? AND topic=?", (pmid, topic)).fetchone()

    def latest_trial(self, nct_id: str, topic: str):
        return self.db.execute("SELECT * FROM trials WHERE nct_id=? AND topic=?", (nct_id, topic)).fetchone()

    def tracked_trial_ids(self, topic: str) -> list[str]:
        return [r["nct_id"] for r in self.db.execute("SELECT nct_id FROM trials WHERE topic=?", (topic,))]

    def all_trials(self, topic: str) -> list[dict]:
        return [dict(json.loads(r["data"]), first_seen_run=r["first_seen_run"], last_seen_run=r["last_seen_run"])
                for r in self.db.execute("SELECT * FROM trials WHERE topic=? ORDER BY nct_id", (topic,))]

    def reviews(self, topic: str) -> dict[str, dict]:
        return {r["source_id"]: dict(r) for r in self.db.execute("SELECT * FROM reviews WHERE topic=?", (topic,))}

    def counts(self, topic: str) -> dict:
        q = lambda sql: self.db.execute(sql, (topic,)).fetchone()[0]  # noqa: E731
        return {"articles": q("SELECT COUNT(*) FROM articles WHERE topic=?"),
                "trials": q("SELECT COUNT(*) FROM trials WHERE topic=?"),
                "runs": q("SELECT COUNT(*) FROM runs WHERE topic=?"),
                "reviews": q("SELECT COUNT(*) FROM reviews WHERE topic=?")}


def dumps(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)
