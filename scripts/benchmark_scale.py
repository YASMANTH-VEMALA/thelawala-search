"""Synthetic scale smoke test; not evidence of real 20k-product relevance.

Run: python scripts/benchmark_scale.py --products 20000
"""

import argparse
import csv
import json
from pathlib import Path
import shutil
from statistics import median
import sys
import tempfile
from time import perf_counter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from thelawala.data import DEFAULT_DATA  # noqa: E402
from thelawala.search import SearchEngine  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--products", type=int, default=20000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.products < 1102:
        parser.error("Use at least 1102 products")
    with (DEFAULT_DATA/"catalog.csv").open(encoding="utf-8-sig", newline="") as handle:
        catalog = list(csv.DictReader(handle))
    with (DEFAULT_DATA/"inventory.csv").open(encoding="utf-8-sig", newline="") as handle:
        stock_rows = list(csv.DictReader(handle))
    stock = {r["sku_id"]: r for r in stock_rows}
    expanded_catalog, expanded_stock = [], []
    for number in range(args.products):
        row = catalog[number % len(catalog)].copy()
        original_id = row["sku_id"]
        if number >= len(catalog):
            row["sku_id"] = f"SYNTH{number:06d}"
        expanded_catalog.append(row)
        if original_id in stock:
            inv = stock[original_id].copy()
            inv["sku_id"] = row["sku_id"]
            expanded_stock.append(inv)
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory)
        for name, rows in [("catalog.csv", expanded_catalog), ("inventory.csv", expanded_stock)]:
            with (target/name).open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
        shutil.copyfile(DEFAULT_DATA/"search_log.jsonl", target/"search_log.jsonl")
        start = perf_counter()
        engine = SearchEngine(target)
        startup = (perf_counter()-start)*1000
        queries = [case["query"] for case in json.loads((ROOT/"evaluation/cases.json").read_text(encoding="utf-8"))]
        timings = []
        for _ in range(3):
            for query in queries:
                start = perf_counter()
                engine.search(query)
                timings.append((perf_counter()-start)*1000)
        timings.sort()
        result = {
            "products": len(engine.products), "queries": len(timings),
            "startup_ms": round(startup, 2), "p50_ms": round(median(timings), 3),
            "p95_ms": round(timings[int((len(timings)-1)*0.95)], 3), "max_ms": round(max(timings), 3),
            "limitations": "Synthetic repetition of the 1102-product vocabulary; measures candidate-volume scaling, not vocabulary growth, concurrent load, memory use or relevance on a real 20k catalog.",
        }
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered+"\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
