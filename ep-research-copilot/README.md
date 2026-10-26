# EP Research Copilot

A small, open-source tool for cardiac electrophysiology research teams. Once a month it:

1. **Finds new literature**: searches PubMed for newly indexed articles on a configured topic,
   removes duplicates, and sorts them into a review queue by topic relevance.
2. **Extracts evidence from abstracts**: study-design terms, sample size, interventions,
   comparison, follow-up, outcome statements, effect estimates, p-values, trial registrations
   and stated limitations. Every value comes with the exact sentence it was taken from.
3. **Tracks clinical trials**: follows ClinicalTrials.gov registrations for the topic and
   reports what changed since last month (status, enrollment, outcomes, dates, results flag,
   Washington State sites), separating substantive from administrative changes.

All three share one local SQLite database and produce one digest (HTML) plus CSV files.

The first topic is **atrial fibrillation catheter ablation**: pulsed-field, radiofrequency
and cryoballoon ablation, recurrence and its predictors, rhythm monitoring, repeat ablation
and procedural safety. Topics are plain configuration (`config/topics.yaml`).

> This tool supports research surveillance and literature organization. It does not perform a
> systematic review, provide medical advice, or establish clinical practice recommendations.
> It is an independent project, not affiliated with or endorsed by UW Medicine, and uses only
> public PubMed and ClinicalTrials.gov data. No patient data, no credentials.

## Quick start

Python 3.11+. No API keys or paid services.

```bash
git clone <this repository> && cd ep-research-copilot
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e .

ep-copilot run                 # first run: last 30 days; later runs: since the previous run
open output/ep_research_digest.html
```

Try it without network access on invented data (clearly marked SYNTHETIC):

```bash
ep-copilot run --offline
ep-copilot run --offline --fixtures tests/fixtures/snapshot_run2   # a second "month", showing changes
```

## Monthly routine (about 30 minutes)

1. `ep-copilot run` (about a minute).
2. Open `output/ep_research_digest.html`. Start with **high** priority and **review**
   (no-abstract) items, then the trial **Changes** table.
3. Optional: record decisions in `output/review_queue.csv` (`include` / `exclude` / `unsure`)
   and load them with `ep-copilot import-reviews output/review_queue.csv`.

## Commands

| Command | What it does |
|---|---|
| `ep-copilot run [--days N]` | Fetch, store, screen, extract, track trials, write outputs |
| `ep-copilot fetch [--days N]` | Same, without writing outputs |
| `ep-copilot screen` | Re-screen and re-extract the last run with the current config (no fetching) |
| `ep-copilot report [--run-id N]` | Rewrite outputs for a stored run |
| `ep-copilot validate` | Database and identifier checks |
| `ep-copilot import-reviews FILE` | Load reviewer decisions from a filled `review_queue.csv` |
| `ep-copilot evaluate [--extraction FILE]` | Screening precision/recall, and extraction accuracy from a filled `evidence_quotes.csv` |

Global options: `--topic`, `--config`, `--db`, `--out`. Set `NCBI_API_KEY` and `NCBI_EMAIL`
for faster PubMed access (optional).

## Outputs (`output/`)

| File | Contents |
|---|---|
| `ep_research_digest.html` | The digest: overview, literature, extraction, trials and changes, methods, queries |
| `articles.csv` | One row per article: links, scope, priority, categories, design label |
| `evidence_extraction.csv` | One row per article, one column per extracted field (blank = not stated) |
| `evidence_quotes.csv` | Every extracted value with its verbatim sentence, plus reviewer columns |
| `review_queue.csv` | Human review sheet: `source_id, title, url, topic, suggested_priority, ..., reviewer_decision, reviewer_notes` |
| `trials.csv`, `trial_changes.csv` | Tracked trials; field-level changes this run |
| `changes.json`, `run_metadata.json` | New/changed IDs; exact queries, windows, counts, provenance |

## How it decides things

- **Search window**: PubMed *Entrez date* (when a record entered PubMed), from the end of
  the last successful run minus one day, so nothing indexed between runs is missed.
- **Scope**: a record is in scope when it mentions AF **and** ablation terms (title, abstract,
  keywords, MeSH). Other EP records and unrelated records are kept and labelled, never dropped.
- **Priority** reflects topic relevance only: 2+ categories = high, 1 = medium, 0 = low,
  no abstract = review. Publication type is shown but never used to rank.
- **Extraction** is rule-based on abstracts. A value is kept only if its sentence is a
  verbatim substring of the abstract; effect estimates are copied, not recalculated.
- **Trial changes** compare stored snapshots field by field. Tracked trials that drop out of
  the status-filtered search are re-read individually, so a move to COMPLETED is caught.
- **Safety of data**: all fetching finishes before anything is written, and writes are one
  transaction, so a failed run never damages the previous month's data.

Details: [`docs/methodology.md`](docs/methodology.md). Limits: [`docs/limitations.md`](docs/limitations.md).

## Validation status

Automated tests cover parsing, deduplication, pagination, retries, windows, screening,
extraction, change detection, failure handling and outputs (`pytest`).
**Screening accuracy and extraction accuracy have not been measured by a human reviewer.**
[`docs/validation.md`](docs/validation.md) gives the procedure and records a developer
spot-check on 26 real records.

## Optional AI extraction

`ep_copilot/ai_optional.py` accepts any `complete(prompt) -> str` function. Proposals are
accepted only when the quoted evidence is verbatim in the abstract and every number in the
value appears in that quote; otherwise they are rejected. No model or key is bundled.

## Adding a topic

Copy the `af-ablation` block in `config/topics.yaml`, change the queries and patterns, and run
`ep-copilot run --topic <name>`. Each topic keeps its own records in the same database.

## Records retrieved some other way

`scripts/import_connector_export.py` converts PubMed / ClinicalTrials.gov connector JSON
exports into a snapshot that `ep-copilot run --snapshot DIR` processes like a normal run,
listing any fields the connector did not provide.

## License and data

Code: MIT. Abstracts and registry text belong to their publishers and sponsors; the digest
links to the sources and quotes only the sentences needed to support each extracted value.
Data courtesy of the U.S. National Library of Medicine (PubMed) and ClinicalTrials.gov.
