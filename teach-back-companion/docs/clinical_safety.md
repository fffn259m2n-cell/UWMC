# Clinical safety

The prototype provides education, explanation of documented instructions, organization of
documented tasks, and understanding checks. It does **not** diagnose, prescribe, change
doses, interpret a patient's own results, triage, or monitor.

## How the boundaries are enforced in code

| Boundary | Mechanism | Test |
|---|---|---|
| Emergencies first | `safety.screen` runs before any other logic in chat and teach-back. Chest pain, breathing trouble, stroke signs, fainting, serious bleeding, confusion, seizure, overdose and allergic swelling show "call 911 now" and the plan's own warning-sign instructions only. Self-harm language shows 988 and 911. | `test_safety_levels`, `test_emergency_answer_*` |
| No medication advice | Requests to stop, skip, double, change or replace a medicine, or about missed doses, are refused; the documented instruction is quoted verbatim with care-team and pharmacist contacts. | `test_medication_change_quotes_plan_and_refers` |
| No diagnosis or result interpretation | "Do I have…", "is this serious", "my potassium was…" are referred to the care team. | `test_safety_levels` |
| No invented content | Chat answers are only: plan text (verbatim), library text (verbatim, with source), or fixed connecting sentences. Unknown questions get "I won't guess". | `test_answer_text_comes_only_from_plan_or_library`, `test_unknown_question_does_not_guess` |
| Plan vs general information kept apart | Every block is labelled *From your care plan* or *General information*; topics from other conditions are not offered as if they applied. | `test_drug_question_separates_plan_and_education`, `test_glossary_and_out_of_plan_topics` |
| Plain versions never change the plan | Every clinician-style plain version must pass the fidelity evaluator with no critical or major issue (CI enforces this). | `test_every_plain_version_passes` |
| Teach-back never grades | Messages say what was covered or not mentioned and quote the original instruction; they never say "correct" or "wrong". | `test_complete_explanation_has_no_concerns`, `test_concern_quotes_original_verbatim` |
| Reminders only for documented tasks | No reminder without a plan task; no repetition unless the plan task is daily; none after a documented appointment date; times always chosen by the patient. | `test_reminder_flow`, `test_test_without_time_allows_same_day` |
| AI output is verified | Optional LLM rephrasing is accepted only if the evaluator finds no critical or major issue; otherwise the clinician-authored version is shown. | `test_llm_rephrase_rejected_when_unfaithful` |
| Unsafe content is refused | Plans must be marked synthetic; text resembling instructions to an AI system blocks loading. | `test_non_synthetic_plan_refused`, `test_prompt_injection_in_plan_refused` |

## Review history

- Independent adversarial review (October 2026): 12 reproduced findings (9 critical),
  covering missed emergency and medication-change wording, negated phrases counted as
  understanding, negation tricks ("no problem taking ibuprofen"), and evaluator gaps
  (tablet counts, added doses, threshold periods, limit direction, negated 911). All
  were fixed and locked in by `tests/test_review_regressions.py`.
- Second review round (October 2026): further negation and emergency-wording gaps; fixed,
  locked in by `tests/test_review_round2.py`.
- Third round (October 2026): about 540 reviewer-written cases showed the rules still
  missed about half of dangerous teach-back explanations. Response: a shared
  meaning-change module (`consistency.py`), a labelled development set
  (`eval/dev_set.json`), and interface changes so nothing reassures (below).
- Held-out round 1 (October 2026): 360 independently written cases scored before tuning;
  results in [evaluation_results.md](evaluation_results.md). The cases were then retired
  into the development set and the exposed patterns fixed.

## Interface safeguards against false reassurance

- A 911 / 988 strip is visible on every screen.
- Teach-back results never use an "all good" colour. Every result says the automatic check
  cannot confirm understanding and asks the patient to review with their nurse, pharmacist
  or care team.
- Covered points are labelled "Points the tool recognized", not "You understood".
- Fidelity verdicts without flags say "this is not evidence the text is correct" and that
  clinician review is still required.

## Known limits

- The emergency screen is keyword-based. It will miss unusual phrasing and will sometimes
  trigger on questions about symptoms. On independent text it missed about 1 in 6
  emergencies before tuning (see evaluation_results.md). It is not validated and the
  interface says so.
- Teach-back matching is phrase-based. Unusual but correct explanations may show as "not
  mentioned"; misunderstandings not anticipated in the plan's patterns may be missed, except
  number mismatches and lost "do not" statements, which are detected generally.
- The fictional plans and education text have not been reviewed by a clinician.
- English only for patient-facing text; the evaluator runs number, 911 and medicine-name
  checks on other languages and reports the rest as not assessed.
