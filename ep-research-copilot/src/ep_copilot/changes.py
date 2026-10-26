"""Field-level differences between consecutive trial snapshots."""

from __future__ import annotations

from .models import Trial

# Changes a researcher would usually want to know about.
SUBSTANTIVE = {
    "overall_status": "Recruitment status",
    "enrollment": "Enrollment",
    "enrollment_type": "Enrollment type (anticipated/actual)",
    "primary_outcomes": "Primary outcome measures",
    "interventions": "Interventions",
    "conditions": "Conditions",
    "phases": "Phase",
    "study_type": "Study type",
    "start_date": "Start date",
    "primary_completion_date": "Primary completion date",
    "completion_date": "Completion date",
    "has_results": "Results posted",
    "washington_sites": "Washington State sites",
}
# Record-keeping changes, reported separately.
ADMINISTRATIVE = {
    "brief_title": "Brief title",
    "official_title": "Official title",
    "sponsor": "Lead sponsor",
    "last_update_posted": "Last update posted",
    "first_posted": "First posted",
    "locations_count": "Number of sites",
}


def diff_trials(old: Trial, new: Trial) -> list[dict]:
    o, n = old.to_dict(), new.to_dict()
    out = []
    for fld, label in {**SUBSTANTIVE, **ADMINISTRATIVE}.items():
        if o.get(fld) != n.get(fld):
            out.append({"field": fld, "label": label, "old": o.get(fld), "new": n.get(fld),
                        "kind": "substantive" if fld in SUBSTANTIVE else "administrative"})
    return out
