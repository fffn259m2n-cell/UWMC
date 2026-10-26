"""Write SYNTHETIC fixtures for tests and the offline demo.

Every article and trial here is invented. Titles start with [SYNTHETIC], PMIDs
use the 9-series (99000001...) and NCT IDs use NCT9900xxxx so they cannot be
confused with real records. Run: python tests/fixtures/make_fixtures.py
"""

import json
from pathlib import Path

HERE = Path(__file__).parent


def art(pmid, title, abstract, **kw):
    d = {"pmid": pmid, "title": f"[SYNTHETIC] {title}", "abstract": abstract,
         "authors": kw.get("authors", ["Test Author", "Second Author"]),
         "journal": kw.get("journal", "Synthetic Journal of Electrophysiology"),
         "pub_date": kw.get("pub_date", "2026-09"), "entrez_date": kw.get("entrez_date", "2026-10-01"),
         "doi": kw.get("doi", ""), "publication_types": kw.get("types", ["Journal Article"]),
         "mesh_terms": kw.get("mesh", []), "keywords": kw.get("keywords", []), "language": "eng"}
    return d


RCT = art("99000001", "Pulsed-field versus thermal ablation for paroxysmal atrial fibrillation: a randomized trial",
          "Background: Pulsed field ablation (PFA) is an alternative to thermal ablation. "
          "Methods: In this multicenter randomized trial, a total of 412 patients with paroxysmal atrial fibrillation "
          "were randomized 1:1 to PFA or radiofrequency ablation. Rhythm was assessed with 72-hour Holter monitoring. "
          "Results: During a median follow-up of 12 months, freedom from atrial arrhythmia was 78.2% with PFA versus 74.0% "
          "with radiofrequency ablation (HR 0.84, 95% CI 0.61-1.15; p = 0.27). Major complications occurred in 1.0% and 1.5%. "
          "Conclusions: PFA was noninferior. A limitation is the open-label design. NCT99000101.",
          types=["Journal Article", "Randomized Controlled Trial"], doi="10.0000/synthetic.0001",
          mesh=["Atrial Fibrillation", "Catheter Ablation"])
COHORT = art("99000002", "Predictors of recurrence after cryoballoon pulmonary vein isolation",
             "This retrospective single-center cohort included 1,250 consecutive patients undergoing cryoballoon "
             "pulmonary vein isolation for atrial fibrillation. Recurrence at 2 years occurred in 31% of patients. "
             "Left atrial volume was associated with recurrence (aHR 1.42, 95% CI 1.10 to 1.83). "
             "Repeat ablation was performed in 140 patients, with pulmonary vein reconnection found in 61%.",
             mesh=["Atrial Fibrillation", "Cryosurgery"])
NO_ABSTRACT = art("99000003", "Catheter ablation of atrial fibrillation: where next?", "",
                  types=["Editorial"])
VT = art("99000004", "Substrate mapping for ventricular tachycardia ablation",
         "We describe 64 patients undergoing ventricular tachycardia ablation with a new mapping approach.")
OUTSIDE = art("99000005", "Dietary sodium and blood pressure in older adults",
              "Sodium intake was associated with blood pressure in 3,000 adults.")
CASE = art("99000006", "Esophageal injury after radiofrequency ablation for atrial fibrillation",
           "We report a case of esophageal injury after radiofrequency catheter ablation for atrial fibrillation "
           "detected by endoscopy on day three.", types=["Case Reports"])
MONITOR = art("99000007", "Insertable cardiac monitor detection of AF recurrence after pulsed field ablation",
              "Insertable cardiac monitors were implanted in 88 participants after pulsed field ablation for AF. "
              "Over a mean follow-up of 18 months, recurrence detected by the insertable cardiac monitor was 22%.")

TRIAL_A = {"nct_id": "NCT99000101", "brief_title": "[SYNTHETIC] PFA vs RF for Paroxysmal AF",
           "official_title": "[SYNTHETIC] A Randomized Trial of Pulsed Field vs Radiofrequency Ablation",
           "overall_status": "RECRUITING", "study_type": "INTERVENTIONAL", "phases": ["NA"],
           "conditions": ["Atrial Fibrillation"], "interventions": ["Device: Pulsed field ablation", "Device: RF ablation"],
           "enrollment": 400, "enrollment_type": "ESTIMATED", "primary_outcomes": ["Freedom from atrial arrhythmia | 12 months"],
           "sponsor": "Synthetic University", "start_date": "2025-01", "primary_completion_date": "2027-06",
           "completion_date": "2027-12", "first_posted": "2024-11-01", "last_update_posted": "2026-08-01",
           "has_results": False, "locations_count": 6, "washington_sites": ["Synthetic Medical Center, Seattle"]}
