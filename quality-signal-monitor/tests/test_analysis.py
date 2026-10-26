import pandas as pd
import pytest
from conftest import CURRENT, PREVIOUS, edit_csv

from uwmc_monitor import analysis, signals
from uwmc_monitor.analysis import analyze, compare_to_national, load_release


def comp_row(comp, mid):
    return comp[comp["hcahps_measure_id"] == mid].iloc[0]


@pytest.fixture(scope="module")
def result():
    return analyze(CURRENT, PREVIOUS)


def test_benchmark_gap_is_hospital_minus_national(result):
    r = comp_row(result.comparison, "H_RECMND_DY")
    assert r["comparable"] and r["uwmc_percent"] == 80 and r["national_percent"] == 69
    assert r["gap_pp"] == 11 and r["favorable_gap_pp"] == 11 and r["gap_band"] == "large"


def test_bottom_box_direction_flips_favorable_gap(result):
    r = comp_row(result.comparison, "H_HSP_RATING_0_6")
    assert r["direction"] == signals.LOWER
    assert r["gap_pp"] == -3 and r["favorable_gap_pp"] == 3


def test_middle_box_has_no_favorable_direction(result):
    r = comp_row(result.comparison, "H_RECMND_PY")
    assert r["direction"] == signals.MIDDLE and pd.isna(r["favorable_gap_pp"])


def test_reporting_period_mismatch_not_comparable(result):
    r = comp_row(result.comparison, "H_QUIET_HSP_A_P")
    assert not r["comparable"] and r["not_comparable_reason"].startswith("Reporting period mismatch")
    assert pd.isna(r["gap_pp"])


def test_missing_national_benchmark(result):
    r = comp_row(result.comparison, "H_EXTRA_A_P")
    assert not r["comparable"] and "No national benchmark" in r["not_comparable_reason"]


def test_suppressed_hospital_value(result):
    r = comp_row(result.comparison, "H_COMP_7_A_P")
    assert not r["comparable"] and "Not Available" in r["not_comparable_reason"]
    assert "footnote 5" in r["not_comparable_reason"]


def test_star_and_linear_rows_excluded(result):
    for mid in ("H_STAR_RATING", "H_COMP_1_LINEAR_SCORE"):
        r = comp_row(result.comparison, mid)
        assert not r["comparable"] and r["direction"] == signals.NOT_PERCENT


def test_unknown_direction_compared_but_not_ranked(result):
    r = comp_row(result.comparison, "H_NEWSURVEY_X")
    assert r["comparable"] and r["direction"] == signals.UNKNOWN
    assert "H_NEWSURVEY_X" not in set(result.signals["hcahps_measure_id"])
    assert any(f.check == "unknown_directionality" for f in result.findings)


def test_response_category_mismatch(release_copy):
    d = release_copy()

    def change(h, rows):
        i, j = h.index("HCAHPS Measure ID"), h.index("HCAHPS Answer Description")
        for r in rows:
            if r[i] == "H_COMP_2_A_P":
                r[j] = "Doctors \"usually\" communicated well"
        return h, rows
    edit_csv(d / "hcahps_national.csv", change)
    r = comp_row(compare_to_national(load_release(d)), "H_COMP_2_A_P")
    assert not r["comparable"] and "Response category" in r["not_comparable_reason"]


def test_duplicate_national_rows_are_not_used(release_copy):
    d = release_copy()

    def dup(h, rows):
        i = h.index("HCAHPS Measure ID")
        extra = [list(r) for r in rows if r[i] == "H_COMP_2_A_P"]
        extra[0][h.index("HCAHPS Answer Percent")] = "50"
        return h, rows + extra
    edit_csv(d / "hcahps_national.csv", dup)
    res = analyze(d)
    r = comp_row(res.comparison, "H_COMP_2_A_P")
    assert not r["comparable"]
    assert any(f.check == "conflicting_duplicates" and f.dataset == "hcahps_national" for f in res.findings)


def test_no_matched_dates_gives_insufficient_data(release_copy):
    d = release_copy()

    def shift(h, rows):
        i = h.index("Start Date")
        for r in rows:
            r[i] = "01/01/2020"
        return h, rows
    edit_csv(d / "hcahps_national.csv", shift)
    res = analyze(d)
    assert not res.comparison["comparable"].any()
    assert res.signals.empty
    assert any(f.check == "no_comparable_measures" and f.severity == "failure" for f in res.findings)


def test_ranking_only_top_box_and_ordered(result):
    s = result.signals
    assert set(s["direction"]) == {signals.HIGHER}
    assert s["score"].is_monotonic_decreasing
    assert s.iloc[0]["hcahps_measure_id"] == "H_RECMND_DY"


def test_persistence_bonus_requires_change_beyond_rounding(result):
    s = result.signals.set_index("hcahps_measure_id")
    # COMP_3: gap -1 -> -5 (gap change -4): widened, bonus applied
    assert s.at["H_COMP_3_A_P", "persistence"] == "gap to national widened"
    assert s.at["H_COMP_3_A_P", "score"] == 6.0
    # RECMND_DY: gap +10 -> +11, within rounding: no bonus
    assert s.at["H_RECMND_DY", "persistence"] == "gap change within rounding"
    assert s.at["H_RECMND_DY", "score"] == 11.0


def test_trend_overlapping_windows_flagged(result):
    t = result.trends.set_index("hcahps_measure_id")
    assert t.at["H_COMP_3_A_P", "change_pp"] == -3
    assert t.at["H_COMP_3_A_P", "gap_change_pp"] == -4
    assert t.at["H_COMP_3_A_P", "window_relation"].startswith("overlapping")
    assert any(f.check == "schema_changed_between_releases" for f in result.findings)


