"""Topic configuration loaded from config/topics.yaml."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

PACKAGED_CONFIG = Path(__file__).with_name("default_topics.yaml")


def default_config() -> Path:
    """config/topics.yaml in the working directory if present, else the packaged copy."""
    local = Path("config") / "topics.yaml"
    return local if local.exists() else PACKAGED_CONFIG


class ConfigError(ValueError):
    pass


@dataclass
class Category:
    key: str
    label: str
    patterns: list[re.Pattern]


@dataclass
class Topic:
    key: str
    title: str
    description: str
    pubmed_query: str
    trial_condition: str
    trial_intervention: str
    trial_statuses: list[str]
    trial_max_records: int
    scope_groups: list[list[re.Pattern]]
    other_ep: list[re.Pattern]
    categories: list[Category] = field(default_factory=list)


def _compile(patterns, where: str) -> list[re.Pattern]:
    try:
        return [re.compile(p, re.IGNORECASE) for p in patterns]
    except re.error as exc:
        raise ConfigError(f"Invalid pattern in {where}: {exc}") from exc


def load_topic(name: str, path: Path | None = None) -> Topic:
    path = Path(path or default_config())
    if not path.exists():
        raise ConfigError(f"Topic config not found: {path}")
    data = yaml.safe_load(path.read_text()) or {}
    topics = data.get("topics", {})
    if name not in topics:
        raise ConfigError(f"Unknown topic '{name}'. Available: {', '.join(topics) or 'none'}")
    t = topics[name]
    try:
        trials = t["trials"]
        return Topic(
            key=name,
            title=t["title"],
            description=t.get("description", ""),
            pubmed_query=" ".join(t["pubmed_query"].split()),
            trial_condition=trials["condition"],
            trial_intervention=trials.get("intervention", ""),
            trial_statuses=list(trials.get("statuses", [])),
            trial_max_records=int(trials.get("max_records", 1000)),
            scope_groups=[_compile(g, f"{name}.scope") for g in t["scope"]["all_of"]],
            other_ep=_compile(t.get("other_ep_patterns", []), f"{name}.other_ep_patterns"),
            categories=[Category(c["key"], c["label"], _compile(c["patterns"], f"{name}.{c['key']}"))
                        for c in t.get("categories", [])],
        )
    except KeyError as exc:
        raise ConfigError(f"Topic '{name}' is missing required key {exc}") from exc