TRIAL_B = {"nct_id": "NCT99000102", "brief_title": "[SYNTHETIC] Posterior Wall Isolation in Persistent AF",
           "overall_status": "ACTIVE_NOT_RECRUITING", "study_type": "INTERVENTIONAL", "phases": ["NA"],
           "conditions": ["Persistent Atrial Fibrillation"], "interventions": ["Procedure: PVI + PWI", "Procedure: PVI"],
           "enrollment": 300, "enrollment_type": "ESTIMATED", "primary_outcomes": ["Recurrence | 12 months"],
           "sponsor": "Synthetic Heart Institute", "start_date": "2024-03", "primary_completion_date": "2026-09",
           "completion_date": "2027-03", "last_update_posted": "2026-06-01", "locations_count": 3}
TRIAL_C = {"nct_id": "NCT99000103", "brief_title": "[SYNTHETIC] Wearable Monitoring After Ablation",
           "overall_status": "NOT_YET_RECRUITING", "study_type": "OBSERVATIONAL", "phases": [],
           "conditions": ["Atrial Fibrillation"], "interventions": ["Device: Smartwatch ECG"],
           "enrollment": 150, "enrollment_type": "ESTIMATED", "primary_outcomes": ["AF burden | 6 months"],
           "sponsor": "Synthetic College", "start_date": "2026-11", "last_update_posted": "2026-09-15", "locations_count": 1}


def write(name, articles, trials, window, rechecked=(), missing=(), pubmed_total=None):
    folder = HERE / name
    folder.mkdir(exist_ok=True)
    (folder / "snapshot.json").write_text(json.dumps({
        "synthetic": True, "provenance": "synthetic fixture (invented records)",
        "window": window, "pubmed_total": pubmed_total or len(articles),
        "articles": articles, "trials": trials, "trials_total": len(trials),
        "rechecked_trials": list(rechecked), "missing_trials": list(missing)}, indent=2), encoding="utf-8")


# Run 1: baseline. Includes a duplicate PMID to exercise deduplication.
write("snapshot_run1", [RCT, COHORT, NO_ABSTRACT, VT, OUTSIDE, CASE, dict(RCT)],
      [TRIAL_A, TRIAL_B, TRIAL_C], {"start": "2026-09-01", "end": "2026-10-01"})

# Run 2: one article gains an abstract (updated), one new article, trial changes,
# trial B drops out of the status-filtered search and is re-read as COMPLETED,
# trial C is no longer returned at all.
updated_editorial = dict(NO_ABSTRACT, abstract="Catheter ablation for atrial fibrillation continues to evolve; "
                         "this editorial discusses pulsed field ablation and recurrence monitoring.")
a2 = dict(TRIAL_A, enrollment=450, last_update_posted="2026-10-10", locations_count=8,
          washington_sites=["Synthetic Medical Center, Seattle", "Synthetic Clinic, Spokane"])
b2 = dict(TRIAL_B, overall_status="COMPLETED", has_results=True, last_update_posted="2026-10-05")
write("snapshot_run2", [updated_editorial, MONITOR, RCT],
      [a2], {"start": "2026-09-30", "end": "2026-10-31"}, rechecked=[b2], missing=["NCT99000103"])

# Raw API responses in the exact formats the live clients parse.
raw = HERE / "api"
raw.mkdir(exist_ok=True)
(raw / "esearch_page1.json").write_text(json.dumps(
    {"esearchresult": {"count": "3", "retmax": "2", "retstart": "0", "idlist": ["99000001", "99000002"]}}), encoding="utf-8")
(raw / "esearch_page2.json").write_text(json.dumps(
    {"esearchresult": {"count": "3", "retmax": "2", "retstart": "2", "idlist": ["99000002", "99000003"]}}), encoding="utf-8")
