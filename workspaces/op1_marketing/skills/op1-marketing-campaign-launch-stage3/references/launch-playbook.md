# Stage3 Launch Playbook (Shadow)

## Typical flow
1. Run Stage3 generation:
   - `./scripts/run_marketing_campaign_stage3.sh --force`
2. Validate contract:
   - `python3 {baseDir}/scripts/verify_stage3_contract.py`
3. Review launch queue:
   - `research/stage3_campaign_launch/campaigns.queue.latest.json`
4. Review decision log + packets:
   - `research/stage3_campaign_launch/decision_log.latest.md`
   - `research/stage3_campaign_launch/packets/*.md`
5. Confirm handoff sync:
   - `../../handoffs/marketing_to_sales.json`

## Decision interpretation
- `launch_ready`: campaign can proceed to human-operated launch execution
- `watchlist`: campaign is near-threshold, monitor or tighten inputs before escalation
- `hold`: campaign is blocked by readiness/risk or upstream quality issues

## Parameter tuning patterns
- Need stricter quality bar:
  - increase `--min-readiness` (e.g., 90)
- Need smaller focused batch:
  - reduce `--max-campaigns` (e.g., 3)
- Need broader intake:
  - add `--include-review-ready` to include Stage2 review-ready assets as watch candidates

## Common failure states
- `blocked_input_incomplete`:
  - one or more required Stage2/handoff artifacts missing
- `blocked_upstream_stage2_unhealthy`:
  - Stage2 run status not healthy (`passed|no_change` expected)
- `blocked_no_launchable_assets`:
  - no selected assets met Stage3 candidate criteria

## Audit checklist
- Confirm `auto_launch=false` in run/state/handoff
- Confirm queue counts are internally consistent
- Confirm attribution map includes rows for each campaign-channel-variant tuple
- Confirm experiments are present and linked to campaign ids
