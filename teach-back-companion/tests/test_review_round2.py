"""Regression tests from the second adversarial review round (all cases were reproduced first)."""

import pytest

from teachback import chat, safety
from teachback.fidelity import evaluate_item
from teachback.teachback import check

from conftest import TODAY


def blocking(rep):
    return [i for i in rep.issues if i.severity in ("critical", "major")]


# ---------------------------------------------------------------- R1 / M1: emergencies
@pytest.mark.parametrize("msg", [
    "I don't know why my chest hurts so much", "I never felt chest pain like this before",
    "I've never had pain in my chest like this", "I had to quit mowing because of chest pressure",
    "How do I stop this chest pain", "I'm not okay my chest hurts", "I cannot tell if my face is drooping",
    "no wait my chest hurts", "What is this crushing chest pain", "Explain why chest is so tight now",
    "my nose won't stop bleeding", "I can't stop the bleeding", "I am bleeding heavily",
    "I can hardly breathe", "I can't get enough air", "I'm out of breath just sitting here",
    "my face feels numb on one side", "I can't lift my arm", "my speech is garbled",
    "I suddenly can't see out of one eye",
])
def test_emergencies_round2(msg):
    assert safety.screen(msg).level == "emergency", msg


@pytest.mark.parametrize("msg", ["I don't want to wake up tomorrow", "I have no reason to live"])
def test_crisis_round2(msg):
    assert safety.screen(msg).level == "crisis"


def test_teachback_present_symptom_not_ignored():
    assert safety.screen("when I woke up my arm was numb and it still is", context="teachback").level == "emergency"


@pytest.mark.parametrize("msg", ["Tell me about stroke", "I had a stroke 5 years ago, what does afib have to do with it",
                                 "I fainted last year, is that related to afib?", "no trouble breathing today"])
def test_history_and_education_not_emergency(msg):
    assert safety.screen(msg).level != "emergency", msg


# ---------------------------------------------------------------- R2 / R3: negation regressions
@pytest.mark.parametrize("said", [
    "Twice a day. Do not stop or skip it unless my cardiologist says",
    "Twice a day and I would never stop or skip a dose",
    "Twice a day. Do not, under any circumstances, stop it",
    "Twice a day. I will never, ever stop it",
])
def test_apixaban_negations_hold(afib, said):
    assert not check(afib, "med-apixaban", said).concerns, said


@pytest.mark.parametrize("said", ["No ibuprofen and no naproxen. Tylenol is OK.",
                                  "I shouldn't take ibuprofen, which is Advil. Tylenol is fine.",
                                  "Tylenol is fine, Advil is not",
                                  "I stopped taking ibuprofen because of the apixaban, Tylenol is fine",
                                  "Stay off ibuprofen and naproxen; Tylenol is OK."])
def test_nsaid_negations_hold(afib, said):
    assert not check(afib, "ins-pain-medicine", said).concerns, said


def test_amox_and_apap_negations_hold(pna):
    assert not check(pna, "med-amox-clav", "Twice a day with food, I don't stop or quit early, I finish all the pills").concerns
    assert not check(pna, "med-acetaminophen", "650 mg every 6 hours if I need it, and I stop at 3,000 mg in 24 hours").concerns
    assert not check(pna, "ins-recovery", "I rest and drink fluids. Smoking it is not allowed.").concerns


@pytest.mark.parametrize("item,candidate", [
    ("med-apixaban", "Apixaban: one 5 mg pill twice a day, 12 hours apart. Do not stop or skip apixaban unless your cardiologist tells you to."),
    ("med-apixaban", "Apixaban: one 5 mg pill twice a day, 12 hours apart. Do not, for any reason, stop taking apixaban unless your cardiologist says so."),
    ("med-apixaban", "Apixaban: one 5 mg pill twice a day, 12 hours apart. Keep taking it. Only your cardiologist can tell you to stop."),
    ("ins-pain-medicine", "Do not take ibuprofen, also sold as Advil or Motrin, or naproxen, also sold as Aleve, while on apixaban. Acetaminophen (Tylenol) is OK if you follow the package directions."),
    ("med-metoprolol", "Metoprolol (Toprol) 25 mg: one pill once a day in the morning. Swallow it whole; do not crush, chew, or split it."),
])
def test_faithful_afib_rewrites(afib, item, candidate):
    assert not blocking(evaluate_item(afib, afib.item(item), candidate)), candidate


