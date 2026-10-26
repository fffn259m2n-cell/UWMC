"""Generate SYNTHETIC CMS-shaped fixture files for tests and offline demos.

Every value written here is invented. The files mimic the column layout of the
CMS Provider Data Catalog CSVs so that the pipeline can be exercised offline.
Run:  python tests/fixtures/make_fixtures.py
"""

import csv
from pathlib import Path

HERE = Path(__file__).parent

HOSP_COLS = ["Facility ID", "Facility Name", "Address", "City/Town", "State", "ZIP Code",
             "County/Parish", "Telephone Number", "HCAHPS Measure ID", "HCAHPS Question",
             "HCAHPS Answer Description", "Patient Survey Star Rating",
             "Patient Survey Star Rating Footnote", "HCAHPS Answer Percent",
             "HCAHPS Answer Percent Footnote", "HCAHPS Linear Mean Value",
             "Number of Completed Surveys", "Number of Completed Surveys Footnote",
             "Survey Response Rate Percent", "Survey Response Rate Percent Footnote",
             "Start Date", "End Date"]
NAT_COLS = ["HCAHPS Measure ID", "HCAHPS Question", "HCAHPS Answer Description",
            "HCAHPS Answer Percent", "Footnote", "Start Date", "End Date"]
GEN_COLS = ["Facility ID", "Facility Name", "Address", "City/Town", "State", "ZIP Code",
            "County/Parish", "Telephone Number", "Hospital Type", "Hospital Ownership",
            "Emergency Services", "Hospital overall rating", "Hospital overall rating footnote"]

# (measure id, question, answer description)
MEASURES = [
    ("H_COMP_1_A_P", "Patients who reported that their nurses \"Always\" communicated well", "Nurses \"always\" communicated well"),
    ("H_COMP_1_U_P", "Patients who reported that their nurses \"Usually\" communicated well", "Nurses \"usually\" communicated well"),
    ("H_COMP_1_SN_P", "Patients who reported that their nurses \"Sometimes\" or \"Never\" communicated well", "Nurses \"sometimes\" or \"never\" communicated well"),
    ("H_COMP_2_A_P", "Patients who reported that their doctors \"Always\" communicated well", "Doctors \"always\" communicated well"),
    ("H_COMP_3_A_P", "Patients who reported that they \"Always\" received help as soon as they wanted", "Patients \"always\" received help as soon as they wanted"),
    ("H_COMP_5_A_P", "Patients who reported that staff \"Always\" explained about medicines before giving it to them", "Staff \"always\" explained"),
    ("H_COMP_6_Y_P", "Patients who reported that YES, they were given information about what to do during their recovery at home", "Yes, staff \"did\" give patients this information"),
    ("H_COMP_6_N_P", "Patients who reported that NO, they were not given information about what to do during their recovery at home", "No, staff \"did not\" give patients this information"),
    ("H_CLEAN_HSP_A_P", "Patients who reported that their room and bathroom were \"Always\" clean", "Room was \"always\" clean"),
    ("H_QUIET_HSP_A_P", "Patients who reported that the area around their room was \"Always\" quiet at night", "\"Always\" quiet at night"),
    ("H_HSP_RATING_9_10", "Patients who gave their hospital a rating of 9 or 10 on a scale from 0 (lowest) to 10 (highest)", "Patients who gave a rating of \"9\" or \"10\" (high)"),
    ("H_HSP_RATING_7_8", "Patients who gave their hospital a rating of 7 or 8 on a scale from 0 (lowest) to 10 (highest)", "Patients who gave a rating of \"7\" or \"8\" (medium)"),
    ("H_HSP_RATING_0_6", "Patients who gave their hospital a rating of 6 or lower on a scale from 0 (lowest) to 10 (highest)", "Patients who gave a rating of \"6\" or lower (low)"),
    ("H_RECMND_DY", "Patients who reported YES, they would definitely recommend the hospital", "\"YES\", patients would definitely recommend the hospital"),
    ("H_RECMND_PY", "Patients who reported YES, they would probably recommend the hospital", "\"YES\", patients would probably recommend the hospital"),
    ("H_RECMND_DN", "Patients who reported NO, they would probably not or definitely not recommend the hospital", "\"NO\", patients would not recommend the hospital (they probably would not or definitely would not recommend it)"),
    # Invented IDs and wording standing in for updated-survey items (not real CMS IDs).
    ("H_SYNTH_COORD_A_P", "Patients who reported that staff \"Always\" worked together to coordinate their care (SYNTHETIC ITEM)", "Staff \"always\" coordinated care"),
    ("H_SYNTH_SYMPTOMS_Y_P", "Patients who reported YES, they were told which symptoms to watch for after leaving (SYNTHETIC ITEM)", "Yes, given information about symptoms"),
    ("H_CT_SA", "Patients who \"Strongly Agree\" they understood their care when they left the hospital", "Patients who \"Strongly Agree\" they understood their care when they left the hospital"),
    ("H_COMP_1_LINEAR_SCORE", "Nurse communication - linear mean score", "Nurse communication - linear mean score"),
    ("H_STAR_RATING", "Summary star rating", "Summary star rating"),
    ("H_COMP_7_A_P", "Synthetic suppressed measure", "\"Always\" synthetic"),
    ("H_EXTRA_A_P", "Synthetic measure with no national row", "\"Always\" synthetic"),
    ("H_NEWSURVEY_X", "Synthetic measure outside directionality rules", "Synthetic"),
]

