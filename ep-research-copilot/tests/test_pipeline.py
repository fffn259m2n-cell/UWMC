import csv
import json
from datetime import date

import pytest
from conftest import FIX

from ep_copilot import cli, pipeline, reporting, review
from ep_copilot.http import FetchError
from ep_copilot.storage import Store, StoreError

RUN1, RUN2 = FIX / "snapshot_run1", FIX / "snapshot_run2"


def test_first_run_dedupes_and_baselines(store, topic):
    r = pipeline.run(store, topic, snapshot=RUN1, mode="offline-fixture")
    assert r.synthetic and len(r.new_pmids) == 6 and r.duplicate_pmids == ["99000001"]
    assert sorted(r.new_trials) == ["NCT99000101", "NCT99000102", "NCT99000103"] and r.trial_changes == []


def test_repeat_run_is_idempotent(store, topic):
    pipeline.run(store, topic, snapshot=RUN1, mode="offline-fixture")
    r = pipeline.run(store, topic, snapshot=RUN1, mode="offline-fixture")
    assert r.new_pmids == [] and r.updated_pmids == [] and r.new_trials == [] and r.trial_changes == []
    assert store.counts(topic.key)["articles"] == 6


def test_second_run_detects_updates_and_trial_changes(store, topic):
    pipeline.run(store, topic, snapshot=RUN1, mode="offline-fixture")
    r = pipeline.run(store, topic, snapshot=RUN2, mode="offline-fixture")
    assert r.new_pmids == ["99000007"] and r.updated_pmids == ["99000003"]
    changes = {(c["nct_id"], c["field"]): c for c in r.trial_changes}
    assert changes[("NCT99000101", "enrollment")]["new"] == 450
    assert changes[("NCT99000102", "overall_status")]["new"] == "COMPLETED"   # from re-read, not search
    assert changes[("NCT99000102", "has_results")]["kind"] == "substantive"
    assert ("NCT99000103", "record") in changes
    r3 = pipeline.run(store, topic, snapshot=RUN2, mode="offline-fixture")
    assert not any(c["field"] == "record" for c in r3.trial_changes)   # missing reported once


def test_failed_fetch_keeps_previous_data(store, topic):
    pipeline.run(store, topic, snapshot=RUN1, mode="offline-fixture")

    class Broken:
        def search(self, *a, **k):
            raise FetchError("network down")
    with pytest.raises(FetchError):
        pipeline.run(store, topic, days=30, pubmed=Broken(), trials=Broken())
    assert store.counts(topic.key)["articles"] == 6
    assert store.last_successful_run(topic.key)["id"] == 1
    assert store.db.execute("SELECT status, error FROM runs ORDER BY id DESC").fetchone()["status"] == "failed"


def test_write_failure_rolls_back(store, topic, monkeypatch):
    pipeline.run(store, topic, snapshot=RUN1, mode="offline-fixture")

    def boom(*a, **k):
        raise RuntimeError("disk full")
    monkeypatch.setattr(pipeline.extraction, "extract", boom)
    with pytest.raises(RuntimeError):
        pipeline.run(store, topic, snapshot=RUN2, mode="offline-fixture")
    assert store.article("99000007", topic.key) is None
    assert store.counts(topic.key)["runs"] == 1


def test_window_selection(store, topic):
    today = date(2026, 10, 26)
    assert pipeline.choose_window(store, topic, 7, today) == (date(2026, 10, 19), today)
    assert pipeline.choose_window(store, topic, None, today) == (date(2026, 9, 26), today)
    pipeline.run(store, topic, snapshot=RUN1, mode="offline-fixture")   # window ends 2026-10-01
    assert pipeline.choose_window(store, topic, None, today) == (date(2026, 9, 30), today)
    with pytest.raises(ValueError):
        pipeline.choose_window(store, topic, 0, today)


