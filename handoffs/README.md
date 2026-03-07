# Handoff Contracts (OperatorOne)

`handoffs/*.json` are the cross-agent contract layer.

Rule: if you change schema/keys, update this file + related docs/README in the same PR.

---

## 1) Primary chain contracts

| File | Producer | Primary consumer | Purpose |
|---|---|---|---|
| `product_to_marketing.json` | Product | Marketing | Product strategy, ICP, scope, landing context |
| `marketing_to_sales.json` | Marketing | Sales | Lead signals, assets, campaigns, offer context |
| `sales_to_operations.json` | Sales | Operations | Contact/reply/conversion KPIs + objections |

## 2) Operations feedback contracts

| File | Producer | Consumer | Purpose |
|---|---|---|---|
| `operations_to_product.json` | Operations Stage2 | Product | Priority feedback for product adjustments |
| `operations_to_marketing.json` | Operations Stage2 | Marketing | Messaging/channel recommendations |
| `operations_to_sales.json` | Operations Stage2 | Sales | Talk tracks + objection guidance |

## 3) Operations iteration contracts

| File | Producer | Consumer | Purpose |
|---|---|---|---|
| `operations_to_product_iterate.json` | Operations Stage3 | Product | Experiment-driven product iteration items |
| `operations_to_marketing_iterate.json` | Operations Stage3 | Marketing | Experiment-driven marketing iteration items |
| `operations_to_sales_iterate.json` | Operations Stage3 | Sales | Experiment-driven sales iteration items |

---

## 4) Current top-level key map (quick reference)

- `product_to_marketing.json`:
  - `idea_name`, `problem`, `icp`, `positioning`, `mvp_scope`, `constraints`, `notes`, `status`, `landing_page_url_or_path`

- `marketing_to_sales.json`:
  - `generated_at`, `lead_signals`, `content_assets`, `campaigns`, `offer_context`, `seo_targets`

- `sales_to_operations.json`:
  - `prospects_contacted`, `replies`, `calls_booked`, `customers_converted`, `mrr`, `objections_summary`, `handoff_notes`

- `operations_to_product.json`:
  - `from`, `generated_at`, `objective`, `items`, `notes`

- `operations_to_marketing.json`:
  - `from`, `generated_at`, `objective`, `recommendations`, `top_signal_topics`

- `operations_to_sales.json`:
  - `from`, `generated_at`, `objective`, `objection_counts`, `talk_tracks`

- `operations_to_*_iterate.json`:
  - `from`, `generated_at`, `objective`, `items`

---

## 5) Contract discipline

1. Keep fields stable and additive when possible.
2. Preserve `generated_at` and source attribution fields for traceability.
3. Do not overload one handoff with unrelated stage data.
4. If you add keys, update consuming scripts and this contract doc together.