# Contributing and extending

All three projects are plain Python 3.11+ packages with no services, accounts or keys.
Anyone who can edit a YAML or JSON file can extend the content, and anyone who knows a
little Python can extend the logic. Every change is checked by the same tests CI runs.

## 1. Set up once

```bash
git clone https://github.com/fffn259m2n-cell/UWMC.git && cd UWMC
python3 -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e "./quality-signal-monitor[dev]" -e "./ep-research-copilot[dev]" -e "./teach-back-companion[dev]" ruff
```

Or open the repository in GitHub Codespaces; the devcontainer does all of this for you.

## 2. Before every commit

```bash
ruff check .                                              # lint (settings in ruff.toml)
(cd quality-signal-monitor && pytest -q)
(cd ep-research-copilot   && pytest -q)
(cd teach-back-companion  && pytest -q && teachback check-content && teachback evaluate-set eval/dev_set.json)
```

CI (`.github/workflows/tests.yml`) runs the same steps on Python 3.11, 3.12 and 3.13, plus
a browser and accessibility check of the Teach-Back web app. A pull request is ready when CI
is green.

## 3. Ground rules (all projects)

- **No patient data, ever.** Public data (CMS, PubMed, ClinicalTrials.gov) or fictional
  patients only. Teach-Back refuses to load a plan not marked `"synthetic": true`.
- **No credentials in the repository.** Nothing here needs one.
- **No institution or vendor branding** without written permission from its owner.
- **Every new rule gets a test**, and every fixed bug gets a regression test that would
  have caught it.
- **Say what is measured, not what is hoped.** Do not describe a tool as validated,
  endorsed or deployed unless that has happened.

## 4. Recipes: common additions

### Quality Signal Monitor (`quality-signal-monitor/`)

| I want to… | Edit | Then |
|---|---|---|
| Change which HCAHPS measures count as discharge / care-coordination focus | `src/uwmc_monitor/domains.py`, the `DOMAINS` tuple (first match wins; match on measure ID or question text) | Add a case to `tests/test_analysis.py` |
| Track a different hospital | `--facility-id <CCN>` on the command line | Nothing; the code is hospital-agnostic |
| Add a data-quality check | `src/uwmc_monitor/validation.py` (`check_*` functions return `Finding`s) | Add a fixture row that triggers it (`tests/fixtures/make_fixtures.py`) and a test in `tests/test_validation.py` |
| Change report wording or layout | `src/uwmc_monitor/templates/report.html.j2`, `narrative.py` | `pytest -q`, then open `output/uwmc_quality_report.html` |
| Add a CMS dataset | `src/uwmc_monitor/sources.py` (`DATASETS`) | Add a synthetic fixture and a schema test in `tests/test_validation.py` |

### EP Research Copilot (`ep-research-copilot/`)

| I want to… | Edit | Then |
|---|---|---|
| Add a research topic (e.g. VT ablation) | Copy the `af-ablation` block in `config/topics.yaml`; change the PubMed and trials queries and the scope patterns | `ep-copilot run --topic <name> --days 30` |
| Change screening categories or priority | `config/topics.yaml` (`categories`), `src/ep_copilot/screening.py` | Add a labelled example to `tests/test_screening.py` |
| Extract a new field from abstracts | `src/ep_copilot/extraction.py` (`FIELDS` plus a function that returns the verbatim sentence) | Add a test to `tests/test_extraction.py`; quotes must stay verbatim |
| Add an optional AI summary | `src/ep_copilot/ai_optional.py` (off by default; output is labelled and never replaces quotes) | Tests must pass with no API key |

### Teach-Back Companion (`teach-back-companion/`)

| I want to… | Edit | Then |
|---|---|---|
| Add a fictional patient or condition | New file in `src/teachback/data/plans/` (copy `heart_failure.json`) | `teachback check-content`; the plain versions must pass the evaluator (`test_every_plain_version_passes`) |
| Add a known misunderstanding for one instruction | That fact's `misconceptions` list: `id`, a regular-expression `pattern`, and a patient-facing `message` that points back to the instruction | Add a "dangerous" and a "correct" case for it to `eval/dev_set.json` |
| Add an education topic or glossary term | `src/teachback/data/knowledge/library.json` (cite a public source) | `teachback check-content` |
| Add a general rule (applies to every plan) | `src/teachback/consistency.py` for meaning changes; `safety.py` for emergency/crisis/medication screening; `text.py` for numbers and negation | Add dev-set cases and a unit test, re-run `teachback evaluate-set eval/dev_set.json`, and check no correct case starts to fail |
| Re-skin the interface | `src/teachback/static/themes/` (see `institution-template.css`); `teachback serve --theme <name>` | Re-run the browser check |

How the content model works (one paragraph): each care-plan **item** stores the clinician's
`original` wording, a `plain` version, and a list of **facts**. A fact lists the
`concepts` a good explanation includes (synonym groups), the `quantities` that must not
change, an optional "do not" `action`, whether it is an `emergency` (911) fact, and known
`misconceptions`. Teach-back, the fidelity evaluator and chat all read these same facts, so
clinical knowledge is written once. Field-by-field reference: `src/teachback/models.py`.

## 5. Measuring accuracy honestly (Teach-Back)

- `eval/dev_set.json` is the **development set**. You may tune rules on it; CI checks that
  it does not regress (`tests/test_evaluation_set.py`).
- `eval/heldout_set.json` is the **held-out set**, written independently. **Never tune on
  it.** Report its numbers as the accuracy estimate. When you have used it to make a
  decision, move it into the dev set and ask someone new for a fresh held-out set.
- The format is documented at the top of `src/teachback/evaluation.py`. Anyone can write
  their own set and run `teachback evaluate-set my_cases.json --show-misses`.

## 6. Reporting problems and reviews

Use the GitHub issue forms (**Issues → New issue**): "Bug report" or "Independent review
finding". For an external review, see [REVIEW.md](REVIEW.md).
