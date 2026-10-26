# Gift handoff: UWMC Quality Signal Monitor

> **Status: DRAFT for human review. Not sent.** Items marked **[CONFIRM]** must be
> checked by hand before anything goes to UW Medicine.

## What it is (non-technical)

A free, open-source tool that reads the patient-survey results CMS publishes for
University of Washington Medical Center and produces a short report, led by the
measures closest to the hospital-to-home transition: discharge information,
communication about medicines, care coordination and information about symptoms. The report shows
where UWMC's publicly reported HCAHPS results sit relative to the national figures for
the same survey period, what changed since an earlier CMS release, and which numbers
should be checked before anyone relies on them. It runs on a laptop in about a minute
and needs no login, no patient data and no access to UW Medicine systems.

## How it could help

- Saves the manual work of downloading CMS files, finding UWMC's rows and lining them
  up with national values after each CMS refresh.
- Checks reporting periods and response categories automatically, so measures from
  different periods are never compared by mistake.
- Records exactly which CMS files were used (URLs, dates, checksums), so anyone can
  re-run it and get the same tables.
- Gives a plain list of data issues (suppressed values, footnotes, small survey counts,
  schema changes) alongside the results.

## Official public datasets used

| Dataset | Page |
|---|---|
| Patient survey (HCAHPS) - Hospital (`dgck-syfz`) | https://data.cms.gov/provider-data/dataset/dgck-syfz |
| Patient survey (HCAHPS) - National (`99ue-w85f`) | https://data.cms.gov/provider-data/dataset/99ue-w85f |
| Hospital General Information (`xubh-q36u`) | https://data.cms.gov/provider-data/dataset/xubh-q36u |
| Archived releases (for change over time) | https://data.cms.gov/provider-data/archived-data/hospitals |

Target: CMS facility ID 500008, University of Washington Medical Center, Seattle, WA.

## Verified findings

**None yet.** The tool was built and tested in an environment that could not reach
data.cms.gov, so it has only been run on synthetic test files. Before sending:

1. **[CONFIRM]** Run `uwmc-monitor run --fetch --pdf` on a machine with internet access.
2. **[CONFIRM]** Check that the identity section shows facility 500008 with the expected
   name and Seattle address, and compare it with the Medicare Care Compare profile.
3. **[CONFIRM]** Spot-check at least three numbers in `benchmark_comparisons.csv` against
   the CMS website values for UWMC and the national figure.
4. **[CONFIRM]** Read the data-quality section; resolve or explain any *failure*.
5. Replace this section with 3-5 findings copied from the report, each with its CMS
   measure ID, both values, the gap and the reporting window, worded descriptively
   (e.g. "X was N pp below the national value for <window>"), with no causes or advice.

## Known limitations

Descriptive gaps only (no significance testing); values are rounded; the national
average is a broad comparator; consecutive releases overlap; new HCAHPS measure IDs
need direction rules; only facility ID 500008 is covered. Full list:
[`limitations.md`](limitations.md).

## Links

- Code: **[CONFIRM: repository URL once published]**
- Report: **[CONFIRM: link to the PDF generated from real CMS data]**
- Methodology: [`methodology.md`](methodology.md)

## Independence and reuse

This contribution is independent and unpaid. UW Medicine did not request or endorse it.
It is released under the MIT license and may be used, modified or discarded freely.
There is no expectation of compensation, a role, or ongoing involvement.

---

## Who should receive it

The intended readers are UW Medicine's patient-experience, quality-improvement or
clinical-analytics staff, not a general volunteer office.

- **Best-fit route:** the UW Center for Scholarship in Patient Care Quality and Safety
  (UW Department of Medicine). UW's Biomedical Informatics faculty page lists
  Andrew White, MD, as a UWMC hospitalist, UW Medicine's assistant Chief Health
  Information Officer, and director of that Center
  (https://bime.uw.edu/faculty/andrew-white/). A 2026 UW Medicine news item gives his
  title slightly differently, so **[CONFIRM]** the current title, and take his email
  address from the official UW directory rather than from any secondary source.
- **If you are at UW**, an introduction from your own faculty mentor is better than a
  cold email.
- **Fallback:** the UW Medicine contact directory on uwmedicine.org, asking for the
  patient-experience or quality team. **[CONFIRM]** the page URL.
- Do not send unsolicited attachments to personal addresses. Prefer a short message
  with links, and offer the PDF on request.

## Draft message

> Subject: Open-source tool for UWMC public discharge and care-transition (HCAHPS) reporting
>
> Hello UW Medicine team,
>
> I independently built a small open-source tool as a contribution to UW Medical Center
> and would be grateful if this could be forwarded to the team responsible for patient
> experience, quality improvement or clinical analytics.
>
> The tool uses only publicly available CMS hospital data (HCAHPS patient-survey and
> Hospital General Information datasets). It focuses on discharge information,
> communication about medicines and care coordination, compares UWMC's publicly
> reported measures with matched national values, accounts for the 2025 HCAHPS survey
> update, track changes between CMS releases, and list data
> limitations. It produces a reproducible summary report. It uses no patient-level data
> and needs no access to UW Medicine systems.
>
> Repository: [link]
> Summary report (PDF): [link]
>
> I am sharing this freely under an open-source license, with no expectation of
> compensation or a formal role. Please feel free to use, adapt or set it aside.
>
> Thank you for your work serving patients and the community.
>
> [Your name]
> [Optional: one line about your background]
