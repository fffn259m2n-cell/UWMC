"""Hospital identification, measure extraction, benchmark and release comparison."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import domains, signals, sources, validation
from .validation import Finding

TARGET_FACILITY_ID = "500008"
# Identity checks applied to the CMS Hospital General Information record.
EXPECTED_NAME_FRAGMENT = "UNIVERSITY OF WASHINGTON"
EXPECTED_STATE = "WA"
EXPECTED_CITY = "SEATTLE"


class IdentityError(ValueError):
    """Raised when the target hospital cannot be found or does not match expectations."""


@dataclass
class Release:
    """One CMS data release, normalized and checked, restricted to the target hospital."""

    label: str
    provenance: dict
    hospital: dict
    uw_rows: pd.DataFrame          # all target-hospital HCAHPS rows, with excluded_reason
    national: pd.DataFrame         # all national rows, with excluded_reason
    columns: dict[str, list[str]]
    findings: list[Finding] = field(default_factory=list)


def identify_hospital(general: pd.DataFrame, facility_id: str = TARGET_FACILITY_ID,
                      name_fragment: str = EXPECTED_NAME_FRAGMENT,
                      state: str = EXPECTED_STATE, city: str = EXPECTED_CITY) -> dict:
    """Find the facility in Hospital General Information and verify its identity."""
    rows = general[general["facility_id"] == facility_id]
    if rows.empty:
        near = general[general["facility_name"].str.upper().str.contains(name_fragment, na=False)]
        hint = ""
        if not near.empty:
            hint = " Facilities with a similar name: " + "; ".join(
                f"{r.facility_id} {r.facility_name}" for r in near.head(5).itertuples())
        raise IdentityError(f"Facility ID {facility_id} not found in Hospital General Information.{hint}")
    if len(rows.drop_duplicates()) > 1:
        raise IdentityError(f"Facility ID {facility_id} appears {len(rows)} times with differing details.")
    rec = rows.iloc[0].to_dict()
    problems = []
    if name_fragment and name_fragment not in rec["facility_name"].upper():
        problems.append(f"name '{rec['facility_name']}' does not contain '{name_fragment}'")
    if state and rec.get("state", "").upper() != state:
        problems.append(f"state '{rec.get('state')}' is not '{state}'")
    if city and rec.get("city_town") and rec["city_town"].upper() != city:
        problems.append(f"city '{rec['city_town']}' is not '{city}'")
    if problems:
        raise IdentityError(
            f"Facility {facility_id} identity check failed: " + "; ".join(problems)
            + ". Confirm the facility on Medicare Care Compare; if CMS has renamed it, update "
              "EXPECTED_NAME_FRAGMENT / EXPECTED_CITY in analysis.py.")
    keep = ["facility_id", "facility_name", "address", "city_town", "state", "zip_code",
            "county_parish", "hospital_type", "hospital_ownership", "emergency_services",
            "hospital_overall_rating", "hospital_overall_rating_footnote"]
    return {k: rec[k] for k in keep if k in rec}


def load_release(release_dir: Path, facility_id: str = TARGET_FACILITY_ID) -> Release:
    """Load, normalize, check and identify one release directory."""
    files = sources.locate_files(release_dir)
    prov = sources.read_provenance(release_dir, files)
    raw = {key: sources.load_csv(path) for key, path in files.items()}

    general = validation.prepare_general(raw["hospital_general"])
    hospital_all = validation.prepare_hcahps(raw["hcahps_hospital"], "hcahps_hospital")
    national = validation.prepare_hcahps(raw["hcahps_national"], "hcahps_national")
    columns = {"hospital_general": list(general.columns),
               "hcahps_hospital": [c for c in hospital_all.columns if c not in
                                   ("answer_percent", "start", "end", "completed_surveys")],
               "hcahps_national": [c for c in national.columns if c not in
                                   ("answer_percent", "start", "end", "completed_surveys")]}

    findings: list[Finding] = []
    findings += validation.check_facility_ids(general, "hospital_general")
    findings += validation.check_facility_ids(hospital_all, "hcahps_hospital")

    hospital = identify_hospital(general, facility_id)
    uw = hospital_all[hospital_all["facility_id"] == facility_id]
    if uw.empty:
        raise IdentityError(
            f"Facility {facility_id} is in Hospital General Information but has no rows in the "
            "HCAHPS hospital file for this release.")
    names = set(uw["facility_name"]) - {""}
    if names and not any(_same_name(n, hospital["facility_name"]) for n in names):
        findings.append(Finding("anomaly", "hcahps_hospital", "facility_name_mismatch",
                                f"HCAHPS file names facility {facility_id} as {sorted(names)}, "
                                f"general information says '{hospital['facility_name']}'."))

    uw, f_uw = validation.check_hcahps(uw, "hcahps_hospital (target facility)")
    national, f_nat = validation.check_hcahps(national, "hcahps_national")
    findings += f_uw + f_nat
    label = str(prov.get("release") or Path(release_dir).name)
    return Release(label, prov, hospital, uw.reset_index(drop=True),
                   national.reset_index(drop=True), columns, findings)


def _same_name(a: str, b: str) -> bool:
    return a.strip().upper() == b.strip().upper()


def _norm_text(s: str) -> str:
    return " ".join((s or "").lower().split())


def compare_to_national(release: Release) -> pd.DataFrame:
    """One row per target-hospital measure, with comparability decision and gap.

    A measure is comparable only if: the hospital value is numeric and valid,
    a single valid national value exists for the same measure ID, both cover
    the identical reporting window, the response category text agrees, and the
    measure is a response percentage.
    """
    uw = release.uw_rows
    nat = release.national[release.national["excluded_reason"] == ""]
    nat_by_id = {mid: g for mid, g in nat.groupby("hcahps_measure_id")}

    rows = []
    for r in uw.itertuples(index=False):
        mid = r.hcahps_measure_id
        direction, meaning, confirmed = signals.classify_measure(mid, r.hcahps_answer_description)
        domain = domains.classify_domain(mid, r.hcahps_question, r.hcahps_answer_description)
        row = {
            "facility_id": r.facility_id,
            "hcahps_measure_id": mid,
            "domain": domain.label,
            "focus_domain": domain.focus,
            "retired_measure": domain.retired,
            "survey_version": domains.survey_version(r.start, r.end),
            "hcahps_question": r.hcahps_question,
            "hcahps_answer_description": r.hcahps_answer_description,
            "direction": direction,
            "direction_meaning": meaning,
            "uwmc_value_raw": r.hcahps_answer_percent,
            "uwmc_percent": r.answer_percent,
            "uwmc_footnote": r.hcahps_answer_percent_footnote,
            "completed_surveys": getattr(r, "completed_surveys", float("nan")),
            "start_date": r.start_date,
            "end_date": r.end_date,
            "national_percent": float("nan"),
            "national_start_date": "",
            "national_end_date": "",
            "gap_pp": float("nan"),
            "favorable_gap_pp": float("nan"),
            "gap_band": "",
            "within_rounding": "",
            "confidence": signals.confidence_label(getattr(r, "completed_surveys", None),
                                                   r.hcahps_answer_percent_footnote),
            "comparable": False,
            "not_comparable_reason": "",
            "notes": "" if confirmed else "Answer description does not confirm the "
                                          "directionality rule; review direction manually.",
        }
        reason = ""
        if r.excluded_reason:
            reason = f"Hospital row failed validation: {r.excluded_reason}"
        elif direction == signals.NOT_PERCENT:
            reason = "Not a response percentage (star rating or linear score)"
        elif pd.isna(r.answer_percent):
            note = f" (footnote {r.hcahps_answer_percent_footnote})" if r.hcahps_answer_percent_footnote else ""
            reason = f"Hospital value not reported: '{r.hcahps_answer_percent or 'blank'}'{note}"
        else:
            g = nat_by_id.get(mid)
            if g is None:
                reason = "No national benchmark row for this measure ID"
            elif len(g) > 1:
                reason = "Multiple national rows for this measure ID; ambiguous benchmark"
            else:
                n = g.iloc[0]
                row.update(national_percent=n["answer_percent"],
                           national_start_date=n["start_date"], national_end_date=n["end_date"])
                if pd.isna(n["answer_percent"]):
                    reason = f"National value not reported: '{n['hcahps_answer_percent'] or 'blank'}'"
                elif (n["start"], n["end"]) != (r.start, r.end):
                    reason = (f"Reporting period mismatch: hospital {r.start_date}-{r.end_date}, "
                              f"national {n['start_date']}-{n['end_date']}")
                elif (r.hcahps_answer_description and n["hcahps_answer_description"]
                      and _norm_text(r.hcahps_answer_description)
                      != _norm_text(n["hcahps_answer_description"])):
                    reason = "Response category differs between hospital and national rows"
        if reason:
            row["not_comparable_reason"] = reason
        else:
            gap = float(r.answer_percent) - float(row["national_percent"])
            fav = gap if direction == signals.HIGHER else -gap if direction == signals.LOWER else float("nan")
            row.update(comparable=True, gap_pp=gap, favorable_gap_pp=fav,
                       gap_band=signals.gap_band(gap),
                       within_rounding=abs(gap) <= signals.ROUNDING_TOLERANCE_PP)
        rows.append(row)

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(["comparable", "hcahps_measure_id"], ascending=[False, True]).reset_index(drop=True)


def comparison_findings(comparison: pd.DataFrame) -> list[Finding]:
    """Summarize comparability problems as data-quality findings."""
    findings = []
    if comparison.empty:
        return [Finding("failure", "comparison", "no_target_rows", "No target-hospital measures.")]
    nc = comparison[~comparison["comparable"]]
    for reason_prefix, sev, check in (
        ("Reporting period mismatch", "anomaly", "reporting_period_mismatch"),
        ("No national benchmark", "anomaly", "unmatched_national_benchmark"),
        ("Multiple national rows", "failure", "ambiguous_national_benchmark"),
        ("Response category differs", "anomaly", "response_category_mismatch"),
        ("Hospital value not reported", "info", "suppressed_or_not_reported"),
        ("National value not reported", "anomaly", "national_value_not_reported"),
    ):
        hit = nc[nc["not_comparable_reason"].str.startswith(reason_prefix)]
        if not hit.empty:
            findings.append(Finding(sev, "comparison", check,
                                    f"{reason_prefix}: measure(s) marked Not Comparable.",
                                    len(hit), sorted(hit["hcahps_measure_id"])))
    unknown = comparison[comparison["direction"] == signals.UNKNOWN]
    if not unknown.empty:
        findings.append(Finding("anomaly", "comparison", "unknown_directionality",
                                "Measure IDs not covered by directionality rules; gaps are shown "
                                "but not labelled favorable/unfavorable or ranked.",
                                len(unknown), sorted(unknown["hcahps_measure_id"])))
    unconfirmed = comparison[comparison["notes"] != ""]
    if not unconfirmed.empty:
        findings.append(Finding("anomaly", "comparison", "directionality_not_confirmed",
                                "Answer description did not contain the words expected by the "
                                "directionality rule.", len(unconfirmed),
                                sorted(unconfirmed["hcahps_measure_id"])))
    retired = comparison[comparison["retired_measure"]]
    if not retired.empty:
        findings.append(Finding("anomaly", "comparison", "retired_measure_present",
                                "Care Transition (H_CT_*) was dropped from the updated HCAHPS survey "
                                "(discharges from 1 Jan 2025). It is shown for reference only and should "
                                "not be treated as a current measure.",
                                len(retired), sorted(retired["hcahps_measure_id"])))
    spans = comparison[comparison["survey_version"] == domains.MIXED]
    if not spans.empty:
        findings.append(Finding("anomaly", "comparison", "window_spans_survey_update",
                                "Reporting window includes discharges before and after the 1 Jan 2025 "
                                "HCAHPS survey update. Check the CMS HCAHPS technical notes for how this "
                                "window was scored; it is not compared with other releases.",
                                len(spans), sorted(spans["hcahps_measure_id"])))
    if not comparison["focus_domain"].any():
        findings.append(Finding("anomaly", "comparison", "no_focus_measures",
                                "No discharge or care-transition measure found in this release."))
    if not comparison["comparable"].any():
        findings.append(Finding("failure", "comparison", "no_comparable_measures",
                                "No measure could be compared with a matched national benchmark. "
                                "Retrieve hospital and national files from the same CMS release."))
    return findings


def compare_releases(current: pd.DataFrame, previous: pd.DataFrame,
                     current_label: str, previous_label: str) -> pd.DataFrame:
    """Change between two releases' comparison tables for the same measure.

    HCAHPS windows are rolling four-quarter periods, so consecutive quarterly
    releases share three quarters of their patients. Overlap is flagged; only
    non-overlapping windows are described as independent periods.
    """
    prev = previous.set_index("hcahps_measure_id")
    rows = []
    for r in current.itertuples(index=False):
        mid = r.hcahps_measure_id
        row = {"hcahps_measure_id": mid, "direction": r.direction,
               "current_release": current_label, "previous_release": previous_label,
               "current_window": f"{r.start_date}-{r.end_date}", "previous_window": "",
               "current_percent": r.uwmc_percent, "previous_percent": float("nan"),
               "change_pp": float("nan"), "national_change_pp": float("nan"),
               "gap_change_pp": float("nan"), "window_relation": "",
               "comparable": False, "not_comparable_reason": ""}
        reason = ""
        if mid not in prev.index:
            reason = "Measure not present in previous release"
        else:
            p = prev.loc[mid]
            if isinstance(p, pd.DataFrame):
                reason = "Measure duplicated in previous release"
            else:
                row["previous_window"] = f"{p['start_date']}-{p['end_date']}"
                row["previous_percent"] = p["uwmc_percent"]
                if not r.comparable or not bool(p["comparable"]):
                    reason = "Not benchmark-comparable in one or both releases"
                elif _norm_text(r.hcahps_answer_description) != _norm_text(p["hcahps_answer_description"]):
                    reason = "Response category text changed between releases"
                else:
                    cs, ce, ps, pe = validation.to_date(pd.Series(
                        [r.start_date, r.end_date, p["start_date"], p["end_date"]]))
                    cv, pv = domains.survey_version(cs, ce), domains.survey_version(ps, pe)
                    if (cs, ce) == (ps, pe):
                        reason = "Same reporting window in both releases (no new data)"
                    elif cv != pv or domains.MIXED in (cv, pv):
                        reason = (f"HCAHPS survey version differs or window spans the 1 Jan 2025 "
                                  f"survey update (previous: {pv}, current: {cv})")
                    elif ce < pe:
                        reason = "'Current' release covers an earlier window than 'previous'"
                    else:
                        # Overlapping windows share patients; see report banner.
                        row["window_relation"] = "overlapping" if cs <= pe else "non-overlapping"
        if reason:
            row["not_comparable_reason"] = reason
        else:
            row.update(comparable=True,
                       change_pp=r.uwmc_percent - p["uwmc_percent"],
                       national_change_pp=r.national_percent - p["national_percent"],
                       gap_change_pp=r.gap_pp - p["gap_pp"])
        rows.append(row)
    for mid in sorted(set(prev.index) - set(current["hcahps_measure_id"])):
        rows.append({"hcahps_measure_id": mid, "previous_release": previous_label,
                     "current_release": current_label, "comparable": False,
                     "not_comparable_reason": "Measure dropped from current release"})
    return pd.DataFrame(rows)


@dataclass
class AnalysisResult:
    current: Release
    comparison: pd.DataFrame
    signals: pd.DataFrame
    findings: list[Finding]
    previous: Release | None = None
    trends: pd.DataFrame | None = None


def analyze(data_dir: Path, previous_dir: Path | None = None,
            facility_id: str = TARGET_FACILITY_ID) -> AnalysisResult:
    current = load_release(data_dir, facility_id)
    comparison = compare_to_national(current)
    findings = list(current.findings) + comparison_findings(comparison)

    previous = trends = None
    if previous_dir is not None:
        previous = load_release(previous_dir, facility_id)
        if previous.provenance.get("synthetic") != current.provenance.get("synthetic"):
            raise ValueError("Refusing to compare a synthetic fixture release with real CMS data.")
        prev_comparison = compare_to_national(previous)
        trends = compare_releases(comparison, prev_comparison, current.label, previous.label)
        findings += validation.check_schema_drift(current.columns, previous.columns)
        findings += [Finding(f.severity, f"{f.dataset} [previous release]", f.check, f.detail,
                             f.count, f.measure_ids) for f in previous.findings if f.severity != "info"]
        same = trends[trends["not_comparable_reason"].fillna("").str.startswith("Same reporting window")]
        if not same.empty:
            findings.append(Finding("anomaly", "trend", "identical_windows",
                                    "Previous release has the same reporting window as the current "
                                    "one; no change can be measured.", len(same)))

    ranked = signals.rank_signals(comparison, trends)
    return AnalysisResult(current, comparison, ranked, findings, previous, trends)