def test_live_fetch_rechecks_tracked_trials(store, topic):
    from ep_copilot.models import Article, Trial
    pipeline.run(store, topic, snapshot=RUN1, mode="offline-fixture")
    store.db.execute("UPDATE meta SET value='0' WHERE key='synthetic'")   # simulate a real DB for this unit test

    class PM:
        def search(self, q, s, e): return ["99000001"], 1
        def fetch(self, ids): return [Article("99000001", title="t")]

    class CT:
        def search(self, *a): return [Trial("NCT99000101")], 1, False
        def get(self, nct): return Trial(nct, overall_status="COMPLETED") if nct == "NCT99000102" else None
    f = pipeline.fetch_live(topic, date(2026, 10, 1), date(2026, 10, 26), store, PM(), CT())
    assert [t.nct_id for t in f.rechecked_trials] == ["NCT99000102"] and f.missing_trials == ["NCT99000103"]


def test_synthetic_and_real_never_mixed(store, topic):
    pipeline.run(store, topic, snapshot=RUN1, mode="offline-fixture")
    with pytest.raises(StoreError, match="synthetic"):
        store.check_kind(False)


def test_corrupt_database_reported(tmp_path):
    p = tmp_path / "bad.sqlite"
    p.write_bytes(b"this is not a database" * 100)
    with pytest.raises(StoreError, match="corrupt"):
        Store(p)


def test_corrupt_snapshot_file(tmp_path, store, topic):
    (tmp_path / "snapshot.json").write_text("{not json")
    with pytest.raises(ValueError):
        pipeline.run(store, topic, snapshot=tmp_path, mode="imported")
    assert store.last_successful_run(topic.key) is None


def test_outputs_and_link_integrity(store, topic, tmp_path):
    r = pipeline.run(store, topic, snapshot=RUN1, mode="offline-fixture")
    paths = reporting.write_outputs(r, store, tmp_path)
    html = paths["digest"].read_text()
    assert "SYNTHETIC TEST DATA" in html and reporting.DISCLAIMER in html
    with paths["articles"].open() as fh:
        arts = list(csv.DictReader(fh))
    assert len(arts) == 6 and len({a["pmid"] for a in arts}) == 6
    for a in arts:
        assert a["url"] == f"https://pubmed.ncbi.nlm.nih.gov/{a['pmid']}/"
        assert f'href="{a["url"]}"' in html
    with paths["trials"].open() as fh:
        for t in csv.DictReader(fh):
            assert t["nct_id"].startswith("NCT") and t["url"] == f"https://clinicaltrials.gov/study/{t['nct_id']}"
    with paths["evidence"].open() as fh:
        assert all(row["evidence"] for row in csv.DictReader(fh))
    meta = json.loads(paths["metadata"].read_text())
    assert meta["pubmed"]["query"] == topic.pubmed_query and meta["synthetic_data"] is True
    with paths["review_queue"].open() as fh:
        assert list(csv.DictReader(fh))[0].keys() >= {"source_id", "reviewer_decision", "reviewer_notes",
                                                       "suggested_priority", "classification_reason"}


def test_report_command_rebuilds_from_db(store, topic, tmp_path):
    pipeline.run(store, topic, snapshot=RUN1, mode="offline-fixture")
    r = pipeline.load_result(store, topic)
    assert len(r.screenings) == 6 and len(r.new_pmids) == 6
    r2 = pipeline.load_result(store, topic, rescreen=True)
    assert r2.screenings.keys() == r.screenings.keys()


