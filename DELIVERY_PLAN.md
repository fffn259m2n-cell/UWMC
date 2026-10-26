# Delivery plan: getting these projects to UW Medicine

How to move from "built and tested" to "in the hands of the right UW people, who can see,
try and use it". Items marked **[YOU]** need you; nothing has been sent to anyone.

---

## 0. The three gifts at a glance

| Project | Best first recipient | Why them | Risk level | Ready to share once… |
|---|---|---|---|---|
| **EP Research Copilot** | Your own EP PI or senior EP research colleague | You already work with them; it saves *their* team time; public data only | Low | It runs once on a networked machine (step 1.3) |
| **Quality Signal Monitor** | UW Center for Scholarship in Patient Care Quality and Safety / UWMC patient-experience or quality team | Public CMS data about their own hospital, led by discharge and care-transition measures | Low to moderate (public numbers about UWMC) | The real CMS report is generated and spot-checked (step 1.2) |
| **Teach-Back Companion** | Clinical informatics + patient education, via a clinical sponsor (e.g. your mentor, then Dr. Andrew White's group) | Patient-facing AI-adjacent work needs a clinician sponsor before anything else | Higher (patient-facing concept) | A clinician has done the review checklist (step 1.4) |

**Recommended order:** EP Copilot, then Quality Monitor, then Teach-Back. Start where you
have a relationship and the stakes are lowest. Each positive response makes the next
introduction easier.

---

## 1. Readiness gates (before contacting anyone)

### 1.1 You test everything **[YOU]** (about 45 minutes)
Follow [TESTING.md](TESTING.md). Note anything odd; send it back for fixing.

### 1.2 Generate the real UWMC quality report **[YOU]** (about 15 minutes)
CMS was unreachable from the build environment, so this has **never run on real data**.
On any computer or Codespace with internet access:
```bash
cd quality-signal-monitor && uwmc-monitor run --fetch
```
Then:
- [ ] Identity section shows CMS facility 500008 and UW Medical Center's Seattle address.
- [ ] Three values in `output/benchmark_comparisons.csv` match Medicare Care Compare.
- [ ] The discharge and care-transition section makes sense (the October 2026 CMS refresh is expected to be the first with updated-survey measures).
- [ ] Any data-quality **failure** is understood.
- [ ] Print the HTML to PDF from your browser (Ctrl/Cmd+P, Save as PDF).

If anything fails, send the error text; fixes will usually be small (column names, dates).

### 1.3 Run the EP Copilot live once **[YOU]** (about 5 minutes)
```bash
cd ep-research-copilot && ep-copilot run --days 30
```
- [ ] It reports PubMed and trial counts similar to the sample (about 100 articles a month, about 400 trials).
- [ ] Open 5 article links and 5 trial links; confirm they go to the right records.
- [ ] Mark 20 to 30 rows of `output/review_queue.csv` yourself, then run
      `ep-copilot import-reviews output/review_queue.csv && ep-copilot evaluate`.
      You now have a real precision figure to quote, measured by a person.

### 1.4 Clinical sanity check of the Teach-Back Companion **[YOU]**
Ask one clinician you know (resident, nurse, pharmacist or your mentor) to spend 20 minutes
with the demo and [teach-back-companion/docs/clinical_review_checklist.md](teach-back-companion/docs/clinical_review_checklist.md).
Fix what they find before showing it to UW Medicine leadership.

### 1.5 Make the code reachable **[YOU decides; I can do the mechanics on request]**
The repository is currently **private** and the work sits on branch
`claude/uwmc-quality-signal-monitor-zfct6y`.
1. **Merge to `main`** (I can open the pull request if you want).
2. **Rename the repository.** "UWMC" alone can look official. Something like
   `uwmc-independent-public-data-tools` keeps the purpose clear. GitHub redirects old links.
3. **Make it public** (Settings, then Danger zone, then Change visibility), or keep it private
   and add specific people as collaborators. Public is simpler for a gift and costs nothing.
   - Already safe to publish: no credentials, no patient data, no copyrighted abstracts (EP
     outputs and data folders are git-ignored), MIT license, independence disclaimers in every README.
4. **Create a release** (Releases, then Draft a new release, tag `v1.0.0`). Attach the real
   UWMC quality report PDF (public CMS data) and the synthetic sample reports. Do **not**
   attach the EP real-data digest publicly: it quotes publisher abstracts. Share that one
   privately with your PI.

---

## 2. Who to contact, and how

### 2.1 EP Research Copilot: your PI or EP research lead
- **Channel:** in person or your usual email. You are a known colleague, not a cold contact.
- **Bring:** the live digest (step 1.3) on your laptop, and the repository link.
- **Ask:** "Would this save the team time? Which topic or task should it cover next?"
- **Draft message:** [ep-research-copilot/docs/gift_handoff.md](ep-research-copilot/docs/gift_handoff.md) (bottom).

### 2.2 Quality Signal Monitor: quality / patient-experience
- **Primary:** UW Center for Scholarship in Patient Care Quality and Safety (Department of
  Medicine). UW's informatics faculty page lists Andrew White, MD, as its director.
  **[CONFIRM]** his current title and email in the official UW directory (directory.uw.edu);
  do not rely on secondary websites.
- **Better route:** ask your PI or mentor to forward it with a one-line introduction. A
  warm forward gets read; a cold email to a busy leader often does not.
- **Fallback:** the UW Medicine contact directory, asking for UWMC patient experience or
  quality improvement. **[CONFIRM]** the page.
- **Send:** a short email (draft in [quality-signal-monitor/docs/gift_handoff.md](quality-signal-monitor/docs/gift_handoff.md)) with
  (1) the one-paragraph summary, (2) the real report PDF, (3) the repository link, (4) an
  offer of a 15-minute walk-through. No attachments other than the PDF.

### 2.3 Teach-Back Companion: clinical informatics and patient education
- **Only after** step 1.4 and ideally after one of the other two has landed.
- **Route:** through your mentor or the person who responded to 2.2. Ask for 20 minutes to
  demo and for feedback, not for a pilot. Explicitly say it is a synthetic-data prototype
  and you are asking whether the problem is worth solving at UW.
- **Bring:** the live demo (Codespaces or laptop) and [teach-back-companion/docs/uw_medicine_proposal.md](teach-back-companion/docs/uw_medicine_proposal.md).
- **Key message:** "Epic's assistant explains records. This checks whether patients
  understood, and whether simplified or translated instructions still say the same thing."

### One-page summaries
`one-pagers/pdf/*.pdf`, one per project, are ready to attach to an introduction email.
After renaming or publishing the repository, rebuild them with the final link:
`python one-pagers/build.py --repo-url https://github.com/<owner>/<new-name> --qsm-status "generated <date> from the <month> CMS release"`.

### 2.4 Message rules (all three)
- Lead with their benefit, in one sentence. Then what it is, then what you are asking.
- State clearly: independent, unpaid, public or synthetic data only, not affiliated or endorsed.
- One ask per email (feedback or a 15-minute look). Never ask for data access or a role.
- No UW logos or branding anywhere.
- Follow up once after 10 to 14 days; then let it rest.

---

## 3. How UW staff can access it

| Need | Option | What they do | Notes |
|---|---|---|---|
| Just read it | PDF report or digest | Open the attachment | Zero effort; best first contact |
| See the code and docs | GitHub repository | Click the link | Needs the repo public, or you add them |
| Try it without installing | GitHub Codespaces | Code, then Codespaces, then Create; the demo opens in the browser | Needs a free GitHub account; avoids installing software on managed UW devices |
| Watch it work | You demo it | 15-minute video call or in person | Often the most effective option |
| Use it regularly | Install on a research or personal machine | `pip install -e .` per the project README | UW Medicine-managed computers may restrict software installs; follow UW IT policy and ask IT if unsure |

**Important for UW devices:** do not install or run anything on a UW Medicine clinical
workstation, and never connect these tools to UW systems. Codespaces or a research or
personal machine is the right place for a demo.

---

## 4. How they use it

### EP Research Copilot (research team)
- **Monthly:** one person runs `ep-copilot run` (about a minute), shares
  `ep_research_digest.html` and `trials.csv`, and spends about 30 minutes on high-priority items.
- **Customise:** add topics (VT ablation, devices, inherited arrhythmias) in `config/topics.yaml`.
- **Keep:** back up `data/ep_copilot.sqlite`; it holds the month-to-month trial history.
- **Measure:** record reviewer decisions; `ep-copilot evaluate` reports precision and recall.

### Quality Signal Monitor (quality team)
- **After each CMS refresh** (CMS updates Care Compare quarterly): `uwmc-monitor run --fetch`.
- **Compare releases:** keep each `data/raw/<date>/` folder; add `--previous-dir` for changes.
- **Use the output** as a starting point for discussion, never as a finding by itself. Gaps
  are descriptive, and the limitations page says why.

### Teach-Back Companion (informatics and patient education)
- **Today:** a demo and a discussion tool. It shows what automated teach-back and
  instruction-fidelity checking could look like, using fictional patients.
- **The fidelity evaluator** can be tried immediately on any de-identified or template
  instruction text: paste the original and a rewrite (human, AI or translated) into the
  "For care teams" tab, or use `teachback evaluate`.
- **Never** enter real patient information. Any real use needs the approvals in section 6.

---

## 5. What you offer after handing it over

Say this explicitly, so nobody worries about an open-ended obligation:
- Fixes for problems found in the first 3 months, through GitHub issues or email.
- One feature adjustment per project if asked (e.g. a new EP topic).
- After that, the code is theirs to use, change or discard (MIT license); no ongoing commitment.

Open a GitHub "Discussions" tab or pin an issue titled "Feedback welcome" so there is one
obvious place to reply.

---

## 6. Governance boundaries (say these before anyone asks)

- **No PHI, ever.** All three tools work with public data or fictional patients.
- **No connection** to Epic, MyChart or any UW system.
- **Any pilot** of the Teach-Back Companion with real patients or real instructions would need:
  a clinical sponsor; UW Medicine IT, privacy and security review; clinical-safety sign-off
  for each instruction template; a determination from UW's Human Subjects Division (IRB) for
  any evaluation; and assessment against FDA clinical-decision-support guidance.
- **Do not describe** any tool as validated, endorsed, deployed or improving outcomes unless
  that has actually happened and been measured.

---

## 7. Timeline

| Week | What | Who |
|---|---|---|
| 1 | Test everything (TESTING.md); send back issues; fixes made | You, then me |
| 1 | Real CMS report + live EP run (1.2, 1.3) | You |
| 2 | Clinician sanity check of Teach-Back (1.4); merge, rename, make public, release v1.0 (1.5) | You (+ me on request) |
| 2 | Show EP Copilot to your PI (2.1) | You |
| 3 | Quality Monitor email via warm introduction (2.2) | You |
| 5 | Follow up once if no reply | You |
| 5 to 8 | Teach-Back demo via sponsor (2.3), if the earlier steps went well | You |
| Ongoing | Respond to feedback; document what changed and why | You + me |

---

## 8. How you will know it worked

| Signal | Strength |
|---|---|
| Someone opens it and replies with a question | Good |
| A reviewer finds a problem and you fix it quickly | Very good (shows follow-through) |
| The EP team runs it a second month without you | Strong |
| The quality team uses the report in a meeting | Strong |
| A clinician sponsor wants to discuss a pilot | Exceptional, but needs the approvals in section 6 |

For your residency application, describe only what actually happened, e.g. "Built and
shared…; received feedback from…; revised…". Measured numbers (your precision figure,
time saved) are worth more than adjectives.

---

## 9. Risks and how to handle them

| Risk | Mitigation |
|---|---|
| A number in the quality report is wrong | Spot-check against Care Compare first (1.2); the report links every value to its CMS measure ID |
| The report seems to criticise UWMC | Lead with discharge measures and descriptive language; offer it privately first; never publish UWMC findings without their awareness |
| Confusion with official UW work | Neutral repo name, disclaimers on every page, no logos, "independent" in the first sentence of every message |
| Teach-Back seen as an unapproved patient tool | Call it a synthetic-data prototype for feedback; route through a clinical sponsor; never offer it to patients |
| No reply | One follow-up, then ask your mentor; the work still stands as a public portfolio project |
| Rule-based checks miss something | Documented limits and review history; positioned as an aid to human review, never a replacement |
