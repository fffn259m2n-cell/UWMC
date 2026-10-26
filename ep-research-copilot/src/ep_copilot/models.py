"""Normalized record types shared by all workflows."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field


def content_hash(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


@dataclass
class Article:
    pmid: str
    title: str = ""
    abstract: str = ""
    authors: list[str] = field(default_factory=list)
    journal: str = ""
    pub_date: str = ""          # publication date as given by the journal (YYYY, YYYY-MM or YYYY-MM-DD)
    entrez_date: str = ""       # date the record entered PubMed (YYYY-MM-DD), if known
    doi: str = ""
    publication_types: list[str] = field(default_factory=list)
    mesh_terms: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    language: str = ""

    @property
    def url(self) -> str:
        return f"https://pubmed.ncbi.nlm.nih.gov/{self.pmid}/"

    @property
    def doi_url(self) -> str:
        return f"https://doi.org/{self.doi}" if self.doi else ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Article":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})

    def fingerprint(self) -> str:
        """Hash of the fields whose change matters (e.g. an abstract added later)."""
        d = self.to_dict()
        d.pop("entrez_date", None)
        return content_hash(d)


@dataclass
class Trial:
    nct_id: str
    brief_title: str = ""
    official_title: str = ""
    overall_status: str = ""
    study_type: str = ""
    phases: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    interventions: list[str] = field(default_factory=list)
    enrollment: int | None = None
    enrollment_type: str = ""
    primary_outcomes: list[str] = field(default_factory=list)
    sponsor: str = ""
    start_date: str = ""
    primary_completion_date: str = ""
    completion_date: str = ""
    first_posted: str = ""
    last_update_posted: str = ""
    has_results: bool = False
    locations_count: int = 0
    washington_sites: list[str] = field(default_factory=list)

    @property
    def url(self) -> str:
        return f"https://clinicaltrials.gov/study/{self.nct_id}"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Trial":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})

    def fingerprint(self) -> str:
        return content_hash(self.to_dict())
