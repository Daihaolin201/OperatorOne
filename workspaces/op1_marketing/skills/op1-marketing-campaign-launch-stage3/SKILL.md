---
name: op1-marketing-campaign-launch-stage3
description: Run and operate OperatorOne Marketing Stage3 launch-campaign orchestration in shadow/review mode. Use when asked to launch campaigns without auto-posting, convert Stage2 approved assets into campaign packets, generate UTM attribution maps, route campaigns into launch_ready/watchlist/hold, validate Stage3 output integrity, or sync campaign launch status to marketing_to_sales handoff.
---

# Stage3 Campaign Launch Operator (Shadow + Review)

## Objective
Operate Stage3 as a deterministic campaign-orchestration loop:
- select Stage2 assets
- build campaign plans and experiment cards
- generate UTM attribution mappings
- queue campaigns into `launch_ready` / `watchlist` / `hold`
- keep auto launch disabled

## Run Stage3 generation
From workspace root:

```bash
./scripts/run_marketing_campaign_stage3.sh
```

Useful variants:

```bash
# Force recompute
./scripts/run_marketing_campaign_stage3.sh --force

# Include Stage2 review_ready assets as watch candidates
./scripts/run_marketing_campaign_stage3.sh --force --include-review-ready

# Tighten readiness threshold
./scripts/run_marketing_campaign_stage3.sh --force --min-readiness 90

# Limit campaign count for narrow tests
./scripts/run_marketing_campaign_stage3.sh --force --max-campaigns 3
```

## Validate outputs
Run deterministic contract checks:

```bash
python3 {baseDir}/scripts/verify_stage3_contract.py
```

Interpretation:
- `checks_failed = 0` => Stage3 contract is consistent
- non-zero failures => inspect `run.latest.json`, `campaigns.queue.latest.json`, and `decision_log.latest.md`

## Required artifact set
Primary artifacts under `research/stage3_campaign_launch/`:
- `run.latest.json`
- `state.latest.json`
- `campaigns.backlog.latest.json`
- `campaigns.queue.latest.json`
- `experiments.latest.json`
- `attribution.map.latest.csv`
- `decision_log.latest.md`
- `packets/`

See detailed invariants in `references/output-contract.md`.

## Guardrails
- Keep `auto_launch=false` in this stage.
- Treat Stage3 as orchestration/measurement prep only (not external deployment).
- If Stage2 is unhealthy (`run.latest.json.status` not `passed|no_change`), stop and report upstream status.
- If completeness gate blocks Stage3, report missing requirements from `run.latest.json.input_sync.completeness`.

## References
- `references/output-contract.md`
- `references/launch-playbook.md`
