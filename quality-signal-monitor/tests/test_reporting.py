import io
import json
import urllib.request

import pandas as pd
import pytest
from conftest import CURRENT, PREVIOUS, edit_csv

from uwmc_monitor import cli, narrative, reporting, sources
from uwmc_monitor.analysis import analyze


@pytest.fixture(scope="module")
def result():
    return analyze(CURRENT, PREVIOUS)


def test_tables_written(result, tmp_path):
    paths = reporting.write_tables(result, tmp_path)
    comp = pd.read_csv(paths["benchmark_comparisons"])
    assert {"hcahps_measure_id", "gap_pp", "not_comparable_reason", "start_date"} <= set(comp.columns)
    meta = json.loads(paths["metadata"].read_text(encoding="utf-8"))
    assert meta["synthetic_data"] is True
    assert meta["hospital"]["facility_id"] == "500008"
    assert pd.read_csv(paths["data_quality_findings"]).shape[0] == len(result.findings)


def test_html_report_has_sections_and_synthetic_banner(result, tmp_path):
    html = reporting.write_report(result, tmp_path)["html"].read_text(encoding="utf-8")
    for text in ("SYNTHETIC TEST DATA", "Independent project", "Executive summary",
                 "Focus: discharge and care transitions", "Retired from the updated survey",
                 "National benchmark comparisons", "Changes between releases", "Data-quality findings",
                 "Limitations", "Methodology", "Sources", "Reproduce this report",
                 "H_RECMND_DY", "data:image/png;base64,"):
        assert text in html, text
    assert "<title>[SYNTHETIC]" in html


def test_report_without_comparable_data_is_availability_report(release_copy, tmp_path):
    d = release_copy()

    def shift(h, rows):
        i = h.index("Start Date")
        for r in rows:
            r[i] = "01/01/2020"
        return h, rows
    edit_csv(d / "hcahps_national.csv", shift)
    html = reporting.render_html(analyze(d))
    assert "could be matched to a national benchmark" in html
    assert "No top-box measure was comparable" in html


def test_manual_files_get_provenance_warning(release_copy):
    d = release_copy()
    (d / "SYNTHETIC_DATA").unlink()
    html = reporting.render_html(analyze(d))
    assert "placed in the data folder by hand" in html
    assert "SYNTHETIC TEST DATA." not in html


def test_template_narrative_uses_only_facts(result):
    facts = narrative.build_facts(result)
    out = narrative.TemplateNarrator().summarize(facts)
    text = "\n\n".join(out["paragraphs"])
    assert narrative.verify_narrative(text, facts) == []
    assert out["review_required"] is True


def test_llm_narrator_rejects_invented_numbers(result):
    facts = narrative.build_facts(result)
    bad = narrative.LLMNarrator(lambda prompt: "H_RECMND_DY is 93% versus 69%.").summarize(facts)
    assert "Number not in verified facts: 93" in bad["problems"]
    assert "rejected" in bad["method"]
    bad_id = narrative.LLMNarrator(lambda p: "H_MADE_UP_A_P is 80%.").summarize(facts)
    assert any("Unknown measure ID" in p for p in bad_id["problems"])


def test_llm_narrator_accepts_grounded_text_and_sees_only_aggregates(result):
    facts = narrative.build_facts(result)
    seen = {}

    def fake(prompt):
        seen["prompt"] = prompt
        return "H_RECMND_DY: 80% at UWMC vs 69% nationally.\n\nDescriptive only."
    out = narrative.LLMNarrator(fake).summarize(facts)
    assert out["problems"] == [] and len(out["paragraphs"]) == 2
    assert "Use ONLY the JSON facts" in seen["prompt"]


def test_cli_run_offline(tmp_path, capsys):
    code = cli.main(["run", "--data-dir", str(CURRENT), "--previous-dir", str(PREVIOUS),
                     "--out", str(tmp_path)])
    assert code == 0
    assert (tmp_path / "uwmc_quality_report.html").exists()
    assert "SYNTHETIC" in capsys.readouterr().out


def test_cli_validate_and_errors(tmp_path, capsys):
    assert cli.main(["validate", "--data-dir", str(CURRENT)]) == 0
    assert cli.main(["analyze", "--data-dir", str(tmp_path)]) == 2
    assert "No CMS files found" in capsys.readouterr().err


def test_resolve_data_dir_picks_newest_release(tmp_path):
    import shutil
    for name in ("2026-05-01", "2026-08-13"):
        shutil.copytree(CURRENT, tmp_path / "raw" / name)
    assert sources.resolve_data_dir(tmp_path).name == "2026-08-13"


def test_fetch_release_with_mocked_cms(monkeypatch, tmp_path):
    """Exercise the download path without network access."""
    def fake_get(url, timeout=60.0):
        for _key, ds in sources.DATASETS.items():
            if url == ds.metastore_url:
                return io.BytesIO(json.dumps({
                    "title": ds.title, "modified": "2026-08-13", "issued": "2020-01-01",
                    "distribution": [{"downloadURL": f"https://example.invalid/{ds.filename}"}],
                }).encode())
            if url.endswith(ds.filename):
                return io.BytesIO((CURRENT / ds.filename).read_bytes())
        raise AssertionError(url)
    monkeypatch.setattr(sources, "_get", fake_get)
    release = sources.fetch_release(tmp_path)
    assert release.name == "2026-08-13"
    manifest = json.loads((release / "manifest.json").read_text(encoding="utf-8"))
    assert {d["key"] for d in manifest["datasets"]} == set(sources.DATASETS)
    assert all(len(d["sha256"]) == 64 and d["retrieved_at"] for d in manifest["datasets"])
    assert manifest["provenance"] == "cms_api"


def test_fetch_network_failure_gives_offline_instructions(monkeypatch, tmp_path):
    def fail(url, timeout=60.0):
        raise urllib.error.URLError("no network")
    monkeypatch.setattr(sources, "_get", fail)
    with pytest.raises(sources.SourceError, match="Download the CSV manually"):
        sources.fetch_release(tmp_path)
