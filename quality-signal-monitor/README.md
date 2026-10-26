# UWMC Quality Signal Monitor

A small, open-source tool that turns **public CMS patient-survey (HCAHPS) data** for
University of Washington Medical Center (CMS facility ID **500008**) into a short,
reproducible report. The report compares UWMC with matched national values, flags
changes between CMS releases, and lists every data problem it finds.

> **Independent project.** This is an unpaid, public-interest contribution. It is not
> affiliated with, requested by, or endorsed by UW Medicine or CMS. It uses only
> public, hospital-level CMS data: no patient records, no PHI, no credentials.

---

## For quality and patient-experience staff

**What problem does it solve?** Each CMS refresh means someone downloads several large
files, finds UWMC's rows, lines them up against the national figures, and checks that
the reporting periods match. This tool does that the same way every time, in about a
minute, and keeps a record of exactly which files it used.

**Focus: discharge and care transitions.** The report opens with the HCAHPS items closest
to the hand-off from hospital to home, the part of patient experience most tied to
Internal Medicine work: discharge information, communication about medicines, care
coordination and information about symptoms. All other HCAHPS measures follow.

**What it tells you**

1. Which publicly reported HCAHPS measures are above or below the matched national value, in percentage points.
2. How each measure changed since an earlier CMS release, when you supply one.
3. Which results need checking first: suppressed values, CMS footnotes, small survey counts,
   reporting-period mismatches, overlapping windows, schema changes.

**What it does not do**

- It does not test statistical significance. CMS publishes adjusted whole-number
  percentages without standard errors, so gaps are descriptive only.
- It does not explain causes, judge quality of care, or make clinical recommendations.
- It does not use or infer anything about individual patients.
- It does not combine other UW Medicine facilities with UWMC; it reports exactly what
  CMS publishes under facility ID 500008.

**Outputs** (in `output/`)

| File | Contents |
|---|---|
| `uwmc_quality_report.html` | The report: summary, signals, charts, comparisons, data quality, limitations, sources |
| `uwmc_quality_report.pdf` | Same report as PDF (if WeasyPrint or Chrome/Chromium is available) |
| `benchmark_comparisons.csv` | Every UWMC measure with national value, gap, and the reason when not comparable |
| `ranked_signals.csv` | Top-box measures ranked by the transparent score |
| `release_changes.csv` | Change versus a prior release (only with `--previous-dir`) |
| `data_quality_findings.csv` | Failures, anomalies and informational notes |
| `analysis_metadata.json` | Source URLs, CMS dates, checksums, retrieval times, all rules used |

---

## Quick start

Requires Python 3.11+.

```bash
git clone <this repository>
cd uwmc-quality-signal-monitor
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e .                                       # or: pip install -r requirements.txt

uwmc-monitor run --fetch      # download the current CMS release, then build the report
```

Open `output/uwmc_quality_report.html` in a browser. Add `--pdf` to also write a PDF.

Equivalent module form: `python -m uwmc_monitor.cli run --fetch`.

### Step by step

```bash
uwmc-monitor fetch       # saves data/raw/<CMS-modified-date>/ with a manifest.json
uwmc-monitor validate    # prints data-quality findings; exit code 1 if any failure
uwmc-monitor analyze     # writes the CSV/JSON tables
uwmc-monitor report      # writes tables + HTML report
```

All commands accept `--data-dir`, `--previous-dir`, `--out` and `--facility-id`.
`--data-dir` may point at a release folder or at `data/`; with `data/`, the newest
`data/raw/<release>/` folder is used.

### Offline or manual downloads

If `fetch` cannot reach CMS, download the three CSVs from the dataset pages below
("Download full dataset (CSV)") and save them in one folder, for example
`data/raw/<release-date>/`, as `hcahps_hospital.csv`, `hcahps_national.csv` and
`hospital_general.csv`. The original CMS archive file names (`HCAHPS-Hospital.csv`,
`HCAHPS-National.csv`, `Hospital_General_Information.csv`) also work. The report will
note that the files were placed by hand and list their checksums. See `data/README.md`.

### Comparing with an earlier release

CMS keeps past releases at <https://data.cms.gov/provider-data/archived-data/hospitals>.
Download one, unzip the three files into their own folder, and run:

```bash
uwmc-monitor run --data-dir data/raw/<current-release> --previous-dir data/raw/<earlier-release>
```

Because HCAHPS uses rolling four-quarter windows, consecutive quarterly releases share
most of their patients; the report says so whenever windows overlap. Use releases a
year apart for non-overlapping periods.

