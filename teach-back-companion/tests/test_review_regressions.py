"""Regression tests from an independent adversarial review (every case was reproduced first).

Grouped by the review's findings. All inputs are synthetic.
"""

import pytest

from teachback import chat, safety
from teachback.fidelity import evaluate_item
from teachback.teachback import check

from conftest import TODAY


# ---------------------------------------------------------------- 1. emergency wording
@pytest.mark.parametrize("msg", [
    "my chest feels heavy", "there's a pressure in my chest", "I can barely breathe",
    "I'm having trouble breathing", "I'm gasping for air", "it hurts to breathe",
    "I'm bleeding a lot and it won't stop", "I am bleeding and it will not stop",
    "my eliquis is making me bleed a lot and it won't stop", "there's blood in my vomit",
    "I have a severe headache", "my face looks droopy", "my words are slurred", "I'm slurring my words",
    "I feel like I'm going to pass out", "I collapsed", "my throat is closing up",
    "I took two doses by accident", "I took an extra pill by mistake",
])
def test_emergency_wording(msg):
    assert safety.screen(msg).level == "emergency", msg


@pytest.mark.parametrize("msg", ["I want to die", "I'm thinking of ending it", "I want to end it all"])
def test_crisis_wording(msg):
    assert safety.screen(msg).level == "crisis"


@pytest.mark.parametrize("msg", ["I'm not confused", "I don't have chest pain", "no trouble breathing today"])
def test_negated_symptoms_are_not_emergencies(msg):
    assert safety.screen(msg).level != "emergency"


def test_teachback_conditional_does_not_raise_banner():
    assert safety.screen("If I have chest pain I call 911", context="teachback").level == "none"
    assert safety.screen("I have chest pain right now", context="teachback").level == "emergency"


# ---------------------------------------------------------------- 2. negated concepts are not coverage
@pytest.mark.parametrize("item,said", [
    ("warn-stroke", "Never call 911 for chest pain, fainting or a drooping face"),
    ("warn-stroke", "If my face droops I don't need to call 911"),
    ("warn-stroke", "I will not call 911, I'll call my daughter"),
    ("med-apixaban", "I don't have to keep taking it after my bottle is done"),
])
def test_afib_negated_coverage(afib, item, said):
    r = check(afib, item, said)
    assert r.concerns, said


def test_hf_negated_coverage(hf):
    assert check(hf, "warn-weight-gain", "If I gain 2 pounds in a day or 5 pounds in a week I don't need to call").concerns
    assert check(hf, "med-carvedilol", "6.25 mg twice a day but not with food").concerns
    assert check(hf, "med-carvedilol", "twice a day without food").concerns


def test_pna_negated_coverage(pna):
    assert check(pna, "med-amox-clav", "I don't have to finish them if I feel better").concerns


# ---------------------------------------------------------------- 3. fidelity 911 checks
def test_negated_911(afib, pna):
    r = evaluate_item(afib, afib.item("warn-stroke"),
                      "Do not call 911 for chest pain, fainting, sudden weakness or numbness on one side, trouble speaking or a drooping face. Call the clinic.")
    assert any(i.severity == "critical" for i in r.issues)
    r = evaluate_item(pna, pna.item("warn-pna-911"),
                      "If it is hard to breathe, your lips look blue or gray, or you get confused, do not call 911; call your clinic.")
    assert any(i.severity == "critical" for i in r.issues)


def test_signs_moved_from_911_to_clinic(afib, hf):
    r = evaluate_item(afib, afib.item("warn-stroke"),
                      "Call 911 for chest pain. Call the clinic if you faint, feel weak or numb on one side, have trouble speaking, or your face droops.")
    assert any(i.check == "emergency_sign_not_with_911" for i in r.issues)
    r = evaluate_item(hf, hf.item("warn-911"),
                      "Call 911 for chest pain or fainting. Call the clinic if you are very short of breath or cannot catch your breath while resting.")
    assert any(i.check == "emergency_sign_not_with_911" for i in r.issues)


# ---------------------------------------------------------------- 4. fidelity dose and limit changes
def blocking(rep):
    return [i for i in rep.issues if i.severity in ("critical", "major")]


@pytest.mark.parametrize("item,candidate", [
    ("med-apixaban", "Apixaban: take 2 tablets twice a day, about 12 hours apart. Do not stop unless your cardiologist tells you to."),
    ("med-apixaban", "Apixaban: take one 5 mg pill twice a day, 12 hours apart, plus one extra at bedtime. Do not stop unless your cardiologist tells you to."),
    ("med-apixaban", "Apixaban: take one 5 mg pill twice a day or once a day, about 12 hours apart. Do not stop unless your cardiologist tells you to."),
    ("warn-heart-rate", "Call the cardiology clinic if your resting heart rate stays below 110 beats per minute, or if you are more short of breath."),
])
def test_afib_dose_changes(afib, item, candidate):
    assert blocking(evaluate_item(afib, afib.item(item), candidate)), candidate


