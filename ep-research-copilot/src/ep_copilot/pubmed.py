"""PubMed via NCBI E-utilities (ESearch + EFetch XML).

Docs: https://www.ncbi.nlm.nih.gov/books/NBK25499/
Without an API key NCBI allows 3 requests/second; we stay below that.
The search window uses the Entrez date (EDAT: when a record entered PubMed),
so articles published earlier but indexed recently are not missed.
"""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from datetime import date

from . import http
from .models import Article

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
TOOL_NAME = "ep-research-copilot"
BATCH = 200
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


class PubMedClient:
    def __init__(self, getter=http.get, api_key: str | None = None, email: str | None = None):
        self.getter = getter
        self.api_key = api_key or os.environ.get("NCBI_API_KEY")
        self.email = email or os.environ.get("NCBI_EMAIL")
        self.limiter = http.RateLimiter(9.0 if self.api_key else 2.5)

    def _params(self, **extra) -> dict:
        p = {"tool": TOOL_NAME, **extra}
        if self.api_key:
            p["api_key"] = self.api_key
        if self.email:
            p["email"] = self.email
        return p

    def search(self, query: str, mindate: date, maxdate: date, max_records: int = 5000) -> tuple[list[str], int]:
        """Return (PMIDs, total count reported by PubMed) for the EDAT window."""
        pmids: list[str] = []
        total = 0
        retstart = 0
        while True:
            raw = self.getter(BASE + "esearch.fcgi", self._params(
                db="pubmed", term=query, retmode="json", retmax=BATCH, retstart=retstart,
                datetype="edat", mindate=mindate.strftime("%Y/%m/%d"),
                maxdate=maxdate.strftime("%Y/%m/%d")), limiter=self.limiter)
            result = json.loads(raw)["esearchresult"]
            if "ERROR" in result:
                raise http.FetchError(f"PubMed ESearch error: {result['ERROR']}")
            total = int(result.get("count", 0))
            batch = result.get("idlist", [])
            pmids.extend(batch)
            retstart += len(batch)
            if not batch or retstart >= total or retstart >= max_records:
                break
        # ESearch can repeat IDs across pages if the index changes mid-paging.
        return list(dict.fromkeys(pmids)), total

    def fetch(self, pmids: list[str]) -> list[Article]:
        articles = []
        for i in range(0, len(pmids), BATCH):
            raw = self.getter(BASE + "efetch.fcgi", self._params(
                db="pubmed", id=",".join(pmids[i:i + BATCH]), retmode="xml"), limiter=self.limiter)
            articles.extend(parse_efetch(raw))
        return articles


def _text(el) -> str:
    return "".join(el.itertext()).strip() if el is not None else ""


def _date(el) -> str:
    """Year[-MM[-DD]] from a PubMed date element (handles month names and MedlineDate)."""
    if el is None:
        return ""
    year = _text(el.find("Year"))
    if not year:
        medline = _text(el.find("MedlineDate"))
        return medline[:4] if medline[:4].isdigit() else ""
    month = _text(el.find("Month"))
    if month and not month.isdigit():
        month = str(MONTHS.get(month[:3].lower(), ""))
    day = _text(el.find("Day"))
    parts = [year] + ([month.zfill(2)] if month else []) + ([day.zfill(2)] if month and day else [])
    return "-".join(parts)


def parse_efetch(xml_bytes: bytes) -> list[Article]:
    root = ET.fromstring(xml_bytes)
    out = []
    for art in root.findall("PubmedArticle"):
        mc = art.find("MedlineCitation")
        pmid = _text(mc.find("PMID"))
        if not pmid:
            continue
        a = mc.find("Article")
        sections = []
        for at in a.findall("Abstract/AbstractText"):
            label = at.get("Label")
            body = _text(at)
            sections.append(f"{label}: {body}" if label else body)
        authors = []
        for au in a.findall("AuthorList/Author"):
            name = " ".join(x for x in (_text(au.find("ForeName")), _text(au.find("LastName"))) if x)
            authors.append(name or _text(au.find("CollectiveName")))
        doi = ""
        for aid in art.findall("PubmedData/ArticleIdList/ArticleId"):
            if aid.get("IdType") == "doi":
                doi = _text(aid)
        if not doi:
            for loc in a.findall("ELocationID"):
                if loc.get("EIdType") == "doi":
                    doi = _text(loc)
        pub_date = _date(a.find("ArticleDate")) or _date(a.find("Journal/JournalIssue/PubDate"))
        entrez = ""
        for d in art.findall("PubmedData/History/PubMedPubDate"):
            if d.get("PubStatus") in ("entrez", "pubmed") and not entrez:
                entrez = _date(d)
        out.append(Article(
            pmid=pmid,
            title=_text(a.find("ArticleTitle")),
            abstract="\n\n".join(s for s in sections if s),
            authors=[x for x in authors if x],
            journal=_text(a.find("Journal/Title")),
            pub_date=pub_date,
            entrez_date=entrez,
            doi=doi,
            publication_types=[_text(p) for p in a.findall("PublicationTypeList/PublicationType")],
            mesh_terms=[_text(m.find("DescriptorName")) for m in mc.findall("MeshHeadingList/MeshHeading")],
            keywords=[_text(k) for k in mc.findall("KeywordList/Keyword")],
            language=_text(a.find("Language")),
        ))
    return out
