# Data folder

Nothing in this folder is committed except this file. Raw CMS downloads go in
`data/raw/<release>/`, one folder per CMS release:

```
data/raw/<release>/
    hcahps_hospital.csv      Patient survey (HCAHPS) - Hospital      https://data.cms.gov/provider-data/dataset/dgck-syfz
    hcahps_national.csv      Patient survey (HCAHPS) - National      https://data.cms.gov/provider-data/dataset/99ue-w85f
    hospital_general.csv     Hospital General Information            https://data.cms.gov/provider-data/dataset/xubh-q36u
    manifest.json            written by `uwmc-monitor fetch`: URLs, CMS dates, retrieval time, SHA-256
```

`uwmc-monitor fetch` creates the folder (named after the CMS "modified" date of the
HCAHPS hospital dataset) and never overwrites existing files.

**Manual download:** on each dataset page choose "Download full dataset (CSV)" and
save into one release folder using the names above. CMS archive names
(`HCAHPS-Hospital.csv`, `HCAHPS-National.csv`, `Hospital_General_Information.csv`)
are also accepted, so an extracted archive folder from
<https://data.cms.gov/provider-data/archived-data/hospitals> can be used as is.

Do not open and re-save the CSVs in a spreadsheet: that can strip leading zeros from
facility IDs and change date formats. The tool flags IDs that look damaged.

All three files from one release folder must come from the same CMS refresh, or the
reporting windows will not match and measures will be marked Not Comparable.

These are public, hospital-level aggregate files. They contain no patient-level data.
