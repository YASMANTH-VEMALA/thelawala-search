"""Parse intent and hard constraints without a network or language model."""

from collections import defaultdict
from decimal import Decimal
from difflib import SequenceMatcher
from functools import lru_cache
import json
from pathlib import Path
import re

from .models import Query
from .text import normalize, replace_phrases

ROOT = Path(__file__).resolve().parent.parent

# Catalog errors are normalized at index build time too. These are linguistic
# repairs, not a table mapping evaluation queries to product IDs.
REPAIRS = {
    "tonned": "toned", "choclate": "chocolate", "biscuts": "biscuit",
    "corriander": "coriander", "turmaric": "turmeric", "ltremon": "lemon",
    "basmathi": "basmati", "sona masuri": "sona masoori",
}
UNITS = {
    "gram": (Decimal(1), "g"), "kilogram": (Decimal(1000), "g"),
    "millilitre": (Decimal(1), "ml"), "litre": (Decimal(1000), "ml"),
    "piece": (Decimal(1), "pcs"),
}
SIZE = re.compile(r"\b(\d+(?:\.\d+)?)\s+(gram|kilogram|millilitre|litre|piece)\b")
STOP_WORDS = {"a", "an", "the", "please", "some", "of", "pack", "new"}


class Normalizer:
    def __init__(self, path: Path | None = None):
        groups = json.loads((path or ROOT / "config/synonyms.json").read_text(encoding="utf-8"))
        self.aliases = {normalize(alias): normalize(target)
                        for target, aliases in groups.items() for alias in aliases}
        self.aliases.update(REPAIRS)
        # Yogurt can mean curd locally, but preserve the distinct Greek product.
        self.aliases["greek yogurt"] = "greek yogurt"

    @lru_cache(maxsize=8192)
    def canonical(self, value: str) -> str:
        text = normalize(value)
        return replace_phrases(text, self.aliases)

    def size(self, value: str) -> tuple[Decimal | None, str | None]:
        text = self.canonical(value)
        match = SIZE.search(text)
        if match:
            factor, unit = UNITS[match[2]]
            return Decimal(match[1]) * factor, unit
        match = re.fullmatch(r"pack of (\d+)", text)
        return (Decimal(match[1]), "pcs") if match else (None, None)

    def product_terms(self, name: str, brand: str) -> tuple[str, ...]:
        text = self.canonical(name)
        text = replace_phrases(text, {self.canonical(brand): ""})
        text = SIZE.sub(" ", text)
        return tuple(t for t in text.split() if t not in STOP_WORDS and not t.isnumeric())


