"""Command line: run the demo app, evaluate rewritten instructions, run the benchmark.

  teachback serve [--host 127.0.0.1] [--port 8000]
  teachback evaluate PLAN_ID ITEM_ID FILE [--language en|es|non-en]
  teachback benchmark
  teachback check-content
  teachback evaluate-set eval/dev_set.json [--show-misses]
  teachback gate drafts.json [--html report.html]       # safety gate for AI-drafted text; exit 1 if any held
  teachback insights [attempts.json] [--csv f] [--html f]  # most-misunderstood instructions by HCAHPS domain
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
    s.add_argument("--theme", help="Optional theme from static/themes/ (portal, high-contrast, or your own)")
    e = sub.add_parser("evaluate", help="Check a rewritten instruction against the plan")
    e.add_argument("plan_id")
    e.add_argument("item_id")
    e.add_argument("file", type=Path, help="Text file with the rewritten instruction ('-' for stdin)")
    e.add_argument("--language", choices=["en", "es", "non-en"])
    sub.add_parser("benchmark", help="Run the evaluator on the synthetic benchmark")
    sub.add_parser("check-content", help="Validate bundled plans and education library")
    g = sub.add_parser("gate", help="Safety gate: check a batch of AI-drafted (or any rewritten) instructions")
    g.add_argument("file", type=Path, help='JSON: {"drafts": [{"id", "plan", "item", "text", "language"}]}')
    g.add_argument("--html", type=Path, help="Also write a readable HTML report")
    ins = sub.add_parser("insights", help="Which instructions are misunderstood most, mapped to HCAHPS domains")
    ins.add_argument("file", type=Path, nargs="?", help='JSON: {"attempts": [...]} (default: bundled synthetic cohort)')
    ins.add_argument("--csv", type=Path, help="Write a CSV the Quality Signal Monitor can read")
    ins.add_argument("--html", type=Path, help="Write an HTML report")
    es = sub.add_parser("evaluate-set", help="Score the checks against a labelled evaluation set")
    es.add_argument("file", type=Path)
    es.add_argument("--show-misses", action="store_true")
    args = p.parse_args(argv)

    from .plans import ContentError, load_plans
    try:
        if args.command == "serve":
            import uvicorn

            from .app import create_app
            if args.theme:
                import os
                os.environ["TEACHBACK_THEME"] = args.theme
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
        elif args.command == "gate":
            from . import gate
            r = gate.run_file(args.file)
            if args.html:
                args.html.write_text(gate.to_html(r), encoding="utf-8")
            print(json.dumps(r, indent=2, ensure_ascii=False))
            return 1 if r["held"] else 0
        elif args.command == "insights":
            from . import insights
            synthetic = args.file is None
            attempts = insights.bundled_cohort() if synthetic else json.loads(args.file.read_text(encoding="utf-8"))["attempts"]
            r = insights.run(attempts)
            if args.csv:
                insights.write_csv(r, args.csv, synthetic=synthetic)
            if args.html:
                args.html.write_text(insights.to_html(r, synthetic=synthetic), encoding="utf-8")
            print(json.dumps({k: r[k] for k in ("attempts", "domains", "note")}, indent=2, ensure_ascii=False))
        elif args.command == "evaluate-set":
            from .evaluation import score
            r = score(args.file)
            summary = {k: r[k] for k in ("teachback", "fidelity", "safety", "safety_net")}
            print(json.dumps(summary, indent=2))
            if args.show_misses:
                print(json.dumps({"misses": r["misses"], "false_alarms": r["false_alarms"]}, indent=2, ensure_ascii=False))
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
