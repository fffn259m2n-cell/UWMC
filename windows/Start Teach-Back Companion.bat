@echo off
setlocal
rem Double-click to install (first time only) and open the Teach-Back Companion demo.
cd /d "%~dp0.."
set PYTHONUTF8=1
echo == UWMC projects: setting up. The first time takes 1 to 3 minutes. ==
set "PY="
rem "python" first; "py -3" uses the newest installed Python 3 and never asks to install one.
for %%C in ("python" "py -3") do call :try %%C
if not defined PY goto :nopython
if not exist ".venv\Scripts\python.exe" %PY% -m venv .venv
if not exist ".venv\Scripts\python.exe" goto :novenv
call ".venv\Scripts\activate.bat"
python -c "import teachback, ep_copilot, uwmc_monitor" >nul 2>&1
if errorlevel 1 goto :install
goto :run

:install
python -m pip install -q --upgrade pip
python -m pip install -q -e ./quality-signal-monitor -e ./ep-research-copilot -e ./teach-back-companion
if errorlevel 1 goto :installfailed

:run
rem UWMC_NO_SERVE=1 installs only (used by the automated Windows check)
if defined UWMC_NO_SERVE exit /b 0
echo.
echo == Starting the Teach-Back Companion at http://127.0.0.1:8000 ==
echo    Your browser will open. Keep this window open while you use it.
echo    To stop: close this window.
start "" /b powershell -NoProfile -Command "Start-Sleep -Seconds 4; Start-Process 'http://127.0.0.1:8000'"
cd teach-back-companion
teachback serve
pause
exit /b 0

:try
if defined PY exit /b 0
%~1 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if not errorlevel 1 set "PY=%~1"
exit /b 0

:nopython
echo.
echo Python 3.11 or newer is needed. Opening the download page.
echo Install it, and on the FIRST installer screen tick "Add python.exe to PATH".
echo Then double-click this file again.
start "" "https://www.python.org/downloads/windows/"
pause
exit /b 1

:novenv
echo Could not create the environment.
pause
exit /b 1

:installfailed
echo Install failed. Check the internet connection and try again.
pause
exit /b 1
