from ep_copilot.models import Article
from ep_copilot.screening import IN_SCOPE, OTHER_EP, OUT_OF_SCOPE, screen, study_design


def A(title="", abstract="", **kw):
    return Article("99000999", title=title, abstract=abstract, **kw)


def test_in_scope_with_categories_and_reason(topic):
    s = screen(A("Pulsed field ablation for atrial fibrillation",
                 "Recurrence was assessed with an insertable cardiac monitor."), topic)
    assert s.scope == IN_SCOPE and s.priority == "high"
    assert {"Pulsed-field ablation", "AF recurrence", "Rhythm monitoring"} <= set(s.categories)
    assert "Matches scope terms" in s.reasons[0]
    assert "insertable cardiac monitor" in s.matched_terms["Rhythm monitoring"]


def test_other_ep_kept_and_labelled(topic):
    s = screen(A("Ventricular tachycardia ablation", "Substrate mapping in 64 patients."), topic)
    assert s.scope == OTHER_EP and s.priority == "low"


def test_outside_scope_kept(topic):
    s = screen(A("Sodium and blood pressure", "Salt intake."), topic)
    assert s.scope == OUT_OF_SCOPE and s.priority == "low" and s.reasons


def test_no_abstract_is_uncertain_not_discarded(topic):
    s = screen(A("Editorial: the future of catheter ablation of atrial fibrillation"), topic)
    assert s.uncertain and s.scope == IN_SCOPE and s.priority == "review"
    s2 = screen(A("Editorial: a new era"), topic)
    assert s2.uncertain and s2.priority == "review"


def test_mesh_terms_count_toward_scope(topic):
    s = screen(A("A new approach", "We studied outcomes.", mesh_terms=["Atrial Fibrillation", "Catheter Ablation"]), topic)
    assert s.scope == IN_SCOPE


def test_study_design_prefers_publication_type_and_is_descriptive():
    assert study_design(A(abstract="randomized", publication_types=["Case Reports"])) == "Case report"
    assert study_design(A(abstract="This retrospective cohort...")) == "Registry / observational cohort (from abstract wording)"
    assert study_design(A()) == "Not determined"


def test_af_abbreviation_needs_word_boundary(topic):
    s = screen(A("Ablation in LEAF valves", "Leaf ablation."), topic)
    assert s.scope != IN_SCOPE


def test_priority_counts_categories(topic):
    one = screen(A("Catheter ablation for atrial fibrillation", "Recurrence was common."), topic)
    two = screen(A("Pulsed field ablation for atrial fibrillation", "Recurrence was common."), topic)
    none = screen(A("Catheter ablation for atrial fibrillation", "We describe outcomes and safety."), topic)
    assert (one.priority, two.priority, none.priority) == ("medium", "high", "low")


def test_generic_query_words_do_not_create_categories(topic):
    s = screen(A("Catheter ablation for atrial fibrillation", "Efficacy, safety and outcomes at follow-up."), topic)
    assert s.categories == []


def test_protocol_and_title_based_design():
    assert study_design(A("Design and rationale of a randomized trial of ablation", "Methods follow.")) == \
        "Protocol / design paper (from abstract wording)"
    assert study_design(A("Ablation versus sham: a systematic review", "We pooled randomized trials.")) == \
        "Systematic review / meta-analysis (from abstract wording)"
