# Teach-Back Companion

A working prototype with two parts that share one data model:

1. **Teach-Back Companion** (for patients). It shows each discharge instruction next to a
   plain-language version, then asks the patient to **explain it back in their own words**.
   It points out what they covered, what they did not mention, and where their explanation
   may conflict with the instruction (for example "I can stop the blood thinner when I feel
   better"). It always sends them back to the original wording and to their care team.
2. **Instruction Fidelity Evaluator** (for care teams). It checks a rewritten instruction
   (a plain-language rewrite, an AI-generated explanation, or a translation) against the
   documented original for changed doses or frequencies, lost "do not" statements, a missing
   "call 911", missing or added medicine names, added numbers and reading level.

> **Synthetic demonstration only.** Three fictional patients (atrial fibrillation, heart
> failure, pneumonia). Not connected to any health record, not medical advice, not
> clinically validated, and not affiliated with or endorsed by UW Medicine. The education
> text is a draft that has not been clinician-reviewed.

## Why this, and not another health chatbot

Epic's patient assistant (Emmie) already explains records, answers questions and drafts
reminders inside MyChart at several health systems (see [docs/prior_work.md](docs/prior_work.md)).
This prototype targets the step those tools do not clearly cover: **checking that the patient
understood**, which is the teach-back method AHRQ recommends. It also targets **checking
that a simplified or translated instruction still says the same thing**, the quality-assurance
step that recent trials of AI-generated discharge summaries leave to physician review.

## Run it

Python 3.11+.

```bash
cd teach-back-companion
pip install -e .
teachback serve              # open http://127.0.0.1:8000
```

No API key, account or network access is needed. Everything runs locally; reminders and
checklist progress live in `data/demo.sqlite` ("Clear demo data" in the footer resets them).

### Demo walk-through (5 minutes)

1. Choose **Alex Rivera (fictional)**: new AFib on apixaban and metoprolol.
2. **My health**: switch between Simple, Standard and More detail.
3. **My medicines**: original instruction beside the plain version.
4. **Check my understanding**: pick *Apixaban*, type
   `I take it twice a day and I can stop when my heart feels normal again.`
5. **Ask**: try `What is apixaban for?`, then *Say it more simply*, then
   `Can I stop my metoprolol?` and `I have chest pain`.
6. **Reminders**: add one for the cardiology visit; try a date after the visit.
7. **For care teams**: paste `Take apixaban 5 mg once a day. You can stop when you feel better.`
   and run the benchmark.

### Newer tools

| Tool | What it does | Where |
|---|---|---|
| **Safety gate for AI-drafted text** | Checks a batch of AI-drafted (or any rewritten) instructions before they reach a patient; holds any that change a dose, a "do not", a 911 instruction or a limit. Never certifies: everything still needs clinician review. | `teachback gate drafts.json --html report.html` (exit 1 if anything is held), `POST /api/gate`, and the "For care teams" tab |
| **Misunderstanding insights** | Which instructions are misunderstood most, and how, grouped by the HCAHPS domain each affects (medicines, symptoms, discharge information, care coordination). Counts only; no patient text kept. | `teachback insights [attempts.json] --csv insights.csv --html insights.html`, `GET /api/insights`, the "For care teams" tab |
| **HCAHPS loop** | The insights CSV can be shown inside the Quality Signal Monitor report, beside the discharge measures. | `uwmc-monitor run ... --teachback-insights insights.csv` |
| **Voice teach-back** | "Speak my answer" (English or Spanish) on the teach-back screen, using the browser's own speech recognition when available. | Teach-back screen. Some browsers send audio to the browser maker's servers; demo only |
| **Caregiver mode** | A family member explains the instruction for someone else ("she takes it…"); third-person wording is checked the same way. | Tick "I am a family member or caregiver" on the teach-back screen |

Not built: automatic back-translation of Spanish rewrites. It needs a translation model;
`llm.py` shows where a locally hosted model could plug in, with the evaluator checking its output.

### Command line

```bash
teachback evaluate afib-demo med-apixaban rewrite.txt [--language es]   # exit 1 on critical issues
teachback benchmark                                                    # evaluator on seeded errors
teachback check-content                                                # validate plans and library
teachback gate drafts.json --html gate.html                            # safety gate for AI-drafted text
teachback insights --csv insights.csv --html insights.html             # misunderstanding insights (synthetic cohort)
```

## What it does and does not do

| Does | Does not |
|---|---|
| Explain documented instructions and diagnoses; show the original beside every explanation | Diagnose, prescribe, change doses, or interpret a patient's own results |
| Label every answer block as *from your care plan* or *general information* (with source) | Generate new medical content (the default mode has no AI at all) |
| Check teach-back answers against the plan's critical facts and known misunderstandings | Grade patients or say an explanation is "correct" |
| Screen every message for emergency, crisis, medication-change and diagnosis requests first | Perform triage; the emergency screen is a conservative prototype safeguard |
| Set in-app reminders only for documented tasks, at times the patient chooses | Invent schedules or deadlines, or send messages to phones |
| Score rewrites and translations for preserved numbers, negations, 911 and medicine names | Certify any text as safe; every verdict ends with "review still required" |
| Say plainly that an automatic check cannot confirm understanding | Reassure: no result is shown as "all good", and a 911/988 strip is on every screen |

## How it works

Each care-plan item stores the **original** clinician wording, a **plain** version for
clinician approval, and a list of **critical facts**. Each fact holds required concepts,
numbers with units (5 mg, twice a day, 2 pounds), any "do not" action, whether 911 is
required, and known misunderstandings written as patterns. Teach-back checking and the
evaluator both read these facts, so the same clinical knowledge drives both.

- Number parsing understands "twice a day", "2 times a day", "two pounds", "2,000 mg",
  "101°F" and Spanish number words.
- Negation is checked in a short window within the same clause, and for lists of drugs
  ("do not take ibuprofen (Advil) or naproxen").
- Plans that are not marked synthetic, or that contain text resembling instructions to an
  AI system, are refused at load time.

Details: [docs/architecture.md](docs/architecture.md), [docs/clinical_safety.md](docs/clinical_safety.md).

## Testing

```bash
pip install -e ".[dev]" && pytest          # all should pass
teachback serve --port 8765 &
node scripts/e2e_check.mjs http://127.0.0.1:8765    # needs playwright + axe-core (npm)
```

The browser check drives every screen, fails on console or CSP errors, and runs axe-core
WCAG 2.x A/AA checks on each view (0 violations at the time of writing). Automated
accessibility checks catch only part of WCAG; see the manual items in
[docs/clinical_review_checklist.md](docs/clinical_review_checklist.md).

**Evaluator benchmark** (synthetic): 30 of 30 seeded errors detected, 0 false alarms on 16
clean rewrites. The same person wrote the benchmark and the evaluator, so this shows the
checks work as designed. It is not evidence of real-world accuracy.

**A real finding during development:** the evaluator flagged two errors in this demo's own
hand-written plain-language text. The antibiotic rewrite had dropped the drug name and
strength, and a negation-scope bug misread a list of drugs to avoid. Both were fixed. That
is the kind of slip the tool is meant to catch.

**Measured accuracy.** The honest numbers come from labelled cases written by independent
reviewers who did not see the rules, scored *before* any tuning. They are in
[docs/evaluation_results.md](docs/evaluation_results.md). In short: this is a rule-based
prototype that misses some dangerous misunderstandings and some emergencies phrased in
unexpected ways. It is an aid for clinician-led teach-back and a research baseline, **never
a safety net**.

```bash
teachback evaluate-set eval/dev_set.json --show-misses      # development set (tuned on; regression check)
teachback evaluate-set my_cases.json --show-misses          # your own labelled cases (format: REVIEW.md)
```

**Review history.** Three rounds of independent adversarial review found and fixed
emergency-wording gaps, negation tricks, and evaluator gaps; every reproduced case is a
regression test or part of the development set. See [docs/clinical_safety.md](docs/clinical_safety.md).

## Documents

| Document | For |
|---|---|
| [docs/uw_medicine_proposal.md](docs/uw_medicine_proposal.md) | A short proposal for UW Medicine reviewers |
| [docs/clinical_review_checklist.md](docs/clinical_review_checklist.md) | Clinician and patient-education reviewer worksheet |
| [docs/evaluation_plan.md](docs/evaluation_plan.md) | Proposed (not conducted) evaluation |
| [docs/clinical_safety.md](docs/clinical_safety.md) | Safety boundaries and how they are enforced |
| [docs/privacy_and_security.md](docs/privacy_and_security.md) | Data handling and threat model |
| [docs/architecture.md](docs/architecture.md) | Components and data flow |
| [docs/epic_integration.md](docs/epic_integration.md) | Why Epic is not integrated yet, and what that would take |
| [docs/prior_work.md](docs/prior_work.md) | What already exists, with sources |
| [docs/evaluation_results.md](docs/evaluation_results.md) | Measured accuracy on four independent held-out rounds |
| [docs/abstract_draft.md](docs/abstract_draft.md) | Draft conference abstract for a mentor to revise |

## License

MIT for the code. The fictional plans and draft education text are provided for
demonstration and must be clinically reviewed before any real use.
