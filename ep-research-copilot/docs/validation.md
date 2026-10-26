# Validation

## What has been verified

**Software behaviour**: the automated test suite (`pytest`, 54 tests) covers PubMed XML
parsing (structured abstracts, missing abstracts/DOIs, MedlineDate), ESearch pagination and
duplicate IDs, ClinicalTrials.gov pagination, duplicate NCT IDs and truncation, HTTP retries,
timeouts and non-retryable errors, search-window selection, screening rules, extraction rules,
LLM-output verification, trial change detection, idempotent re-runs, rollback on failure,
corrupt database/snapshot handling, synthetic/real separation, reviewer import and metrics,
link integrity in the outputs, and the offline CLI.

**Developer spot-check on real records (not a human validation).** On 26 October 2026 the
tool processed 26 real PubMed records (Entrez dates 19 to 26 October 2026) and 396
ClinicalTrials.gov registrations, retrieved through PubMed and ClinicalTrials.gov connectors
because the build environment blocked direct API access. The developer (an AI coding
assistant) read the extracted sample sizes and effect estimates against their quoted sentences:

- Sample size (18 abstracts with a count): across rule revisions three wrong picks were found
  (an event count "172 patients (33.27%)", a per-group "n=62", and "16 million individuals"
  from a database description). The rules were revised (enrolment phrasing first, event
  counts demoted, scale words excluded). In the final version all 18 suggested values are a
  stated study-population count; 5 carry a "several counts reported" note for the reviewer.
- Effect estimates: an "or" in running text was briefly read as "OR"; fixed with a
  case-sensitive abbreviation match. The 21 extracted estimates are verbatim spans, and
  labels such as "HR," are kept with the value.
- Priority: the first version marked all 26 records "high" because category patterns reused
  the query's generic words; after revision, 16 high and 10 medium.

These checks shaped the rules but are **not** an accuracy measurement: they were done by the
software's author, on the same records used to tune the rules.

## What still needs a human

1. **Screening**: run the tool for one month, open `output/review_queue.csv`, and mark
   `reviewer_decision` for every row (20 to 30 records is enough to start). Then:
   `ep-copilot import-reviews output/review_queue.csv && ep-copilot evaluate`.
   To estimate recall, also search PubMed by hand for the same window and add any relevant
   article the tool missed to the CSV as `include`.
2. **Extraction**: in `output/evidence_quotes.csv`, mark `reviewer_correct` = `yes`/`no`
   for each row you check, then `ep-copilot evaluate --extraction output/evidence_quotes.csv`.
3. Record results below. Do not describe the tool as validated until this is done.

| Date | Reviewer | Records | Precision | Recall | Extraction accuracy (by field) | Notes |
|---|---|---|---|---|---|---|
| | | | | | | |

## Time-savings evaluation (optional)

Measure, do not estimate. Fill in after timing both workflows on the same month.

| Task | Manual time | Tool-assisted time | Quality comparison | Reviewer feedback | Observed limitations |
|---|---|---|---|---|---|
| Find new AF-ablation articles for the month | | | | | |
| Pull sample size / design / effect estimates for in-scope articles | | | | | |
| Check registered trials for status or enrollment changes | | | | | |
