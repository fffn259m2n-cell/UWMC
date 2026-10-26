"""Build a self-contained zip to send to an independent reviewer.

    python review/make_review_packet.py            # -> review/out/uwmc-review-packet-<date>.zip

The packet holds the committed source (git archive of HEAD, so nothing uncommitted or
git-ignored is included), the one-page PDFs, freshly generated SYNTHETIC sample outputs
for the Quality Monitor and the EP Copilot, and the reviewer guide. It never includes
real-data EP digests (they quote copyrighted abstracts) or anything under data/.
"""

from __future__ import annotations

import datetime as dt
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], cwd: Path) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def main() -> int:
    if subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.strip():
        print("Note: uncommitted changes are NOT included; the packet uses the last commit.")
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    stamp = dt.date.today().isoformat()
    out_dir = ROOT / "review" / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"uwmc-review-packet-{stamp}-{sha}.zip"

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        src_zip = tmp / "source.zip"
        run(["git", "archive", "--format=zip", "-o", str(src_zip), "HEAD"], ROOT)
        samples = tmp / "samples"
        samples.mkdir()
        qsm = ROOT / "quality-signal-monitor"
        run([sys.executable, "-m", "uwmc_monitor.cli", "run", "--data-dir", "tests/fixtures/synthetic_current",
             "--previous-dir", "tests/fixtures/synthetic_previous", "--out", str(tmp / "qsm")], qsm)
        shutil.copy(tmp / "qsm" / "uwmc_quality_report.html", samples / "QualityMonitor_SYNTHETIC_sample.html")
        ep = ROOT / "ep-research-copilot"
        run([sys.executable, "-m", "ep_copilot.cli", "--out", str(tmp / "ep"), "--db", str(tmp / "ep.sqlite"), "run", "--offline"], ep)
        shutil.copy(tmp / "ep" / "ep_research_digest.html", samples / "EPCopilot_SYNTHETIC_digest.html")

        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
            with zipfile.ZipFile(src_zip) as s:
                for info in s.infolist():
                    if not info.is_dir():
                        z.writestr(f"source/{info.filename}", s.read(info))
            for name in ("REVIEW.md", "TESTING.md"):
                z.write(ROOT / name, name)
            for pdf in sorted((ROOT / "one-pagers" / "pdf").glob("*.pdf")):
                z.write(pdf, f"one-pagers/{pdf.name}")
            for f in sorted(samples.iterdir()):
                z.write(f, f"samples/{f.name}")
            z.write(ROOT / "review" / "findings_template.csv", "findings_template.csv")
            z.write(ROOT / "review" / "heldout_template.json", "heldout_template.json")
            z.writestr("START_HERE.txt",
                       "Independent review packet\n\n"
                       f"Built {stamp} from commit {sha}.\n\n"
                       "1. Read REVIEW.md (what to look for, how to report).\n"
                       "2. one-pagers/ and samples/ need no software (samples are SYNTHETIC data).\n"
                       "3. To run the tools: unzip source/, install Python 3.11+, follow TESTING.md.\n"
                       "4. Send back findings_template.csv, or your own heldout_template.json cases.\n\n"
                       "No patient data is included anywhere. Independent prototype; not affiliated with or\n"
                       "endorsed by any health system.\n")
    print(f"\nWrote {target} ({target.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
