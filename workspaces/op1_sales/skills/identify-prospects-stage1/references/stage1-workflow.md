# Stage1 Workflow Reference (Identify Prospects)

## Objective
Convert upstream marketing/product signals into a ranked, evidence-backed prospect queue for early sales.

## Scoring model
- `market_score` = average BOFU keyword priority from `marketing_to_sales.json`
- `evidence_score` = matched pain-signal volume (capped at 25 matched signals)
- `urgency_score` = urgency flag from `opportunity_records.json`
- `priority_score` = `0.45*market + 0.35*evidence + 0.20*urgency`

## Output interpretation
- **A1**: score >= 95, immediate outreach priority
- **A2**: 90-94.99, second-wave outreach
- **B1**: 85-89.99, backlog / interview pool
- **B2**: <85, park until new evidence arrives

## Top1 extraction rule
1. Read `prospect_queue.latest.json`.
2. Select segment at index 0 (`segments[0]`).
3. Use up to 20 leads from `social_signals.top_posts` as first-wave evidence.
4. Render the default output file `top1_20_outreach.latest.md` with this fixed section order:
   - Top1 分段快照
   - 20条候选
   - 外联草稿（A1/A2/B1）
5. For each lead, include:
   - inferred ICP
   - explicit pain signal
   - evidence URL
   - one outreach angle

## Constraints
- Avoid vanity metrics.
- Include explicit evidence URLs for every lead shared with operators.
- Keep inferred claims conservative; do not state unverified company/contact data as fact.
