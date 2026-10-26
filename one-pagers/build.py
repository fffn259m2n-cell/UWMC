"""Fill in the one-pagers and print them to PDF with a local Chrome/Chromium.

  python one-pagers/build.py --repo-url https://github.com/OWNER/REPO [--qsm-status "..."]

Set CHROME to the browser executable if it is not on PATH.
"""
import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
CANDIDATES = ["chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "chrome", "msedge"]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-url", required=True)
    p.add_argument("--qsm-status", default="pending first run on live CMS data; verify before sharing.")
    p.add_argument("--bench", default="30 of 30 seeded errors detected, 0 false alarms on 16 faithful rewrites (synthetic cases).")
    p.add_argument("--tbc-tests", default="200+")
    a = p.parse_args()
    exe = os.environ.get("CHROME") or next((shutil.which(c) for c in CANDIDATES if shutil.which(c)), None)
    out = HERE / "pdf"
    out.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(HERE / "_style.css", tmp)
        for src in sorted(HERE.glob("*.html")):
            html = (src.read_text(encoding="utf-8").replace("{{REPO_URL}}", a.repo_url.rstrip("/"))
                    .replace("{{QSM_STATUS}}", a.qsm_status).replace("{{BENCH}}", a.bench)
                    .replace("{{TBC_TESTS}}", a.tbc_tests))
            filled = Path(tmp) / src.name
            filled.write_text(html, encoding="utf-8")
            if not exe:
                print(f"No Chrome/Chromium found; open {filled} in a browser and print to PDF.")
                continue
            pdf = out / src.with_suffix(".pdf").name
            subprocess.run([exe, "--headless", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer",
                            f"--print-to-pdf={pdf}", filled.as_uri()], check=True, capture_output=True)
            print(f"wrote {pdf}")


if __name__ == "__main__":
    main()