@pytest.mark.parametrize("item,candidate", [
    ("med-furosemide", "Furosemide is a water pill. Take one 40 mg pill once a day in the morning and once at night."),
    ("warn-weight-gain", "Call the heart failure clinic if you gain more than 5 pounds in one day or more than 2 pounds in one week."),
    ("warn-weight-gain", "If you gain more than 2 pounds in one day or 5 pounds in one week, wait for your next visit; do not call the clinic."),
    ("ins-sodium-fluid", "Eat at least 2,000 mg of sodium (salt) a day. Drink at least 2 liters of fluid a day, about 8 cups."),
])
def test_hf_dose_changes(hf, item, candidate):
    assert blocking(evaluate_item(hf, hf.item(item), candidate)), candidate


def test_acetaminophen_minimum(pna):
    c = "Acetaminophen (Tylenol): take 2 pills (650 mg) every 6 hours if needed. Take at least 3,000 mg in 24 hours."
    assert blocking(evaluate_item(pna, pna.item("med-acetaminophen"), c))


# ---------------------------------------------------------------- 5. negation lost without the verb
def test_negation_lost_without_verb(afib, pna):
    c = "Apixaban: take one 5 mg pill twice a day, 12 hours apart. It is not necessary to keep taking apixaban once you feel better."
    assert blocking(evaluate_item(afib, afib.item("med-apixaban"), c))
    c = "Amoxicillin-clavulanate 875 mg/125 mg: one pill twice a day with food for 5 more days. It is okay not to finish the pills if you feel better."
    assert blocking(evaluate_item(pna, pna.item("med-amox-clav"), c))


# ---------------------------------------------------------------- 6. NSAID negation tricks
@pytest.mark.parametrize("said", [
    "No Tylenol, ibuprofen is fine", "Tylenol is not good, I'll use Aleve", "Not only Tylenol, Aleve is fine too",
    "No problem taking ibuprofen with it", "I don't mind taking Advil", "I will not stop taking Advil for my back",
    "No more Tylenol, only Advil from now on", "I never have issues with Advil so I'll keep using it",
])
def test_nsaid_negation_tricks(afib, said):
    assert ("contradiction", "no-nsaids") in {(c.kind, c.fact_id) for c in check(afib, "ins-pain-medicine", said).concerns}, said


@pytest.mark.parametrize("said", [
    "I can take Tylenol but not ibuprofen or Aleve.", "No ibuprofen, no Advil, no Aleve. Tylenol is OK.",
    "Do not take ibuprofen (Advil, Motrin) or naproxen (Aleve); Tylenol is fine.",
])
def test_nsaid_correct_still_clean(afib, said):
    assert not check(afib, "ins-pain-medicine", said).concerns, said


def test_cant_wait_to_stop(afib):
    assert check(afib, "med-apixaban", "I can't wait to stop taking it").concerns


# ---------------------------------------------------------------- 7. medication-change requests
@pytest.mark.parametrize("msg", [
    "is it ok if I don't take my water pill today", "I ran out of apixaban", "I missed my apixaban dose",
    "I didn't take my medicine yesterday", "I stopped taking my metoprolol", "I'm going to stop my eliquis",
    "I don't want to take my pills anymore", "should I take an extra lasix", "Can I take 2 lasix today since my weight is up?",
    "I double up on my water pill", "can I take advil with my eliquis", "is it okay to take aleve",
    "I need to cut my pills in half", "can I take my metoprolol at night instead", "is ibuprofen ok for my headache",
])
def test_medication_change_requests(msg):
    assert safety.screen(msg).level in ("refer", "emergency"), msg


def test_informational_drug_questions_not_refused():
    for msg in ["What is apixaban for?", "What does metoprolol do?", "tell me about advil"]:
        assert safety.screen(msg).level == "none", msg


# ---------------------------------------------------------------- 8. chat shows the NSAID instruction
def test_chat_nsaid_questions_show_plan_rule(afib):
    for msg in ["tell me about advil", "can I take advil with my eliquis", "is ibuprofen ok for my headache"]:
        a = chat.answer(afib, msg, today=TODAY)
        assert any(b.ref == "ins-pain-medicine" for b in a.blocks), msg


def test_chat_water_pill_shows_plan_item(hf):
    a = chat.answer(hf, "is it ok if I don't take my water pill today", today=TODAY)
    assert any(b.ref == "med-furosemide" for b in a.blocks)


