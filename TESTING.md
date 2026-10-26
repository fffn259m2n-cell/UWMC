# How to test everything yourself

About 45 minutes for all three projects. You do not need to know Python.
Write anything surprising in the "Notes" column, and send it back for fixing.

## Option A: in your browser (no install), recommended

1. Open https://github.com/fffn259m2n-cell/UWMC on a laptop or tablet.
2. Switch the branch selector (top left) to `claude/uwmc-quality-signal-monitor-zfct6y`
   (or `main`, once it is merged).
3. Click the green **Code** button, then the **Codespaces** tab, then **Create codespace on …**.
4. Wait 2 to 4 minutes while it installs. A browser tab or preview pane opens with the
   **Teach-Back Companion**. If it does not, open the **Ports** tab at the bottom and click the
   globe icon next to port 8000.
5. For the other two projects, type the commands below into the **Terminal** panel at the bottom.

Codespaces is private to your GitHub account. GitHub's free monthly allowance covers this
easily; stop the codespace afterwards (**Code**, then **Codespaces**, then **…**, then **Stop**).

## Option B: on your own computer

Install Python 3.11 or newer (python.org), then in a terminal:

```bash
git clone https://github.com/fffn259m2n-cell/UWMC.git
cd UWMC
git checkout claude/uwmc-quality-signal-monitor-zfct6y
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e ./quality-signal-monitor -e ./ep-research-copilot -e ./teach-back-companion
```

## Option C: run the automated tests (optional)

```bash
pip install pytest httpx
cd quality-signal-monitor && pytest -q && cd ..      # expect: 74 passed
cd ep-research-copilot   && pytest -q && cd ..      # expect: 54 passed
cd teach-back-companion  && pytest -q && cd ..      # expect: all passed
```

---

## 1. Teach-Back Companion (about 20 minutes)

Start it (Option B only; Codespaces starts it for you):
`cd teach-back-companion && teachback serve`, then open http://127.0.0.1:8000

| # | Do this | You should see | Notes |
|---|---|---|---|
| 1 | Click **Alex Rivera (fictional)** | "My health" with an AFib explanation; a yellow notice that the plan is synthetic | |
| 2 | Click **Simple**, then **More detail** | The explanation changes reading level; the care-plan note stays the same | |
| 3 | **My medicines** | Each medicine shows the original instruction (green) beside a plain version (blue) | |
| 4 | **Check my understanding**, pick *Apixaban*, type: `I take it twice a day and I can stop when my heart feels normal again.` | "Points to check with your care team", explaining you should keep taking it even when you feel well, with the original instruction quoted | |
| 5 | Same item, type: `I take one 5 mg pill twice a day, 12 hours apart, and I keep taking it every day.` | A neutral message: the tool recognized the main points and found no conflicts, but says this does not confirm understanding and to review with the care team | |
| 6 | Pick *Pain medicine while on apixaban*, type: `No problem taking ibuprofen with it.` | A concern that the instruction says not to take ibuprofen | |
| 7 | Pick *Emergency warning signs*, type: `If my face droops I will drive myself to the ER.` | A concern: call 911 rather than getting yourself to hospital | |
| 8 | Try your own explanations, right and wrong | Write down anything it gets wrong | |
| 9 | **Ask**: `What is apixaban for?` then click **Say it more simply** | Answer labelled "From your care plan" and "General information" with a source link; then a simpler version | |
| 10 | **Ask**: `Can I stop my metoprolol?` | A refusal to advise, the exact metoprolol instruction, and care-team contacts | |
| 11 | **Ask**: `my chest feels heavy` | A red "call 911 now" box and the plan's warning signs, with no reassurance | |
| 12 | **Ask**: `What is the best diet for diabetes?` | "I won't guess", with a suggestion to ask the care team | |
| 13 | **Reminders**: choose the cardiology visit, set a time 2 minutes from now, add it, then wait | The reminder appears in the list; after about 2 minutes a pop-up appears with the instruction | |
| 14 | Try a reminder date in 2099 | "That time is after the planned date" | |
| 15 | **For care teams**: pick *Apixaban*, replace the text with `Take apixaban 5 mg once a day. You can stop when you feel better.` and click **Check** | "do not use: critical issues found", with each issue listed | |
| 16 | Click **Run benchmark** | "30 of 30 seeded errors detected; 0 false alarms on 16 clean rewrites" | |
| 17 | Click **Get help** (red, top right) | 911 and 988 guidance and the fictional care-team contacts | |
| 18 | Click **A+** a few times; try the keyboard only (Tab, Enter) | Text grows; everything is reachable and the focus outline is visible | |
| 19 | Repeat steps 4 to 7 with **Jordan Lee** (heart failure) and **Sam Okafor** (pneumonia), e.g. `If I gain 3 pounds I take an extra water pill` or `I stop the antibiotic when my fever is gone` | Concerns for each | |
| 20 | Open it on your phone (Codespaces port link) | Usable on a small screen; no sideways scrolling | |

## 2. EP Research Copilot (about 10 minutes)

```bash
cd ep-research-copilot
ep-copilot run --offline                                         # synthetic demo
ep-copilot run --offline --fixtures tests/fixtures/snapshot_run2 # a second "month"
```

Open `ep-research-copilot/output/ep_research_digest.html` (in Codespaces: right-click it in the
file list and choose **Open with Live Preview**, or download it).

| # | Check | You should see | Notes |
|---|---|---|---|
| 1 | Banner | Red "SYNTHETIC TEST DATA" | |
| 2 | Literature table | Priorities, topics, design labels; "N quoted items" expands to the exact source sentences | |
| 3 | Trials, then Changes | Enrollment 400 to 450, a status change to COMPLETED, a trial "not returned by ClinicalTrials.gov" | |
| 4 | Filters | Typing in the filter box narrows the table | |

**Real data** (only on a computer or codespace with internet access): `ep-copilot run --days 30`.
This contacts PubMed and ClinicalTrials.gov directly. It has not yet been run from a networked
machine, so please tell me what it prints. The real-record sample (26 articles, 396 trials)
generated during development is attached separately.

## 3. Quality Signal Monitor (about 10 minutes)

```bash
cd quality-signal-monitor
uwmc-monitor run --data-dir tests/fixtures/synthetic_current --previous-dir tests/fixtures/synthetic_previous
```

Open `output/uwmc_quality_report.html`: red synthetic banner, discharge and care-transition
section first, charts, data-quality findings.

**Real data**: `uwmc-monitor run --fetch --pdf` downloads the current CMS release and builds the
real UWMC report. **This is the most important test.** It has never run against real CMS
data, because CMS was blocked where it was built. Check:

| # | Check | Notes |
|---|---|---|
| 1 | It finishes without errors (if not, copy the error message) | |
| 2 | Identity section shows facility 500008 and the UW Medical Center name and Seattle address | |
| 3 | Pick three measures in `output/benchmark_comparisons.csv` and compare UWMC and national values with Medicare Care Compare | |
| 4 | Read the data-quality findings; note any **failure** | |

## Sending feedback

Note the project, step number, what you typed, and what you saw. Screenshots help.
