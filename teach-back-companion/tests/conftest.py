"""All plans and texts used in tests are SYNTHETIC."""

from datetime import date

import pytest

from teachback.plans import load_plans

TODAY = date(2026, 10, 26)


@pytest.fixture(scope="session")
def plans():
    return load_plans()


@pytest.fixture
def afib(plans):
    return plans["afib-demo"]


@pytest.fixture
def hf(plans):
    return plans["hf-demo"]


@pytest.fixture
def pna(plans):
    return plans["pna-demo"]
