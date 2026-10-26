"""Command line: run the demo app, evaluate rewritten instructions, run the benchmark.

  teachback serve [--host 127.0.0.1] [--port 8000]
  teachback evaluate PLAN_ID ITEM_ID FILE [--language en|es|non-en]
  teachback benchmark
  teachback check-content
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="teachback", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("serve")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--db", type=Path, default=Path("data/demo.sqlite"))
    e = sub.add_parser("evaluate", help="Check a rewritten instruction against the plan")
    e.add_argument("plan_id")
    e.add_argument("item_id")
    e.add_argument("file", type=Path, help="Text file with the rewritten instruction ('-' for stdin)")
    e.add_argument("--language", choices=["en", "es", "non-en"])
    sub.add_parser("benchmark", help="Run the evaluator on the synthetic benchmark")
    sub.add_parser("check-content", help="Validate bundled plans and education library")
    args = p.parse_args(argv)

    from .plans import ContentError, load_plans
    try:
        if args.command == "serve":
            import uvicorn
            from .app import create_app
            if args.host not in ("127.0.0.1", "localhost"):
                print("WARNING: serving beyond this computer. This is a synthetic-data demo with no login.",
                      file=sys.stderr)
            uvicorn.run(create_app(args.db), host=args.host, port=args.port)
        elif args.command == "evaluate":
            from .fidelity import evaluate_item
            plans = load_plans()
            if args.plan_id not in plans:
                print(f"Unknown plan. Choose from: {', '.join(plans)}", file=sys.stderr)
                return 2
            plan = plans[args.plan_id]
            candidate = sys.stdin.read() if str(args.file) == "-" else args.file.read_text(encoding="utf-8")
            rep = evaluate_item(plan, plan.item(args.item_id), candidate, args.language)
            print(json.dumps(rep.to_dict(), indent=2, ensure_ascii=False))
            return 1 if rep.counts["critical"] else 0
        elif args.command == "benchmark":
            from .benchmark import run
            r = run()
            print(json.dumps(r, indent=2))
            return 0 if r["detected"] == r["seeded_errors"] and r["false_alarms"] == 0 else 1
        elif args.command == "check-content":
            from . import knowledge
            plans = load_plans()
            lib = knowledge.library()
            print(f"OK: {len(plans)} synthetic plans, {len(lib['topics'])} education topics, "
                  f"{len(lib['glossary'])} glossary terms")
        return 0
    except (ContentError, KeyError, ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
