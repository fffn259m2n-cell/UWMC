"""Measure directionality and deterministic, transparent signal ranking.

Nothing here estimates statistical significance. CMS publishes HCAHPS
percentages already patient-mix and mode adjusted, rounded to whole numbers,
without standard errors, so a descriptive gap is all that can be computed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

HIGHER = "higher_is_better"
LOWER = "lower_is_better"
MIDDLE = "middle_category"
NOT_PERCENT = "not_a_percentage"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class DirectionRule:
    pattern: str            # regex matched against the full measure ID
    direction: str
    meaning: str
    keywords: tuple[str, ...] = ()  # expected in the answer description, used as a cross-check


# Order matters: first match wins. Derived from the CMS HCAHPS measure-ID
# conventions (A_P = "always", SN_P = "sometimes or never", etc.). Any ID not
# matched is labelled UNKNOWN and never ranked as favorable or unfavorable.
DIRECTION_RULES: tuple[DirectionRule, ...] = (
    DirectionRule(r".*(STAR_RATING|LINEAR_SCORE|LINEAR_MEAN).*", NOT_PERCENT,
                  "Star rating or linear mean score; not a response percentage"),
    DirectionRule(r"H_HSP_RATING_9_10", HIGHER, "Rated hospital 9-10 (top box)", ("9", "10")),
    DirectionRule(r"H_HSP_RATING_7_8", MIDDLE, "Rated hospital 7-8 (middle box)", ("7", "8")),
    DirectionRule(r"H_HSP_RATING_0_6", LOWER, "Rated hospital 0-6 (bottom box)", ("0", "6")),
    DirectionRule(r"H_RECMND_DY", HIGHER, "Would definitely recommend (top box)", ("definitely",)),
    DirectionRule(r"H_RECMND_PY", MIDDLE, "Would probably recommend (middle box)", ("probably",)),
    DirectionRule(r"H_RECMND_DN", LOWER, "Would not recommend (bottom box)", ("not",)),
    DirectionRule(r".*_SA$|.*_SA_P$", HIGHER, "Strongly agree (top box)", ("strongly agree",)),
    DirectionRule(r".*_D_SD$|.*_D_SD_P$", LOWER, "Disagree or strongly disagree (bottom box)",
                  ("disagree",)),
    DirectionRule(r"H_CT_A$|.*_AGREE_P$", MIDDLE, "Agree (middle box)", ("agree",)),
    DirectionRule(r".*_A_P$", HIGHER, "\"Always\" response (top box)", ("always",)),
    DirectionRule(r".*_U_P$", MIDDLE, "\"Usually\" response (middle box)", ("usually",)),
    DirectionRule(r".*_SN_P$", LOWER, "\"Sometimes\" or \"never\" response (bottom box)",
                  ("sometimes", "never")),
    DirectionRule(r".*_Y_P$", HIGHER, "\"Yes\" response (top box)", ("yes",)),
    DirectionRule(r".*_N_P$", LOWER, "\"No\" response (bottom box)", ("no",)),
)

# Descriptive bands for |gap| in percentage points. Heuristic, documented, not
# significance thresholds. Values are reported as whole numbers, so a 1 pp gap
# can be pure rounding.
GAP_BANDS = ((5.0, "large"), (3.0, "moderate"), (0.0, "small"))
ROUNDING_TOLERANCE_PP = 1.0

# Completed-survey thresholds for confidence labels. CMS footnotes 6 and 10
# flag fewer than 100 and fewer than 50 completed surveys respectively.
CONFIDENCE_WEIGHTS = {"standard": 1.0, "caution": 0.75, "low": 0.5}
CAUTION_FOOTNOTES = {"6", "10"}


def classify_measure(measure_id: str, answer_description: str = "") -> tuple[str, str, bool]:
    """Return (direction, meaning, description_confirms_rule)."""
    mid = (measure_id or "").upper()
    desc = (answer_description or "").lower()
    for rule in DIRECTION_RULES:
        if re.fullmatch(rule.pattern, mid):
            confirmed = not rule.keywords or not desc or any(k in desc for k in rule.keywords)
            return rule.direction, rule.meaning, confirmed
    return UNKNOWN, "Measure ID not covered by directionality rules", True


def gap_band(gap_pp: float) -> str:
    mag = abs(gap_pp)
    for floor, label in GAP_BANDS:
        if mag >= floor:
            return label
    return "small"


def confidence_label(completed_surveys: float | None, footnote: str) -> str:
    notes = {n.strip() for n in re.split(r"[,;\s]+", footnote or "") if n.strip()}
    if notes & CAUTION_FOOTNOTES or (completed_surveys is not None
                                     and not pd.isna(completed_surveys)
                                     and completed_surveys < 100):
        return "low"
    if notes or completed_surveys is None or pd.isna(completed_surveys) or completed_surveys < 300:
        return "caution"
    return "standard"


def rank_signals(comparison: pd.DataFrame, trends: pd.DataFrame | None = None) -> pd.DataFrame:
    """Rank comparable top-box measures by a transparent score.

    score = |favorable gap| x confidence weight
            + 1.0 if, since a comparable prior release, the gap to national grew by
              more than the rounding tolerance in the direction of the current gap

    Only top-box ("higher is better") measures are ranked: middle and bottom
    boxes of the same question are largely the complement of the top box, so
    ranking them too would count one finding two or three times. Retired
    measures (Care Transition) are never ranked.
    """
    retired = comparison.get("retired_measure", pd.Series(False, index=comparison.index))
    eligible = comparison[comparison["comparable"] & (comparison["direction"] == HIGHER)
                          & ~retired.astype(bool)].copy()
    if eligible.empty:
        return eligible.assign(score=[], rank=[], persistence="")
    eligible["persistence"] = "no comparable prior release"
    eligible["persistence_bonus"] = 0.0
    if trends is not None and not trends.empty:
        t = trends.set_index("hcahps_measure_id")
        for idx, row in eligible.iterrows():
            mid = row["hcahps_measure_id"]
            if mid not in t.index or not bool(t.at[mid, "comparable"]):
                continue
            gap_change = t.at[mid, "gap_change_pp"]
            if pd.isna(gap_change) or row["gap_pp"] == 0:
                eligible.at[idx, "persistence"] = "no current gap"
            elif abs(gap_change) <= ROUNDING_TOLERANCE_PP:
                eligible.at[idx, "persistence"] = "gap change within rounding"
            elif (gap_change > 0) == (row["gap_pp"] > 0):
                eligible.at[idx, "persistence"] = "gap to national widened"
                eligible.at[idx, "persistence_bonus"] = 1.0
            else:
                eligible.at[idx, "persistence"] = "gap to national narrowed"
    weights = eligible["confidence"].map(CONFIDENCE_WEIGHTS).fillna(0.5)
    eligible["score"] = (eligible["favorable_gap_pp"].abs() * weights
                         + eligible["persistence_bonus"]).round(2)
    eligible = eligible.sort_values(["score", "hcahps_measure_id"], ascending=[False, True])
    eligible["rank"] = range(1, len(eligible) + 1)
    return eligible.reset_index(drop=True)
