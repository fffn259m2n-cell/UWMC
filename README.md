# UWMC

Independent, open-source contributions intended for UW Medicine and University of
Washington Medical Center teams. Each folder is a self-contained project with its own
README, tests, documentation and gift-handoff notes.

> None of these projects is affiliated with, requested by, or endorsed by UW Medicine.
> They use only public data or clearly labelled synthetic data. No patient records,
> no PHI, no institutional credentials.

| Project | What it does | Data | Status |
|---|---|---|---|
| [quality-signal-monitor](quality-signal-monitor/) | Benchmarks UWMC's public CMS HCAHPS patient-experience results against matched national values, led by discharge and care-transition measures, with data-quality checks and an HTML/PDF report | CMS Provider Data Catalog (public) | Tested on synthetic fixtures; first real run pending (CMS blocked in build environment) |
| [ep-research-copilot](ep-research-copilot/) | Monthly AF-ablation literature discovery, abstract evidence extraction with source quotes, and ClinicalTrials.gov change tracking for an EP research team | PubMed, ClinicalTrials.gov (public) | Tested; sample run on 26 real articles and 396 real trials |
| [teach-back-companion](teach-back-companion/) | Patient teach-back checks on discharge instructions, plus an Instruction Fidelity Evaluator that flags dose, negation, 911 and medicine-name errors in simplified, AI-generated or translated instructions | Fictional patients only | Working local web app; 247 tests; browser and accessibility checks pass; accuracy measured on independent cases (see its docs); not clinically reviewed |

## Quick start

Each project installs and runs on its own (Python 3.11+):

```bash
cd quality-signal-monitor && pip install -e . && uwmc-monitor run --fetch
cd ep-research-copilot   && pip install -e . && ep-copilot run
cd teach-back-companion  && pip install -e . && teachback serve   # http://127.0.0.1:8000
```

Offline demos with synthetic data are described in each README. CI runs every project's
tests on Python 3.11 to 3.13.

## What is new

- **Safety gate for AI-drafted patient text** and **misunderstanding insights** in the Teach-Back Companion, plus **voice** and **caregiver** modes.
- The Quality Monitor report can show **teach-back findings beside the HCAHPS discharge measures**.
- The EP digest opens with **alerts**: results posted, new randomized trials, Washington State site changes.
- **Automatic real-data runs** on GitHub: quarterly CMS report and monthly EP digest (`.github/workflows/scheduled-reports.yml`).
- Double-click start files for **Mac** and **Windows**; Windows is tested in CI.

## Guides

| Guide | For |
|---|---|
| [TESTING.md](TESTING.md) | Trying everything yourself, step by step, with expected results |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Adding topics, measures, plans and rules; checks to run before a commit |
| [REVIEW.md](REVIEW.md) | Independent reviewers: access, what to look for, how to report (`python review/make_review_packet.py` builds a zip to send) |
| [DELIVERY_PLAN.md](DELIVERY_PLAN.md) | How to hand these over to UW Medicine teams |
| [samples/](samples/) | Sample outputs on synthetic data (open in a browser) |
| [one-pagers/pdf/](one-pagers/pdf/) | One-page PDF summary of each project |
| [downloads/](downloads/) | Everything in one zip, and the reviewer packet |
| [mac/](mac/), [windows/](windows/) | Double-click files that install everything and start the demo |

## Before sharing anything

Each project has a `docs/gift_handoff.md` with a checklist marked **[CONFIRM]**. Work
through it, run the tool on real data, and have a qualified person review the output
before it goes to anyone at UW Medicine.

## License

MIT for all code (see each project's LICENSE). Source data keeps its own terms.
