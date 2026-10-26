#!/bin/bash
# Double-click to run every project's demo on synthetic data and all automated tests.
cd "$(dirname "$0")/.." || exit 1
if [ ! -x .venv/bin/python ]; then
  echo "Please double-click 'Start Teach-Back Companion.command' once first (it installs everything)."
  read -r -p "Press Enter to close."; exit 1
fi
source .venv/bin/activate
python -m pip install -q pytest httpx >/dev/null 2>&1
echo "== 1/3 Quality Signal Monitor demo (synthetic data) =="
(cd quality-signal-monitor && uwmc-monitor run --data-dir tests/fixtures/synthetic_current --previous-dir tests/fixtures/synthetic_previous | tail -2)
echo "== 2/3 EP Research Copilot demo (synthetic data, two months) =="
(cd ep-research-copilot && ep-copilot run --offline | tail -1 && ep-copilot run --offline --fixtures tests/fixtures/snapshot_run2 | tail -1)
echo "== 3/3 Automated tests (expect 74, 54 and 249 passed) =="
for d in quality-signal-monitor ep-research-copilot teach-back-companion; do
  printf "%-24s" "$d"; (cd "$d" && python -m pytest -q 2>&1 | tail -1)
done
open quality-signal-monitor/output/uwmc_quality_report.html
open ep-research-copilot/output/ep_research_digest.html
echo
echo "Done. Two reports opened in your browser."
echo "Real data (needs internet): in Terminal, inside this folder, run"
echo "   source .venv/bin/activate && cd quality-signal-monitor && uwmc-monitor run --fetch"
read -r -p "Press Enter to close."
