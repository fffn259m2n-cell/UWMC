# Methodology

## Sources and queries

**PubMed** via NCBI E-utilities (`esearch.fcgi`, `efetch.fcgi`, XML),
https://www.ncbi.nlm.nih.gov/books/NBK25499/. Default query (`config/topics.yaml`):

```
("Atrial Fibrillation"[MeSH Terms] OR "atrial fibrillation"[Title/Abstract])
AND ("Catheter Ablation"[MeSH Terms] OR "catheter ablation"[Title/Abstract]
  OR "pulsed field ablation"[Title/Abstract] OR "pulsed-field ablation"[Title/Abstract]
  OR "cryoballoon"[Title/Abstract] OR "radiofrequency ablation"[Title/Abstract]
  OR "pulmonary vein isolation"[Title/Abstract])
AND (recurrence[Title/Abstract] OR outcomes[Title/Abstract] OR follow-up[Title/Abstract]
  OR efficacy[Title/Abstract] OR safety[Title/Abstract])
```

This extends the original draft query with "pulsed-field" (hyphenated) and "pulmonary vein
isolation". No language filter is applied. Known gaps: articles that describe ablation
results without any of the five outcome words; brand-name-only titles; items not yet
indexed with MeSH (the Title/Abstract terms reduce this).

- Window: Entrez date (EDAT), not publication date.
- Rate: 2.5 requests/s without an API key (NCBI limit 3/s); 9/s with `NCBI_API_KEY`.
- Batches of 200; retries with exponential backoff (1, 2, 4, 8 s) on timeouts, network errors
  and HTTP 429/5xx; no retry on other 4xx.
- `tool=ep-research-copilot` is sent on every request; `email` if `NCBI_EMAIL` is set.

**ClinicalTrials.gov** API v2 `/studies`, https://clinicaltrials.gov/data-api/api.
`query.cond="atrial fibrillation"`, `query.intr="catheter ablation OR pulsed field ablation OR
cryoballoon OR radiofrequency ablation OR pulmonary vein isolation"`, statuses NOT_YET_RECRUITING,
RECRUITING, ENROLLING_BY_INVITATION, ACTIVE_NOT_RECRUITING; pages of 100 following
`nextPageToken`, capped at `max_records` (truncation is reported). Tracked trials missing from
a later search are re-read with `/studies/{NCT}`; if that also fails they are reported once
as "not returned by ClinicalTrials.gov".

## Storage and runs

SQLite (`data/ep_copilot.sqlite`). Tables: runs, articles, article_events, screenings,
extractions, trials, trial_snapshots, trial_changes, reviews. Articles are keyed by PMID and
trials by NCT ID per topic. A content fingerprint (SHA-256 of the normalized record) decides
"new", "updated" (e.g. an abstract added later) or unchanged. Every fetch completes before
one write transaction; failures are logged in `runs` and leave data unchanged. Synthetic
fixtures and real records cannot share a database.

## Screening (`screening.py`)

- In scope: matches at least one pattern from each `scope.all_of` group (AF terms; ablation terms).
- Other EP: EP vocabulary present but not both groups. Outside scope: neither.
- Categories: AF ablation outcomes, Pulsed-field ablation, AF recurrence, Rhythm monitoring,
  Repeat ablation, Procedural safety. Patterns avoid the query's own generic words
  ("outcomes", "efficacy", "safety"), which every record contains.
- Priority (in scope): 2+ categories high, 1 medium, 0 low; no abstract → review.
- Design label (descriptive only): PubMed publication type first, then title/abstract
  wording (labelled "from abstract wording"): protocol, systematic review/meta-analysis,
  RCT, guideline, case report, registry/observational, review, editorial.

## Extraction (`extraction.py`)

Abstract-only, deterministic. Sentences are split without breaking decimals or "vs.".

| Field | Rule |
|---|---|
| study_design_stated | Design words as written (randomized, prospective, retrospective, multicenter, registry, ...) |
| sample_size | Ranked candidates: "a total of N", enrolment verbs ("included/enrolled N ..."), "N patients were included", "N patients", "n = N". Counts followed by "(x%)" are demoted as likely events; scale words ("16 million") are ignored. All counts found are listed in the note. |
| intervention | Modality terms (PFA, RF, cryoballoon, laser balloon, PVI, PWI, LAA, AADs) |
| comparator | First sentence with "versus / vs. / compared with / randomized to"; read the quote |
| follow_up | "median follow-up of 12 months", "2-year follow-up" |
| outcome_statements | Recurrence / freedom / success / complication phrases ending in a percentage |
| effect_estimates | Ratios (HR, OR, RR, IRR, hazard/odds/risk ratio) with 95% CI, and estimates with CI, copied verbatim |
| p_values | "p = 0.27", "P<.001" |
| trial_registration | NCT IDs, linked to ClinicalTrials.gov |
| limitations | Sentences with limitation / further or larger studies language |

Every value is stored with its sentence and rule name and is dropped if the sentence is not a
verbatim substring of the abstract.

## Trial changes (`changes.py`)

Substantive: status, enrollment and its type, primary outcomes, interventions, conditions,
phase, study type, start/primary completion/completion dates, results flag, Washington sites.
Administrative: titles, sponsor name, first/last posted dates, site count.

## Evaluation (`review.py`)

Precision = reviewer-included ∩ tool-in-scope / tool-in-scope; recall = reviewer-included ∩
tool-in-scope / reviewer-included; "unsure" is excluded. Extraction accuracy is the share of
reviewed `evidence_quotes.csv` rows marked `yes` per field.
