"""Command-line interface: fetch, validate, analyze, report, run."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import analysis, reporting, sources
from .analysis import IdentityError
from .sources import SourceError
from .validation import SchemaError, findings_frame


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--data-dir", type=Path, default=Path("data"),
                   help="Release folder with the three CSVs, or a data root whose newest "
                        "raw/<release>/ folder is used (default: data)")
    p.add_argument("--previous-dir", type=Path,
                   help="An earlier release folder, for release-to-release changes")
    p.add_argument("--facility-id", default=analysis.TARGET_FACILITY_ID,
                   help="CMS facility ID (default: %(default)s, University of Washington Medical Center)")
    p.add_argument("--out", type=Path, default=Path("output"), help="Output folder (default: output)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="uwmc-monitor", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    f = sub.add_parser("fetch", help="Download the current CMS release")
    f.add_argument("--raw-dir", type=Path, default=Path("data/raw"))

    for name, help_ in (("validate", "Run data-quality checks and print findings"),
                        ("analyze", "Write comparison tables (CSV/JSON)"),
                        ("report", "Write tables and the HTML report"),
                        ("run", "Full pipeline: [fetch], validate, analyze, report")):
        p = sub.add_parser(name, help=help_)
        _common(p)
        if name in ("report", "run"):
            p.add_argument("--pdf", action="store_true",
                           help="Also export PDF (needs WeasyPrint or a local Chrome/Chromium)")
        if name == "run":
            p.add_argument("--fetch", action="store_true", help="Download the current release first")
            p.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    return parser


def _analyze(args):
    data_dir = sources.resolve_data_dir(args.data_dir)
    print(f"Using data: {data_dir}")
    result = analysis.analyze(data_dir, args.previous_dir, args.facility_id)
    if result.current.provenance.get("synthetic"):
        print("WARNING: SYNTHETIC TEST DATA - results are not real CMS findings.")
    h = result.current.hospital
    print(f"Verified facility: {h['facility_id']} {h['facility_name']} "
          f"({h.get('city_town', '')}, {h.get('state', '')})")
    return result


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "fetch" or (args.command == "run" and args.fetch):
            release = sources.fetch_release(args.raw_dir)
            print(f"Release saved to {release}")
            if args.command == "fetch":
                return 0
            args.data_dir = release
        result = _analyze(args)
        failures = sum(f.severity == "failure" for f in result.findings)
        if args.command == "validate":
            print(findings_frame(result.findings).to_string(index=False, max_colwidth=70))
            return 1 if failures else 0
        paths = reporting.write_tables(result, args.out)
        if args.command in ("report", "run"):
            paths.update(reporting.write_report(result, args.out, pdf=args.pdf))
            if args.pdf and "pdf" not in paths:
                print("PDF not written: install WeasyPrint or Chrome/Chromium, or print the HTML to PDF.")
        comp = result.comparison
        print(f"Measures: {len(comp)}, comparable: {int(comp['comparable'].sum()) if len(comp) else 0}, "
              f"findings: {failures} failure(s), "
              f"{sum(f.severity == 'anomaly' for f in result.findings)} anomaly(ies)")
        for key, path in paths.items():
            print(f"  {key}: {path}")
        return 0
    except (SourceError, SchemaError, IdentityError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
