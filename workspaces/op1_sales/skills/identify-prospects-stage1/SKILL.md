---
name: identify-prospects-stage1
description: Build and refresh Stage1 prospect-identification outputs for op1_sales. Use when asked to identify prospects, rank ICP segments, show top prospects, or generate evidence-backed lead queues from OperatorOne handoff data (marketing_to_sales, opportunity_records, reddit_signals).
---

# Identify Prospects Stage1

Run a deterministic Stage1 prospecting pipeline, then present ranked and evidence-backed leads.

## Execute

1. Locate OperatorOne repo root.
2. Run:
   - `python3 workspaces/op1_sales/skills/identify-prospects-stage1/scripts/build_prospect_queue.py`
3. Confirm files were written:
   - `workspaces/op1_sales/research/prospecting/prospect_queue.latest.json`
   - `workspaces/op1_sales/research/prospecting/prospect_queue.latest.csv`
   - `workspaces/op1_sales/research/prospecting/prospect_queue.latest.md`
   - `workspaces/op1_sales/research/prospecting/top1_20_outreach.latest.md` (default output template)

If auto-detection fails, pass repo root explicitly:
- `python3 .../build_prospect_queue.py --repo-root /path/to/OperatorOne`

## Return format

When user asks for plan/capability status:
- State pipeline is active.
- Report top ranked segments with score.
- Mention evidence source count (`matched_posts`).

When user asks for `top1 prospects` (or asks for output default template):
1. Read `workspaces/op1_sales/research/prospecting/top1_20_outreach.latest.md` first.
2. Return exactly this structure in order:
   - `Top1 分段快照`
   - `20条候选`
   - `外联草稿（A1/A2/B1）`
3. Keep evidence URL on every candidate row.
4. If fewer than 20 candidates exist, state the count explicitly and still keep the same structure.

## Quality bar

- Keep every prospect tied to an explicit evidence URL.
- Prefer high-signal, high-relevance leads over raw volume.
- Avoid unverified claims (no fabricated company/contact details).
- Keep recommendations convertible to outreach in one step.

## Reference

Read `references/stage1-workflow.md` when tuning thresholds, interpreting score bands, or preparing Top1 extraction.
Read `references/default-output-template.md` when enforcing the response structure for Top1 output.
