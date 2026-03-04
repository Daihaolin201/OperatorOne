# Stage 2 — Publish Content (Shadow / Review)

## Goal
Turn Stage1 SEO experiment outputs into publish-ready content assets with quality gates,
without automatic publishing.

## Canonical outputs
- `run.latest.json`
- `state.latest.json`
- `content.backlog.latest.json`
- `publish.queue.latest.json`
- `qa.latest.json`
- `decision_log.latest.md`
- `review_log.latest.json`
- `drafts/`

## Input artifacts
- `input/stage1_snapshot.latest.json`
- `input/delta.latest.json`
- `input/mirror.latest/`

## Upstream dependencies
- `research/stage1_marketing_seo/run.latest.json`
- `research/stage1_marketing_seo/context_index.latest.json`
- `research/stage1_marketing_seo/experiments.backlog.latest.json`
- `research/stage1_marketing_seo/experiments.queue.latest.json`
- `research/stage1_marketing_seo/scoreboard.latest.json`
- `../../handoffs/product_to_marketing.json`

## Runtime modes
- `shadow` (default): generate drafts + queue for review
- `review`: same output contract, tuned for manual editorial review pass

> Auto publish is explicitly disabled in this stage.

## Run
```bash
# single cycle
./scripts/run_marketing_content_stage2.sh

# include hold candidates and force recompute
./scripts/run_marketing_content_stage2.sh --force --include-hold

# continuous mode
./scripts/run_marketing_content_stage2.sh --continuous --interval 300
```

## Manual review workflow
Queue buckets:
- `approved`
- `review_ready`
- `needs_revision`
- `blocked`

Apply manual decisions:
```bash
# approve all review-ready items
./scripts/review_marketing_content_stage2.sh --approve-all --note "editorial pass"

# mix approve + request-revision for specific items
./scripts/review_marketing_content_stage2.sh \
  --approve cnt_x,cnt_y \
  --reject cnt_z \
  --reason "tighten evidence" \
  --note "editor pass 1"
```

Manual review updates:
- `research/stage2_content_publish/review_log.latest.json`
- `research/stage2_content_publish/publish.queue.latest.json`
- `research/stage2_content_publish/content.backlog.latest.json`

## Handoff output
Every successful generation/review update writes:
- `../../handoffs/marketing_to_sales.json`

With content asset statuses (`approved` / `review_ready` / `needs_revision`) and shadow lead-signal estimates for sales alignment.
