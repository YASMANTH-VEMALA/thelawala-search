# Product and engineering decisions

The email thread is client input, not a consistent checklist. These choices resolve conflicts explicitly. No external client clarification was available. The supplied assignment date (2026-10-12) is the reproducible clock.

| Issue | Chosen behavior | Reason and tradeoff |
|---|---|---|
| Hide unavailable products vs show assortment | Batch and primary page results require active positive stock. Separate page section can show zero/unknown stock. | Protects delivery expectations while revealing the product range. This is an interpretation of conflicting requests. |
| Missing inventory | Unknown, never assumed deliverable. | 41 catalog records have no stock record. |
| Discontinued products | Excluded from both sections regardless of quantity. | Not a promise of future supply. |
| Past restock ETA | Hide the stale date as a current ETA; show that the previous estimate passed. | An estimate does not prove restocking. |
| Own label vs explicit brand | Exact/unique partial brand is a hard restriction. Otherwise own-label boost is only 0.04. | Founder explicitly prioritizes brand intent over margin. |
| Most-clicked first | Bounded query-specific historical signal, subordinate to intent. Ignore sponsored events. | Popularity and exposure can reinforce wrong results. |
| Plain `milk` | Drinking milk only. Specific chocolate, powder, and flavoured-milk queries remain supported. | Ingredient words should not displace the product sought. |
| No available onions | No purchasable matches; show actual onions as unavailable. | This snapshot has two zero-stock and two missing-inventory onion SKUs. Chips are not a substitute. |
| Unrecognized or unavailable item | Empty results rather than aggressive broadening. | Avoid inventing matches for medicine, chargers, etc. |
| Budget semantics | `under`/`below` strict; `up to` inclusive; `between` inclusive; pack price in rupees. | Predictable and testable. No filter UI is added. |
| Cheap semantics | Ascending total pack price within an intent tier. | Explicitly does not claim value per gram/ml. |
| Size matching | Normalize g/kg, ml/L, pcs/NOS; exact normalized quantity/unit. | Trust structured `size` rather than inconsistent names. |
| Bare numbers | Interpret bare egg count; otherwise retain ambiguity and warn. | `atta 5` should not silently become ₹5 or 5 kg. |
| Catalog duplicates | Deduplicate identical normalized brand/identity/size within each availability section. Keep SKUs and stock separate. | Avoid repeated display without merging possibly distinct warehouse items. |
| Descriptions | Not used for retrieval. | Generic ingredient boilerplate causes matches such as milk in unrelated products. 360 are missing. |
| External services | None during ingestion or serving. | Meets latency/cost constraints and makes review reproducible. |
| Daily catalog updates | Rebuild on restart from a consistent input snapshot. | Small enough for this assignment; hot refresh is future work. |

## Price assumptions

The feed has no currency field. `metro_feed` values such as `6200` for one litre of toned milk are consistent with paise; values from `thela_direct`/`local_vendor` are treated as rupees. The supplier-specific conversion is configured in `data.py`. It is a documented hypothesis, not a verified finance correction. Unknown suppliers receive a price warning until their units are verified.

Even after conversion some prices remain implausible. Three conservative rules flag uncertainty:

1. More than 8x above/below the median for the same product identity and normalized pack size, with at least three records in that group.
2. Produce sold by weight above 30x the median produce price per gram, with at least ten weighed produce records.
3. Multipiece bath soap whose per-piece price is below one quarter of the cheapest 100 g single-bar price.

The last two are explicit domain heuristics: they can flag legitimate premium produce or promotions. They are necessary because an entire pack-size group can be corrupted together; a same-size median would then look normal. No repair is inferred from price magnitude alone. Flagged amounts are retained internally, withheld from display, and excluded from price-sensitive queries. Product discovery remains available.

## Ranking details

All query terms and any explicit brand must match. An intent tier separates a requested product type from secondary meanings. Selected generic ingredient queries apply a hard identity guard. Within a tier:

```text
lexical = sum(log(1 + (N - document_frequency + 0.5)
                        / (document_frequency + 0.5)))
score = lexical / (1 + 0.12 * extra_identity_tokens)
        + 1.0 if query phrase occurs
        + min(0.35, 0.08 * log(1 + behavior_weight))
        + 0.04 for own label when no brand is requested
```

The phrase bonus and own-label term are conditional additions. Sort by `(intent tier, price if cheap, -score, sku_id)`. Inventory eligibility is enforced before returning results, not used as a soft score. Query parser/normalization caches improve repeated queries; full search results are not cached.

Behavior uses click=1, add-to-cart=3; browse multiplies by 0.5 after a failed search and 0.15 otherwise. Search positions below first receive up to a 1.3 multiplier. All signals decay with a 45-day half-life. Signals group canonical query terms and brand, while hard price/size constraints still apply at retrieval time. We do not claim an unbiased propensity estimate because full impressions are missing.

## Deliberate boundaries

No learned semantic model, autocomplete, checkout, filter panel, user accounts, live inventory integration, or general conversational understanding. The lightweight design meets the specified interfaces and leaves the candidate a codebase they can explain and change live. Fuzzy correction uses a small catalog vocabulary and only unknown words; ties/weak corrections remain unresolved rather than silently guessed.