def test_same_window_releases_report_no_change():
    res = analyze(CURRENT, CURRENT)
    assert not res.trends["comparable"].any()
    assert any(f.check == "identical_windows" for f in res.findings)


def test_synthetic_and_real_not_mixed(release_copy):
    d = release_copy()
    (d / "SYNTHETIC_DATA").unlink()
    with pytest.raises(ValueError, match="synthetic"):
        analyze(d, PREVIOUS)


def test_confidence_labels():
    assert signals.confidence_label(1250, "") == "standard"
    assert signals.confidence_label(250, "") == "caution"
    assert signals.confidence_label(1250, "5") == "caution"
    assert signals.confidence_label(80, "") == "low"
    assert signals.confidence_label(1250, "6") == "low"


@pytest.mark.parametrize("mid,desc,direction", [
    ("H_COMP_1_A_P", "Nurses \"always\" communicated well", signals.HIGHER),
    ("H_COMP_1_SN_P", "Nurses \"sometimes\" or \"never\"", signals.LOWER),
    ("H_COMP_1_U_P", "", signals.MIDDLE),
    ("H_COMP_6_Y_P", "Yes", signals.HIGHER),
    ("H_COMP_6_N_P", "No", signals.LOWER),
    ("H_HSP_RATING_9_10", "", signals.HIGHER),
    ("H_HSP_RATING_0_6", "", signals.LOWER),
    ("H_RECMND_DN", "", signals.LOWER),
    ("H_CT_SA", "Strongly agree", signals.HIGHER),
    ("H_CT_D_SD", "Disagree or strongly disagree", signals.LOWER),
    ("H_COMP_1_STAR_RATING", "", signals.NOT_PERCENT),
    ("H_SOMETHING_NEW", "", signals.UNKNOWN),
])
def test_directionality_rules(mid, desc, direction):
    assert signals.classify_measure(mid, desc)[0] == direction


def test_directionality_cross_check_flags_contradiction():
    _, _, confirmed = signals.classify_measure("H_COMP_1_A_P", "Nurses sometimes communicated well")
    assert confirmed is False


def test_missing_uw_hcahps_rows_raises(release_copy):
    d = release_copy()
    edit_csv(d / "hcahps_hospital.csv",
             lambda h, rows: (h, [r for r in rows if r[0] != "500008"]))
    with pytest.raises(analysis.IdentityError, match="no rows"):
        load_release(d)


# ---------------------------------------------------------------- focus domains & survey versions

from uwmc_monitor import domains  # noqa: E402


@pytest.mark.parametrize("mid,question,key", [
    ("H_COMP_6_Y_P", "given information about what to do during their recovery at home", "discharge_information"),
    ("H_COMP_5_A_P", "staff \"Always\" explained about medicines", "medicines"),
    ("H_NEW_ITEM_A_P", "staff worked together to coordinate their care", "care_coordination"),
    ("H_NEW_ITEM_Y_P", "told which symptoms to watch for", "symptoms"),
    ("H_CT_SA", "understood their care when they left", "care_transition"),
    ("H_COMP_1_A_P", "nurses \"Always\" communicated well", "communication"),
    ("H_RECMND_DY", "would definitely recommend", "global"),
])
def test_domain_classification(mid, question, key):
    assert domains.classify_domain(mid, question).key == key


def test_focus_columns_and_retired_measure(result):
    c = result.comparison.set_index("hcahps_measure_id")
    assert c.at["H_COMP_6_Y_P", "focus_domain"] and not c.at["H_RECMND_DY", "focus_domain"]
    assert c.at["H_CT_SA", "retired_measure"]
    assert "H_CT_SA" not in set(result.signals["hcahps_measure_id"])
    assert any(f.check == "retired_measure_present" for f in result.findings)


@pytest.mark.parametrize("start,end,version", [
    ("2024-01-01", "2024-12-31", domains.ORIGINAL),
    ("2025-01-01", "2025-12-31", domains.UPDATED),
    ("2024-07-01", "2025-06-30", domains.MIXED),
])
def test_survey_version(start, end, version):
    assert domains.survey_version(pd.Timestamp(start), pd.Timestamp(end)) == version


def test_release_comparison_blocked_across_survey_versions(release_copy):
    prev = release_copy(PREVIOUS, "prev")
    for name in ("hcahps_hospital.csv", "hcahps_national.csv"):
        def to_2024(h, rows):
            i, j = h.index("Start Date"), h.index("End Date")
            for r in rows:
                r[i], r[j] = "01/01/2024", "12/31/2024"
            return h, rows
        edit_csv(prev / name, to_2024)
    res = analyze(CURRENT, prev)
    assert not res.trends["comparable"].fillna(False).any()
    t = res.trends.set_index("hcahps_measure_id")
    assert "survey version" in t.at["H_COMP_2_A_P", "not_comparable_reason"]


def test_window_spanning_update_flagged(release_copy):
    d = release_copy()
    for name in ("hcahps_hospital.csv", "hcahps_national.csv"):
        def span(h, rows):
            i, j = h.index("Start Date"), h.index("End Date")
            for r in rows:
                r[i], r[j] = "07/01/2024", "06/30/2025"
            return h, rows
        edit_csv(d / name, span)
    res = analyze(d)
    assert res.comparison["comparable"].any()   # same-window benchmark still valid
    assert any(f.check == "window_spans_survey_update" for f in res.findings)
