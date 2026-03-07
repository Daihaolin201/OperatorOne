# Stage 3 — Launch Campaigns (Shadow / Review)

## Goal
Convert Stage2 approved assets into launch-ready campaign packets with tracking,
experiments, and decision queues.

> Auto launch is intentionally disabled in Stage3.

## Canonical outputs
- `run.latest.json`
- `state.latest.json`
- `campaigns.backlog.latest.json`
- `campaigns.queue.latest.json`
- `experiments.latest.json`
- `attribution.map.latest.csv`
- `decision_log.latest.md`
- `packets/`

## Input artifacts
- `input/stage2_snapshot.latest.json`
- `input/delta.latest.json`
- `input/mirror.latest/`

## Upstream dependencies
- `research/stage2_content_publish/run.latest.json`
- `research/stage2_content_publish/content.backlog.latest.json`
- `research/stage2_content_publish/publish.queue.latest.json`
- `research/stage2_content_publish/qa.latest.json`
- `../../handoffs/marketing_to_sales.json`
- `../../handoffs/product_to_marketing.json`

## Runtime modes
- `shadow` (default): full campaign orchestration without external launch
- `review`: same output contract for manual operator review

## Run
```bash
# single cycle
./scripts/run_marketing_campaign_stage3.sh

# force recompute
./scripts/run_marketing_campaign_stage3.sh --force

# include Stage2 review_ready assets as watch candidates
./scripts/run_marketing_campaign_stage3.sh --force --include-review-ready
```

## Verify contract
```bash
python3 ./scripts/verify_marketing_campaign_stage3.py
```

## Handoff output
Successful Stage3 runs update:
- `../../handoffs/marketing_to_sales.json`

With campaign launch queue summaries, campaign assets, and weekly lead forecasts.
