@echo off
setlocal
rem Double-click to run every project's demo on synthetic data and all automated tests.
cd /d "%~dp0.."
set PYTHONUTF8=1
if not exist ".venv\Scripts\python.exe" goto :notinstalled
call ".venv\Scripts\activate.bat"
python -m pip install -q pytest httpx >nul 2>&1
echo == 1/3 Quality Signal Monitor demo, synthetic data ==
pushd quality-signal-monitor
uwmc-monitor run --data-dir tests/fixtures/synthetic_current --previous-dir tests/fixtures/synthetic_previous
popd
echo == 2/3 EP Research Copilot demo, synthetic data, two months ==
pushd ep-research-copilot
ep-copilot run --offline
ep-copilot run --offline --fixtures tests/fixtures/snapshot_run2
popd
echo == 3/3 Automated tests. Each project should say "passed", with nothing failed. ==
for %%D in (quality-signal-monitor ep-research-copilot teach-back-companion) do call :tests %%D
rem UWMC_NO_SERVE=1 is the automated check: do not open a browser there.
if not defined UWMC_NO_SERVE start "" "quality-signal-monitor\output\uwmc_quality_report.html"
if not defined UWMC_NO_SERVE start "" "ep-research-copilot\output\ep_research_digest.html"
echo.
echo Done. Two reports opened in your browser.
echo Real data needs internet. In this folder, in a Command Prompt, run:
echo    .venv\Scripts\activate ^&^& cd quality-signal-monitor ^&^& uwmc-monitor run --fetch
if not defined UWMC_NO_SERVE pause
exit /b 0

:tests
echo --- %1
pushd %1
python -m pytest -q
popd
exit /b 0

:notinstalled
echo Please double-click "Start Teach-Back Companion.bat" once first. It installs everything.
pause
exit /b 1