def test_review_import_and_evaluation(store, topic, tmp_path):
    r = pipeline.run(store, topic, snapshot=RUN1, mode="offline-fixture")
    paths = reporting.write_outputs(r, store, tmp_path)
    assert review.evaluate(store, topic.key)["precision"] is None   # nothing measured without humans
    with paths["review_queue"].open() as fh:
        rows = list(csv.DictReader(fh))
    decisions = {"99000001": "include", "99000002": "include", "99000006": "exclude",
                 "99000004": "include", "99000005": "exclude", "99000003": "maybe"}
    for row in rows:
        row["reviewer_decision"] = decisions.get(row["source_id"], "")
    filled = tmp_path / "filled.csv"
    with filled.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    n, problems = review.import_decisions(store, topic.key, filled)
    assert n == 5 and len(problems) == 1 and "maybe" in problems[0]
    m = review.evaluate(store, topic.key)
    assert (m["true_positives"], m["false_positives"], m["false_negatives"], m["true_negatives"]) == (2, 1, 1, 1)
    assert m["precision"] == 0.667 and m["recall"] == 0.667
    # automated re-screening never touches reviewer decisions
    pipeline.load_result(store, topic, rescreen=True)
    assert store.reviews(topic.key)["99000004"]["reviewer_decision"] == "include"


def test_cli_offline_end_to_end(tmp_path, capsys):
    db, out = tmp_path / "db.sqlite", tmp_path / "out"
    assert cli.main(["--db", str(db), "--out", str(out), "run", "--offline"]) == 0
    assert (out / "ep_research_digest.html").exists()
    assert "SYNTHETIC" in capsys.readouterr().out
    assert cli.main(["--db", str(db), "validate"]) == 0
    assert cli.main(["--db", str(db), "--out", str(out), "report"]) == 0
    assert cli.main(["--topic", "nope", "--db", str(db), "validate"]) == 2


def test_packaged_config_matches_repo_config():
    from pathlib import Path

    from ep_copilot.config import PACKAGED_CONFIG
    assert PACKAGED_CONFIG.read_text() == (Path(__file__).parents[1] / "config" / "topics.yaml").read_text()


def test_extraction_accuracy_from_reviewer_file(store, topic, tmp_path):
    r = pipeline.run(store, topic, snapshot=RUN1, mode="offline-fixture")
    paths = reporting.write_outputs(r, store, tmp_path)
    with paths["evidence"].open() as fh:
        rows = list(csv.DictReader(fh))
    assert "reviewer_correct" in rows[0]
    assert review.extraction_accuracy(paths["evidence"])["reviewed_items"] == 0
    for i, row in enumerate(rows[:4]):
        row["field"], row["reviewer_correct"] = "sample_size", "yes" if i < 3 else "no"
    filled = tmp_path / "ev.csv"
    with filled.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    acc = review.extraction_accuracy(filled)
    assert acc["by_field"]["sample_size"] == {"correct": 3, "incorrect": 1, "accuracy": 0.75}


def test_connector_import_script(tmp_path):
    import subprocess
    import sys
    from pathlib import Path
    arts = tmp_path / "a.json"
    arts.write_text(json.dumps({"articles": [{
        "identifiers": {"pmid": "99000050", "doi": "10.0000/x"}, "title": "[SYNTHETIC] t", "abstract": "A total of 20 patients.",
        "journal": {"title": "J"}, "authors": [{"fore_name": "A", "last_name": "B"}],
        "publication_date": {"year": "2026", "month": "Oct", "day": "21"}, "article_types": ["Journal Article"],
        "keywords": [], "language": "eng"}]}))
    trials = tmp_path / "t.json"
    trials.write_text(json.dumps({"items": [{"nct_id": "NCT99000150", "title": "[SYNTHETIC] T", "status": "RECRUITING",
                                             "phase": None, "conditions": None, "interventions": None}]}))
    script = Path(__file__).parents[1] / "scripts" / "import_connector_export.py"
    subprocess.run([sys.executable, str(script), str(tmp_path / "snap"), "--window", "2026-10-01", "2026-10-26",
                    "--articles", str(arts), "--trials", str(trials)], check=True, capture_output=True)
    snap = json.loads((tmp_path / "snap" / "snapshot.json").read_text())
    assert snap["articles"][0]["pub_date"] == "2026-10-21" and snap["articles"][0]["authors"] == ["A B"]
    assert snap["trials"][0]["phases"] == [] and snap["synthetic"] is False
    assert "washington_sites" in snap["fields_unavailable"]["trials"]
