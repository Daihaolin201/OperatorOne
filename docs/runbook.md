# OperatorOne Runbook

## 1) First-time setup (per machine)

1. Clone repo:
   - `~/.openclaw/workspace/OperatorOne`
2. Sync OperatorOne profile safely:
   - `bash openclaw/sync-operatorone-safe.sh`
3. Verify profile:
   - `openclaw --profile operatorone status`
   - `openclaw --profile operatorone agents list`
4. Start fresh chat session:
   - `/new` or `/reset`

Advanced:

- Config-only sync: `bash openclaw/sync-openclaw.sh`
- Allow dual gateways temporarily: `bash openclaw/sync-operatorone-safe.sh --allow-dual-gateway`
- Cleanup legacy default-profile sync: `bash openclaw/cleanup-default-profile.sh`

---

## 2) Daily health check

From repo root:

```bash
openclaw --profile operatorone status
openclaw --profile operatorone agents list
git status --short
```

If `op1_*` agents are missing in UI, check active profile first.

---

## 3) Stage execution commands

All commands below assume current directory is repo root.

### 3.1 Product (`workspaces/op1_product`)

```bash
# Stage1/2: idea discovery + screening
bash workspaces/op1_product/scripts/run_generate_startup_ideas.sh

# Stage3 landing package + product->marketing handoff
bash workspaces/op1_product/scripts/run_create_landing_pages_v1.sh

# Build/deploy simple web product
bash workspaces/op1_product/scripts/run_build_deploy_v1.sh
```

Key outputs:

- `workspaces/op1_product/research/stage1_idea_discovery/opportunity_records.json`
- `workspaces/op1_product/research/stage2_idea_screening/decision_log.json`
- `workspaces/op1_product/research/stage2_web_product/run.latest.json`
- `workspaces/op1_product/research/stage3_landing_launch/run.latest.json`
- `handoffs/product_to_marketing.json`

### 3.2 Marketing (`workspaces/op1_marketing`)

```bash
# Stage1 SEO
bash workspaces/op1_marketing/scripts/run_marketing_seo_stage1.sh

# Stage2 content
bash workspaces/op1_marketing/scripts/run_marketing_content_stage2.sh

# Optional: manual review decisions
bash workspaces/op1_marketing/scripts/review_marketing_content_stage2.sh --approve-all --note "qa pass"

# Stage3 campaign
bash workspaces/op1_marketing/scripts/run_marketing_campaign_stage3.sh

# Contract check
python3 workspaces/op1_marketing/scripts/verify_marketing_campaign_stage3.py
```

Key output handoff:

- `handoffs/marketing_to_sales.json`

### 3.3 Sales (`workspaces/op1_sales`)

```bash
# Stage1 prospect queue
python3 workspaces/op1_sales/scripts/build_prospect_queue.py

# Stage2 outreach prep
python3 workspaces/op1_sales/scripts/build_outreach_stage2.py
python3 workspaces/op1_sales/scripts/resolve_outreach_contacts_stage2.py
python3 workspaces/op1_sales/scripts/approve_outreach_batch_stage2.py --approver <name>
python3 workspaces/op1_sales/scripts/dispatch_outreach_stage2.py --mode simulate
python3 workspaces/op1_sales/scripts/process_outreach_replies_stage2.py --mode commit

# Stage3 conversion
python3 workspaces/op1_sales/scripts/run_convert_early_customers_stage3.py --mode commit
python3 workspaces/op1_sales/scripts/verify_reproducibility_stage3.py
```

Key output handoff:

- `handoffs/sales_to_operations.json`

### 3.4 Operations (`workspaces/op1_operations`)

```bash
# Stage1 tracking
bash workspaces/op1_operations/scripts/run_stage1_tracking.sh

# Stage2 feedback + priorities + ops->* handoffs
bash workspaces/op1_operations/scripts/run_stage2_feedback.sh

# Stage3 iteration + ops->*_iterate handoffs
bash workspaces/op1_operations/scripts/run_stage3_iteration.sh
```

Key outputs:

- `workspaces/op1_operations/research/stage1_tracking/run_stage1.latest.json`
- `workspaces/op1_operations/research/stage2_feedback/run_stage2.latest.json`
- `workspaces/op1_operations/research/stage3_product_iteration/run_stage3.latest.json`
- `handoffs/operations_to_product*.json`
- `handoffs/operations_to_marketing*.json`
- `handoffs/operations_to_sales*.json`

---

## 4) Dashboard operations

```bash
python3 dashboard/server.py --host 127.0.0.1 --port 8765
```

Open:

- <http://127.0.0.1:8765>

Reference:

- `dashboard/README.md`
- `docs/studio_usage_guide.md`

---

## 5) Contract validation & upgrade

Validate all handoff contracts:

```bash
python3 scripts/validate_handoffs.py --repo-root .
```

Validate only changed contracts:

```bash
python3 scripts/validate_handoffs.py --repo-root . --contracts product_to_marketing,marketing_to_sales
```

Upgrade existing handoff files to current contract metadata fields (`contract_version`, `generated_at`, `generated_by`):

```bash
python3 scripts/upgrade_handoffs.py --repo-root .
```

## 6) Troubleshooting

### `op1_*` agents not visible in web

- Confirm profile: `openclaw --profile operatorone status`
- Confirm manifest sync: `bash openclaw/sync-operatorone-safe.sh`

### Handoff looks stale

- Re-run upstream stage script and verify `run.latest.json` updated timestamp.
- Check script mode (`simulate` vs `commit`) for sales/ops scripts.

### Reproducibility failures

- Use fixed timestamp options where supported (`--as-of`).
- Compare latest run artifacts vs baseline files in stage directories.

### Drift between docs and runtime

- Runtime artifact paths are source of truth in the short term.
- Fix docs in same PR cycle (`README`, stage index, runbook).

---

## 7) Safety notes

- Keep profile isolation (`operatorone`) for all OperatorOne operations.
- Treat `handoffs/*.json` as contract files; avoid ad-hoc key changes.
- Separate generated artifact refreshes from intentional code/doc changes during review.