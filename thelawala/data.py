"""Validated, deterministic ingestion. Supplied CSV files are never rewritten."""

from collections import Counter, defaultdict
import csv
from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import median

from .models import Product
from .query import Normalizer, ROOT

DEFAULT_DATA = ROOT / "thelawala-search-data"
DEFAULT_AS_OF = date(2026, 10, 12)
PRICE_DIVISORS = {"metro_feed": Decimal(100), "thela_direct": Decimal(1), "local_vendor": Decimal(1)}

# Match product identities before generic ingredients. This small taxonomy is
# independent of SKU IDs and automatically applies to new catalog rows.
TYPES = sorted({
    "milk chocolate", "milk powder", "flavoured milk", "peanut butter",
    "sugar free sweetener", "sugar free chocolate", "sugar free biscuit",
    "coconut hair oil", "hair oil", "face wash", "potato chips", "banana chips",
    "cream biscuit", "glucose biscuit", "digestive biscuit", "namkeen mixture",
    "corn flakes", "ice cream", "baby cereal", "baby diaper", "baby wipes",
    "sanitary pads", "toilet cleaner", "floor cleaner", "dishwash liquid",
    "dishwash bar", "detergent powder", "garbage bags", "body lotion",
    "rice flour", "whole wheat atta", "sona masoori rice", "basmati rice",
    "rice bran oil", "sunflower oil", "groundnut oil", "mustard oil",
    "gingelly oil", "coconut oil", "coconut water", "mustard seeds",
    "cumin seeds", "coriander powder", "coriander leaves", "curry leaves",
    "red chilli powder", "turmeric powder", "green chilli", "black pepper",
    "toor dal", "moong dal", "urad dal", "chana dal", "masoor dal",
    "idli rava", "bombay rava", "jain masala", "biryani masala", "garam masala",
    "sambar powder", "tomato ketchup", "gongura pickle", "garlic pickle",
    "mango pickle", "instant noodles", "instant coffee", "filter coffee powder",
    "lemon tea premix", "tea powder", "green tea", "fruit juice", "energy drink",
    "diet cola", "packaged drinking water", "chicken nuggets", "frozen green peas",
    "frozen malabar parotta", "mosquito repellent refill", "unsalted butter",
    "bath soap", "shaving cream", "toothbrush", "toothpaste", "shampoo",
    "greek yogurt", "buttermilk", "paneer", "curd", "butter", "ghee", "khoa",
    "cheese slice", "milk", "egg", "onion", "tomato", "potato", "brinjal",
    "lady finger", "spinach", "bottle gourd", "drumstick", "ginger", "garlic",
    "lemon", "cucumber", "apple", "banana", "mango", "coconut", "jaggery",
    "sugar", "iodised salt", "besan", "maida", "poha", "honey", "oats",
    "bread", "rusk", "pasta", "dark chocolate", "jam", "cola", "agarbatti",
    "camphor", "matchbox", "tamarind",
}, key=lambda phrase: (-len(phrase.split()), -len(phrase), phrase))


def product_type(terms: tuple[str, ...]) -> str:
    text = " " + " ".join(terms) + " "
    matches = [kind for kind in TYPES if " " + kind + " " in text]
    # Multiword identities beat ingredients; equal-length identities prefer
    # their first appearance ("rusk milk" is rusk, not drinking milk).
    return min(matches, key=lambda kind: (-len(kind.split()), text.index(" "+kind+" "), -len(kind))) if matches else " ".join(terms)


def read_csv(path: Path, required: set[str]) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not required <= set(reader.fieldnames or []):
            raise ValueError(f"{path.name}: required columns missing: {sorted(required-set(reader.fieldnames or []))}")
        rows = list(reader)
    ids = [r.get("sku_id") for r in rows]
    if any(not sku for sku in ids) or len(set(ids)) != len(ids):
        raise ValueError(f"{path.name}: empty or duplicate sku_id")
    if any(None in r or any(value is None for value in r.values()) for r in rows):
        raise ValueError(f"{path.name}: malformed CSV row")
    return rows


