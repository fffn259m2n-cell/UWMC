"""Schema normalization, type conversion and data-quality checks.

Findings have one of three severities:
  failure  - a confirmed validation failure; affected rows are excluded from analysis
  anomaly  - a potential problem worth a human look; rows are kept but flagged
  info     - context (e.g. counts of suppressed values), not a problem in itself
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

import pandas as pd

# Older CMS releases used different header names for the same fields.
COLUMN_ALIASES = {
    "provider_id": "facility_id",
    "ccn": "facility_id",
    "hospital_name": "facility_name",
    "city": "city_town",
    "measure_start_date": "start_date",
    "measure_end_date": "end_date",
    "footnote": "hcahps_answer_percent_footnote",
}

REQUIRED_COLUMNS = {
    "hcahps_hospital": ["facility_id", "hcahps_measure_id", "hcahps_answer_percent",
                        "start_date", "end_date"],
    "hcahps_national": ["hcahps_measure_id", "hcahps_answer_percent", "start_date", "end_date"],
    "hospital_general": ["facility_id", "facility_name", "state"],
}

# Retained when present; absence is reported but not fatal.
OPTIONAL_COLUMNS = {
    "hcahps_hospital": ["facility_name", "hcahps_question", "hcahps_answer_description",
                        "hcahps_answer_percent_footnote", "number_of_completed_surveys",
                        "number_of_completed_surveys_footnote", "survey_response_rate_percent"],
    "hcahps_national": ["hcahps_question", "hcahps_answer_description",
                        "hcahps_answer_percent_footnote"],
    "hospital_general": ["city_town", "hospital_type", "hospital_ownership",
                         "hospital_overall_rating"],
}

# CMS CCNs are six characters: two-digit state code + four characters.
CCN_PATTERN = re.compile(r"^[0-9]{2}[0-9A-Z]{4}$")


class SchemaError(ValueError):
    """Raised when a dataset lacks columns the analysis cannot do without."""


@dataclass
class Finding:
    severity: str
    dataset: str
    check: str
    detail: str
    count: int = 0
    measure_ids: list[str] = field(default_factory=list)

    def as_row(self) -> dict:
        row = asdict(self)
        row["measure_ids"] = ";".join(self.measure_ids)
        return row


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """snake_case all headers, map historical aliases, strip cell whitespace."""
    out = df.copy()
    out.columns = (
        out.columns.str.strip().str.lower()
        .str.replace(r"[^a-z0-9]+", "_", regex=True).str.strip("_")
    )
    renames = {old: new for old, new in COLUMN_ALIASES.items()
               if old in out.columns and new not in out.columns}
    out = out.rename(columns=renames)
    for col in out.columns:
        out[col] = out[col].astype("string").str.strip().fillna("")
    return out


def require_columns(df: pd.DataFrame, key: str) -> None:
    missing = [c for c in REQUIRED_COLUMNS[key] if c not in df.columns]
    if missing:
        raise SchemaError(
            f"{key}: required column(s) missing: {', '.join(missing)}. "
            f"Columns present: {', '.join(df.columns)}. "
            "CMS may have changed the schema; compare with the dataset dictionary."
        )


def to_number(series: pd.Series) -> pd.Series:
    """Parse numeric text. 'Not Available', blanks, etc. become NaN."""
    cleaned = series.astype("string").str.replace(",", "", regex=False).str.rstrip("%")
    return pd.to_numeric(cleaned, errors="coerce").astype("float64")


def to_date(series: pd.Series) -> pd.Series:
    """CMS uses MM/DD/YYYY; accept ISO dates as well."""
    s = series.astype("string")
    parsed = pd.to_datetime(s, format="%m/%d/%Y", errors="coerce")
    iso = pd.to_datetime(s, format="%Y-%m-%d", errors="coerce")
    return parsed.fillna(iso)


def prepare_hcahps(df: pd.DataFrame, key: str) -> pd.DataFrame:
    """Normalize an HCAHPS table and add parsed numeric/date columns."""
    df = normalize_columns(df)
    require_columns(df, key)
    for col in OPTIONAL_COLUMNS[key]:
        if col not in df.columns:
            df[col] = ""
    df["hcahps_measure_id"] = df["hcahps_measure_id"].str.upper()
    df["answer_percent"] = to_number(df["hcahps_answer_percent"])
    df["start"] = to_date(df["start_date"])
    df["end"] = to_date(df["end_date"])
    if "number_of_completed_surveys" in df.columns:
        df["completed_surveys"] = to_number(df["number_of_completed_surveys"])
    return df


def prepare_general(df: pd.DataFrame) -> pd.DataFrame:
    df = normalize_columns(df)
    require_columns(df, "hospital_general")
    for col in OPTIONAL_COLUMNS["hospital_general"]:
        if col not in df.columns:
            df[col] = ""
    return df


# ---------------------------------------------------------------- checks


def _ids(frame: pd.DataFrame) -> list[str]:
    return sorted(frame["hcahps_measure_id"].dropna().unique().tolist())


def check_hcahps(df: pd.DataFrame, dataset: str) -> tuple[pd.DataFrame, list[Finding]]:
    """Run row-level checks. Returns the frame with an `excluded_reason` column and findings.

    Rows with a confirmed failure keep their place in the frame but get an
    `excluded_reason`, so every exclusion stays traceable in the outputs.
    """
    df = df.copy()
    findings: list[Finding] = []
    df["excluded_reason"] = ""

    def exclude(mask: pd.Series, reason: str) -> None:
        df.loc[mask & (df["excluded_reason"] == ""), "excluded_reason"] = reason

    raw = df["hcahps_answer_percent"]
    nonnumeric = df["answer_percent"].isna()
    if nonnumeric.any():
        values = sorted(set(raw[nonnumeric].replace("", "(blank)")))
        findings.append(Finding(
            "info", dataset, "non_numeric_answer_percent",
            "Answer percent is not a number (suppressed, not applicable, or a star/linear-score "
            f"row). Values seen: {', '.join(values[:6])}.",
            int(nonnumeric.sum()), _ids(df[nonnumeric])))

    out_of_range = ~nonnumeric & ~df["answer_percent"].between(0, 100)
    if out_of_range.any():
        exclude(out_of_range, "percentage outside 0-100")
        findings.append(Finding(
            "failure", dataset, "percent_out_of_range",
            "Answer percent outside 0-100; rows excluded.",
            int(out_of_range.sum()), _ids(df[out_of_range])))

    bad_dates = df["start"].isna() | df["end"].isna()
    if bad_dates.any():
        exclude(bad_dates, "unparseable reporting dates")
        findings.append(Finding(
            "failure", dataset, "unparseable_dates",
            "Start or end date missing or unparseable; rows excluded.",
            int(bad_dates.sum()), _ids(df[bad_dates])))

    reversed_dates = ~bad_dates & (df["start"] > df["end"])
    if reversed_dates.any():
        exclude(reversed_dates, "start date after end date")
        findings.append(Finding(
            "failure", dataset, "start_after_end",
            "Reporting start date is after end date; rows excluded.",
            int(reversed_dates.sum()), _ids(df[reversed_dates])))

    windows = df.loc[~bad_dates, ["start_date", "end_date"]].drop_duplicates()
    if len(windows) > 1:
        desc = "; ".join(f"{a} to {b}" for a, b in windows.itertuples(index=False))
        findings.append(Finding(
            "anomaly", dataset, "multiple_reporting_windows",
            f"More than one reporting window in a single release ({desc}). "
            "Only measures sharing a window with the benchmark are compared.",
            len(windows)))

    keys = ["hcahps_measure_id"] + (["facility_id"] if "facility_id" in df.columns else [])
    exact_dupes = df.duplicated(keep="first")
    if exact_dupes.any():
        exclude(exact_dupes, "exact duplicate row")
        findings.append(Finding(
            "anomaly", dataset, "exact_duplicate_rows",
            "Identical rows repeated; duplicates dropped, first kept.",
            int(exact_dupes.sum()), _ids(df[exact_dupes])))

    live = df["excluded_reason"] == ""
    conflicting = pd.Series(False, index=df.index)
    conflicting[live] = df[live].duplicated(subset=keys, keep=False)
    if conflicting.any():
        exclude(conflicting, "conflicting duplicate measure rows")
        findings.append(Finding(
            "failure", dataset, "conflicting_duplicates",
            f"Same {' + '.join(keys)} appears with different values; all copies excluded "
            "because the correct value cannot be determined.",
            int(conflicting.sum()), _ids(df[conflicting])))

    blank_ids = df["hcahps_measure_id"] == ""
    if blank_ids.any():
        exclude(blank_ids, "missing measure ID")
        findings.append(Finding(
            "failure", dataset, "missing_measure_id",
            "Rows without a measure ID; excluded.", int(blank_ids.sum())))

    return df, findings


def check_facility_ids(df: pd.DataFrame, dataset: str) -> list[Finding]:
    """Flag identifiers that do not look like a CMS Certification Number."""
    if "facility_id" not in df.columns:
        return []
    ids = df["facility_id"].drop_duplicates()
    odd = ids[~ids.str.fullmatch(CCN_PATTERN.pattern)]
    if odd.empty:
        return []
    return [Finding(
        "anomaly", dataset, "unexpected_facility_ids",
        "Facility IDs not matching the six-character CCN pattern "
        f"(examples: {', '.join(odd.head(5))}). Leading zeros may have been lost if a "
        "file was opened and re-saved in a spreadsheet.", int(len(odd)))]


def check_schema_drift(current: dict[str, list[str]], previous: dict[str, list[str]]) -> list[Finding]:
    """Compare normalized column sets of two releases, dataset by dataset."""
    findings = []
    for key in current:
        cur, prev = set(current[key]), set(previous.get(key, []))
        added, removed = sorted(cur - prev), sorted(prev - cur)
        if added or removed:
            findings.append(Finding(
                "anomaly", key, "schema_changed_between_releases",
                f"Added columns: {', '.join(added) or 'none'}; "
                f"removed columns: {', '.join(removed) or 'none'}.",
                len(added) + len(removed)))
    return findings


def findings_frame(findings: list[Finding]) -> pd.DataFrame:
    cols = ["severity", "dataset", "check", "detail", "count", "measure_ids"]
    order = {"failure": 0, "anomaly": 1, "info": 2}
    df = pd.DataFrame([f.as_row() for f in findings], columns=cols)
    return df.sort_values("severity", key=lambda s: s.map(order), kind="stable").reset_index(drop=True)
