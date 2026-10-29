"""Domain records; monetary amounts are Decimal rupees, never binary floats."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Product:
    sku_id: str
    name: str
    brand: str
    category: str
    size: str
    raw_price: Decimal
    price: Decimal
    supplier: str
    description: str
    terms: tuple[str, ...]
    product_type: str
    quantity: Decimal | None
    unit: str | None
    stock_qty: int | None
    status: str
    restock_eta: date | None
    price_issue: str | None = None

    @property
    def available(self) -> bool:
        return self.status == "active" and self.stock_qty is not None and self.stock_qty > 0


@dataclass(frozen=True)
class Query:
    original: str
    normalized: str
    terms: tuple[str, ...]
    brand: str | None = None
    max_price: Decimal | None = None
    min_price: Decimal | None = None
    max_inclusive: bool = False
    min_inclusive: bool = False
    quantity: Decimal | None = None
    unit: str | None = None
    cheap: bool = False
    corrections: tuple[tuple[str, str], ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass
class Hit:
    product: Product
    score: float
    reasons: list[str] = field(default_factory=list)

    def as_dict(self, as_of: date) -> dict:
        p = self.product
        eta = p.restock_eta
        return {
            "sku_id": p.sku_id, "name": p.name, "brand": p.brand,
            "category": p.category, "size": p.size,
            "price": None if p.price_issue else float(p.price),
            "price_warning": p.price_issue,
            "available": p.available, "stock_qty": p.stock_qty,
            "availability": "in_stock" if p.available else (
                "unknown" if p.status == "unknown" else "out_of_stock"
            ),
            "restock_eta": eta.isoformat() if eta and eta >= as_of else None,
            "restock_note": "Previous restock estimate has passed" if eta and eta < as_of else None,
            "score": round(self.score, 4), "reasons": self.reasons,
        }
