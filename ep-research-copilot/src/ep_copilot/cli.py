"""Command-line interface.

  ep-copilot run       fetch new records, screen, extract, track trials, write the digest
  ep-copilot fetch     same as run, without writing the digest
  ep-copilot screen    re-screen and re-extract the last run with the current config
  ep-copilot report    rewrite the digest for the last (or a given) run
  ep-copilot validate  check the database and configuration
  ep-copilot import-reviews FILE   load reviewer decisions from review_queue.csv
  ep-copilot evaluate [--extraction FILE]  screening precision/recall (and extraction accuracy)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import pipeline, reporting, review
from .config import ConfigError, load_topic
from .http import FetchError
from .storage import Store, StoreError

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ep-copilot", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--topic", default="af-ablation")
    p.add_argument("--config", type=Path, help="Topic config (default: config/topics.yaml)")
    p.add_argument("--db", type=Path, help="SQLite database (default: data/ep_copilot.sqlite; "
                                           "offline fixtures use data/ep_copilot_fixtures.sqlite)")
    p.add_argument("--out", type=Path, default=Path("output"))
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("run", "fetch"):
        s = sub.add_parser(name)
        s.add_argument("--days", type=int, help="Search the last N days (default: since last run, else 30)")
        s.add_argument("--offline", action="store_true", help="Use bundled SYNTHETIC fixtures, no network")
        s.add_argument("--fixtures", type=Path, nargs="?", const=FIXTURES / "snapshot_run1",
                       help="Fixture snapshot folder for --offline")
        s.add_argument("--snapshot", type=Path, help="Import a pre-captured snapshot folder (snapshot.json)")
    r = sub.add_parser("report")
    r.add_argument("--run-id", type=int)
    sub.add_parser("screen")
    sub.add_parser("validate")
    i = sub.add_parser("import-reviews")
    i.add_argument("file", type=Path)
    e = sub.add_parser("evaluate")
    e.add_argument("--extraction", type=Path, help="Filled-in evidence_quotes.csv to score extraction accuracy")
    return p


def _db_path(args) -> Path:
    if args.db:
        return args.db
    offline = getattr(args, "offline", False)
    return Path("data") / ("ep_copilot_fixtures.sqlite" if offline else "ep_copilot.sqlite")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        topic = load_topic(args.topic, args.config)
        store = Store(_db_path(args))
        if args.command in ("run", "fetch"):
            snapshot, mode = None, "live"
            if args.offline:
                snapshot, mode = args.fixtures or FIXTURES / "snapshot_run1", "offline-fixture"
            elif args.snapshot:
                snapshot, mode = args.snapshot, "imported"
            result = pipeline.run(store, topic, days=args.days, snapshot=snapshot, mode=mode)
            if result.synthetic:
                print("WARNING: SYNTHETIC TEST DATA - not real publications or trials.")
            print(f"Run #{result.run_id}: {len(result.screenings)} unique PubMed records "
                  f"({len(result.new_pmids)} new, {len(result.updated_pmids)} updated, "
                  f"{len(result.duplicate_pmids)} duplicate(s) removed), "
                  f"{len(result.fetch.trials)} trials ({len(result.new_trials)} new, "
                  f"{len({c['nct_id'] for c in result.trial_changes})} changed)")
            if args.command == "run":
                paths = reporting.write_outputs(result, store, args.out)
                print(f"Digest: {paths['digest']}")
        elif args.command in ("report", "screen"):
            result = pipeline.load_result(store, topic, getattr(args, "run_id", None),
                                          rescreen=args.command == "screen")
            paths = reporting.write_outputs(result, store, args.out)
            print(f"Digest: {paths['digest']}")
        elif args.command == "validate":
            counts = store.counts(topic.key)
            last = store.last_successful_run(topic.key)
            print(json.dumps({"database": str(store.path), "synthetic": store.is_synthetic(), **counts,
                              "last_successful_run": dict(last) if last else None}, indent=2, default=str))
            bad = store.db.execute("SELECT COUNT(*) FROM articles WHERE pmid NOT GLOB '[0-9]*'").fetchone()[0]
            bad += store.db.execute("SELECT COUNT(*) FROM trials WHERE nct_id NOT GLOB 'NCT[0-9]*'").fetchone()[0]
            if bad:
                print(f"{bad} record(s) with invalid identifiers", file=sys.stderr)
                return 1
        elif args.command == "import-reviews":
            n, problems = review.import_decisions(store, topic.key, args.file)
            print(f"Imported {n} reviewer decision(s).")
            for p in problems:
                print(f"  skipped {p}", file=sys.stderr)
        elif args.command == "evaluate":
            out = {"screening": review.evaluate(store, topic.key)}
            if args.extraction:
                out["extraction"] = review.extraction_accuracy(args.extraction)
            print(json.dumps(out, indent=2))
        return 0
    except (ConfigError, StoreError, FetchError, ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
