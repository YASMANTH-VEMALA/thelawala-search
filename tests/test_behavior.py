"""Synthetic signals make bias handling independently verifiable."""

from datetime import date
import json
from pathlib import Path
import tempfile
import unittest

from thelawala.behavior import Behavior
from thelawala.query import Normalizer, QueryParser


class BehaviorTests(unittest.TestCase):
    def test_sponsored_cutoff_unknown_skus_and_cart_weight(self):
        parser = QueryParser(Normalizer(), {"Test Brand"}, {"milk"})
        def event(sku, action="click", sponsored=False):
            return {"sku_id": sku, "action": action, "source": "search", "position": 1, "sponsored": sponsored}
        rows = [
            {"ts": "2026-09-30T12:00:00+05:30", "session_id": "a", "query": "milk", "results_count": 4,
             "events": [event("A"), event("B", "add_to_cart"), event("C", sponsored=True), event("unknown")]},
            {"ts": "2026-10-01T12:00:00+05:30", "session_id": "b", "query": "milk", "results_count": 1,
             "events": [event("C", "add_to_cart")]},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"log.jsonl"
            path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
            behavior = Behavior()
            behavior.load(path, parser, {"A", "B", "C"}, date(2026, 10, 1))
            query = parser.parse("milk")
            self.assertGreater(behavior.boost(query, "B"), behavior.boost(query, "A"))
            self.assertEqual(0, behavior.boost(query, "C"))
            self.assertEqual(0, behavior.boost(query, "unknown"))
            self.assertEqual(1, behavior.report["excluded_by_cutoff"])
            self.assertLessEqual(behavior.boost(query, "B"), 0.35)
