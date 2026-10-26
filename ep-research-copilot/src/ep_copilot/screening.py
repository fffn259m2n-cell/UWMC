"""Deterministic, transparent topic screening and review prioritization.

Screening decides what a human should look at first. It never discards a
record: out-of-scope and uncertain records stay in the review queue, labelled.
Priority reflects topic relevance only (how many configured topic categories an
in-scope record matches: 2+ high, 1 medium, 0 low; no abstract -> review). It
does not rate study quality, and publication type is a descriptor, not a rank.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import Topic
from .models import Article

IN_SCOPE, OTHER_EP, OUT_OF_SCOPE = "in_scope", "other_ep", "outside_scope"
HIGH_AT = 2  # categories matched for "high" review priority


@dataclass
class Screening:
    pmid: str
    scope: str
    categories: list[str] = field(default_factory=list)
    matched_terms: dict[str, list[str]] = field(default_factory=dict)
    study_design: str = ""
    priority: str = ""
    reasons: list[str] = field(default_factory=list)
    uncertain: bool = False


DESIGN_RULES = (  # (label, publication types, title/abstract phrases), first match wins
    ("Protocol / design paper", {"Clinical Trial Protocol"},
     ("design and rationale", "study protocol", "rationale and design", "protocol for a")),
    ("Systematic review / meta-analysis", {"Meta-Analysis", "Systematic Review"},
     ("meta-analysis", "systematic review")),
    ("Randomized controlled trial", {"Randomized Controlled Trial"}, ("randomized", "randomised")),
    ("Guideline / consensus", {"Practice Guideline", "Guideline", "Consensus Development Conference"},
     ("consensus statement", "guideline")),
    ("Case report", {"Case Reports"}, ("we report a case", "we present a case", "case report")),
    ("Registry / observational cohort", {"Observational Study"},
     ("registry", "retrospective", "prospective", "cohort", "observational")),
    ("Review", {"Review"}, ()),
    ("Editorial / comment / letter", {"Editorial", "Comment", "Letter"}, ()),
)


def study_design(article: Article) -> str:
    types = set(article.publication_types)
    text = f"{article.title}\n{article.abstract}".lower()
    for label, ptypes, phrases in DESIGN_RULES:
        if types & ptypes:
            return label
    for label, _, phrases in DESIGN_RULES:
        if any(p in text for p in phrases):
            return label + " (from abstract wording)"
    return "Not determined"


def _haystack(a: Article) -> str:
    return "\n".join([a.title, a.abstract, " ".join(a.keywords), " ".join(a.mesh_terms)])


def screen(article: Article, topic: Topic) -> Screening:
    text = _haystack(article)
    s = Screening(pmid=article.pmid, scope=OUT_OF_SCOPE, study_design=study_design(article))

    group_hits = []
    for group in topic.scope_groups:
        hits = sorted({m.group(0) for p in group for m in [p.search(text)] if m})
        group_hits.append(hits)
    if all(group_hits):
        s.scope = IN_SCOPE
        s.reasons.append("Matches scope terms: " + "; ".join(", ".join(h) for h in group_hits))
    elif any(p.search(text) for p in topic.other_ep):
        s.scope = OTHER_EP
        s.reasons.append("Electrophysiology terms present but not all scope groups matched")
    else:
        s.reasons.append("No scope terms matched")

    for cat in topic.categories:
        hits = sorted({m.group(0).lower() for p in cat.patterns for m in [p.search(text)] if m})
        if hits:
            s.categories.append(cat.label)
            s.matched_terms[cat.label] = hits

    if not article.abstract.strip():
        s.uncertain = True
        s.reasons.append("No abstract in PubMed: screened on title and indexing terms only")

    # Relevance = number of distinct topic categories matched (in scope only).
    n = len(s.categories) if s.scope == IN_SCOPE else 0
    s.priority = "high" if n >= HIGH_AT else "medium" if n >= 1 else "low"
    if s.uncertain and s.priority != "high":
        s.priority = "review"  # never let a no-abstract record sink silently
    return s
