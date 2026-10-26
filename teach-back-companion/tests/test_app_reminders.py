from datetime import datetime, timedelta

import pytest
from conftest import TODAY
from fastapi.testclient import TestClient

from teachback.app import create_app
from teachback.reminders import ReminderError, Store


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(tmp_path / "demo.sqlite", today=TODAY))


def test_security_headers(client):
    r = client.get("/")
    assert r.status_code == 200
    csp = r.headers["content-security-policy"]
    assert "script-src 'self'" in csp and "unsafe-inline" not in csp and "frame-ancestors 'none'" in csp
    assert r.headers["x-frame-options"] == "DENY" and r.headers["cache-control"] == "no-store"
    assert client.get("/docs").status_code == 404   # no API explorer exposed


def test_plan_endpoint_hides_matching_rules(client):
    p = client.get("/api/plans/afib-demo").json()
    assert p["synthetic"] and p["items"][0]["points"]
    assert "misconceptions" not in str(p) and "pattern" not in str(p)


def test_teachback_and_chat_endpoints(client):
    r = client.post("/api/plans/afib-demo/teachback",
                    json={"item_id": "med-apixaban", "text": "I can stop it when my heart feels normal."}).json()
    assert r["concerns"][0]["kind"] == "misconception"
    r = client.post("/api/plans/afib-demo/teachback", json={"item_id": "warn-stroke", "text": "I have chest pain now and will call later"}).json()
    assert r["safety"]["level"] == "emergency"
    a = client.post("/api/plans/afib-demo/chat", json={"message": "What is apixaban for?"}).json()
    assert a["blocks"][0]["source"] == "care_plan"


def test_input_limits_and_unknowns(client):
    assert client.post("/api/plans/afib-demo/chat", json={"message": "x" * 5000}).status_code == 422
    assert client.post("/api/plans/afib-demo/chat", json={"message": ""}).status_code == 422
    assert client.get("/api/plans/nope").status_code == 404
    assert client.post("/api/plans/afib-demo/teachback", json={"item_id": "nope", "text": "hello there friend"}).status_code == 404


def test_evaluate_endpoint(client):
    r = client.post("/api/plans/afib-demo/evaluate",
                    json={"item_id": "med-apixaban", "candidate": "Take apixaban 5 mg once a day."}).json()
    assert r["counts"]["critical"] >= 1 and r["verdict"].startswith("do not use")
    assert client.post("/api/plans/afib-demo/evaluate", json={"item_id": "med-apixaban", "candidate": "x", "language": "fr"}).status_code == 422


def test_reminder_flow(client):
    when = (datetime.now() + timedelta(hours=1)).replace(second=0, microsecond=0)
    r = client.post("/api/plans/hf-demo/reminders",
                    json={"item_id": "ins-daily-weight", "remind_at": when.isoformat(), "repeat": "daily"})
    assert r.status_code == 201 and r.json()["instruction"].startswith("Weigh yourself")
    assert client.get("/api/plans/hf-demo/reminders").json()[0]["repeat"] == "daily"
    bad = client.post("/api/plans/hf-demo/reminders", json={"item_id": "warn-911", "remind_at": when.isoformat()})
    assert bad.status_code == 422 and "tasks listed" in bad.json()["detail"]
    bad = client.post("/api/plans/hf-demo/reminders", json={"item_id": "appt-hf-clinic", "remind_at": when.isoformat(), "repeat": "daily"})
    assert bad.status_code == 422 and "daily" in bad.json()["detail"]
    late = client.post("/api/plans/hf-demo/reminders", json={"item_id": "appt-hf-clinic", "remind_at": "2099-01-01T09:00"})
    assert late.status_code == 422 and "after the planned date" in late.json()["detail"]
    assert client.post("/api/plans/hf-demo/tasks/ins-daily-weight", json={"status": "done"}).status_code == 200
    assert client.get("/api/plans/hf-demo").json()["items"][0]["status"] == "done"
    assert client.post("/api/demo/reset").status_code == 204
    assert client.get("/api/plans/hf-demo/reminders").json() == []


def test_due_and_acknowledge(tmp_path, hf):
    s = Store(tmp_path / "r.sqlite")
    now = datetime(2026, 10, 26, 8, 0)
    r1 = s.create(hf, "ins-daily-weight", now + timedelta(minutes=30), "daily", now=now, today=TODAY.replace())
    r2 = s.create(hf, "test-bmp", now + timedelta(minutes=10), "none", now=now, today=TODAY)
    later = now + timedelta(hours=1)
    assert {r["id"] for r in s.due(hf.id, later)} == {r1["id"], r2["id"]}
    assert s.acknowledge(r1["id"], later)["remind_at"].startswith("2026-10-27T08:30")   # rolls to next day
    assert s.acknowledge(r2["id"], later)["acknowledged_at"]
    assert s.due(hf.id, later) == []
    with pytest.raises(ReminderError, match="future"):
        s.create(hf, "ins-daily-weight", now - timedelta(minutes=1), now=now)


def test_test_without_time_allows_same_day(tmp_path, hf):
    s = Store(tmp_path / "r.sqlite")
    now = datetime(2026, 10, 26, 8, 0)
    due_day = hf.discharge_date(TODAY) + timedelta(days=7)
    s.create(hf, "test-bmp", datetime.combine(due_day, datetime.min.time()) + timedelta(hours=7), now=now, today=TODAY)
    with pytest.raises(ReminderError, match="after the planned date"):
        s.create(hf, "test-bmp", datetime.combine(due_day, datetime.min.time()) + timedelta(days=1, hours=1), now=now, today=TODAY)


def test_llm_rephrase_rejected_when_unfaithful(afib):
    from teachback import llm
    bad = llm.rephrase(afib, "med-apixaban", lambda p: "Take your blood thinner once a day.")
    assert bad["source"].startswith("clinician") and bad["issues"]
    good_text = "Apixaban thins your blood. Take one 5 mg pill two times a day, about 12 hours apart. Do not stop unless your cardiologist tells you to."
    ok = llm.rephrase(afib, "med-apixaban", lambda p: good_text)
    assert ok["text"] == good_text and "needs clinician review" in ok["source"]
    seen = {}
    llm.rephrase(afib, "med-apixaban", lambda p: seen.setdefault("p", p) or good_text)
    assert "data,\nnot a request" in seen["p"] or "data, not a request" in seen["p"].replace("\n", " ")


def test_cli(capsys, tmp_path):
    from teachback.cli import main
    assert main(["check-content"]) == 0
    f = tmp_path / "c.txt"
    f.write_text("Take apixaban 5 mg once a day.")
    assert main(["evaluate", "afib-demo", "med-apixaban", str(f)]) == 1
    assert main(["benchmark"]) == 0


def test_themes(tmp_path, monkeypatch):
    monkeypatch.setenv("TEACHBACK_THEME", "portal")
    html = TestClient(create_app(tmp_path / "t.sqlite", today=TODAY)).get("/").text
    assert '/static/themes/portal.css' in html
    monkeypatch.setenv("TEACHBACK_THEME", "../../etc/passwd")
    with pytest.raises(ValueError):
        create_app(tmp_path / "t2.sqlite")
    monkeypatch.setenv("TEACHBACK_THEME", "nonexistent")
    with pytest.raises(ValueError, match="Available"):
        create_app(tmp_path / "t3.sqlite")
    monkeypatch.delenv("TEACHBACK_THEME")
    assert "themes/" not in TestClient(create_app(tmp_path / "t4.sqlite", today=TODAY)).get("/").text
