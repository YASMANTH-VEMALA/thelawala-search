"""Small query-specific preference signal, never a replacement for relevance."""

from collections import Counter, defaultdict
from datetime import date, datetime
import json
import math
from pathlib import Path

from .query import QueryParser


class Behavior:
    def __init__(self):
        self.weights: dict[str, Counter] = defaultdict(Counter)
        self.report: dict = {}

    def load(self, path: Path, parser: QueryParser, catalog_ids: set[str], cutoff: date) -> None:
        counts = Counter()
        queries = set()
        sessions = set()
        first = last = None
        with path.open(encoding="utf-8-sig") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                    timestamp = datetime.fromisoformat(row["ts"])
                    query = row["query"]
                    if not isinstance(query, str) or not isinstance(row["events"], list):
                        raise ValueError("invalid query or events")
                    if timestamp.date() >= cutoff:
                        counts["excluded_by_cutoff"] += 1
                        continue
                    counts["searches"] += 1
                    counts["zero_results"] += row["results_count"] == 0
                    queries.add(query)
                    sessions.add(row["session_id"])
                    first = min(first, row["ts"]) if first else row["ts"]
                    last = max(last, row["ts"]) if last else row["ts"]
                    parsed = parser.parse(query, fuzzy=False)
                    key = self.key(parsed)
                    seen = set()
                    for event in row["events"]:
                        counts["events"] += 1
                        if event["sponsored"]:
                            counts["sponsored_events_ignored"] += 1
                            continue
                        if event["sku_id"] not in catalog_ids:
                            counts["unknown_sku_events_ignored"] += 1
                            continue
                        if event["action"] not in {"click", "add_to_cart"} or event["source"] not in {"search", "browse"}:
                            counts["unsupported_events_ignored"] += 1
                            continue
                        identity = (event["sku_id"], event["action"])
                        if identity in seen:
                            continue
                        seen.add(identity)
                        value = 1.0 if event["action"] == "click" else 3.0
                        if event["source"] == "browse":
                            # Browse is weak evidence, especially if search succeeded.
                            value *= 0.5 if row["results_count"] == 0 else 0.15
                        position = event["position"]
                        if event["source"] == "search" and isinstance(position, int) and position > 1:
                            # Modest, capped adjustment; no exposure data is available
                            # for a defensible inverse-propensity estimator.
                            value *= min(1.3, 1 + 0.025*(position-1))
                        age = max(0, (cutoff-timestamp.date()).days)
                        value *= 0.5**(age/45)
                        self.weights[key][event["sku_id"]] += value
                except (KeyError, TypeError, ValueError) as error:
                    raise ValueError(f"search_log.jsonl:{line_number}: {error}") from error
        self.report = {**counts, "unique_raw_queries": len(queries), "sessions": len(sessions),
                       "first_timestamp": first, "last_timestamp": last,
                       "training_cutoff_exclusive": cutoff.isoformat()}

    @staticmethod
    def key(query) -> str:
        return " ".join(sorted(query.terms)) + "|" + (query.brand or "")

    def boost(self, query, sku_id: str) -> float:
        value = self.weights.get(self.key(query), {}).get(sku_id, 0)
        # This can move near-ties, but cannot overcome an intent tier.
        return min(0.35, math.log1p(value)*0.08)