class QueryParser:
    def __init__(self, normalizer: Normalizer, brands: set[str], vocabulary: set[str]):
        self.normalizer = normalizer
        self.brands = {normalizer.canonical(b): b for b in sorted(brands)}
        self.brand_tokens = set(" ".join(self.brands).split())
        self.vocabulary = vocabulary | self.brand_tokens | set(UNITS)
        self.by_length: dict[int, list[str]] = defaultdict(list)
        for token in sorted(self.vocabulary):
            self.by_length[len(token)].append(token)
        self.correction_cache: dict[str, str] = {}

    def correct(self, token: str) -> str:
        if token in self.vocabulary or len(token) < 3 or token.isnumeric():
            return token
        if token in self.correction_cache:
            return self.correction_cache[token]
        # Limit distance and only repair unknown tokens. Known "salted" must
        # never be fuzzily changed into "unsalted".
        candidates = [t for n in range(len(token)-1, len(token)+2)
                      for t in self.by_length.get(n, [])]
        scored = sorted(((SequenceMatcher(None, token, t).ratio(), t) for t in candidates),
                        key=lambda pair: (-pair[0], pair[1]))
        cutoff = 0.78 if len(token) >= 5 else 0.74
        best = scored[0] if scored else (0, token)
        # Ambiguous guesses should produce no match instead of a random product.
        if best[0] >= cutoff and (len(scored) == 1 or best[0]-scored[1][0] >= 0.025):
            result = best[1]
        else:
            result = token
        self.correction_cache[token] = result
        return result

    @lru_cache(maxsize=8192)
    def parse(self, original: str, *, fuzzy: bool = True) -> Query:
        text = self.normalizer.canonical(original)
        # Currency symbols were removed by normalization. Currency words are
        # optional before/after the amount, but only inside a price expression.
        currency = r"(?:rs\s*|inr\s*|rupees\s*)?"
        max_price = min_price = None
        max_inclusive = min_inclusive = False
        warnings: list[str] = []
        between = re.search(r"\bbetween\s+"+currency+r"(\d+(?:\.\d+)?)\s+(?:and|to)\s+"+currency+r"(\d+(?:\.\d+)?)", text)
        if between:
            min_price, max_price = Decimal(between[1]), Decimal(between[2])
            min_inclusive = max_inclusive = True
            text = text[:between.start()] + " " + text[between.end():]
        bounds = r"\b(under|below|less than|up to|upto|at most|above|over|more than|at least)\s+"+currency+r"(\d+(?:\.\d+)?)\s*(?:rupees|rs|inr)?\b"
        for match in re.finditer(bounds, text):
            op, value = match[1], Decimal(match[2])
            if op in {"under", "below", "less than", "up to", "upto", "at most"}:
                inclusive = op in {"up to", "upto", "at most"}
                if max_price is None or value < max_price:
                    max_price, max_inclusive = value, inclusive
                elif value == max_price:
                    max_inclusive = max_inclusive and inclusive
            else:
                inclusive = op == "at least"
                if min_price is None or value > min_price:
                    min_price, min_inclusive = value, inclusive
                elif value == min_price:
                    min_inclusive = min_inclusive and inclusive
        text = re.sub(bounds, " ", text)
        cheap = bool(re.search(r"\b(cheap|cheapest|budget|affordable)\b", text))
        text = re.sub(r"\b(cheap|cheapest|budget|affordable)\b", " ", text)
        corrections = []
        corrected = []
        for term in text.split():
            replacement = self.correct(term) if fuzzy else term
            if replacement != term:
                corrections.append((term, replacement))
            corrected.append(replacement)
        # Re-apply aliases after typo repair (e.g. corrupted regional names).
        text = self.normalizer.canonical(" ".join(corrected))
        brand_matches = [b for b in self.brands if re.search(r"(?<!\w)"+re.escape(b)+r"(?!\w)", text)]
        brand = self.brands[max(brand_matches, key=len)] if brand_matches else None
        if brand:
            text = replace_phrases(text, {self.normalizer.canonical(brand): ""})
        else:
            # Unique partial brands: "godavari milk", "banjara".
            pieces = [t for t in text.split() if t in self.brand_tokens]
            possible = [b for b in self.brands if pieces and set(pieces) <= set(b.split())]
            if len(possible) == 1:
                brand = self.brands[possible[0]]
                text = " ".join(t for t in text.split() if t not in pieces)
        quantity, unit = self.normalizer.size(text)
        text = SIZE.sub(" ", text)
        terms = tuple(t for t in text.split() if t not in STOP_WORDS)
        # Bare pack counts are unambiguous for eggs. "atta 5" remains ambiguous
        # rather than silently interpreting it as price or weight.
        if quantity is None and "egg" in terms:
            counts = [t for t in terms if t.isnumeric()]
            if len(counts) == 1:
                quantity, unit = Decimal(counts[0]), "pcs"
                terms = tuple(t for t in terms if t != counts[0])
        if any(t.isnumeric() for t in terms):
            warnings.append("A number without a unit is ambiguous; specify kg, g, ml, L or pcs.")
        if max_price is not None and min_price is not None and (
            min_price > max_price or (min_price == max_price and not (min_inclusive and max_inclusive))
        ):
            warnings.append("The price range is empty.")
        return Query(original, " ".join(terms), terms, brand, max_price, min_price,
                     max_inclusive, min_inclusive, quantity, unit, cheap,
                     tuple(corrections), tuple(warnings))
