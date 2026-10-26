import pandas as pd
import pytest

from uwmc_monitor import sources, validation
from uwmc_monitor.analysis import IdentityError, identify_hospital, load_release

from conftest import CURRENT, edit_csv


def test_normalize_columns_snake_case_and_aliases():
    df = pd.DataFrame({" Facility ID ": ["500008"], "City/Town": ["SEATTLE"],
                       "Measure Start Date": ["01/01/2025"], "HCAHPS Answer Percent": [" 77 "]})
    out = validation.normalize_columns(df)
    assert list(out.columns) == ["facility_id", "city_town", "start_date", "hcahps_answer_percent"]
    assert out.loc[0, "hcahps_answer_percent"] == "77"


def test_provider_id_alias_maps_to_facility_id():
    out = validation.normalize_columns(pd.DataFrame({"Provider ID": ["500008"]}))
    assert "facility_id" in out.columns


def test_missing_required_columns_raises():
    df = pd.DataFrame({"HCAHPS Measure ID": ["H_COMP_1_A_P"], "Start Date": ["01/01/2025"]})
    with pytest.raises(validation.SchemaError, match="hcahps_answer_percent"):
        validation.prepare_hcahps(df, "hcahps_national")


def test_numeric_conversion_handles_text_and_symbols():
    s = pd.Series(["77", "Not Available", "", "1,250", "12%", "Not Applicable"])
    out = validation.to_number(s)
    assert out.tolist()[0] == 77 and out.tolist()[3] == 1250 and out.tolist()[4] == 12
    assert out.isna().tolist() == [False, True, True, False, False, True]


def test_facility_id_leading_zeros_preserved(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("Facility ID,Facility Name,State\n050008,A,CA\n")
    assert sources.load_csv(p).iloc[0, 0] == "050008"


def _hcahps(rows):
    df = pd.DataFrame(rows, columns=["facility_id", "hcahps_measure_id", "hcahps_answer_percent",
                                     "start_date", "end_date"])
    return validation.prepare_hcahps(df, "hcahps_hospital")


def test_percentage_out_of_range_is_failure_and_excluded():
    df, findings = validation.check_hcahps(_hcahps([
        ["500008", "H_COMP_1_A_P", "130", "01/01/2025", "12/31/2025"],
        ["500008", "H_COMP_2_A_P", "80", "01/01/2025", "12/31/2025"]]), "t")
    assert df.loc[0, "excluded_reason"] == "percentage outside 0-100"
    assert df.loc[1, "excluded_reason"] == ""
    assert any(f.check == "percent_out_of_range" and f.severity == "failure" for f in findings)


def test_exact_duplicates_dropped_but_first_kept():
    row = ["500008", "H_COMP_1_A_P", "80", "01/01/2025", "12/31/2025"]
    df, findings = validation.check_hcahps(_hcahps([row, row]), "t")
    assert df["excluded_reason"].tolist() == ["", "exact duplicate row"]
    assert [f.check for f in findings if f.severity != "info"] == ["exact_duplicate_rows"]


def test_conflicting_duplicates_all_excluded():
    df, findings = validation.check_hcahps(_hcahps([
        ["500008", "H_COMP_1_A_P", "80", "01/01/2025", "12/31/2025"],
        ["500008", "H_COMP_1_A_P", "70", "01/01/2025", "12/31/2025"]]), "t")
    assert (df["excluded_reason"] == "conflicting duplicate measure rows").all()
    assert any(f.check == "conflicting_duplicates" for f in findings)


def test_start_after_end_and_bad_dates():
    df, findings = validation.check_hcahps(_hcahps([
        ["500008", "H_COMP_1_A_P", "80", "12/31/2025", "01/01/2025"],
        ["500008", "H_COMP_2_A_P", "80", "not a date", "01/01/2025"]]), "t")
    assert df["excluded_reason"].tolist() == ["start date after end date", "unparseable reporting dates"]
    checks = {f.check for f in findings}
    assert {"start_after_end", "unparseable_dates"} <= checks


def test_suppressed_values_reported_as_info_not_failure():
    df, findings = validation.check_hcahps(_hcahps([
        ["500008", "H_COMP_1_A_P", "Not Available", "01/01/2025", "12/31/2025"]]), "t")
    assert df.loc[0, "excluded_reason"] == ""
    assert [(f.severity, f.check) for f in findings] == [("info", "non_numeric_answer_percent")]


def test_unexpected_facility_ids_flagged():
    df = pd.DataFrame({"facility_id": ["500008", "5008", "50000A"]})
    (finding,) = validation.check_facility_ids(df, "g")
    assert finding.count == 1 and "5008" in finding.detail


def test_schema_drift_detected():
    (f,) = validation.check_schema_drift({"h": ["a", "b"]}, {"h": ["a", "c"]})
    assert "Added columns: b" in f.detail and "removed columns: c" in f.detail


def test_identify_hospital_filters_by_facility_id():
    general = validation.prepare_general(sources.load_csv(CURRENT / "hospital_general.csv"))
    h = identify_hospital(general, "500008")
    assert h["facility_name"] == "UNIVERSITY OF WASHINGTON MEDICAL CTR"


def test_identify_hospital_missing_id_raises_with_hint():
    general = validation.prepare_general(sources.load_csv(CURRENT / "hospital_general.csv"))
    with pytest.raises(IdentityError, match="not found.*500008"):
        identify_hospital(general, "123456")


def test_identity_mismatch_raises(release_copy):
    d = release_copy()
    edit_csv(d / "hospital_general.csv",
             lambda h, rows: (h, [[c.replace("SEATTLE", "PORTLAND") for c in r] for r in rows]))
    with pytest.raises(IdentityError, match="city"):
        load_release(d)


def test_target_rows_only(release_copy):
    rel = load_release(release_copy())
    assert set(rel.uw_rows["facility_id"]) == {"500008"}


def test_cms_archive_file_names_are_accepted(release_copy):
    d = release_copy()
    (d / "hcahps_hospital.csv").rename(d / "HCAHPS-Hospital.csv")
    assert sources.locate_files(d)["hcahps_hospital"].name == "HCAHPS-Hospital.csv"


def test_missing_file_error_names_source(tmp_path):
    with pytest.raises(sources.SourceError, match="dgck-syfz"):
        sources.locate_files(tmp_path)
