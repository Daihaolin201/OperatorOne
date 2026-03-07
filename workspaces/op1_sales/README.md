# op1_sales — Sales Agent

Sales owns prospecting, outreach execution, and early-customer conversion.

Core mission:

1. Build qualified prospect queues (Stage1)
2. Prepare and run outreach with approval gates (Stage2)
3. Move leads through conversion stages and produce ops-ready KPI rollups (Stage3)

## Stage pipelines

### Stage1 — Identify prospects

```bash
python3 workspaces/op1_sales/scripts/build_prospect_queue.py
```

Key outputs:

- `research/prospecting/prospect_queue.latest.json`
- `research/prospecting/prospect_queue.latest.csv`
- `research/prospecting/prospect_queue.latest.md`

### Stage2 — Send outreach (approval-gated)

```bash
# Build queue + message pack
python3 workspaces/op1_sales/scripts/build_outreach_stage2.py

# Resolve contact routes
python3 workspaces/op1_sales/scripts/resolve_outreach_contacts_stage2.py

# Approve batch
python3 workspaces/op1_sales/scripts/approve_outreach_batch_stage2.py --approver <name>

# Dispatch (simulate first, then commit)
python3 workspaces/op1_sales/scripts/dispatch_outreach_stage2.py --mode simulate
python3 workspaces/op1_sales/scripts/dispatch_outreach_stage2.py --mode commit

# Process replies and update KPI rollups
python3 workspaces/op1_sales/scripts/process_outreach_replies_stage2.py --mode commit
```

Key outputs:

- `research/outreach/outreach_queue.latest.json`
- `research/outreach/outreach_queue.resolved.latest.json`
- `research/outreach/outreach_dispatch_report.latest.json`
- `research/outreach/outreach_events.latest.jsonl`
- `research/outreach/reply_processing_report.latest.md`

### Stage3 — Convert early customers

```bash
python3 workspaces/op1_sales/scripts/run_convert_early_customers_stage3.py --mode commit
python3 workspaces/op1_sales/scripts/verify_reproducibility_stage3.py
```

Key outputs:

- `research/conversion/conversion_pipeline.latest.json`
- `research/conversion/close_motion.latest.md`
- `research/conversion/pilot_onboarding.latest.json`
- `research/conversion/conversion_scoreboard.latest.json`
- `research/conversion/conversion_scoreboard.latest.md`
- `research/conversion/objection_playbook.latest.md`

## Handoff ownership

Primary outbound contract:

- `../../handoffs/sales_to_operations.json`

This is updated from reply processing + conversion scoreboard pipelines.

## References

- Stage path index: `research/STAGE_INDEX.md`
- Skills:
  - `skills/identify-prospects-stage1/`
  - `skills/send-outreach-stage2/`
  - `skills/convert-early-customers-stage3/`