---
name: send-outreach-stage2
description: End-to-end Stage2 send outreach pipeline for op1_sales. Use when asked to send outreach, run follow-up sequences, generate outreach dispatch packs, approval-gated dispatch batches, process outreach replies, enforce suppression/frequency controls, or roll up outreach outcomes into handoffs/sales_to_operations.json.
---

# Send Outreach Stage2

Run the Stage2 outreach lifecycle from queue creation through reply processing.

## Quick start

Use this sequence in order:

1. Build queue and outreach drafts
   - `python3 workspaces/op1_sales/skills/send-outreach-stage2/scripts/build_outreach_stage2.py --repo-root <repo_root> --mode approval_required`
2. Resolve contacts and route status
   - `python3 workspaces/op1_sales/skills/send-outreach-stage2/scripts/resolve_outreach_contacts_stage2.py --repo-root <repo_root>`
3. Approve batch
   - `python3 workspaces/op1_sales/skills/send-outreach-stage2/scripts/approve_outreach_batch_stage2.py --repo-root <repo_root> --approver <name> --note "<note>"`
4. Dispatch
   - Dry run: `python3 workspaces/op1_sales/skills/send-outreach-stage2/scripts/dispatch_outreach_stage2.py --repo-root <repo_root> --mode simulate`
   - Commit: `python3 workspaces/op1_sales/skills/send-outreach-stage2/scripts/dispatch_outreach_stage2.py --repo-root <repo_root> --mode commit`
5. (Optional but recommended) Validate reply classifier
   - `python3 workspaces/op1_sales/skills/send-outreach-stage2/scripts/validate_stage2_reply_classifier.py`
6. Process replies and roll up metrics
   - `python3 workspaces/op1_sales/skills/send-outreach-stage2/scripts/process_outreach_replies_stage2.py --repo-root <repo_root> --mode commit`

## Workflow rules

- Require Stage1 prospect output before starting Stage2.
- Keep approval gating enabled before commit dispatch.
- Keep low-fit leads in `needs_review` until manually cleared.
- Keep suppression enforcement active on every dispatch run.
- Prefer `simulate` first, then `commit`.

## Output expectations

After a normal run, verify these artifacts:

- Queue and routing
  - `workspaces/op1_sales/research/outreach/outreach_queue.latest.json`
  - `workspaces/op1_sales/research/outreach/outreach_queue.resolved.latest.json`
- Dispatch outputs
  - `workspaces/op1_sales/research/outreach/outreach_dispatch_report.latest.json`
  - `workspaces/op1_sales/research/outreach/outreach_send_requests.latest.json`
  - `workspaces/op1_sales/research/outreach/outreach_manual_dispatch_bundle.latest.md`
- Reply loop outputs
  - `workspaces/op1_sales/research/outreach/outreach_replies.processed.latest.json`
  - `workspaces/op1_sales/research/outreach/reply_processing_report.latest.md`
  - `handoffs/sales_to_operations.json`

## References

- Read `references/workflow.md` for full run order and artifact map.
- Read `references/status-model.md` when interpreting lead states and events.
- Read `references/compliance-gates.md` before any commit-mode dispatch.
- Read `references/reply-classification.md` when debugging or tuning reply classification behavior.
