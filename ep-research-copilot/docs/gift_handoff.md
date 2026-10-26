# Gift handoff: EP Research Copilot

> **Status: draft for human review. Nothing has been sent.** Items marked **[CONFIRM]**
> need checking by hand.

## What it is

A free, open-source tool that does the routine part of keeping up with atrial fibrillation
ablation research. Each month it finds newly indexed PubMed articles, pulls the key facts
from each abstract (with the exact sentence they came from), and reports what changed in
registered AF-ablation trials, including trials with a Washington State site. The output is
one HTML digest plus spreadsheets a research coordinator can filter and annotate.

## How it could help an EP research team

- Replaces repeated manual PubMed searches with one recorded, repeatable query.
- Gives a first-pass evidence table (design, n, interventions, follow-up, effect estimates)
  with quotes, so checking is faster than extracting from scratch.
- Catches trial status, enrollment, outcome and site changes that are easy to miss,
  including trials that quietly move to "Completed".
- Keeps reviewer decisions separate, so screening accuracy can be measured over time.

## How to run it

```bash
pip install -e .
ep-copilot run                     # about a minute; writes output/ep_research_digest.html
ep-copilot run --offline           # demo on synthetic data, no network
```

Change topics in `config/topics.yaml` (copy the af-ablation block). Maintenance is about
30 minutes a month: run, skim the digest, optionally mark the review queue.

## Inspecting results

Every article links to PubMed (and DOI), every trial to ClinicalTrials.gov. Extracted values
sit next to their verbatim sentence in `evidence_quotes.csv`. A blank means "not stated in the
abstract in a recognizable form".

## Validating AI-assisted content

AI is off by default. If someone enables `ai_optional.py`, every proposal must quote the
abstract verbatim and contain only numbers present in that quote; failures are rejected.
Treat accepted values like rule-based ones: check before use.

## Data sources

- PubMed via NCBI E-utilities: https://www.ncbi.nlm.nih.gov/books/NBK25499/
- ClinicalTrials.gov API v2: https://clinicaltrials.gov/data-api/api

## Verified so far

- 54 automated tests pass.
- A sample run on real records (26 PubMed articles entered 19 to 26 Oct 2026; 396 tracked
  trials) completed. Records came through PubMed/ClinicalTrials.gov connectors because the
  build environment blocked direct API access; a direct `ep-copilot run` has **not** yet been
  executed against the live APIs. **[CONFIRM]** run it once on a networked machine.
- Screening and extraction accuracy are **not yet measured** by a person (docs/validation.md).

## Known limitations

Abstract-only, rule-based, no quality appraisal, depends on the query, registry data is
sponsor-maintained. Full list: [limitations.md](limitations.md).

## Independence and reuse

Independent, unpaid contribution. Not requested or endorsed by UW Medicine. MIT-licensed
code; use, change or discard it freely. Feedback: open an issue in the repository
**[CONFIRM: repository URL]** or reply to the message below.

## Draft message to your PI or senior EP research colleague

> Hi Dr. [Last name],
>
> I've built a small independent Python tool for our EP research work. Each month it finds
> new PubMed articles on AF ablation, pulls study design, sample size and effect estimates
> from the abstracts (each with its source sentence), and flags changes in registered
> AF-ablation trials, including ones with Washington sites. It uses only public PubMed and
> ClinicalTrials.gov data, with no patient or institutional records.
>
> Could I show you a sample digest? I'd value your view on whether it would save the team
> time, or whether another repetitive task (full-text extraction, trial tracking for a
> different topic) would be more useful to automate.
>
> Thank you,
> [Your name]

## Time-savings record (fill in only with measured times)

| Task | Manual time | Tool-assisted time | Quality comparison | Reviewer feedback | Observed limitations |
|---|---|---|---|---|---|
| Monthly literature search | | | | | |
| Evidence table for in-scope articles | | | | | |
| Trial status review | | | | | |
