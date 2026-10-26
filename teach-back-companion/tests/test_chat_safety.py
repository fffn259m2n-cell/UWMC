
import pytest
from conftest import TODAY

from teachback import chat, safety


@pytest.mark.parametrize("msg,level", [
    ("I have chest pain right now", "emergency"),
    ("my face is drooping and I can't talk", "emergency"),
    ("I can't breathe", "emergency"),
    ("I passed out this morning", "emergency"),
    ("I'm throwing up blood", "emergency"),
    ("I took too many pills", "emergency"),
    ("I want to kill myself", "crisis"),
    ("Can I stop my metoprolol?", "refer"),
    ("I missed a dose of apixaban", "refer"),
    ("Should I take more furosemide?", "refer"),
    ("Do I have cancer?", "refer"),
    ("My potassium was 5.8", "refer"),
    ("What is apixaban for?", "none"),
])
def test_safety_levels(msg, level):
    assert safety.screen(msg).level == level


def test_emergency_answer_shows_911_and_warning_items_only(afib):
    a = chat.answer(afib, "I have chest pain", today=TODAY)
    assert a.safety["level"] == "emergency" and "911" in a.blocks[0].text
    assert {b.ref for b in a.blocks if b.source == "care_plan"} == {"warn-stroke", "warn-heart-rate"}
    assert not any(b.source == "education" for b in a.blocks)


def test_medication_change_quotes_plan_and_refers(afib):
    a = chat.answer(afib, "Can I stop apixaban?", today=TODAY)
    assert a.safety["level"] == "refer"
    plan_blocks = [b for b in a.blocks if b.source == "care_plan" and b.ref == "med-apixaban"]
    assert plan_blocks and plan_blocks[0].text == afib.item("med-apixaban").original
    assert any("Pharmacist" in b.text for b in a.blocks)


def test_drug_question_separates_plan_and_education(afib):
    a = chat.answer(afib, "What is apixaban for?", today=TODAY)
    assert [b.source for b in a.blocks] == ["care_plan", "education"]
    assert a.blocks[1].url.startswith("https://medlineplus.gov/")
    assert a.topic == "apixaban"


def test_simpler_and_more_detail(afib):
    a = chat.answer(afib, "Tell me about AFib", level="standard", today=TODAY)
    s = chat.answer(afib, "Can you explain that more simply?", level=a.level, last_topic=a.topic, today=TODAY)
    assert s.level == "simple" and s.blocks[0].text.startswith("AFib means")
    d = chat.answer(afib, "Tell me more", level="simple", last_topic="atrial-fibrillation", today=TODAY)
    assert d.level == "standard"


def test_appointments_with_dates(hf):
    a = chat.answer(hf, "When is my next appointment?", today=TODAY)
    texts = " ".join(b.text for b in a.blocks)
    assert "Heart failure clinic visit in 7 days" in texts and "November 01" in texts


def test_unknown_question_does_not_guess(pna):
    a = chat.answer(pna, "What is the best diet for diabetes?", today=TODAY)
    assert a.blocks[0].label == "Not covered" and "won't guess" in a.blocks[0].text


def test_glossary_and_out_of_plan_topics(pna):
    a = chat.answer(pna, "What does antibiotic mean?", today=TODAY)
    assert a.blocks and a.blocks[0].source in ("education", "care_plan")
    # A topic from another patient's plan is not offered as if it applied to this patient.
    b = chat.answer(pna, "Explain heart failure", today=TODAY)
    assert all(blk.ref != "heart-failure" for blk in b.blocks)


def test_answer_text_comes_only_from_plan_or_library(afib):
    from teachback import knowledge
    allowed = {i.original for i in afib.items} | {d.documented_note for d in afib.diagnoses}
    lib = knowledge.library()
    allowed |= {lv for t in lib["topics"] for lv in t["levels"].values()}
    allowed |= {g["definition"] for g in lib["glossary"]}
    for q in ["What is apixaban for?", "Explain my diagnosis atrial fibrillation", "What are my warning signs?",
              "What does stroke mean?"]:
        for b in chat.answer(afib, q, today=TODAY).blocks:
            if b.source in ("care_plan", "education") and " • " not in b.text and "Planned date" not in b.text:
                assert b.text in allowed, (q, b.text)


def test_safety_net_adds_911_988_box_for_unrecognised_wording():
    from teachback import safety
    from teachback.chat import answer
    from teachback.plans import load_plans
    plan = load_plans()["afib-demo"]
    for msg in ["sometimes I feel like everyone would be better off", "my lips feel kind of funny and tingly"]:
        a = answer(plan, msg)
        assert any(b.source == "help" and "911" in b.text and "988" in b.text for b in a.blocks), msg
    # ordinary questions do not get the box
    assert not safety.screen("when is my cardiology appointment?").caution
    assert not safety.screen("What is a blood test?").caution
