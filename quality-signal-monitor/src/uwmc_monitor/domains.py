"""Clinical focus domains and HCAHPS survey-version handling.

Focus: discharge and care transitions, the part of HCAHPS closest to everyday
Internal Medicine work (discharge information, medicines, care coordination,
information about symptoms).

Domains are assigned from the CMS question text as well as the measure ID, so
measures added by the updated survey are picked up even if their IDs are new.

Survey versions. CMS introduced an updated HCAHPS survey for patients discharged
on or after 1 January 2025. Care Transition (H_CT_*) was dropped, and Care
Coordination, Restfulness of the Hospital Environment and Information About
Symptoms were added. CMS training materials state Care Transition left public
reporting in the January 2026 refresh and updated-survey measures were expected
from the October 2026 refresh (dates CMS describes as estimates). Results from
different survey versions are not compared over time here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

SURVEY_UPDATE_DATE = pd.Timestamp("2025-01-01")
ORIGINAL, UPDATED, MIXED, UNKNOWN_VERSION = "original", "updated", "spans update", "unknown"


@dataclass(frozen=True)
class Domain:
    key: str
    label: str
    focus: bool
    id_pattern: str = r"(?!)"          # regex on measure ID; default never matches
    text_pattern: str = r"(?!)"        # regex on question/answer text, case-insensitive
    retired: bool = False


# First match wins. Text patterns are deliberately specific to avoid catching
# unrelated questions (e.g. "medicine" alone would match nothing else in HCAHPS,
# but "help" or "information" alone would).
DOMAINS: tuple[Domain, ...] = (
    Domain("care_transition", "Care transition (retired measure)", True,
           id_pattern=r"H_CT_.*", text_pattern=r"care transition|understood their care when", retired=True),
    Domain("discharge_information", "Discharge information", True,
           id_pattern=r"H_COMP_6_.*",
           text_pattern=r"recovery at home|discharge information"),
    Domain("medicines", "Communication about medicines", True,
           id_pattern=r"H_COMP_5_.*", text_pattern=r"medicine|medication"),
    Domain("care_coordination", "Care coordination", True,
           text_pattern=r"coordinat"),
    Domain("symptoms", "Information about symptoms", True,
           text_pattern=r"symptom"),
    Domain("communication", "Nurse and doctor communication", False,
           id_pattern=r"H_COMP_[12]_.*", text_pattern=r"(nurses|doctors) .*communicated"),
    Domain("responsiveness", "Responsiveness of staff", False,
           id_pattern=r"H_COMP_3_.*", text_pattern=r"help as soon as"),
    Domain("environment", "Hospital environment", False,
           id_pattern=r"H_CLEAN_.*|H_QUIET_.*|H_REST.*", text_pattern=r"clean|quiet|restful"),
    Domain("global", "Overall rating and recommendation", False,
           id_pattern=r"H_HSP_RATING_.*|H_RECMND_.*|H_STAR_RATING"),
)
OTHER = Domain("other", "Other", False)


def classify_domain(measure_id: str, question: str = "", answer: str = "") -> Domain:
    mid = (measure_id or "").upper()
    text = f"{question or ''} {answer or ''}".lower()
    for d in DOMAINS:
        if re.fullmatch(d.id_pattern, mid) or re.search(d.text_pattern, text):
            return d
    return OTHER


def survey_version(start: pd.Timestamp, end: pd.Timestamp) -> str:
    """Which HCAHPS survey version a reporting window's discharges came from."""
    if pd.isna(start) or pd.isna(end):
        return UNKNOWN_VERSION
    if end < SURVEY_UPDATE_DATE:
        return ORIGINAL
    if start >= SURVEY_UPDATE_DATE:
        return UPDATED
    return MIXED
