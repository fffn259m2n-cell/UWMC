"""Readability estimates (Flesch-Kincaid grade, Flesch reading ease) for English text.

Syllables are counted with a standard vowel-group heuristic, so values are
approximate. Health-literacy guidance commonly recommends patient materials at
about a 6th- to 8th-grade reading level.
"""

from __future__ import annotations

import re

TARGET_GRADE = 8.0


def syllables(word: str) -> int:
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    if len(w) <= 3:
        return 1
    w = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", w)
    w = re.sub(r"^y", "", w)
    return max(1, len(re.findall(r"[aeiouy]{1,2}", w)))


def stats(text: str) -> dict:
    sents = [s for s in re.split(r"[.!?]+(?:\s+|$)", text or "") if re.search(r"[A-Za-z]", s)]
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", text or "")
    if not sents or not words:
        return {"words": 0, "sentences": 0, "fk_grade": None, "reading_ease": None,
                "words_per_sentence": None, "long_words_pct": None}
    syl = [syllables(w) for w in words]
    wps = len(words) / len(sents)
    spw = sum(syl) / len(words)
    return {
        "words": len(words),
        "sentences": len(sents),
        "words_per_sentence": round(wps, 1),
        "fk_grade": round(0.39 * wps + 11.8 * spw - 15.59, 1),
        "reading_ease": round(206.835 - 1.015 * wps - 84.6 * spw, 1),
        "long_words_pct": round(100 * sum(1 for s in syl if s >= 3) / len(words), 1),
    }