# ---------------------------------------------------------------- 9. wrong frequencies in teach-back
def test_wrong_frequencies(afib, hf):
    assert check(hf, "med-furosemide", "I take 40 mg in the morning and again at night").concerns
    assert check(afib, "med-apixaban", "I take one 5 mg pill a day").concerns
    assert check(afib, "med-apixaban", "5 mg every morning").concerns
    assert check(hf, "med-furosemide", "Once a day in the morning, but I skip it if I am going out").concerns


def test_twice_daily_phrasings_ok(afib):
    for said in ["5 mg every morning and every night, I keep taking it every day",
                 "one 5 mg pill in the morning and one at night, and I never stop unless my cardiologist says"]:
        r = check(afib, "med-apixaban", said)
        assert not r.concerns, (said, r.concerns)


# ---------------------------------------------------------------- 10. spurious concerns
def test_correct_explanations_not_flagged(afib, pna):
    assert not check(afib, "med-apixaban", "Twice a day. I wouldn't stop it unless my cardiologist says").concerns
    assert not check(pna, "med-amox-clav", "Twice a day with food. Don't stop until they are all gone, even if I feel better").concerns
    assert not check(pna, "ins-recovery", "I rest, drink fluids, and I should stop smoking").concerns
    assert not check(pna, "ins-recovery", "Rest, fluids, and quit smoking").concerns


@pytest.mark.parametrize("plan_id,item,candidate", [
    ("pna-demo", "ins-recovery", "Rest and drink plenty of fluids. Please stop smoking. Your cough may last a few weeks."),
    ("pna-demo", "ins-recovery", "Rest and drink plenty of fluids. Smoking is not allowed. Your cough may last a few weeks."),
    ("afib-demo", "med-metoprolol", "Metoprolol (Toprol) 25 mg: one pill once a day in the morning. Swallow it whole; crushing or chewing is not allowed."),
    ("afib-demo", "med-apixaban", "Apixaban: one 5 mg pill 2 times daily, about 12 hours apart. Do not stop unless your cardiologist tells you to."),
    ("afib-demo", "med-apixaban", "Apixaban: one 5 mg pill two times every day, 12 hours apart. Do not stop unless your cardiologist tells you to."),
    ("afib-demo", "med-apixaban", "Apixaban 5 mg: one in the morning and one at night, 12 hours apart. Do not stop unless your cardiologist tells you to."),
    ("hf-demo", "med-sacval", "Entresto (sacubitril/valsartan) 24/26 mg: take one pill twice a day."),
    ("pna-demo", "med-acetaminophen", "Acetaminophen (Tylenol): 2 pills (650 mg) every 6 hours if needed. Never more than 3,000 mg in one day (24 hours)."),
    ("hf-demo", "warn-911", "Call nine-one-one if you are very short of breath, have chest pain, faint, or cannot catch your breath when resting."),
    ("afib-demo", "ins-pain-medicine", "Avoid pain pills called NSAIDs, like ibuprofen (Advil, Motrin) or naproxen (Aleve). Acetaminophen (Tylenol) is OK if you follow the package directions."),
])
def test_faithful_rewrites_not_flagged(plans, plan_id, item, candidate):
    plan = plans[plan_id]
    rep = evaluate_item(plan, plan.item(item), candidate)
    assert not blocking(rep), (candidate, rep.issues)


# ---------------------------------------------------------------- 11. bare numbers
def test_bare_numbers(afib, pna):
    assert check(afib, "warn-heart-rate", "I call the clinic if my heart rate stays above 150").concerns
    assert check(afib, "warn-heart-rate", "call if my pulse is over 130").concerns
    r = check(pna, "warn-pna-clinic", "I call the clinic if I have a fever above 103 after 3 days")
    assert r.concerns and not any(c["fact_id"] == "fever-101" for c in r.covered)
    assert check(afib, "appt-cardiology", "I see cardiology in 2 months and bring my pill bottles").concerns


# ---------------------------------------------------------------- 12. last_topic must belong to the plan
def test_last_topic_validated(afib):
    a = chat.answer(afib, "explain that more simply", last_topic="heart-failure", today=TODAY)
    assert all(b.ref != "heart-failure" for b in a.blocks)
    a = chat.answer(afib, "tell me more", last_topic="furosemide", today=TODAY)
    assert all(b.ref != "furosemide" for b in a.blocks)


# ---------------------------------------------------------------- minor findings
def test_spanish_frequency_and_stop(afib):
    c = "El apixabán: tome una pastilla de 5 mg una vez al día. Puede dejar de tomar apixabán cuando se sienta mejor."
    rep = evaluate_item(afib, afib.item("med-apixaban"), c, "es")
    assert any(i.severity == "critical" for i in rep.issues)


def test_cut_in_half_and_beers(afib):
    assert check(afib, "med-metoprolol", "25 mg once a day in the morning, and I can cut it in half").concerns
    assert check(afib, "ins-activity", "I can have three beers a day").concerns
