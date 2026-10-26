"""The labelled development set must not regress.

These cases were written by an independent adversarial reviewer and then used to tune
the rules, so the numbers here are *development* results, not an accuracy estimate.
The held-out set (eval/heldout_set.json) is measured separately and never tuned on.
"""
from pathlib import Path

from teachback.evaluation import score

DEV = Path(__file__).resolve().parents[1] / "eval" / "dev_set.json"


def test_dev_set_does_not_regress():
    r = score(DEV)
    assert r["teachback"]["sensitivity"] >= 0.97 and r["teachback"]["specificity"] >= 0.98
    assert r["fidelity"]["sensitivity"] >= 0.98 and r["fidelity"]["specificity"] >= 0.97
    for k in ("E", "C", "M"):
        assert r["safety"][k]["rate"] == 1.0, (k, r["misses"]["safety"])
    assert r["safety"]["N"]["rate"] >= 0.9
