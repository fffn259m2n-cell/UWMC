"""Unit tests for the shared meaning-change rules (consistency.compare).

Each case names the check that must fire, or None when nothing may fire. Add a case
here whenever you add or change a rule in consistency.py.
"""
import pytest

from teachback.consistency import compare
from teachback.plans import load_plans

PLANS = load_plans()

CASES = [
    # plan, item, text, patient?, expected check (None = no change expected)
    ("hf-demo", "med-furosemide", "40 mg at bedtime", True, "time_of_day_changed"),
    ("hf-demo", "med-furosemide", "40 mg once in the morning, not at night", True, None),
    ("hf-demo", "med-carvedilol", "6.25 mg twice a day on an empty stomach", True, "food_changed"),
    ("afib-demo", "med-apixaban", "5 mg twice a day until I feel better", True, "stop_condition_added"),
    ("pna-demo", "med-amox-clav", "twice a day with food, finish them all even if I feel better", True, None),
    ("afib-demo", "med-apixaban", "I take both together at breakfast", True, "doses_combined"),
    ("afib-demo", "med-metoprolol", "two of the 25 mg metoprolol every morning", True, "tablet_count_changed"),
    ("pna-demo", "med-acetaminophen", "2 pills every 6 hours, never more than 9 pills in a day", True, None),
    ("hf-demo", "warn-weight-gain", "if I gain 2 pounds in a day I'll mention it at my next appointment", True, "action_delayed"),
    ("afib-demo", "ins-bleeding", "black stools are normal on this medicine", True, "warning_normalised"),
    ("afib-demo", "warn-stroke", "if my face droops I call my cardiologist", True, "emergency_sign_not_with_911"),
    ("afib-demo", "warn-stroke", "face drooping or trouble speaking, I call 911 and wait for the ambulance", True, None),
    ("hf-demo", "ins-sodium-fluid", "salt under 2000 mg per meal", True, "period_changed"),
    ("hf-demo", "warn-weight-gain", "call if I lose more than 2 pounds in a day", True, "direction_changed"),
    ("hf-demo", "ins-daily-weight", "I weigh myself once a week in the morning", True, "frequency_changed"),
    ("pna-demo", "ins-recovery", "rest and drink as little as possible", True, "limit_reversed"),
    ("hf-demo", "test-bmp", "the blood test is only if I feel bad", True, "instruction_dropped"),
    ("hf-demo", "test-bmp", "blood test in a week, I won't skip it", True, None),
    ("afib-demo", "warn-stroke", "Call 911 or have a family member drive you to the hospital.", False, "alternative_to_911"),
    ("hf-demo", "ins-sodium-fluid", "Eat no more than 2,000 mg of sodium a day. Aim for 2 liters of fluid a day.", False, "limit_softened"),
    ("afib-demo", "med-apixaban", "Do not stop taking apixaban unless you feel fine.", False, "exception_added"),
    ("afib-demo", "ins-pain-medicine", "Puede tomar ibuprofeno mientras toma apixabán.", False, "negation_possibly_lost"),
]


@pytest.mark.parametrize("plan,item,text,patient,expected", CASES)
def test_compare(plan, item, text, patient, expected):
    checks = {c.check for c in compare(PLANS[plan].item(item), text, patient=patient)}
    if expected is None:
        assert not checks, checks
    else:
        assert expected in checks, checks
