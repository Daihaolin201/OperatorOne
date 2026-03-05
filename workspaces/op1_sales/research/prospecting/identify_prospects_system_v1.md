# Identify Prospects System v1

## Goal
Build a repeatable, evidence-based prospect identification engine that can run even when live paid APIs are unavailable.

## Inputs
- `../../../../handoffs/marketing_to_sales.json`
- `../../../op1_product/research/stage1_idea_discovery/opportunity_records.json`
- `../../../op1_product/research/reddit_signals.json`

## Pipeline
1. **ICP lock**: ingest target segment per opportunity (`role`, `size`, `industry`).
2. **Signal extraction**:
   - BOFU keyword priority from marketing handoff
   - community pain signals from Reddit corpus (title + body + matched query)
3. **Segment classification**:
   - map each content asset/post to a single opportunity segment
   - use weighted term relevance + subreddit priors to avoid noisy overlaps
4. **Scoring**:
   - `market_score` (keyword priority)
   - `evidence_score` (matched community signal volume)
   - `urgency_score` (from opportunity records)
   - composite `priority_score`
5. **Actionability package**:
   - ranked segment list
   - top evidence posts with links
   - first-20 targeting approach
   - suggested search queries for account-level expansion

## Outputs
- `prospect_queue.latest.json`
- `prospect_queue.latest.csv`
- `prospect_queue.latest.md`

## Run
```bash
python3 workspaces/op1_sales/scripts/build_prospect_queue.py
```

## Quality rules
- No vanity metrics: every ranked segment must include explicit evidence links.
- Track assumptions: every query and score source is saved in output artifacts.
- Keep it convertible: output is optimized for immediate outreach queue building.
