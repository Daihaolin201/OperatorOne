# Stage2 Send Outreach Workflow

## Preconditions
- Stage1 prospect output exists:
  - `workspaces/op1_sales/research/prospecting/prospect_queue.latest.json`
- Use `approval_required` mode for queue creation unless explicitly asked otherwise.

## Run order
1. Build outreach queue
   - `python3 workspaces/op1_sales/skills/send-outreach-stage2/scripts/build_outreach_stage2.py --repo-root <repo_root> --mode approval_required`
2. Resolve contacts
   - `python3 workspaces/op1_sales/skills/send-outreach-stage2/scripts/resolve_outreach_contacts_stage2.py --repo-root <repo_root>`
3. Approve batch
   - `python3 workspaces/op1_sales/skills/send-outreach-stage2/scripts/approve_outreach_batch_stage2.py --repo-root <repo_root> --approver <name> --note "<note>"`
4. Dispatch
   - Dry run: `python3 .../dispatch_outreach_stage2.py --repo-root <repo_root> --mode simulate`
   - Commit: `python3 .../dispatch_outreach_stage2.py --repo-root <repo_root> --mode commit`
5. Process replies
   - `python3 .../process_outreach_replies_stage2.py --repo-root <repo_root> --mode commit`

## Main artifacts
- Queue:
  - `research/outreach/outreach_queue.latest.json`
  - `research/outreach/outreach_queue.resolved.latest.json`
- Dispatch:
  - `research/outreach/outreach_dispatch_report.latest.json`
  - `research/outreach/outreach_send_requests.latest.json`
  - `research/outreach/outreach_manual_dispatch_bundle.latest.md`
- Reply loop:
  - `research/outreach/outreach_replies.processed.latest.json`
  - `research/outreach/reply_processing_report.latest.md`
  - `handoffs/sales_to_operations.json`
