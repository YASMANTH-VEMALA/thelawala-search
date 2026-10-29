# Supplied data: inferred dictionary and audit

All original files are preserved. The report can be regenerated with `python -m thelawala audit`; it is checked into `evaluation/data_audit.json`. Interpret dates relative to **2026-10-12**.

## Catalog: 1,102 rows

| Field | Interpretation |
|---|---|
| `sku_id` | Unique catalog identifier, shared with inventory and events |
| `name` | Customer-facing product name; includes supplier-specific abbreviations/typos |
| `brand` | Authoritative brand label used for restrictions |
| `category` | One of 11 provided merchandising categories |
| `size` | Authoritative pack size; normalize mass, volume, and piece-count spellings |
| `price` | Supplier-dependent numeric amount; units inferred, see decision record |
| `supplier` | `thela_direct` (798), `local_vendor` (154), `metro_feed` (150) |
| `description` | Optional, often generic; 360 missing |

There are 39 brands; Thela Select has 234 products. No duplicate SKU IDs exist, but some normalized product identities repeat under different IDs. Names are not reliable IDs. Category does not uniquely identify product intent: dairy has both drinking milk and milk powder, while snacks have milk chocolate and rusk.

## Inventory: 1,070 rows

| Field | Interpretation |
|---|---|
| `sku_id` | Warehouse product identifier; join to catalog, never by row order |
| `stock_qty` | Nonnegative integer; positive stock alone does not override status |
| `status` | `active` or `discontinued` |
| `restock_eta` | Optional ISO date; an estimate, not proof of stock |
| `updated_at` | ISO timestamp with timezone |

Across the inventory file: 907 active positive-stock records, 81 active zero-stock records, and 82 discontinued records. Nine positive-stock records have no catalog entry; they are older orphan records and are never searchable. That leaves **898 confirmed available catalog products**, 81 active out-of-stock, 82 discontinued, and 41 with unknown stock. Of 59 supplied ETAs, 23 are already before the assignment clock.

An `active` status is not equivalent to in stock. Daily updates are not live warehouse guarantees. This implementation trusts the supplied current snapshot for matched catalog items and does not invent a freshness SLA; production would need a refresh/freshness contract.

## Search log: 6,578 JSON objects

Dates span **15 Aug–10 Oct 2026**. There are 3,600 sessions, 1,446 distinct raw query strings, and 2,782 zero-result searches. Distinct raw queries include capitalization, whitespace, and spelling variants; they are not 1,446 distinct intents.

| Field | Interpretation |
|---|---|
| `ts` | Search timestamp with +05:30 timezone |
| `session_id` | Groups searches within a customer session; not a customer identity |
| `query` | Original typed query, including multilingual text and errors |
| `results_count` | Count reported by the historical search system |
| `events` | Subsequent interactions linked to this search record |

Each event contains `sku_id`, `action` (`click` or `add_to_cart`), `source` (`search` or `browse`), `position` (nullable), and `sponsored` (boolean). There are 7,555 events: 4,864 clicks and 2,691 cart additions; 4,768 search-origin and 2,787 browse-origin events. 108 are sponsored. All event SKU IDs exist in the catalog.

Example evidence of bias: the exact raw query `milk` has 28 sponsored clicks on Gomatha flavoured badam milk. Promoting the most-clicked product without interpreting intent could preserve this exposure bias. Add-to-cart is an implicit positive, not a purchase or a complete relevance label.

## Validation and future inputs

The loader rejects missing required columns, malformed CSV rows, empty/duplicate SKU IDs, invalid/nonpositive prices, invalid stock/status/date values, and missing pack identity. Extra CSV fields are tolerated. The supplied stock statuses and size units define the currently supported schema. Malformed logs fail with a line number rather than silently disappearing from aggregates. Sponsored and unknown-SKU events are counted and ignored as ranking evidence.

The audit identifies join gaps and price concerns without changing input files. New supplier units, vocabulary, statuses, or unusual pack conventions need explicit policy review; the engine does not pretend that no maintenance will ever be required.