# Synthetic percentages: (UWMC current, national current, UWMC previous, national previous)
VALUES = {
    "H_COMP_1_A_P": (77, 79, 79, 79), "H_COMP_1_U_P": (17, 16, 16, 16), "H_COMP_1_SN_P": (6, 5, 5, 5),
    "H_COMP_2_A_P": (82, 79, 81, 79), "H_COMP_3_A_P": (60, 65, 63, 64), "H_COMP_5_A_P": (62, 62, 61, 62),
    "H_COMP_6_Y_P": (88, 86, 87, 86), "H_COMP_6_N_P": (12, 14, 13, 14),
    "H_CLEAN_HSP_A_P": (70, 72, 71, 72), "H_QUIET_HSP_A_P": (55, 62, 56, 62),
    "H_HSP_RATING_9_10": (78, 71, 77, 71), "H_HSP_RATING_7_8": (16, 20, 17, 20), "H_HSP_RATING_0_6": (6, 9, 6, 9),
    "H_RECMND_DY": (80, 69, 79, 69), "H_RECMND_PY": (16, 25, 17, 25), "H_RECMND_DN": (4, 6, 4, 6),
    "H_NEWSURVEY_X": (40, 38, 40, 38),
    "H_SYNTH_COORD_A_P": (68, 72, 70, 71), "H_SYNTH_SYMPTOMS_Y_P": (84, 83, 84, 83),
    "H_CT_SA": (55, 51, 54, 51),
}

UW = ["500008", "UNIVERSITY OF WASHINGTON MEDICAL CTR", "1959 NE PACIFIC ST", "SEATTLE", "WA",
      "98195", "KING", "(000) 000-0000"]
OTHER = ["990001", "SYNTHETIC COMPARISON HOSPITAL", "1 TEST WAY", "TESTVILLE", "WA",
         "99999", "TEST", "(000) 000-0000"]


def write(path, cols, rows):
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        w.writerows(rows)


def release(folder, start, end, which, drop_col=None):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SYNTHETIC_DATA").write_text(
        "All files in this folder are SYNTHETIC test fixtures. They are not CMS data.\n", encoding="utf-8")
    hosp, nat = [], []
    for mid, q, a in MEASURES:
        v = VALUES.get(mid)
        pct, foot, star = (str(v[which]) if v else "Not Applicable"), "", "Not Applicable"
        if mid == "H_STAR_RATING":
            star = "4"
        if mid == "H_COMP_1_LINEAR_SCORE":
            pct = "Not Applicable"
        if mid in ("H_COMP_7_A_P", "H_EXTRA_A_P"):
            pct, foot = ("Not Available", "5") if mid == "H_COMP_7_A_P" else ("74", "")
        hosp.append(UW + [mid, q, a, star, "", pct, foot, "", "1250", "", "21", "", start, end])
        hosp.append(OTHER + [mid, q, a, star, "", pct, foot, "", "80", "10", "15", "", start, end])
        if v:
            n_start = "01/01/2025" if (mid == "H_QUIET_HSP_A_P" and which == 0) else start
            nat.append([mid, q, a, str(v[which + 1]), "", n_start, end])
    if drop_col:
        i = HOSP_COLS.index(drop_col)
        cols = HOSP_COLS[:i] + HOSP_COLS[i + 1:]
        hosp = [r[:i] + r[i + 1:] for r in hosp]
    else:
        cols = HOSP_COLS
    write(folder / "hcahps_hospital.csv", cols, hosp)
    write(folder / "hcahps_national.csv", NAT_COLS, nat)
    write(folder / "hospital_general.csv", GEN_COLS, [
        UW + ["Acute Care Hospitals", "Government - State", "Yes", "4", ""],
        OTHER + ["Acute Care Hospitals", "Voluntary non-profit - Private", "Yes", "3", ""],
        ["5008", "SYNTHETIC ID WITH LOST LEADING ZERO", "", "", "WA", "", "", "",
         "Acute Care Hospitals", "", "", "", ""],
    ])


if __name__ == "__main__":
    # index 0 = current, index 2 = previous (VALUES tuple positions)
    release(HERE / "synthetic_current", "04/01/2025", "03/31/2026", 0)
    release(HERE / "synthetic_previous", "01/01/2025", "12/31/2025", 2,
            drop_col="Survey Response Rate Percent Footnote")
    print("Synthetic fixtures written.")
