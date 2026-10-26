#!/bin/bash
# Double-click to install (first time only) and open the Teach-Back Companion demo.
cd "$(dirname "$0")/.." || exit 1
echo "== UWMC projects: setting up (the first time takes 1 to 3 minutes) =="
PY=""
for c in python3.13 python3.12 python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo
  echo "Python 3.11 or newer is needed. Opening the download page."
  echo "Install it (choose 'macOS 64-bit universal2 installer'), then double-click this file again."
  open "https://www.python.org/downloads/macos/"
  read -r -p "Press Enter to close."; exit 1
fi
if [ ! -x .venv/bin/python ]; then
  "$PY" -m venv .venv || { read -r -p "Could not create the environment. Press Enter to close."; exit 1; }
fi
source .venv/bin/activate
if ! python -c "import teachback, ep_copilot, uwmc_monitor" 2>/dev/null; then
  python -m pip install -q --upgrade pip
  python -m pip install -q -e ./quality-signal-monitor -e ./ep-research-copilot -e ./teach-back-companion \
    || { read -r -p "Install failed (is the internet on?). Press Enter to close."; exit 1; }
fi
echo
echo "== Starting the Teach-Back Companion at http://127.0.0.1:8000 =="
echo "   Your browser will open. Keep this window open while you use it."
echo "   To stop: press Control+C here, or close this window."
(sleep 3; open "http://127.0.0.1:8000") &
cd teach-back-companion && teachback serve
