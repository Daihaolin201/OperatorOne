# Stage1 Capability Implementation — Track traffic, signups, revenue

Implemented by: `workspaces/op1_operations`

## Scope

This implementation intentionally supports simulated/shadow source signals while preserving a production migration path through adapter contracts.

## Capability matrix

1. **Metric governance**
   - `contracts/metric_dictionary.v1.yaml`

2. **Tracking plan governance**
   - `contracts/tracking_plan.v1.json`

3. **Event collection (canonical model)**
   - `scripts/ingest_stage1_events.py`
   - `research/stage1_tracking/raw_events.latest.jsonl`

4. **Identity stitching**
   - `research/stage1_tracking/identity_map.latest.json`

5. **Attribution layers (first/session/event)**
   - `research/stage1_tracking/attribution_facts.latest.json`

6. **Traffic quality controls**
   - `research/stage1_tracking/traffic_quality_report.latest.json`

7. **Funnel engine (visit -> qualified signup -> paid)**
   - `research/stage1_tracking/funnel_daily.latest.json`

8. **Signup quality controls**
   - `research/stage1_tracking/signup_quality_daily.latest.json`

9. **Revenue engine (MRR movement model)**
   - `contracts/revenue_rules.v1.yaml`
   - `research/stage1_tracking/revenue_mrr_daily.latest.json`

10. **Channel economics**
    - `research/stage1_tracking/channel_scoreboard.latest.json`

11. **Operations scoreboard**
    - `research/stage1_tracking/stage1_scoreboard.latest.json`
    - `research/stage1_tracking/stage1_scoreboard.latest.md`

12. **Alerts**
    - `research/stage1_tracking/alerts.latest.json`

13. **Data quality**
    - `research/stage1_tracking/data_quality_report.latest.json`

14. **Reproducibility and audit**
    - `scripts/verify_stage1_reproducibility.py`
    - `research/stage1_tracking/reproducibility_report.latest.json`

15. **Prod migration adapter model**
    - `config/source_adapters.v1.json`

## Runner

```bash
cd workspaces/op1_operations
./scripts/run_stage1_tracking.sh
```

## Headline outputs (latest run)

- sessions: 905.67
- qualified_signups: 13
- paid_customers: 1
- net_new_mrr: 49.0
- progress to $100 MRR: 49%