# ---------------------------------------------------------------- R4: direction false alarms
def test_direction_equivalents(hf, pna):
    c = "Keep sodium (salt) under 2,000 mg a day. Keep all fluids under 2 liters (about 8 cups) a day."
    assert not blocking(evaluate_item(hf, hf.item("ins-sodium-fluid"), c))
    c = "Acetaminophen (Tylenol): 2 pills (650 mg) every 6 hours if needed. Never go over 3,000 mg in 24 hours."
    assert not blocking(evaluate_item(pna, pna.item("med-acetaminophen"), c))


# ---------------------------------------------------------------- M2: dangerous teach-backs
@pytest.mark.parametrize("item,said", [
    ("warn-stroke", "I'd skip 911 and call my son to take me in"),
    ("warn-stroke", "For a drooping face I wait to see if it passes"),
    ("med-apixaban", "Twice a day, and I can come off it when I feel fine"),
    ("med-apixaban", "Twice a day. Once the bottle is empty I'm done with it"),
])
def test_dangerous_afib_teachbacks(afib, item, said):
    assert check(afib, item, said).concerns, said


@pytest.mark.parametrize("item,said", [
    ("warn-weight-gain", "If I gain 2 pounds in a day or 5 in a week I'd hold off on calling till my visit"),
    ("med-furosemide", "40 mg once a day in the morning, and a second one in the evening if my legs swell"),
    ("med-furosemide", "Once a day in the morning, but on days I go out I leave it out"),
    ("ins-sodium-fluid", "No more than 2,000 mg of salt, and I should drink at least 2 liters a day"),
])
def test_dangerous_hf_teachbacks(hf, item, said):
    assert check(hf, item, said).concerns, said


def test_dangerous_other_teachbacks(afib, pna):
    assert check(afib, "warn-heart-rate", "I call the clinic if my resting heart rate stays below 110").concerns
    assert check(pna, "med-amox-clav", "Twice a day with food, and I can leave the rest if I feel better").concerns


# ---------------------------------------------------------------- M3: dangerous rewrites
def test_dangerous_rewrites(afib, hf):
    c = "Call 911 right away, or have someone drive you, if you have chest pain, faint, feel weak or numb on one side, have trouble speaking or your face droops."
    assert blocking(evaluate_item(afib, afib.item("warn-stroke"), c))
    c = "If you gain more than 2 pounds in one day or more than 5 pounds in one week, watch it for a few days before calling the heart failure clinic."
    assert blocking(evaluate_item(hf, hf.item("warn-weight-gain"), c))
    c = "Eat no more than 2,000 mg of sodium a day. Drink 2 liters (about 8 cups) of fluids or more a day."
    assert blocking(evaluate_item(hf, hf.item("ins-sodium-fluid"), c))
    c = "Furosemide is a water pill. Take one 40 mg pill once a day in the morning. If your legs swell, take a second tablet."
    assert blocking(evaluate_item(hf, hf.item("med-furosemide"), c))


# ---------------------------------------------------------------- medication-change detection
def test_med_change_round2():
    assert safety.screen("I'm thinking about not taking my water pill on Saturday").level == "refer"


@pytest.mark.parametrize("msg", ["What should I bring to my appointment with my pills?", "Can you explain more about apixaban?",
                                 "Do I take apixaban with food?", "Why do I take metoprolol in the morning?"])
def test_informational_not_refused(msg):
    assert safety.screen(msg).level == "none", msg


def test_appointment_question_shows_appointment(afib):
    a = chat.answer(afib, "What should I bring to my appointment with my pills?", today=TODAY)
    assert any(b.ref == "appt-cardiology" for b in a.blocks)
