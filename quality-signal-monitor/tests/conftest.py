"""Shared helpers. All data built here is SYNTHETIC test data."""

import csv
import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
CURRENT = FIXTURES / "synthetic_current"
PREVIOUS = FIXTURES / "synthetic_previous"


def read_rows(path):
    with path.open(newline="", encoding="utf-8") as fh:
        r = csv.reader(fh)
        header = next(r)
        return header, list(r)


def write_rows(path, header, rows):
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


@pytest.fixture
def release_copy(tmp_path):
    """Copy the synthetic current release so a test can edit it."""
    def make(src=CURRENT, name="release"):
        dst = tmp_path / name
        shutil.copytree(src, dst)
        return dst
    return make


def edit_csv(path, fn):
    """Apply fn(header, rows) -> (header, rows) to a CSV in place."""
    header, rows = read_rows(path)
    header, rows = fn(header, rows)
    write_rows(path, header, rows)
