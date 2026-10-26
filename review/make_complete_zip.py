"""Build downloads/UWMC_complete.zip: everything in one file for offline use.

    python review/make_complete_zip.py [--private-samples DIR]

Contains the committed source (git archive of HEAD), one-page PDFs, synthetic samples, the
reviewer packet and the guides. ``--private-samples`` adds a folder of real-data outputs
(for example an EP digest that quotes abstracts) under samples_REAL_private_do_not_publish/;
never commit a zip built with that option.
"""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDES = ("README.md", "TESTING.md", "DELIVERY_PLAN.md", "REVIEW.md", "CONTRIBUTING.md")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--private-samples", type=Path)
    p.add_argument("--out", type=Path, default=ROOT / "downloads" / "UWMC_complete.zip")
    args = p.parse_args()
    sha = git("rev-parse", "--short", "HEAD")
    packets = sorted((ROOT / "review" / "out").glob("uwmc-review-packet-*.zip"))
    if not packets:
        subprocess.run([sys.executable, str(ROOT / "review" / "make_review_packet.py")], check=True)
        packets = sorted((ROOT / "review" / "out").glob("uwmc-review-packet-*.zip"))
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "src.zip"
        subprocess.run(["git", "archive", "--format=zip", "-o", str(src), "HEAD"], cwd=ROOT, check=True)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED) as z, zipfile.ZipFile(src) as s:
            base = "UWMC_complete/"
            for info in s.infolist():
                if not info.is_dir() and not info.filename.startswith("downloads/"):
                    out = zipfile.ZipInfo(f"{base}source/{info.filename}", info.date_time)
                    out.external_attr, out.compress_type = info.external_attr, zipfile.ZIP_DEFLATED  # keeps scripts executable
                    z.writestr(out, s.read(info))
            for g in GUIDES:
                z.write(ROOT / g, base + g)
            for pdf in sorted((ROOT / "one-pagers" / "pdf").glob("*.pdf")):
                z.write(pdf, f"{base}one-pagers/{pdf.name}")
            for f in sorted((ROOT / "samples").glob("*.html")):
                z.write(f, f"{base}samples_synthetic/{f.name}")
            z.write(packets[-1], f"{base}send_to_reviewer/{packets[-1].name}")
            private = ""
            if args.private_samples:
                for f in sorted(args.private_samples.iterdir()):
                    z.write(f, f"{base}samples_REAL_private_do_not_publish/{f.name}")
                private = ("  samples_REAL_private_.../   Real-data EP outputs. They quote publisher abstracts:\n"
                           "                              share privately (e.g. with your PI), never publish.\n")
            z.writestr(base + "START_HERE.txt", f"""UWMC projects: complete package
Built {dt.date.today().isoformat()} from commit {sha}. Online: https://github.com/fffn259m2n-cell/UWMC (main branch)

WHAT IS IN HERE
  source/                     The full repository: all three projects, tests and docs.
  one-pagers/                 One-page PDF summaries to attach to an introduction email.
  samples_synthetic/          Sample outputs on SYNTHETIC data (safe to share).
{private}  send_to_reviewer/           The zip to send an independent reviewer (see REVIEW.md).
  TESTING.md                  Test everything yourself, step by step.
  DELIVERY_PLAN.md            How to get it to UW Medicine, who to contact, how they use it.
  REVIEW.md                   Guide for independent reviewers.
  CONTRIBUTING.md             How anyone can extend the code.

QUICKEST START ON A MAC (no GitHub sign-in needed)
  1. Open source/mac/ and double-click "Start Teach-Back Companion.command".
     If the Mac blocks it: right-click (Control-click) the file, choose Open, then Open.
     The first time it installs everything (1 to 3 minutes; internet needed), then opens
     the demo in your browser. If it says Python is needed, install Python 3.11+ from the
     page it opens, then double-click again.
  2. Double-click "Run demos and tests.command" for the other two projects and all tests.
  Step-by-step checks with expected results: TESTING.md.

QUICKEST START ON WINDOWS (no GitHub sign-in needed)
  1. Open source\\windows\\ and double-click "Start Teach-Back Companion.bat".
     If Windows says "Windows protected your PC": click More info, then Run anyway.
     If it says Python is needed: install Python 3.11+ from the page it opens and TICK
     "Add python.exe to PATH" on the first installer screen, then double-click again.
  2. Double-click "Run demos and tests.bat" for the other two projects and all tests.

OTHER WAYS
  Browser: open the GitHub repository in Codespaces (TESTING.md, Option A).
  Linux or by hand: install Python 3.11+, then in source/:
           pip install -e ./quality-signal-monitor -e ./ep-research-copilot -e ./teach-back-companion
           teachback serve      (then open http://127.0.0.1:8000)

Measured accuracy of the Teach-Back Companion: source/teach-back-companion/docs/evaluation_results.md
No patient data anywhere. Independent prototypes; not affiliated with or endorsed by UW Medicine.
""")
    print(f"Wrote {args.out} ({args.out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
