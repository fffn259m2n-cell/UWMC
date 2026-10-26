# Proposal: checking patient understanding of discharge instructions

*Independent prototype offered for feedback. Not requested or endorsed by UW Medicine.*

## 1. Summary

Patients often leave the hospital unsure what to do with new medicines and warning signs.
AI assistants now explain records inside MyChart, and AI-drafted discharge summaries are
being trialled with physician review. Neither clearly addresses two questions: **did the
patient understand?** and **does the simplified or translated version still say the same
thing?** This prototype answers both, for fictional patients, with no AI required.

## 2. Problem

- Teach-back is recommended (AHRQ Tool 5) but time-consuming and inconsistent at discharge.
- Simplified, AI-generated or translated instructions can silently change a dose, drop a
  "do not", or omit "call 911".

## 3. What exists in the prototype

- **Teach-back Companion**: patient explains each instruction in their own words; the tool
  shows covered points, points not mentioned, and possible misunderstandings, always quoting
  the original and pointing to the care team.
- **Instruction Fidelity Evaluator**: checks any rewrite against the original for numbers,
  units, negations, 911, medicine names and reading level; 30/30 seeded errors detected with
  0 false alarms on 16 clean rewrites (synthetic benchmark).
- Grounded Q&A, plan/education labelling, reminders for documented tasks, and a safety screen.

## 4. Possible value across UW Medicine

Any discharge instruction can be expressed as critical facts, so the approach is not limited
to one specialty. A small library of high-risk templates (anticoagulants, heart-failure
diuretics, insulin, antibiotics, opioids) could cover many discharges.

## 5. Example patient journey (fictional)

Alex is discharged on apixaban. Asked to explain it back, Alex says "I'll stop when my heart
feels normal." The companion shows the instruction ("Do not stop taking apixaban unless your
cardiologist tells you to") and suggests raising it with the nurse before leaving.

## 6. Role of Epic / MyChart

None in this version (see `epic_integration.md`). A realistic first pilot needs no EHR
integration: staff choose the instruction template during discharge teaching.

## 7. Data

Fictional plans and draft education text only. No PHI, no network calls, nothing typed is stored.

## 8. Safety safeguards

See `clinical_safety.md`: emergency-first screening, no medication or diagnostic advice,
verbatim plan quotes, verified optional AI, synthetic-only loading.

## 9. Privacy and security

See `privacy_and_security.md`. Not a production system; would require UW review.

## 10. Demonstration plan

A 15-minute local demo (README walk-through) with a clinician and a patient-education
specialist, then the review checklist.

## 11. Clinical review process

`clinical_review_checklist.md`: per-instruction fidelity, misconception coverage, safety
behaviour, accessibility.

## 12. Potential pilot design / 13. Evaluation measures

See `evaluation_plan.md`: expert review, evaluator validation against clinician labels,
simulated usability, then (only with approvals) a single-unit pilot of nurse-led teach-back.

## 14. Ownership and maintenance questions for UW

Who would author and approve critical facts for each template? Who owns updates when
instructions change? Would the evaluator run on vendor AI output, and where?

## 15. Limitations and approvals

Not clinically validated; rule-based matching that misses some dangerous misunderstandings
and unusually phrased emergencies (independent measurements in `evaluation_results.md`);
English patient text only; draft education content. Positioned as an aid to clinician-led
teach-back and a research baseline, never as a safety net. Any real use requires a clinical sponsor, IT, privacy and security review, clinical-
safety sign-off, an IRB determination for evaluation, and regulatory assessment.

## Who to approach **[CONFIRM before sending]**

The UW Center for Scholarship in Patient Care Quality and Safety (Department of Medicine),
whose director, per UW's informatics faculty page, also oversees generative AI in the EHR
for UW Medicine. Your own UW faculty mentor is the best route to an introduction. No contact
has been made.
