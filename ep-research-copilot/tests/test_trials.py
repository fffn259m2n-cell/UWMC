import json

from conftest import API

from ep_copilot.changes import diff_trials
from ep_copilot.clinical_trials import TrialsClient, parse_study
from ep_copilot.models import Trial


def test_parse_study_fields_and_washington_sites():
    t = parse_study(json.loads((API / "ctgov_single.json").read_text(encoding="utf-8")))
    assert t.nct_id == "NCT99000104" and t.overall_status == "COMPLETED"
    assert t.interventions == ["Device: Pulsed field ablation"]
    assert t.primary_outcomes == ["Freedom from AF | 12 months"]
    assert t.enrollment == 100 and t.enrollment_type == "ESTIMATED"
    assert t.washington_sites == ["Synthetic Hospital, Seattle"] and t.locations_count == 2
    assert t.url == "https://clinicaltrials.gov/study/NCT99000104"


def test_pagination_and_duplicate_nct_ids():
    pages = [(API / "ctgov_page1.json").read_bytes(), (API / "ctgov_page2.json").read_bytes()]
    calls = []

    def getter(url, params, limiter=None):
        calls.append(params)
        return pages[len(calls) - 1]
    trials, total, truncated = TrialsClient(getter=getter).search("af", "ablation", ["RECRUITING"])
    assert [t.nct_id for t in trials] == ["NCT99000101", "NCT99000102", "NCT99000103"]
    assert total == 3 and not truncated
    assert calls[1]["pageToken"] == "PAGE2" and calls[0]["filter.overallStatus"] == "RECRUITING"


def test_truncation_reported():
    page = (API / "ctgov_page1.json").read_bytes()
    trials, total, truncated = TrialsClient(getter=lambda *a, **k: page).search("af", "", [], max_records=2)
    assert len(trials) == 2 and truncated


def test_single_study_lookup():
    body = (API / "ctgov_single.json").read_bytes()
    seen = []
    t = TrialsClient(getter=lambda url, params, limiter=None: seen.append(url) or body).get("NCT99000104")
    assert t.nct_id == "NCT99000104" and seen[0].endswith("/studies/NCT99000104")


def test_diff_separates_substantive_and_administrative():
    old = Trial("NCT99000101", overall_status="RECRUITING", enrollment=400, last_update_posted="2026-01-01")
    new = Trial("NCT99000101", overall_status="COMPLETED", enrollment=400, last_update_posted="2026-02-01")
    d = {c["field"]: c["kind"] for c in diff_trials(old, new)}
    assert d == {"overall_status": "substantive", "last_update_posted": "administrative"}


def test_no_diff_for_identical_snapshots():
    t = Trial("NCT99000101", overall_status="RECRUITING")
    assert diff_trials(t, Trial.from_dict(t.to_dict())) == []
