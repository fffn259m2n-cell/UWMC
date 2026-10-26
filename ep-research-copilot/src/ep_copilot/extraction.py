"""Deterministic, abstract-only evidence extraction with provenance.

Every extracted value carries the exact sentence it came from. A value is only
kept if that sentence is a verbatim substring of the abstract, and effect
estimates are stored as the verbatim text span rather than re-typed numbers.
Fields that are not explicitly reported stay empty (None). Nothing here reads
full text, appraises study quality, or interprets results.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from .models import Article

FIELDS = ("study_design_stated", "sample_size", "intervention", "comparator", "follow_up",
          "outcome_statements", "effect_estimates", "p_values", "trial_registration", "limitations")


@dataclass
class Extracted:
    pmid: str
    field: str
    value: str
    evidence: str
    method: str
    source: str = "abstract only"
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# Sentence split that keeps decimals ("1.5-T", "p = 0.03") and abbreviations like "vs." intact.
_SENT_END = re.compile(
    r"(?<!\bvs\.)(?<!\bal\.)(?<!\bet\.)(?<!\be\.g\.)(?<!\bi\.e\.)(?<!\bFig\.)(?<!\bapprox\.)"
    r"(?<=[.!?])\s+(?=[A-Z0-9(\[])|\n+")


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_END.split(text or "") if s and s.strip()]


_UNITS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * i for i, w in enumerate(
    "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "_"}


def words_to_int(text: str) -> int | None:
    """'Fifty', 'twenty-four', 'one hundred and twelve' -> int; None if not a number word."""
    words = re.split(r"[\s-]+", text.lower().replace(" and ", " "))
    total, current = 0, 0
    for w in words:
        if w in _UNITS:
            current += _UNITS[w]
        elif w in _TENS:
            current += _TENS[w]
        elif w == "hundred" and current:
            current *= 100
        elif w == "thousand" and current:
            total += current * 1000
            current = 0
        else:
            return None
    return total + current or None


_NUM_WORD = r"(?:(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|and)[\s-]*)+"
_PEOPLE = r"(?:consecutive\s+|eligible\s+|adult\s+|unique\s+)?(?:patients|participants|subjects|individuals|procedures|cases)"

_SCALE = r"(?!\s*(?:million|billion|thousand|hundred thousand)\b)"  # "16 million individuals" is not n=16
_NUM = rf"(\d[\d,]*{_SCALE}|{_NUM_WORD}{_SCALE})"
_MODS = r"(?:[A-Za-z][\w/-]*\s+){0,3}?"  # e.g. "517 AF patients", "1,250 consecutive adult patients"
SAMPLE_PATTERNS = (  # (rule name, regex); lower index = stronger evidence of the study population
    ("total_of", re.compile(rf"\b(?:a\s+)?total\s+of\s+{_NUM}\s+{_MODS}{_PEOPLE}", re.I)),
    ("enrolment_verb", re.compile(
        rf"\b(?:included|enrolled|comprised|consisted of|recruited|studied|analy[sz]ed|involving|totaling|totalling)"
        rf"\s+(?:a total of\s+|data (?:from|on)\s+)?{_NUM}\s+{_MODS}{_PEOPLE}", re.I)),
    ("count_then_verb", re.compile(
        rf"{_NUM}\s+{_MODS}{_PEOPLE}\s+(?:were|was)\s+(?:included|enrolled|randomi[sz]ed|analy[sz]ed|studied|recruited)", re.I)),
    ("count_people", re.compile(rf"(?<![\d.,/%])\b{_NUM}\s+{_MODS}{_PEOPLE}", re.I)),
    ("n_equals", re.compile(r"\b[Nn]\s*=\s*(\d[\d,]*)")),
)
# A count followed by a percentage, e.g. "172 patients (33.27%)", is usually an event or subgroup.
_EVENT_AFTER = re.compile(r"\s*\(\s*\d+(?:\.\d+)?\s*%")

INTERVENTION_TERMS = (
    ("Pulsed-field ablation", r"pulsed[- ]field|\bPFA\b|electroporation"),
    ("Radiofrequency ablation", r"radiofrequency|\bRFA?\b(?! ?power)"),
    ("Cryoballoon ablation", r"cryoballoon|cryoablation|\bCBA\b"),
    ("Laser balloon ablation", r"laser balloon"),
    ("Pulmonary vein isolation", r"pulmonary vein isolation|\bPVI\b"),
    ("Posterior wall isolation", r"posterior wall isolation|\bPWI\b"),
    ("Left atrial appendage intervention", r"appendage (?:occlusion|closure|isolation)"),
    ("Antiarrhythmic drug therapy", r"antiarrhythmic drug|\bAADs?\b"),
)
COMPARATOR = re.compile(r"\b(?:versus|vs\.?|compared (?:with|to)|randomi[sz]ed\s+(?:\d:\d\s+)?to)\b", re.I)
FOLLOW_UP = re.compile(
    r"(?:(?:median|mean)\s+)?follow[- ]up(?:\s+(?:of|was|period of|duration of))?\s+"
    r"(?:of\s+)?(\d+(?:\.\d+)?(?:\s*(?:±|\+/-)\s*\d+(?:\.\d+)?)?)\s*(days?|weeks?|months?|years?)"
    r"|(\d+(?:\.\d+)?)[- ](day|week|month|year)s?\s+follow[- ]up", re.I)
_BOUNDS = r"\d+(?:\.\d+)?\s*%?\s*(?:-|–|to|,)\s*\d+(?:\.\d+)?\s*%?\)?"
EFFECT = re.compile(  # e.g. "HR 0.84, 95% CI 0.61-1.15", "(hazard ratio [HR], 0.56; 95% CI, 0.32-0.97)"
    r"\b(?:(?-i:a?HRs?|a?ORs?|RRs?|IRRs?)|(?:adjusted\s+)?(?:hazard|odds|risk|rate)\s+ratios?|relative\s+risks?)\b"
    r"[^.\n]{0,25}?\d+(?:\.\d+)?[^\d\n]{0,12}?(?:95\s*%\s*)?(?:CI|confidence interval)(?:\s*\[CI\])?[^\d\n]{0,6}?"
    + _BOUNDS, re.I)
P_VALUE = re.compile(r"\b[Pp](?:[- ]?value)?\s*(?:[<=>≤≥]|&lt;)\s*(?:0?\.\d+(?:\s*[x×]\s*10\S+)?|1(?:\.0+)?)(?![\d.])")
# A percentage or number followed directly by its 95% CI, e.g. "6%; 95% CI 1.3-16.5".
ESTIMATE_CI = re.compile(
    r"\d+(?:\.\d+)?\s*%?\s*[;,(]?\s*\(?95\s*%\s*(?:CI|confidence interval)[:,]?\s*"
    r"\d+(?:\.\d+)?\s*%?\s*(?:-|–|to|,)\s*\d+(?:\.\d+)?\s*%?\)?", re.I)
OUTCOME = re.compile(r"(?:freedom from|recurren|success|arrhythmia[- ]free|sinus rhythm|complication|adverse event)[^.]*?\d+(?:\.\d+)?\s*%", re.I)
NCT = re.compile(r"\bNCT\d{8}\b")
LIMITATION = re.compile(r"\blimitation|\blimited by\b|\bfurther (?:studies|research)\b|\blarger (?:studies|trials)\b", re.I)
DESIGN_STATED = re.compile(
    r"\b(randomi[sz]ed(?: controlled)?(?: trial)?|prospective|retrospective|multicent(?:er|re)|single[- ]cent(?:er|re)|"
    r"registry|meta-analysis|systematic review|cohort|case[- ]control|cross-sectional|observational)\b", re.I)


def _balanced(span: str) -> str:
    """Drop a trailing ')' that closes a parenthesis opened before the span."""
    span = span.strip()
    while span.endswith(")") and span.count(")") > span.count("("):
        span = span[:-1].rstrip()
    return span


def _first_sentence(sents: list[str], pattern: re.Pattern) -> tuple[str, re.Match] | None:
    for s in sents:
        m = pattern.search(s)
        if m:
            return s, m
    return None


def extract(article: Article) -> list[Extracted]:
    text = article.abstract or ""
    if not text.strip():
        return []
    sents = sentences(text)
    out: list[Extracted] = []

    def add(field: str, value: str, evidence: str, method: str, note: str = "") -> None:
        if evidence and evidence in text:  # provenance guard: evidence must be verbatim
            out.append(Extracted(article.pmid, field, value, evidence, method, note=note))

    designs = []
    for s in sents:
        for m in DESIGN_STATED.finditer(s):
            term = m.group(1).lower()
            if not any(term in d or d in term for d in designs):
                designs.append(term)
                add("study_design_stated", m.group(1), s, "rule:design_terms")

    # Sample size: every candidate is kept for the note; the suggested value is the one
    # with the strongest phrasing, demoting counts that look like events/subgroups.
    candidates = []  # (rank, position, sentence, n, rule)
    for rank, (name, pat) in enumerate(SAMPLE_PATTERNS):
        for si, s in enumerate(sents):
            for m in pat.finditer(s):
                raw = m.group(1).strip()
                n = int(raw.replace(",", "")) if raw[0].isdigit() else words_to_int(raw)
                if not n:
                    continue
                penalty = 10 if _EVENT_AFTER.match(s, m.end()) else 0
                candidates.append((rank + penalty, si, s, n, name))
    if candidates:
        candidates.sort(key=lambda c: (c[0], c[1]))
        distinct = sorted({c[3] for c in candidates})
        rank, _, s, n, name = candidates[0]
        note = "" if len(distinct) == 1 else (
            f"Several counts reported ({', '.join(map(str, distinct[:8]))}); check which is the study population.")
        if rank >= 10:
            note = ("Only counts followed by a percentage were found (often events, not the cohort). " + note).strip()
        add("sample_size", str(n), s, f"rule:{name}", note)

    for label, pat in INTERVENTION_TERMS:
        hit = _first_sentence(sents, re.compile(pat, re.I))
        if hit:
            add("intervention", label, hit[0], "rule:intervention_terms")

    hit = _first_sentence(sents, COMPARATOR)
    if hit:
        add("comparator", hit[1].group(0), hit[0], "rule:comparison_phrase",
            "Sentence contains a comparison; the comparator itself must be read from the evidence.")

    hit = _first_sentence(sents, FOLLOW_UP)
    if hit:
        m = hit[1]
        if m.group(1):
            value = f"{m.group(1)} {m.group(2)}"
        else:
            value = f"{m.group(3)} {m.group(4)}" + ("" if m.group(3) == "1" else "s")
        add("follow_up", value, hit[0], "rule:follow_up",
            "Timing as stated; may describe one assessment rather than total follow-up.")

    for s in sents:
        for m in OUTCOME.finditer(s):
            add("outcome_statements", m.group(0).strip(), s, "rule:percent_outcome")
        ratio_spans = []
        for m in EFFECT.finditer(s):
            ratio_spans.append(m.span())
            add("effect_estimates", _balanced(m.group(0)), s, "rule:ratio_with_ci")
        for m in ESTIMATE_CI.finditer(s):
            if not any(a <= m.start() < b for a, b in ratio_spans):
                add("effect_estimates", _balanced(m.group(0)), s, "rule:estimate_with_ci")
        for m in P_VALUE.finditer(s):
            add("p_values", m.group(0), s, "rule:p_value")
        for m in NCT.finditer(s):
            add("trial_registration", m.group(0), s, "rule:nct_id")
        if LIMITATION.search(s):
            add("limitations", "stated in abstract", s, "rule:limitation_language")
    return dedupe(out)


def dedupe(items: list[Extracted]) -> list[Extracted]:
    seen, out = set(), []
    for e in items:
        key = (e.pmid, e.field, e.value, e.evidence)
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out


def summary_row(article: Article, items: list[Extracted]) -> dict:
    """One row per article: field -> '; '-joined values (None when not reported)."""
    row = {"pmid": article.pmid, "title": article.title, "url": article.url,
           "evidence_source": "abstract only" if article.abstract else "no abstract available"}
    for f in FIELDS:
        vals = [e.value for e in items if e.field == f]
        row[f] = "; ".join(dict.fromkeys(vals)) if vals else None
    notes = [f"{e.field}: {e.note}" for e in items if e.note and e.field == "sample_size"]
    row["notes"] = "; ".join(notes)
    return row
