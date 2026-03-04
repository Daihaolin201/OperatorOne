# Stage2 Output Contract (Publish Content, no auto publish)

## Canonical outputs
- `research/stage2_content_publish/run.latest.json`
- `research/stage2_content_publish/state.latest.json`
- `research/stage2_content_publish/content.backlog.latest.json`
- `research/stage2_content_publish/publish.queue.latest.json`
- `research/stage2_content_publish/qa.latest.json`
- `research/stage2_content_publish/decision_log.latest.md`
- `research/stage2_content_publish/review_log.latest.json`
- `research/stage2_content_publish/drafts/`

## Queue schema
`publish.queue.latest.json.queue` buckets:
- `approved`
- `review_ready`
- `needs_revision`
- `blocked`

`counts` must mirror queue bucket lengths.

## State invariants
- `state.latest.json.auto_publish = false`
- `state.latest.json.last_run_status` reflects latest generation/review update
- `state.latest.json.approved/review_ready/needs_revision` align with queue counts

## Run invariants
- `run.latest.json.capability = marketing_publish_content_stage2_shadow_v1`
- `run.latest.json.auto_publish = false`
- `run.latest.json.publish_mode = disabled`

## Sales handoff invariants
`../../handoffs/marketing_to_sales.json` is updated after generation/review:
- `content_assets[].status` matches Stage2 queue state
- `seo_targets[].status` matches Stage2 queue state
- campaign status is `review_only` or `review_approved`
