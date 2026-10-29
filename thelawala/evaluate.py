"""Reproducible curated assertions and a chronologically held-out log proxy."""

from collections import defaultdict
from datetime import date, datetime
import json
from pathlib import Path
import platform
from statistics import median
from time import perf_counter

from .query import ROOT
from .search import SearchEngine


def case_errors(engine, case: dict, response: dict) -> list[str]:
    hits = response["results"]
    errors = []
    if case.get("empty"):
        return ["Expected no results"] if hits else []
    if not hits:
        return ["Expected at least one result"]
    types = case.get("top_types", [case["top_type"]] if "top_type" in case else None)
    if types and engine.products[hits[0]["sku_id"]].product_type not in types:
        errors.append(f"Wrong first product type: {engine.products[hits[0]['sku_id']].product_type}")
    for hit in hits:
        product = engine.products[hit["sku_id"]]
        if not product.available:
            errors.append("Unavailable SKU in purchasable results")
        if "brand" in case and hit["brand"] != case["brand"]:
            errors.append("Wrong brand")
        if "category" in case and hit["category"] != case["category"]:
            errors.append("Wrong category")
        if "max_price" in case and (hit["price"] is None or hit["price"] > case["max_price"]
                or (not case.get("inclusive") and hit["price"] == case["max_price"])):
            errors.append("Maximum price violated")
        if "min_price" in case and (hit["price"] is None or hit["price"] < case["min_price"]):
            errors.append("Minimum price violated")
        if "quantity" in case and (product.quantity != case["quantity"] or product.unit != case["unit"]):
            errors.append("Wrong pack size")
    if case.get("cheap") and [h["price"] for h in hits] != sorted(h["price"] for h in hits):
        errors.append("Prices not ascending")
    return errors


def _fingerprint(product):
    return product.brand, tuple(sorted(product.terms)), product.quantity, product.unit


def evaluate(data_dir: Path, as_of: date) -> dict:
    cutoff = date(2026, 10, 1)
    start = perf_counter()
    engine = SearchEngine(data_dir, as_of, log_cutoff=cutoff)
    startup_ms = (perf_counter()-start)*1000
    cases = json.loads((ROOT/"evaluation/cases.json").read_text(encoding="utf-8"))
    failures = []
    for case in cases:
        response = engine.search(case["query"])
        errors = case_errors(engine, case, response)
        if errors:
            failures.append({"query": case["query"], "errors": errors})
    lexical = SearchEngine(data_dir, as_of, use_logs=False)
    rows = [json.loads(line) for line in (Path(data_dir)/"search_log.jsonl").read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    train_sessions = {r["session_id"] for r in rows if datetime.fromisoformat(r["ts"]).date() < cutoff}
    positives = defaultdict(set)
    excluded_crossing = set()
    for row in rows:
        timestamp = datetime.fromisoformat(row["ts"]).date()
        if not cutoff <= timestamp < as_of:
            continue
        if row["session_id"] in train_sessions:
            excluded_crossing.add(row["session_id"])
            continue
        for event in row["events"]:
            # Search-origin and browse-recovery are both positives here, but
            # only actual cart additions count. No sponsored positives.
            if event["action"] != "add_to_cart" or event["sponsored"]:
                continue
            if event["source"] == "browse" and row["results_count"] != 0:
                continue
            product = engine.products.get(event["sku_id"])
            if product and product.available:
                positives[row["query"]].add(_fingerprint(product))
    metrics = {}
    for name, candidate_engine in [("lexical_only", lexical), ("with_training_logs", engine), ("literal_substring", None)]:
        reciprocal, hit_count = 0.0, 0
        for query, relevant in positives.items():
            if candidate_engine:
                skus = [p["sku_id"] for p in candidate_engine.search(query)["results"]]
            else:
                skus = sorted(p.sku_id for p in engine.products.values()
                              if p.available and query.strip() and query.strip().casefold() in p.name.casefold())[:10]
            rank = next((n for n, sku in enumerate(skus, 1) if _fingerprint(engine.products[sku]) in relevant), None)
            if rank:
                hit_count += 1
                reciprocal += 1/rank
        count = len(positives)
        metrics[name] = {"hit_rate_at_10": round(hit_count/count, 4) if count else None,
                         "mrr_at_10": round(reciprocal/count, 4) if count else None}
    # Cold query parsing + retrieval, followed by an identical warm pass. No
    # complete result cache is used; only normalization/parser caches exist.
    latency_engine = SearchEngine(data_dir, as_of, use_logs=False)
    queries = list(dict.fromkeys(row["query"] for row in rows))
    timings = {}
    for label in ("first_pass", "warm_pass"):
        durations = []
        for query in queries:
            start = perf_counter()
            latency_engine.search(query)
            durations.append((perf_counter()-start)*1000)
        durations.sort()
        timings[label] = {"p50_ms": round(median(durations), 3),
                          "p95_ms": round(durations[int((len(durations)-1)*0.95)], 3),
                          "max_ms": round(max(durations), 3), "queries": len(durations)}
    return {
        "environment": {"python": platform.python_version(), "platform": platform.system(),
                        "processor": platform.processor()},
        "as_of": as_of.isoformat(), "startup_ms": round(startup_ms, 2),
        "curated": {"total": len(cases), "passed": len(cases)-len(failures), "failed": len(failures), "failures": failures},
        "temporal_proxy": {
            "train_before": cutoff.isoformat(), "test_from": cutoff.isoformat(),
            "test_before": as_of.isoformat(), "unique_raw_queries_with_eligible_cart_positives": len(positives),
            "cross_boundary_sessions_excluded": len(excluded_crossing), "metrics": metrics,
            "limitations": [
                "Implicit cart labels reflect the old search system, not complete relevance judgments.",
                "Eligibility uses current inventory; no historical inventory snapshots exist.",
                "Queries are equally weighted; normalized duplicate SKU identities count as equivalent.",
                "Curated cases were authored during development and are regression checks, not blind evaluation.",
                "Literal substring is an intentionally simple baseline without query interpretation.",
            ],
        },
        "latency": timings,
    }
