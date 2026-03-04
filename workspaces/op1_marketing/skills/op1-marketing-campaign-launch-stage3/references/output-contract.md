# Stage3 Output Contract (Launch Campaigns, no auto launch)

## Canonical outputs
- `research/stage3_campaign_launch/run.latest.json`
- `research/stage3_campaign_launch/state.latest.json`
- `research/stage3_campaign_launch/campaigns.backlog.latest.json`
- `research/stage3_campaign_launch/campaigns.queue.latest.json`
- `research/stage3_campaign_launch/experiments.latest.json`
- `research/stage3_campaign_launch/attribution.map.latest.csv`
- `research/stage3_campaign_launch/decision_log.latest.md`
- `research/stage3_campaign_launch/packets/`

## Queue schema
`campaigns.queue.latest.json.queue` buckets:
- `launch_ready`
- `watchlist`
- `hold`

`counts` must mirror queue bucket lengths.

## Run invariants
- `run.latest.json.capability = marketing_launch_campaigns_stage3_shadow_v1`
- `run.latest.json.auto_launch = false`
- `run.latest.json.launch_mode = disabled`

## State invariants
- `state.latest.json.auto_launch = false`
- `state.latest.json.last_run_status` reflects latest generation pass or no-change pass
- `state.latest.json.launch_ready/watchlist/hold` align with queue counts

## Attribution invariants
- `attribution.map.latest.csv` contains a header row and tracked URL rows
- each tracked row includes `utm_id`, `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`

## Sales handoff invariants
`../../handoffs/marketing_to_sales.json` is updated by Stage3 run:
- `campaign_launch.stage = stage3_campaign_launch_shadow`
- `campaign_launch.auto_launch = false`
- `campaign_launch.queue_counts` matches Stage3 queue counts
- Stage3 campaign rows have ids starting with `stage3-`
