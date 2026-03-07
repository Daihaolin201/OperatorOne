# Handoff Contracts (OperatorOne)

`handoffs/*.json` are the cross-agent contract layer.

Rule: if you change schema/keys, update this file + related docs/README in the same PR.

Validation command:

```bash
python3 scripts/validate_handoffs.py --repo-root .
```

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

Common keys across all contracts:

- `contract_version`
- `generated_at`
- `generated_by`

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

## 5) Required metadata fields

Every handoff payload must include:

- `contract_version`
- `generated_at`
- `generated_by`

Current baseline version for all contracts is `1.0.0`.

## 6) Contract versioning policy

Contract versions follow **MAJOR.MINOR.PATCH** semantics:

| Bump | Trigger | Example |
|---|---|---|
| **MAJOR** | Breaking change: field removal, key rename, schema restructure | `1.0.0` → `2.0.0` |
| **MINOR** | Additive change: new optional field added | `1.0.0` → `1.1.0` |
| **PATCH** | Non-schema change: description update, value tweak, comment | `1.0.0` → `1.0.1` |

**Rules**:
- Any contract change **MUST** bump `contract_version` in the JSON file AND in `scripts/handoff_contracts.py → CONTRACT_VERSION_MAP`.
- Any MAJOR or MINOR bump **MUST** update `scripts/handoff_contracts.py` validator schema.
- PATCH bumps require no validator change — only update the value in the file and the version map entry.
- All changes **MUST** pass `python3 scripts/validate_handoffs.py --repo-root .` before merging.
- Breaking changes (MAJOR) require updating all consuming agent scripts and communicating the break to downstream agents.
- **No absolute filesystem paths** are permitted in any contract field. Use repo-relative paths (e.g. `workspaces/op1_product/...`) or the placeholder `"<repo-relative-path>"`.

## 7) Contract discipline

1. Keep fields stable and additive when possible.
2. Preserve `generated_at` and source attribution fields for traceability.
3. Do not overload one handoff with unrelated stage data.
4. If you add keys, update consuming scripts and this contract doc together.
5. Run `scripts/validate_handoffs.py` after any handoff producer change.
6. Never hardcode absolute paths (e.g. `/Users/*/...`) in contract values — use repo-relative paths only.