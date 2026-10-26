import pytest

from teachback.teachback import check


def kinds(r):
    return {(c.kind, c.fact_id) for c in r.concerns}


def test_complete_explanation_has_no_concerns(afib):
    r = check(afib, "med-apixaban", "I take one 5 mg pill twice a day, 12 hours apart, and keep taking it every day.")
    assert not r.concerns and not r.not_mentioned
    assert "main points" in r.summary and "correct" not in r.summary.lower()


@pytest.mark.parametrize("said,expected", [
    ("I take it twice a day and I can stop when my heart feels normal again.", ("misconception", "apx-continue")),
    ("I take it once a day in the morning.", ("number_mismatch", "apx-dose")),
    ("I take 10 mg two times a day and never stop.", ("number_mismatch", "apx-dose")),
])
def test_apixaban_misunderstandings(afib, said, expected):
    assert expected in kinds(check(afib, "med-apixaban", said))


def test_do_not_instructions(afib, pna):
    assert ("contradiction", "no-nsaids") in kinds(check(afib, "ins-pain-medicine", "For pain I can take Advil."))
    ok = check(afib, "ins-pain-medicine", "I can take Tylenol but not ibuprofen or Aleve.")
    assert not ok.concerns and {c["fact_id"] for c in ok.covered} == {"no-nsaids", "tylenol-ok"}
    assert {k for k, f in kinds(check(pna, "ins-recovery", "I rest and drink fluids and I'll smoke less.")) if f == "no-smoking"}
    assert not check(pna, "ins-recovery", "I rest, drink water and I do not smoke.").concerns


def test_emergency_misconceptions(afib, hf):
    r = check(afib, "warn-stroke", "If my face droops I will drive myself to the ER.")
    assert ("misconception", "stroke-911") in kinds(r)
    r = check(hf, "warn-weight-gain", "If I gain 3 pounds I take an extra water pill and wait until my appointment.")
    k = kinds(r)
    assert ("misconception", "gain-2-5") in k and ("number_mismatch", "gain-2-5") in k
    assert r.concerns[0].severity == "critical"


def test_antibiotic_course(pna):
    assert ("misconception", "amox-finish") in kinds(check(pna, "med-amox-clav", "Twice a day with meals and I stop once my fever is gone."))
    assert not check(pna, "med-amox-clav", "Two times a day with food until all the pills are gone, for 5 more days.").concerns


def test_pill_strength_is_not_a_mismatch(pna):
    r = check(pna, "med-acetaminophen", "2 pills, 650 mg, every 6 hours if I need it, never more than 3000 mg in 24 hours. Each pill is 325 mg.")
    assert not r.concerns


def test_missing_points_listed_by_severity(hf):
    r = check(hf, "ins-sodium-fluid", "I should eat less salt.")
    assert [f["fact_id"] for f in r.not_mentioned][0] in ("sodium-2000", "fluid-2l")
    assert "not mentioned" in r.summary


def test_too_short_input(afib):
    r = check(afib, "med-apixaban", "ok")
    assert "own words" in r.summary and not r.concerns


def test_concern_quotes_original_verbatim(afib):
    item = afib.item("med-apixaban")
    r = check(afib, "med-apixaban", "I can stop when I feel better.")
    assert all(c.original == item.original for c in r.concerns)


def test_unknown_item(afib):
    with pytest.raises(KeyError):
        check(afib, "nope", "text here please")
