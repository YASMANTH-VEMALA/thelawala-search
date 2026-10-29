"""Inverted retrieval, explicit constraints, intent tiers, bounded reranking."""

from collections import defaultdict
from datetime import date
import math
from pathlib import Path

from .behavior import Behavior
from .data import DEFAULT_AS_OF, DEFAULT_DATA, load_products, product_type
from .models import Hit, Query
from .query import Normalizer, QueryParser


class SearchEngine:
    def __init__(self, data_dir: Path = DEFAULT_DATA, as_of: date = DEFAULT_AS_OF,
                 *, use_logs: bool = True, log_cutoff: date | None = None):
        self.as_of = as_of
        self.normalizer = Normalizer()
        products, self.audit = load_products(Path(data_dir), self.normalizer)
        self.products = {p.sku_id: p for p in products}
        self.postings: dict[str, set[str]] = defaultdict(set)
        self.brand_postings: dict[str, set[str]] = defaultdict(set)
        for product in products:
            for token in set(product.terms):
                self.postings[token].add(product.sku_id)
            self.brand_postings[product.brand].add(product.sku_id)
        self.parser = QueryParser(self.normalizer, {p.brand for p in products}, set(self.postings))
        self.behavior = Behavior()
        if use_logs:
            cutoff = min(log_cutoff or as_of, as_of)
            self.behavior.load(Path(data_dir)/"search_log.jsonl", self.parser, set(self.products), cutoff)
        self.audit["logs"] = self.behavior.report
        self.audit["as_of"] = as_of.isoformat()
        inventory = self.audit.pop("inventory_records")
        self.audit["expired_restock_estimates"] = [r["sku_id"] for r in inventory
            if r["restock_eta"] and date.fromisoformat(r["restock_eta"]) < as_of]

    def _candidates(self, query: Query) -> set[str]:
        sets = [self.postings.get(token, set()) for token in set(query.terms)]
        if query.brand:
            sets.append(self.brand_postings[query.brand])
        if not sets:
            return set()
        sets.sort(key=len)
        candidates = sets[0].copy()
        for posting in sets[1:]:
            candidates.intersection_update(posting)
        return candidates

    @staticmethod
    def _constraints(product, query: Query) -> bool:
        if product.status == "discontinued":
            return False
        if query.quantity is not None and (product.quantity != query.quantity or product.unit != query.unit):
            return False
        if (query.min_price is not None or query.max_price is not None or query.cheap) and product.price_issue:
            return False
        if query.max_price is not None:
            if product.price > query.max_price or (product.price == query.max_price and not query.max_inclusive):
                return False
        if query.min_price is not None:
            if product.price < query.min_price or (product.price == query.min_price and not query.min_inclusive):
                return False
        return True

    def _rank(self, product, query: Query) -> tuple[int, Hit]:
        phrase = " ".join(query.terms)
        text = " ".join(product.terms)
        intent = product_type(query.terms)
        # Generic ingredient terms should prefer the product itself. Otherwise
        # "onion" could lead with onion-flavoured chips and "oil" with face wash.
        preferred = {
            "milk": {"milk"}, "butter": {"butter", "unsalted butter"},
            "sugar": {"sugar"}, "salt": {"iodised salt"},
            "oil": {"sunflower oil", "groundnut oil", "mustard oil", "rice bran oil", "coconut oil", "gingelly oil"},
            "coconut oil": {"coconut oil"},
            "tomato": {"tomato"}, "onion": {"onion"}, "potato": {"potato"},
            "garlic": {"garlic"}, "banana": {"banana"}, "mango": {"mango"},
            "apple": {"apple"}, "coconut": {"coconut"}, "chilli": {"green chilli"},
            "sugar free": {"sugar free sweetener"},
        }
        desired = preferred.get(phrase, {intent})
        tier = 0 if not query.terms or product.product_type in desired else 1
        reasons = ["All query terms matched" if query.terms else "Requested brand matched"]
        if tier == 0:
            reasons.append("Primary product intent matched")
        if query.brand:
            reasons.append("Requested brand matched")
        n = len(self.products)
        lexical = sum(math.log(1 + (n-len(self.postings[t])+0.5)/(len(self.postings[t])+0.5))
                      for t in set(query.terms))
        # Length normalization rewards exact identities over ingredient mentions.
        score = lexical / (1 + 0.12*max(0, len(product.terms)-len(query.terms)))
        if phrase and (" " + phrase + " ") in (" " + text + " "):
            score += 1
            reasons.append("Query phrase matched")
        behavior = self.behavior.boost(query, product.sku_id)
        if behavior:
            score += behavior
            reasons.append("Small preference from non-sponsored customer activity")
        if not query.brand and product.brand == "Thela Select":
            score += 0.04
            reasons.append("Small own-label tie-break")
        if query.quantity is not None:
            reasons.append("Requested pack size matched")
        if query.max_price is not None or query.min_price is not None:
            reasons.append("Price constraint satisfied")
        if query.cheap:
            reasons.append("Sorted by total pack price within product intent")
        return tier, Hit(product, score, reasons)

    def search(self, text: str, limit: int = 10, *, include_unavailable: bool = False) -> dict:
        if not isinstance(text, str) or len(text) > 500:
            raise ValueError("Query must be text of at most 500 characters")
        if not 1 <= limit <= 10:
            raise ValueError("Limit must be between 1 and 10")
        query = self.parser.parse(text)
        ranked = []
        for sku in self._candidates(query):
            product = self.products[sku]
            if self._constraints(product, query):
                tier, hit = self._rank(product, query)
                if tier and query.normalized in {
                    "milk", "butter", "sugar", "salt", "oil", "coconut oil", "tomato", "onion",
                    "potato", "garlic", "banana", "mango", "apple", "coconut", "chilli",
                }:
                    # An unavailable onion is not a reason to sell onion chips.
                    continue
                price_order = product.price if query.cheap else 0
                ranked.append(((tier, price_order, -hit.score, product.sku_id), hit))
        ranked.sort(key=lambda pair: pair[0])
        available, unavailable = [], []
        seen = set()
        for _, hit in ranked:
            product = hit.product
            # Missing/zero inventory can never displace an available duplicate.
            if not product.available and not include_unavailable:
                continue
            fingerprint = (product.brand, tuple(sorted(product.terms)), product.quantity, product.unit)
            # Deduplicate each section independently; SKU records are retained in
            # the data model so stock is never combined across distinct IDs.
            key = (product.available, fingerprint)
            if key in seen:
                continue
            seen.add(key)
            target = available if product.available else unavailable
            if len(target) < limit:
                target.append(hit.as_dict(self.as_of))
        return {
            "query": text, "interpreted_query": query.normalized,
            "brand": query.brand,
            "corrections": [{"from": a, "to": b} for a, b in query.corrections],
            "constraints": {
                "max_price": float(query.max_price) if query.max_price is not None else None,
                "min_price": float(query.min_price) if query.min_price is not None else None,
                "max_inclusive": query.max_inclusive, "min_inclusive": query.min_inclusive,
                "quantity": float(query.quantity) if query.quantity is not None else None,
                "unit": query.unit, "cheap": query.cheap,
            },
            "warnings": list(query.warnings), "results": available,
            "unavailable": unavailable if include_unavailable else [],
            "as_of": self.as_of.isoformat(),
        }
