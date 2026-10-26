# Prior work: what already exists

Checked October 2026. Trade-press items are self-reported by vendors and health systems.

## Patient-facing AI in the EHR

- **Epic Emmie** is a patient AI assistant inside MyChart. Sutter Health was reported as the
  first health system live; Community Health Network (Indianapolis) launched it in July 2026,
  stating it uses only information already available to patients in MyChart. Reported uses
  include explaining test results, answering questions after a visit, rescheduling and billing.
  Sources: [Becker's: Sutter Health first to adopt](https://www.beckershospitalreview.com/healthcare-information-technology/ehrs/sutter-health-1st-to-adopt-epics-ai-chatbot-for-patients/),
  [Becker's: Community Health Network launches Emmie](https://www.beckershospitalreview.com/healthcare-information-technology/community-health-network-launches-epics-emmie-in-mychart/),
  [Becker's: early use of Epic's newest AI tools](https://www.beckershospitalreview.com/healthcare-information-technology/ehrs/inside-health-systems-early-use-of-epics-newest-ai-tools/).
- Whether UW Medicine has deployed Emmie was **not** publicly verifiable. **[CONFIRM]** with UW
  Medicine before positioning this work.

**Implication:** a general "explain my record" chatbot would duplicate vendor capability. This
prototype instead focuses on (1) checking patient understanding with teach-back, and (2)
checking whether simplified or translated instructions preserve critical facts, a step
that applies to any vendor's AI output.

## Evidence on AI-generated discharge information

- Rust P, et al. *Effects of large language model-generated, patient-oriented discharge
  summaries on patient activation: a single-centre, single-blind, randomised controlled trial
  in Germany.* Lancet Digit Health 2026;8(6):100991. Internal medicine; 128 participants;
  GPT-4o drafts **reviewed by the treating physician**; higher PAM-13 activation at discharge.
  The authors call for more work on quality assurance before routine adoption.
  [DOI](https://doi.org/10.1016/j.landig.2026.100991) (retrieved via PubMed).

The Instruction Fidelity Evaluator is a candidate aid for that physician-review step.

## Teach-back

- AHRQ *Health Literacy Universal Precautions Toolkit*, "Use the Teach-Back Method" (Tool 5):
  ask patients to state in their own words what they need to know or do.
  [AHRQ TeamSTEPPS teach-back tool](https://www.ahrq.gov/teamstepps-program/curriculum/communication/tools/teachback.html),
  [Toolkit, 3rd edition (PDF)](https://www.ahrq.gov/sites/default/files/publications2/files/health-literacy-universal-precautions-toolkit-3rd-edition.pdf).

## UW context

- UW's Biomedical Informatics faculty page lists Andrew White, MD, as a UWMC hospitalist, UW
  Medicine's assistant Chief Health Information Officer (clinical decision support,
  documentation, predictive and generative AI in the EHR) and director of the UW Center for
  Scholarship in Patient Care Quality and Safety:
  [bime.uw.edu/faculty/andrew-white](https://bime.uw.edu/faculty/andrew-white/). A 2026 UW
  Medicine news item gives his title as assistant chief *clinical* information officer.
  **[CONFIRM]** the current title and contact route from an official UW directory.
- UW Medicine publishes patient-education handouts through Health Online
  (https://healthonline.washington.edu/). **[CONFIRM]** link and reuse terms; this prototype
  does not copy any UW handout.
