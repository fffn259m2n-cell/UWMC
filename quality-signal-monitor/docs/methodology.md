# Methodology

## Sources

| Dataset | CMS ID | Landing page |
|---|---|---|
| Patient survey (HCAHPS) - Hospital | `dgck-syfz` | https://data.cms.gov/provider-data/dataset/dgck-syfz |
| Patient survey (HCAHPS) - National | `99ue-w85f` | https://data.cms.gov/provider-data/dataset/99ue-w85f |
| Hospital General Information | `xubh-q36u` | https://data.cms.gov/provider-data/dataset/xubh-q36u |

`uwmc-monitor fetch` reads each dataset's metadata from the public CMS metastore API
(`https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items/<id>`),
takes the CSV `downloadURL` listed there, and records the URL, CMS `modified` and
`issued` dates, retrieval time (UTC), byte count and SHA-256 in `manifest.json`.
No URL to a data file is hard-coded, so a CMS file rename does not break the download.

Archived releases: https://data.cms.gov/provider-data/archived-data/hospitals

## Pipeline

1. **Normalization.** Headers become snake_case (`HCAHPS Answer Percent` →
   `hcahps_answer_percent`). Older header names are mapped (`provider_id` →
   `facility_id`, `measure_start_date` → `start_date`, ...). Every cell is read as text
   so leading zeros in IDs survive; numbers and dates are parsed into separate columns.
   The national file's `footnote` column is mapped to `hcahps_answer_percent_footnote`.
2. **Required columns.** A missing required column stops the run with a message naming it.
3. **Identity.** Facility `500008` must exist once in Hospital General Information, with a
   name containing `UNIVERSITY OF WASHINGTON`, state `WA` and city `SEATTLE`; the
   facility must also have rows in the HCAHPS hospital file. A different name in the
   HCAHPS file than in General Information is reported as an anomaly.
4. **Row checks** (see `validation.py`):

   | Check | Severity | Effect |
   |---|---|---|
   | Percent outside 0-100 | failure | row excluded |
   | Missing/unparseable dates, start after end | failure | row excluded |
   | Same measure ID repeated with different values | failure | all copies excluded |
   | Missing measure ID | failure | row excluded |
   | Exact duplicate rows | anomaly | extra copies dropped |
   | More than one reporting window in a release | anomaly | flagged |
   | Facility IDs not shaped like a CCN | anomaly | flagged |
   | Non-numeric percent ("Not Available", "Not Applicable") | info | counted |
   | Columns added/removed between releases | anomaly | flagged |

5. **Benchmark comparison.** For each UWMC measure, it is *comparable* only if all hold:
   - the row passed validation and the measure is a response percentage (star ratings
     and linear mean scores are excluded);
   - the UWMC value is numeric;
   - exactly one valid national row has the same measure ID, with a numeric value;
   - the national start and end dates equal UWMC's;
   - the answer description text matches (case and whitespace ignored).

   Otherwise the measure is *Not Comparable* and the first failing condition is recorded.

   `gap_pp = uwmc_percent − national_percent`.

6. **Directionality.** Rules in `signals.DIRECTION_RULES`, first match wins:

   | Pattern | Meaning | Direction |
   |---|---|---|
   | `*STAR_RATING*`, `*LINEAR_SCORE*` | not a percentage | excluded |
   | `H_HSP_RATING_9_10` / `_7_8` / `_0_6` | rating 9-10 / 7-8 / 0-6 | higher / middle / lower |
   | `H_RECMND_DY` / `_PY` / `_DN` | definitely / probably / not recommend | higher / middle / lower |
   | `*_SA`, `*_D_SD`, `H_CT_A` | strongly agree / disagree / agree | higher / lower / middle |
   | `*_A_P`, `*_U_P`, `*_SN_P` | always / usually / sometimes-never | higher / middle / lower |
   | `*_Y_P`, `*_N_P` | yes / no | higher / lower |
   | anything else | unknown | shown, never interpreted |

   `favorable_gap_pp` equals the gap for higher-is-better measures and its negative for
   lower-is-better ones. Each rule also lists words expected in the answer description;
   if none appear, an anomaly asks for manual review.

6a. **Focus domains** (`domains.py`). Each measure gets a domain from its ID or CMS
   question text, first match wins: Care transition (retired, `H_CT_*`), Discharge
   information (`H_COMP_6_*`, "recovery at home"), Communication about medicines
   (`H_COMP_5_*`, "medicine"), Care coordination ("coordinat"), Information about symptoms
   ("symptom"), then non-focus domains. The first four focus domains open the report.

6b. **Survey version.** Windows ending before 1 Jan 2025 are *original* survey, windows
   starting on or after it are *updated*, others *span the update* (flagged). Source: the
   CMS HCAHPS 2025 training materials on hcahpsonline.org, which also give January 2026
   for Care Transition leaving public reporting and October 2026 (estimated) for the first
   updated-survey results.

7. **Release comparison** (optional, `--previous-dir`). Both releases are processed
   independently; a measure's change is reported only if it was comparable in both, the
   response text is unchanged, the windows differ with the current one ending later, and both windows
   come from the same survey version (neither spanning the 1 Jan 2025 update).
   Overlapping windows are labelled "shared patients; changes are not independent".
   Synthetic fixtures cannot be compared with real data.

8. **Signal ranking.** Only comparable, non-retired top-box measures are ranked (middle and bottom boxes
   are close to the complement of the top box; ranking them too would count one result
   two or three times).

   ```
   confidence = low      if CMS footnote 6 or 10, or < 100 completed surveys
                caution  if any other footnote, or < 300 completed surveys, or count missing
                standard otherwise
   weight     = 1.0 standard, 0.75 caution, 0.5 low
   score      = |favorable_gap_pp| × weight
                + 1.0 if a comparable prior release exists and the gap to national
                      moved by more than 1 pp in the direction of the current gap
   ```

   Gap bands: *large* ≥ 5 pp, *moderate* ≥ 3 pp, otherwise *small*. A gap of ≤ 1 pp is
   marked "within rounding". These bands are reading aids, not significance thresholds.

9. **Narrative.** `TemplateNarrator` fills fixed sentences from the computed facts.
   The optional `LLMNarrator` receives only those aggregate facts and its output is
   rejected if it mentions any number or measure ID not in them.

## Reproducibility

The same input folder always yields the same tables. `analysis_metadata.json` records
tool version, input checksums and every rule value used. Tests in `tests/` cover each
rule above with synthetic fixtures.
