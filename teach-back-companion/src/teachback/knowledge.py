"""Curated education library (general information, separate from the patient's care plan)."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib import resources

from . import text
from .plans import check_content

LEVELS = ("simple", "standard", "detailed")


@lru_cache(maxsize=1)
def library() -> dict:
    data = json.loads(resources.files("teachback").joinpath("data/knowledge/library.json").read_text())
    for t in data["topics"]:
        missing = [lv for lv in LEVELS if not t["levels"].get(lv)]
        if missing:
            raise ValueError(f"topic {t['id']} missing levels {missing}")
        check_content(f"library:{t['id']}", *t["levels"].values(), *t["key_points"], *t["questions_to_ask"])
    for g in data["glossary"]:
        check_content(f"glossary:{g['term']}", g["definition"])
    return data


def topic(topic_id: str) -> dict | None:
    return next((t for t in library()["topics"] if t["id"] == topic_id), None)


def _mentions(message: str, phrases) -> bool:
    return any(text.find_phrase(message, p) for p in phrases)


def find_topic(message: str, allowed: set[str] | None = None) -> dict | None:
    """Best topic for a message; longest alias wins."""
    best, best_len = None, 0
    for t in library()["topics"]:
        if allowed is not None and t["id"] not in allowed:
            continue
        for a in t["aliases"] + [t["title"]]:
            if len(a) > best_len and text.find_phrase(message, a):
                best, best_len = t, len(a)
    return best


def find_term(message: str) -> dict | None:
    best, best_len = None, 0
    for g in library()["glossary"]:
        for a in g["aliases"]:
            if len(a) > best_len and re.search(rf"(?<![a-z]){re.escape(a)}(?![a-z])", text.normalize(message)):
                best, best_len = g, len(a)
    return best
