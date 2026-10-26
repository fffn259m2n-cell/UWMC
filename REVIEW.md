# Independent review guide

Thank you for reviewing. This page is all you need. You do not need to have seen these
projects before, and no patient data is involved anywhere.

**What these are.** Three independent, unpaid prototypes built with public data or fictional
patients. They are not affiliated with or endorsed by any health system, and none is
clinically validated.

| Project | One line | Most useful reviewer |
|---|---|---|
| `quality-signal-monitor/` | Public CMS HCAHPS patient-experience data for one hospital vs national benchmarks, focused on discharge and care coordination | Quality-improvement or patient-experience staff; anyone comfortable with CMS data |
| `ep-research-copilot/` | Monthly digest of new PubMed articles and ClinicalTrials.gov changes for an electrophysiology topic, with verbatim evidence quotes | EP clinician or researcher |
| `teach-back-companion/` | Patient teach-back checks plus an evaluator that flags meaning changes in simplified or translated discharge instructions | Clinician, nurse, pharmacist, patient-education or health-literacy specialist |

You can review one project or all three. Budget: 30 to 90 minutes.

## 1. Get access (pick one)

- **Browser, no install (recommended):** open the repository link you were sent, then
  **Code → Codespaces → Create codespace**. After 2 to 4 minutes the Teach-Back demo opens in
  a browser tab. Needs a free GitHub account.
- **Review packet:** the zip file you were sent contains the full source, one-page
  summaries, a synthetic sample report and this guide. Install Python 3.11+, then
  `pip install -e ./teach-back-companion` (or another project) and follow its README.
- **Read-only:** the PDFs in `one-pagers/pdf/` and the sample reports need no software.

Step-by-step test scripts with expected results are in [TESTING.md](TESTING.md).

## 2. What to look for

Please be adversarial; finding problems is the point.

**All projects**
- [ ] Could any output mislead a reader (a number, a label, a claim of accuracy)?
- [ ] Is anything presented as validated, official or endorsed?
- [ ] Are the limitations pages honest and complete?
- [ ] Code: is it clear enough that you could add to it? (See [CONTRIBUTING.md](CONTRIBUTING.md).)

**Quality Signal Monitor**
- [ ] Spot-check 3 values in `output/benchmark_comparisons.csv` against Medicare Care Compare (needs a real run: `uwmc-monitor run --fetch`).
- [ ] Is handling of the 2025 HCAHPS survey update (Care Transition retired, new measures) correct?
- [ ] Is the language descriptive rather than judgemental?

**EP Research Copilot**
- [ ] For 10 digest items: is the topic right, and is each quoted sentence really in the abstract and correctly labelled (sample size, design, effect estimate)?
- [ ] Were any obviously relevant articles or trials missed?

**Teach-Back Companion** (the highest-risk project)
- [ ] Try to make it miss a dangerous misunderstanding, in your own words (wrong dose, stopping early, the wrong response to an emergency sign).
- [ ] Try to make it flag a correct explanation (false alarm).
- [ ] Does any message reassure a patient when it should not?
- [ ] Emergency and crisis messages in **Ask**: is anything missed or over-triggered?
- [ ] Use [teach-back-companion/docs/clinical_review_checklist.md](teach-back-companion/docs/clinical_review_checklist.md) for the clinical content.

## 3. Measure it yourself (optional, about 30 minutes, very valuable)

The most useful thing an independent reviewer can do is write test cases **without looking
at the rules**, then score them. Copy [review/heldout_template.json](review/heldout_template.json),
add your cases (realistic patient explanations, rewrites and chat messages, each labelled),
then run:

```bash
cd teach-back-companion
teachback evaluate-set ../review/my_cases.json --show-misses
```

It prints sensitivity (dangerous cases caught) and specificity (correct cases not flagged)
for each component, and lists every miss. Send the file and the output back; your cases
become the next held-out set.

## 4. How to report

Any of these works:
- **GitHub:** Issues → New issue → **Independent review finding** (one issue per finding).
- **Spreadsheet:** fill in [review/findings_template.csv](review/findings_template.csv) and email it back.
- **Free text:** an email is fine. For each finding give the project, what you did, what you
  expected, what happened, and how serious you think it is (critical / major / minor).

Severity guide: **critical** could lead to harm or a seriously wrong conclusion if acted on;
**major** is wrong or misleading but unlikely to cause harm; **minor** is wording, layout or
convenience.

## 5. Your independence

You are under no obligation, and there is no payment or affiliation. Please say anything
you think, including "this should not be pursued". With your permission your name may be
acknowledged in the review history; otherwise findings are recorded anonymously.