def load_products(data_dir: Path, normalizer: Normalizer) -> tuple[list[Product], dict]:
    catalog = read_csv(data_dir / "catalog.csv", {
        "sku_id", "name", "brand", "category", "size", "price", "supplier", "description"})
    inventory = read_csv(data_dir / "inventory.csv", {
        "sku_id", "stock_qty", "status", "restock_eta", "updated_at"})
    stock = {row["sku_id"]: row for row in inventory}
    for row in inventory:
        if int(row["stock_qty"]) < 0 or row["status"] not in {"active", "discontinued"}:
            raise ValueError(f"inventory.csv: invalid stock/status for {row['sku_id']}")
        datetime.fromisoformat(row["updated_at"])
        if row["restock_eta"]:
            date.fromisoformat(row["restock_eta"])
    products = []
    for row in catalog:
        try:
            raw = Decimal(row["price"])
        except InvalidOperation as error:
            raise ValueError(f"catalog.csv: invalid price for {row['sku_id']}") from error
        if not raw.is_finite() or raw <= 0:
            raise ValueError(f"catalog.csv: invalid price for {row['sku_id']}")
        supplier = row["supplier"]
        divisor = PRICE_DIVISORS.get(supplier, Decimal(1))
        inv = stock.get(row["sku_id"])
        quantity, unit = normalizer.size(row["size"])
        terms = normalizer.product_terms(row["name"], row["brand"])
        if not terms or not row["brand"].strip() or quantity is None:
            raise ValueError(f"catalog.csv: missing product identity/size for {row['sku_id']}")
        products.append(Product(
            row["sku_id"], " ".join(row["name"].split()), row["brand"], row["category"], row["size"],
            raw, (raw/divisor).quantize(Decimal("0.01")), supplier, row["description"],
            terms, product_type(terms), quantity, unit,
            int(inv["stock_qty"]) if inv else None, inv["status"] if inv else "unknown",
            date.fromisoformat(inv["restock_eta"]) if inv and inv["restock_eta"] else None,
            None if supplier in PRICE_DIVISORS else "Unknown supplier price units; price needs verification",
        ))
    # Compare total pack prices within product type + normalized pack size.
    # Flag extreme deviations, do not guess replacement prices. A factor of 8
    # is deliberately conservative; at least three peers are required.
    groups: dict[tuple, list[Decimal]] = defaultdict(list)
    for product in products:
        groups[(product.product_type, product.quantity, product.unit)].append(product.price)
    flagged = []
    produce_unit_prices = [p.price/p.quantity for p in products
                           if p.category == "Fruits & Vegetables" and p.unit == "g" and p.quantity]
    produce_reference = median(produce_unit_prices) if len(produce_unit_prices) >= 10 else None
    single_soap_prices = [p.price for p in products
                          if p.product_type == "bath soap" and p.unit == "g" and p.quantity == 100]
    for product in products:
        peers = groups[(product.product_type, product.quantity, product.unit)]
        issue = product.price_issue
        if len(peers) >= 3:
            reference = median(peers)
            if product.price > reference*8 or product.price < reference/8:
                issue = "Price differs by more than 8x from comparable packs; verification required"
        # Cross-pack checks catch systematic errors shared by an entire size
        # group. They only flag uncertainty; they do not overwrite the price.
        if (produce_reference and product.category == "Fruits & Vegetables"
                and product.unit == "g" and product.quantity
                and product.price/product.quantity > produce_reference*30):
            issue = "Produce unit price exceeds category median by 30x; verification required"
        if (single_soap_prices and product.product_type == "bath soap" and product.unit == "pcs"
                and product.quantity and product.price/product.quantity < min(single_soap_prices)/4):
            issue = "Soap pack price per piece is below one quarter of a 100 g bar; verification required"
        flagged.append(replace(product, price_issue=issue))
    catalog_ids = {p.sku_id for p in products}
    report = {
        "catalog_rows": len(catalog), "inventory_rows": len(inventory),
        "categories": dict(Counter(p.category for p in products)),
        "brands": len({p.brand for p in products}),
        "missing_descriptions": sum(not p.description for p in products),
        "missing_inventory": sorted(catalog_ids-stock.keys()),
        "orphan_inventory": sorted(stock.keys()-catalog_ids),
        "available_products": sum(p.available for p in products),
        "discontinued_products": sum(p.status == "discontinued" for p in products),
        "out_of_stock_products": sum(p.status == "active" and not p.available for p in products),
        "supplier_price_divisors": {k: int(v) for k, v in PRICE_DIVISORS.items()},
        "price_flags": [{"sku_id": p.sku_id, "name": p.name, "raw_price": str(p.raw_price),
                         "normalized_price": str(p.price), "issue": p.price_issue}
                        for p in flagged if p.price_issue],
        "inventory_records": inventory,
    }
    return flagged, report