(raw / "efetch.xml").write_text("""<?xml version="1.0" ?>
<PubmedArticleSet>
<PubmedArticle><MedlineCitation><PMID>99000001</PMID><Article>
<Journal><Title>Synthetic Journal of Electrophysiology</Title><JournalIssue><PubDate><Year>2026</Year><Month>Sep</Month></PubDate></JournalIssue></Journal>
<ArticleTitle>[SYNTHETIC] Structured abstract record</ArticleTitle>
<ELocationID EIdType="doi">10.0000/synthetic.eloc</ELocationID>
<Abstract><AbstractText Label="BACKGROUND">Pulsed field ablation is new.</AbstractText><AbstractText Label="RESULTS">A total of 412 patients were randomized.</AbstractText></Abstract>
<AuthorList><Author><LastName>Author</LastName><ForeName>Test</ForeName></Author><Author><CollectiveName>Synthetic Investigators</CollectiveName></Author></AuthorList>
<Language>eng</Language>
<PublicationTypeList><PublicationType>Journal Article</PublicationType><PublicationType>Randomized Controlled Trial</PublicationType></PublicationTypeList>
<ArticleDate><Year>2026</Year><Month>09</Month><Day>15</Day></ArticleDate>
</Article>
<MeshHeadingList><MeshHeading><DescriptorName>Atrial Fibrillation</DescriptorName></MeshHeading></MeshHeadingList>
<KeywordList><Keyword>pulsed field ablation</Keyword></KeywordList>
</MedlineCitation>
<PubmedData><History><PubMedPubDate PubStatus="entrez"><Year>2026</Year><Month>10</Month><Day>2</Day></PubMedPubDate></History>
<ArticleIdList><ArticleId IdType="pubmed">99000001</ArticleId><ArticleId IdType="doi">10.0000/synthetic.0001</ArticleId></ArticleIdList></PubmedData>
</PubmedArticle>
<PubmedArticle><MedlineCitation><PMID>99000003</PMID><Article>
<Journal><Title>Synthetic Journal</Title><JournalIssue><PubDate><MedlineDate>2026 Sep-Oct</MedlineDate></PubDate></JournalIssue></Journal>
<ArticleTitle>[SYNTHETIC] Record without abstract or DOI</ArticleTitle>
<Language>eng</Language><PublicationTypeList><PublicationType>Editorial</PublicationType></PublicationTypeList>
</Article></MedlineCitation><PubmedData><ArticleIdList><ArticleId IdType="pubmed">99000003</ArticleId></ArticleIdList></PubmedData>
</PubmedArticle>
</PubmedArticleSet>
""", encoding="utf-8")
study = lambda nct, status, token=None: {  # noqa: E731
    "protocolSection": {
        "identificationModule": {"nctId": nct, "briefTitle": f"[SYNTHETIC] Trial {nct}"},
        "statusModule": {"overallStatus": status, "startDateStruct": {"date": "2025-01"},
                         "lastUpdatePostDateStruct": {"date": "2026-10-01"}},
        "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Synthetic Sponsor"}},
        "conditionsModule": {"conditions": ["Atrial Fibrillation"]},
        "designModule": {"studyType": "INTERVENTIONAL", "phases": ["NA"],
                         "enrollmentInfo": {"count": 100, "type": "ESTIMATED"}},
        "armsInterventionsModule": {"interventions": [{"type": "DEVICE", "name": "Pulsed field ablation"}]},
        "outcomesModule": {"primaryOutcomes": [{"measure": "Freedom from AF", "timeFrame": "12 months"}]},
        "contactsLocationsModule": {"locations": [
            {"facility": "Synthetic Hospital", "city": "Seattle", "state": "Washington", "country": "United States"},
            {"facility": "Other Site", "city": "Portland", "state": "Oregon", "country": "United States"}]}},
    "hasResults": False}
(raw / "ctgov_page1.json").write_text(json.dumps(
    {"totalCount": 3, "studies": [study("NCT99000101", "RECRUITING"), study("NCT99000102", "RECRUITING")],
     "nextPageToken": "PAGE2"}), encoding="utf-8")
(raw / "ctgov_page2.json").write_text(json.dumps(
    {"totalCount": 3, "studies": [study("NCT99000102", "RECRUITING"), study("NCT99000103", "NOT_YET_RECRUITING")]}), encoding="utf-8")
(raw / "ctgov_single.json").write_text(json.dumps(study("NCT99000104", "COMPLETED")), encoding="utf-8")
print("Synthetic fixtures written.")
