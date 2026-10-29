"""Behavioral regressions and contract tests using the supplied snapshot."""

from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest

from thelawala.batch import run_batch
from thelawala.data import DEFAULT_DATA, load_products, read_csv
from thelawala.evaluate import case_errors
from thelawala.query import Normalizer, ROOT
from thelawala.search import SearchEngine


class SearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = SearchEngine()

    def test_curated_behavior(self):
        for case in json.loads((ROOT/"evaluation/cases.json").read_text(encoding="utf-8")):
            with self.subTest(query=case["query"]):
                self.assertEqual([], case_errors(self.engine, case, self.engine.search(case["query"])))

    def test_milk_never_fills_with_rusk_or_chocolate(self):
        for query in ["milk", "milk under 50", "godavari milk"]:
            hits = self.engine.search(query)["results"]
            self.assertTrue(hits)
            self.assertTrue(all(self.engine.products[h["sku_id"]].product_type == "milk" for h in hits))

    def test_onions_are_unavailable_not_replaced_by_chips(self):
        response = self.engine.search("onion", include_unavailable=True)
        self.assertEqual([], response["results"])
        self.assertTrue(response["unavailable"])
        self.assertTrue(all(self.engine.products[h["sku_id"]].product_type == "onion" for h in response["unavailable"]))
        self.assertTrue(any(h["availability"] == "unknown" for h in response["unavailable"]))

    def test_every_log_query_obeys_inventory_and_constraints(self):
        queries = {json.loads(line)["query"] for line in (DEFAULT_DATA/"search_log.jsonl").read_text(encoding="utf-8").splitlines()}
        for query in queries:
            response = self.engine.search(query, include_unavailable=True)
            with self.subTest(query=query):
                self.assertLessEqual(len(response["results"]), 10)
                self.assertEqual(len(response["results"]), len({h["sku_id"] for h in response["results"]}))
                for hit in response["results"]:
                    p = self.engine.products[hit["sku_id"]]
                    self.assertTrue(p.available)
                    if response["brand"]:
                        self.assertEqual(response["brand"], p.brand)
                    self.assertNotEqual("discontinued", p.status)
                for hit in response["unavailable"]:
                    self.assertFalse(self.engine.products[hit["sku_id"]].available)
                    self.assertNotEqual("discontinued", self.engine.products[hit["sku_id"]].status)

    def test_supplier_price_units_and_flags(self):
        self.assertEqual(Decimal("62.00"), self.engine.products["MF40423"].price)
        self.assertEqual(Decimal("6200"), self.engine.products["MF40423"].raw_price)
        self.assertTrue(self.engine.products["TW99611"].price_issue)
        self.assertTrue(self.engine.products["TW89432"].price_issue)
        self.assertTrue(self.engine.products["TW26791"].price_issue)
        # Flagged apples remain discoverable, with their price withheld.
        apples = self.engine.search("apple")["results"]
        self.assertTrue(any(h["price"] is None for h in apples))
        self.assertTrue(all(h["price"] is not None for h in self.engine.search("apple under 300")["results"]))

    def test_stale_eta_is_not_promised(self):
        candidates = [p for p in self.engine.products.values() if p.restock_eta and p.restock_eta < self.engine.as_of and p.status == "active"]
        self.assertTrue(candidates)
        from thelawala.models import Hit
        hit = Hit(candidates[0], 1).as_dict(self.engine.as_of)
        self.assertIsNone(hit["restock_eta"])
        self.assertTrue(hit["restock_note"])

    def test_unicode_synonyms_preserve_combining_marks(self):
        for query in ["పాలు", "दूध", "paalu", "milk"]:
            self.assertEqual("milk", self.engine.parser.parse(query).normalized)
        self.assertEqual("greek yogurt", self.engine.parser.parse("greek yogurt").normalized)

    def test_price_boundary_is_strict_or_inclusive(self):
        under = self.engine.search("milk under 62")["results"]
        inclusive = self.engine.search("milk up to 62")["results"]
        self.assertTrue(all(h["price"] < 62 for h in under))
        self.assertTrue(any(h["sku_id"] == "MF40423" for h in inclusive))
        self.assertEqual(Decimal("50.5"), self.engine.parser.parse("milk under Rs 50.50").max_price)

    def test_normalized_sizes(self):
        n = Normalizer()
        for value in ["0.5 KG", "500gm", "500G"]:
            self.assertEqual((Decimal(500), "g"), n.size(value))
        self.assertEqual((Decimal(1000), "ml"), n.size("1LTR"))
        self.assertEqual((Decimal(12), "pcs"), n.size("Pack of 12"))

    def test_no_logs_mode(self):
        engine = SearchEngine(use_logs=False)
        self.assertFalse(engine.behavior.weights)
        self.assertTrue(engine.search("milk")["results"])

    def test_duplicate_product_identity_not_repeated(self):
        hits = self.engine.search("rice flour")["results"]
        identities = [(p.brand, tuple(sorted(p.terms)), p.quantity, p.unit)
                      for hit in hits for p in [self.engine.products[hit["sku_id"]]]]
        self.assertEqual(len(identities), len(set(identities)))

    def test_invalid_limits_and_queries(self):
        for limit in [0, 11]:
            with self.assertRaises(ValueError):
                self.engine.search("milk", limit)
        with self.assertRaises(ValueError):
            self.engine.search("x"*501)

    def test_batch_contract_blank_unicode_duplicates_and_atomic_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/"queries.txt"
            output = Path(directory)/"results.jsonl"
            source.write_text("milk\n\nపాలు\nmilk\n", encoding="utf-8-sig")
            self.assertEqual(4, run_batch(self.engine, source, output))
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(["milk", "", "పాలు", "milk"], [r["query"] for r in rows])
            self.assertEqual(rows[0], rows[3])
            for row in rows:
                self.assertEqual({"query", "results"}, set(row))
                self.assertTrue(all(isinstance(sku, str) for sku in row["results"]))
                self.assertLessEqual(len(row["results"]), 10)
            previous = output.read_bytes()
            source.write_text("x"*501, encoding="utf-8")
            with self.assertRaises(ValueError):
                run_batch(self.engine, source, output)
            self.assertEqual(previous, output.read_bytes())
            with self.assertRaises(ValueError):
                run_batch(self.engine, source, source)

    def test_invalid_csv_fails_loudly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"bad.csv"
            path.write_text("sku_id,name\nA,first\nA,second\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                read_csv(path, {"sku_id", "name"})
            with self.assertRaisesRegex(ValueError, "columns"):
                read_csv(path, {"sku_id", "price"})


if __name__ == "__main__":
    unittest.main()
