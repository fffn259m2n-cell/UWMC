"""ClinicalTrials.gov API v2 (/studies), with pagination.

Docs: https://clinicaltrials.gov/data-api/api
Registry entries describe what a trial plans or reports administratively.
They are not results, and a COMPLETED status does not mean results exist.
"""

from __future__ import annotations

import json

from . import http
from .models import Trial

BASE = "https://clinicaltrials.gov/api/v2/studies"
PAGE_SIZE = 100


class TrialsClient:
    def __init__(self, getter=http.get):
        self.getter = getter
        self.limiter = http.RateLimiter(3.0)

    def search(self, condition: str, intervention: str, statuses: list[str],
               max_records: int = 1000) -> tuple[list[Trial], int, bool]:
        """Return (trials, total reported, truncated)."""
        params = {"query.cond": condition, "query.intr": intervention, "pageSize": PAGE_SIZE,
                  "countTotal": "true", "format": "json"}
        if statuses:
            params["filter.overallStatus"] = ",".join(statuses)
        trials: dict[str, Trial] = {}
        total, token = 0, None
        while True:
            page = dict(params, **({"pageToken": token} if token else {}))
            data = json.loads(self.getter(BASE, page, limiter=self.limiter))
            total = data.get("totalCount", total)
            for study in data.get("studies", []):
                t = parse_study(study)
                if t:
                    trials[t.nct_id] = t
            token = data.get("nextPageToken")
            if not token or len(trials) >= max_records:
                break
        return list(trials.values()), int(total or len(trials)), bool(token)

    def get(self, nct_id: str) -> Trial | None:
        """Re-read one tracked study, e.g. after it drops out of a status-filtered search."""
        try:
            data = json.loads(self.getter(f"{BASE}/{nct_id}", {"format": "json"}, limiter=self.limiter))
        except http.FetchError as exc:
            if "404" in str(exc):
                return None
            raise
        return parse_study(data)


def parse_study(study: dict) -> Trial | None:
    p = study.get("protocolSection", {})
    ident = p.get("identificationModule", {})
    nct = ident.get("nctId", "")
    if not nct:
        return None
    status = p.get("statusModule", {})
    design = p.get("designModule", {})
    enroll = design.get("enrollmentInfo", {})
    arms = p.get("armsInterventionsModule", {})
    outcomes = p.get("outcomesModule", {})
    locations = p.get("contactsLocationsModule", {}).get("locations", [])
    wa_sites = sorted({
        f"{loc.get('facility', '').strip()}, {loc.get('city', '').strip()}".strip(", ")
        for loc in locations
        if loc.get("state") == "Washington" and loc.get("country") == "United States"
    })
    return Trial(
        nct_id=nct,
        brief_title=ident.get("briefTitle", ""),
        official_title=ident.get("officialTitle", ""),
        overall_status=status.get("overallStatus", ""),
        study_type=design.get("studyType", ""),
        phases=list(design.get("phases", [])),
        conditions=list(p.get("conditionsModule", {}).get("conditions", [])),
        interventions=[f"{i.get('type', '').title()}: {i.get('name', '')}".strip(": ")
                       for i in arms.get("interventions", [])],
        enrollment=enroll.get("count"),
        enrollment_type=enroll.get("type", ""),
        primary_outcomes=[" | ".join(x for x in (o.get("measure", ""), o.get("timeFrame", "")) if x)
                          for o in outcomes.get("primaryOutcomes", [])],
        sponsor=p.get("sponsorCollaboratorsModule", {}).get("leadSponsor", {}).get("name", ""),
        start_date=status.get("startDateStruct", {}).get("date", ""),
        primary_completion_date=status.get("primaryCompletionDateStruct", {}).get("date", ""),
        completion_date=status.get("completionDateStruct", {}).get("date", ""),
        first_posted=status.get("studyFirstPostDateStruct", {}).get("date", ""),
        last_update_posted=status.get("lastUpdatePostDateStruct", {}).get("date", ""),
        has_results=bool(study.get("hasResults", False)),
        locations_count=len(locations),
        washington_sites=wa_sites,
    )
