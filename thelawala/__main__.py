"""Run with python -m thelawala --help from the repository root."""

import argparse
from datetime import date
import json
from pathlib import Path
import sys

from .batch import run_batch
from .data import DEFAULT_AS_OF, DEFAULT_DATA
from .search import SearchEngine


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Offline Thelawala grocery search")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--as-of", type=date.fromisoformat, default=DEFAULT_AS_OF,
                        help="Reference date, default 2026-10-12 (assignment clock)")
    parser.add_argument("--no-logs", action="store_true", help="Disable behavioral ranking")
    commands = parser.add_subparsers(dest="command", required=True)
    search = commands.add_parser("search", help="Search once, with detailed JSON results")
    search.add_argument("query")
    search.add_argument("--include-unavailable", action="store_true")
    batch = commands.add_parser("batch", help="One query per input line → results.jsonl")
    batch.add_argument("input", type=Path)
    batch.add_argument("--output", type=Path, default=Path("results.jsonl"))
    web = commands.add_parser("serve", help="Open a local search page")
    web.add_argument("--port", type=int, default=8000)
    commands.add_parser("audit", help="Print data quality findings as JSON")
    evaluate = commands.add_parser("evaluate", help="Run curated and temporal evaluation")
    evaluate.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "evaluate":
            from .evaluate import evaluate
            result = evaluate(args.data_dir, args.as_of)
            rendered = json.dumps(result, ensure_ascii=False, indent=2)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(rendered+"\n", encoding="utf-8")
            print(rendered)
            return 0 if result["curated"]["failed"] == 0 else 1
        engine = SearchEngine(args.data_dir, args.as_of, use_logs=not args.no_logs)
        if args.command == "search":
            print(json.dumps(engine.search(args.query, include_unavailable=args.include_unavailable),
                             ensure_ascii=False, indent=2))
        elif args.command == "batch":
            count = run_batch(engine, args.input, args.output)
            print(f"Wrote {count} queries to {args.output}")
        elif args.command == "audit":
            print(json.dumps(engine.audit, ensure_ascii=False, indent=2))
        elif args.command == "serve":
            from .web import serve
            serve(engine, args.port)
    except (ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
