# Limitations

**What the data is.** HCAHPS percentages are survey results from a sample of adult
inpatients after discharge, adjusted by CMS for patient mix and survey mode, and
published as whole numbers for a rolling four-quarter window that ends several months
before release. They describe patient-reported experience, not clinical outcomes.

**What the tool cannot say**

- **No significance testing.** CMS does not publish standard errors with these values,
  so the tool does not claim any difference is statistically significant.
- **Rounding.** Both values are rounded; a 1 pp gap can come from rounding alone.
- **National average is a broad comparator.** It pools hospitals of every size, type and
  case mix. An academic medical center may differ for reasons unrelated to patient
  experience. A peer-group benchmark (e.g. similar teaching hospitals) would need a
  defensible peer definition and is not implemented.
- **Overlapping windows.** Consecutive quarterly releases share about three quarters of
  their patients, so release-to-release changes are not independent; the report says so.
- **One snapshot is not a trend.** Without `--previous-dir`, no change over time is shown.
- **Discharge measures are patient-reported.** A high "given information about recovery at
  home" score means patients said they received it, not that they understood it, followed
  it, or had a safe transition. Readmission and outcome data are outside this tool.
- **Survey transition.** Domain matching for updated-survey items relies on CMS question
  wording; confirm against the current HCAHPS data dictionary once the first updated-survey
  release is out.
- **Directionality is rule-based.** It follows CMS measure-ID conventions. New measure IDs
  (the HCAHPS survey was updated for discharges from January 2025, adding and retiring
  items) are reported as *unknown* until a rule is added. Check new rules against the
  current CMS data dictionary.
- **Footnotes.** Footnote codes are carried through and lower the confidence label, but
  their meaning is not restated in full; see the CMS footnote crosswalk on the Provider
  Data Catalog.
- **Facility scope.** Results cover only CMS facility ID 500008. Whether CMS reports
  other UW Medicine campuses under that ID depends on CMS's own enrollment records;
  verify on Medicare Care Compare before describing scope.
- **Schema changes.** CMS can rename or restructure columns. The tool stops on a missing
  required column and flags added/removed columns between releases, but cannot repair them.

**What it does not do by design:** no patient-level data, no causal claims, no clinical
recommendations, no predictions, no automatic contact with any organization.
