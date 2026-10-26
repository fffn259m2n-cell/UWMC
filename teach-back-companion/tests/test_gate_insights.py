import json

from fastapi.testclient import TestClient

from teachback import gate, insights
from teachback.app import create_app
from teachback.cli import main


def test_gate_holds_unsafe_and_never_certifies(tmp_path):
    r = gate.run([
        {"id": "a", "plan": "afib-demo", "item": "med-apixaban", "text": "Take apixaban 5 mg once a day. You can stop when you feel better."},
        {"id": "b", "plan": "hf-demo", "item": "med-furosemide",
         "text": "Furosemide is a water pill. Take one 40 mg pill once a day, in the morning."},
        {"id": "c", "plan": "nope", "item": "x", "text": "anything"},
    ])
    status = {row["id"]: row["status"] for row in r["rows"]}
    assert status["a"] == gate.HELD and status["c"] == gate.HELD
    assert status["b"] == gate.REVIEW and "review" in status["b"]
    assert r["held"] == 2 and "clinician review" in r["note"]
    f = tmp_path / "d.json"
    f.write_text(json.dumps({"drafts": r["rows"][:0] + [{"plan": "afib-demo", "item": "med-apixaban", "text": "Take apixaban 5 mg once a day."}]}), encoding="utf-8")
    assert main(["gate", str(f), "--html", str(tmp_path / "g.html")]) == 1
    assert "AI draft safety gate" in (tmp_path / "g.html").read_text(encoding="utf-8")


def test_insights_counts_no_text_and_maps_domains(tmp_path):
    attempts = [
        {"plan": "hf-demo", "item": "med-furosemide", "text": "40 mg at bedtime"},
        {"plan": "hf-demo", "item": "med-furosemide", "text": "one 40 mg pill once a day in the morning"},
        {"plan": "afib-demo", "item": "warn-stroke", "text": "if my face droops I call my cardiologist"},
    ]
    r = insights.run(attempts)
    furo = next(i for i in r["items"] if i["item"] == "med-furosemide")
    assert furo["attempts"] == 2 and furo["flagged"] == 1 and furo["hcahps_label"] == "Communication about medicines"
    assert any(d["label"] == "Information about symptoms" for d in r["domains"])
    blob = json.dumps(r)
    assert "bedtime" not in blob and "cardiologist" not in blob   # counts only, no patient text
    out = tmp_path / "i.csv"
    insights.write_csv(r, out, synthetic=False)
    assert out.read_text(encoding="utf-8").splitlines()[0].endswith("synthetic")


def test_bundled_cohort_cli_and_api(tmp_path):
    assert main(["insights", "--csv", str(tmp_path / "c.csv"), "--html", str(tmp_path / "c.html")]) == 0
    assert "SYNTHETIC DATA" in (tmp_path / "c.html").read_text(encoding="utf-8")
    client = TestClient(create_app(tmp_path / "t.sqlite"))
    assert client.get("/api/insights").json()["attempts"] > 100
    g = client.post("/api/gate", json={"drafts": [{"plan": "afib-demo", "item": "med-apixaban", "text": "Take apixaban 5 mg once a day."}]})
    assert g.status_code == 200 and g.json()["held"] == 1