### Try it with synthetic data (no network)

```bash
uwmc-monitor run --data-dir tests/fixtures/synthetic_current \
                 --previous-dir tests/fixtures/synthetic_previous
```

Every value in these fixtures is invented. The report is stamped **SYNTHETIC TEST DATA**
on the page, in the title and across each chart, and must not be shared as a result.

---

## Data sources

All are public CMS Provider Data Catalog datasets, retrieved through the documented
DKAN metastore API (`/provider-data/api/1/metastore/schemas/dataset/items/<id>`), which
needs no API key.

| Dataset | CMS ID | Used for |
|---|---|---|
| [Patient survey (HCAHPS) - Hospital](https://data.cms.gov/provider-data/dataset/dgck-syfz) | `dgck-syfz` | UWMC's measure values, footnotes, survey counts, reporting window |
| [Patient survey (HCAHPS) - National](https://data.cms.gov/provider-data/dataset/99ue-w85f) | `99ue-w85f` | National values for the same measure IDs and window |
| [Hospital General Information](https://data.cms.gov/provider-data/dataset/xubh-q36u) | `xubh-q36u` | Verifying facility identity and metadata |

Raw files are saved unchanged and never committed (`data/raw/` is git-ignored).

## How it works

1. **Identity.** Find facility `500008` in Hospital General Information and check that the
   name contains "UNIVERSITY OF WASHINGTON", the state is WA and the city is SEATTLE.
   Any mismatch stops the run.
2. **Normalize and validate.** Snake-case headers (with aliases for older CMS names), parse
   numbers and dates, and record failures (excluded rows) and anomalies (flagged rows).
3. **Compare.** A measure is comparable only if the UWMC value is numeric, exactly one
   national row has the same measure ID, both cover the identical reporting window,
   and the response text agrees. Otherwise it is listed as *Not Comparable* with the reason.
4. **Interpret direction** from CMS measure-ID conventions (`_A_P` "always" = top box,
   `_SN_P` = bottom box, `H_HSP_RATING_9_10`, `H_RECMND_DY`, ...). Unknown IDs are shown
   but never labelled favorable or unfavorable.
5. **Group by domain.** Measures are assigned to domains (discharge information, medicines,
   care coordination, symptoms, ...) from their CMS question text, so items added by the
   updated survey are found even under new IDs.
6. **Respect the 2025 survey update.** CMS updated HCAHPS for discharges from 1 January 2025
   (Care Transition dropped; Care Coordination, Information About Symptoms and Restfulness
   added). Care Transition is shown as retired and never ranked; release-to-release changes
   are only computed when both windows come from the same survey version.
7. **Rank** top-box measures: `score = |gap| x confidence weight (+1 if the gap grew >1 pp
   since a comparable prior release)`.
8. **Report** with a deterministic template narrative. Every number in it comes from
   the tables.

Details: [`docs/methodology.md`](docs/methodology.md) and [`docs/limitations.md`](docs/limitations.md).

## Optional AI narrative

Off by default, with no AI dependency. `uwmc_monitor.narrative.LLMNarrator` accepts any
function `complete(prompt) -> str`. It sends only aggregate facts (published percentages,
measure IDs, counts), rejects any draft containing a number or measure ID not found in
those facts, and falls back to the template. All narrative is marked as a draft for
human review.

```python
from uwmc_monitor.analysis import analyze
from uwmc_monitor.narrative import LLMNarrator
from uwmc_monitor.reporting import write_report

result = analyze("data/raw/<release>")
write_report(result, "output", narrator=LLMNarrator(my_complete_function))
```

## Modifying the tool

| To change | Edit |
|---|---|
| Target hospital | `--facility-id`, and the identity constants at the top of `analysis.py` |
| Direction rules, gap bands, confidence weights | `signals.py` (all rules are listed in the report) |
| Focus domains, survey-version dates | `domains.py` |
| Data checks | `validation.py` |
| Report layout | `src/uwmc_monitor/templates/report.html.j2` |
| Source datasets | `DATASETS` in `sources.py` |

Run the tests with `pip install -e ".[dev]" && pytest`. CI runs them on Python 3.11-3.13.

## Project layout

```
src/uwmc_monitor/   cli, sources, validation, analysis, domains, signals, narrative, reporting, templates/
tests/              pytest suite; fixtures/ holds SYNTHETIC CMS-shaped files + generator
data/               README for data placement; raw/ downloads are git-ignored
docs/               methodology, limitations, gift handoff
output/             generated reports (git-ignored)
```

## License

MIT. Free to use, modify and redistribute.
