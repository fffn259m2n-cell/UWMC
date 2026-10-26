# Draft abstract (for a mentor to revise; not submitted)

**Status:** draft for discussion with a faculty co-author. All numbers come from
[evaluation_results.md](evaluation_results.md). Check the target meeting's word limit,
format and rules on prior presentation before use. Author list and affiliations are
**[CONFIRM]**; do not list any institution without its agreement.

---

**Title:** Rule-based checking of patient teach-back and AI-rewritten discharge instructions:
four rounds of independent held-out evaluation

**Background.** Teach-back is recommended to confirm patients understand discharge
instructions, and health systems are beginning to use AI to draft patient-facing text. Both
need a fast check that the patient's explanation, or the rewritten text, still carries the
critical facts of the original instruction.

**Methods.** We built an open-source prototype that represents each discharge instruction as
critical facts (required concepts, quantities with units, "do not" actions, emergency
actions, known misunderstandings). The same facts drive (1) a teach-back checker, (2) an
instruction-fidelity evaluator for rewrites and translations, and (3) a safety screen for
emergencies, crisis language and medication-change requests. Three fictional care plans
(atrial fibrillation, heart failure, pneumonia) were used. In four rounds, a separate writer
with no access to the code or earlier cases wrote 360 to 390 labelled cases (patient
explanations in varied voices, English and Spanish rewrites, chat messages). Each round was
scored once before any change, then retired into a development set used for improvement.

**Results.** Before tuning, sensitivity for dangerous teach-back explanations was 77%, 88%,
82% and 91% across rounds, with specificity 91% to 100%. The fidelity evaluator flagged 95% to
98% of dangerous rewrites, with 83% to 100% of faithful rewrites passing. Strict emergency
recognition was 83% to 91%. Crisis (suicide or self-harm) recognition stayed between 53% and
73% across rounds despite fixes after each round. A broad safety net added in round 4 delivered
911 guidance for 98% of emergency messages but 988 guidance for only 60% of crisis messages,
while showing a caution box on 11% of ordinary messages.

**Conclusions.** Fixing the phrases one writer used did not reliably transfer to the next
writer's phrasing, especially for crisis language. Rule-based checks are useful as a
transparent aid and as a backstop, but should not be the only safeguard. Interfaces should
show crisis resources unconditionally, and real deployment needs a validated classifier,
clinical validation and monitoring.

---

*Independent prototype with synthetic data only; not affiliated with or endorsed by any
health system. Code: https://github.com/fffn259m2n-cell/UWMC*
