import pytest

from teachback import benchmark, readability
from teachback.fidelity import detect_language, evaluate_item


def checks(rep):
    return {i.check for i in rep.issues if i.severity in ("critical", "major")}


def test_every_plain_version_passes(plans):
    for plan in plans.values():
        for item in plan.items:
            rep = evaluate_item(plan, item, item.plain)
            assert not checks(rep), (plan.id, item.id, rep.issues)


def test_original_passes_against_itself(plans):
    for plan in plans.values():
        for item in plan.items:
            assert not checks(evaluate_item(plan, item, item.original)), (plan.id, item.id)


def test_benchmark_all_detected_no_false_alarms():
    r = benchmark.run()
    assert r["detected"] == r["seeded_errors"] == 30
    assert r["false_alarms"] == 0 and r["clean_cases"] == 16


@pytest.mark.parametrize("candidate,expected", [
    ("Apixaban: take one 5 mg pill twice a day, about 12 hours apart. Also take aspirin daily. Do not stop unless your cardiologist says.", "medicine_added"),
    ("A blood thinner: take one 5 mg pill twice a day, 12 hours apart. Do not stop unless your cardiologist says.", "medicine_name_missing"),
    ("Apixaban: take one 5 mg pill twice a day, about 12 hours apart, for 30 days. Do not stop unless your cardiologist says.", "number_added"),
])
def test_specific_checks(afib, candidate, expected):
    assert expected in checks(evaluate_item(afib, afib.item("med-apixaban"), candidate))


def test_non_english_reports_what_was_not_assessed(afib):
    rep = evaluate_item(afib, afib.item("med-apixaban"),
                        "El apixabán: tome una pastilla de 5 mg dos veces al día, cada 12 horas. No deje de tomarlo.", "es")
    assert rep.language == "es" and rep.not_assessed
    assert "human review" in rep.verdict


def test_verdict_never_certifies(afib):
    item = afib.item("med-apixaban")
    rep = evaluate_item(afib, item, item.plain)
    assert "review" in rep.verdict and "safe" not in rep.verdict


def test_language_detection():
    assert detect_language("Get a follow-up chest X-ray in 6 weeks.") == "en"
    assert detect_language("Tome una pastilla dos veces al día con comida.") == "es"


def test_readability():
    easy = readability.stats("Take one pill. Drink water. Call us.")
    hard = readability.stats("Pharmacological anticoagulation necessitates meticulous adherence to prescribed administration intervals.")
    assert easy["fk_grade"] < 3 < hard["fk_grade"]
    assert readability.stats("")["fk_grade"] is None
