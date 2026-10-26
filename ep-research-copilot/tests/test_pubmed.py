import json
from datetime import date

import pytest

from ep_copilot import http
from ep_copilot.pubmed import PubMedClient, parse_efetch

from conftest import API


def test_parse_structured_abstract_doi_dates_and_authors():
    a, b = parse_efetch((API / "efetch.xml").read_bytes())
    assert a.pmid == "99000001"
    assert a.abstract == "BACKGROUND: Pulsed field ablation is new.\n\nRESULTS: A total of 412 patients were randomized."
    assert a.doi == "10.0000/synthetic.0001"          # ArticleIdList preferred over ELocationID
    assert a.pub_date == "2026-09-15" and a.entrez_date == "2026-10-02"
    assert a.authors == ["Test Author", "Synthetic Investigators"]
    assert "Randomized Controlled Trial" in a.publication_types
    assert a.mesh_terms == ["Atrial Fibrillation"] and a.keywords == ["pulsed field ablation"]
    assert a.url == "https://pubmed.ncbi.nlm.nih.gov/99000001/"


def test_missing_abstract_and_doi_and_medline_date():
    _, b = parse_efetch((API / "efetch.xml").read_bytes())
    assert b.abstract == "" and b.doi == "" and b.doi_url == ""
    assert b.pub_date == "2026"


def test_search_paginates_dedupes_and_uses_entrez_dates():
    pages = [(API / "esearch_page1.json").read_bytes(), (API / "esearch_page2.json").read_bytes()]
    calls = []

    def getter(url, params, limiter=None):
        calls.append(params)
        return pages[len(calls) - 1]
    pmids, total = PubMedClient(getter=getter).search("q", date(2026, 9, 1), date(2026, 10, 1))
    assert pmids == ["99000001", "99000002", "99000003"] and total == 3
    assert calls[0]["datetype"] == "edat" and calls[0]["mindate"] == "2026/09/01"
    assert calls[1]["retstart"] == 2
    assert all(c["tool"] == "ep-research-copilot" for c in calls)


def test_esearch_error_is_raised():
    getter = lambda url, params, limiter=None: json.dumps({"esearchresult": {"ERROR": "bad query"}}).encode()  # noqa: E731
    with pytest.raises(http.FetchError, match="bad query"):
        PubMedClient(getter=getter).search("q", date(2026, 1, 1), date(2026, 1, 2))


def test_fetch_batches(monkeypatch):
    seen = []

    def getter(url, params, limiter=None):
        seen.append(params["id"].count(",") + 1)
        return b"<PubmedArticleSet/>"
    PubMedClient(getter=getter).fetch([str(i) for i in range(450)])
    assert seen == [200, 200, 50]


class _Resp:
    def __init__(self, body): self.body = body
    def read(self): return self.body
    def __enter__(self): return self
    def __exit__(self, *a): return False


def test_http_retries_then_succeeds():
    attempts, sleeps = [], []

    def opener(req, timeout):
        attempts.append(timeout)
        if len(attempts) < 3:
            raise TimeoutError("slow")
        return _Resp(b"ok")
    assert http.get("https://example.invalid", opener=opener, sleep=sleeps.append, timeout=5) == b"ok"
    assert len(attempts) == 3 and sleeps == [1.0, 2.0] and attempts[0] == 5


def test_http_gives_up_with_clear_error():
    def opener(req, timeout):
        raise http.urllib.error.URLError("no route")
    with pytest.raises(http.FetchError, match="no route"):
        http.get("https://example.invalid", opener=opener, sleep=lambda s: None, retries=2)


def test_http_does_not_retry_client_errors():
    attempts = []

    def opener(req, timeout):
        attempts.append(1)
        raise http.urllib.error.HTTPError(req.full_url, 400, "Bad Request", {}, None)
    with pytest.raises(http.FetchError):
        http.get("https://example.invalid", opener=opener, sleep=lambda s: None)
    assert len(attempts) == 1
