"""Shared fixtures. Everything here is SYNTHETIC test data."""

from pathlib import Path

import pytest

from ep_copilot.config import load_topic
from ep_copilot.storage import Store

FIX = Path(__file__).parent / "fixtures"
API = FIX / "api"
CONFIG = Path(__file__).parents[1] / "config" / "topics.yaml"


@pytest.fixture
def topic():
    return load_topic("af-ablation", CONFIG)


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "test.sqlite")
    yield s
    s.close()
