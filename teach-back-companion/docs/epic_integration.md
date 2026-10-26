# Epic / MyChart integration: not built, by design

An earlier plan proposed a SMART on FHIR connection to Epic's public sandbox. It was left out
of this version for three reasons:

1. **Overlap.** Epic's own patient assistant already reads the chart inside MyChart
   (see prior_work.md). Re-implementing record access would add risk without adding the
   part that is new here (teach-back and fidelity checking).
2. **The needed data is not in FHIR.** Teach-back needs each instruction's *critical facts*
   (numbers, "do not" actions, emergency actions, known misunderstandings). Standard FHIR
   resources (MedicationRequest, Condition, Appointment, DocumentReference) do not carry
   these, and complete discharge instructions are often only in narrative notes.
3. **It cannot be tested honestly here.** A sandbox connection needs an Epic developer
   registration and client ID, which this project does not have. Untested OAuth code would
   not meet the "verified before claimed" standard.

## If UW Medicine wanted to pilot it

Most realistic first path: **clinician-authored critical facts for a small set of common
discharge instruction templates** (for example new anticoagulant, heart failure diuretic,
antibiotic course), used by nurses or pharmacists during discharge teaching, with no
patient-data integration at all. Later options, each needing UW approval:

- SMART on FHIR (patient or provider launch) to pull the medication list, with facts
  mapped from structured sig fields (dose, frequency) and template-level facts for the rest.
- Running the fidelity evaluator on AI-generated patient instructions *before* they are
  released, as a quality gate for physician review.

Requirements before any of this: a clinical sponsor; UW Medicine IT, privacy and security
review; clinical-safety review of every template; an IRB determination for any evaluation
with patients; and assessment of FDA clinical-decision-support guidance.
