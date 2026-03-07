# Live migration guide (from simulated signals to production data)

## Objective

Keep metric contracts unchanged while replacing source adapters.

## Adapter replacement matrix

### Traffic adapter

Replace `marketing_campaign_shadow` with one of:

- PostHog export/API
- GA4 export (BigQuery)
- first-party server event stream

Required mapping:

- `event_name=session_observed`
- `event_count` from session counts
- attribution fields from UTM/source dimensions

### Signup adapter

Replace `sales_outreach_sim` and/or `sales_conversion_sim` with:

- Product signup service logs
- CRM lifecycle events (HubSpot/Salesforce)

Required mapping:

- `signup_started`
- `signup_captured`
- `signup_qualified`
- `lead_unsubscribed` (if available)

### Revenue adapter

Replace `billing_proxy` with billing-system events (Stripe/Chargebee/etc.)

Required mapping:

- `paid_started`
- `mrr_movement` with one of:
  - `new_business`
  - `expansion`
  - `contraction`
  - `churn`
  - `reactivation`

## Migration checklist

1. Preserve metric dictionary and revenue rules unchanged.
2. Enable new adapter(s) in `config/source_adapters.v1.json`.
3. Disable simulated adapters (`enabled=false`).
4. Run pipeline twice with fixed `STAGE1_AS_OF`; require strict reproducibility pass.
5. Compare old vs new scoreboard and document expected deltas.
6. Set alert thresholds based on observed production variance.

## Non-negotiable guardrails

- Do not change metric formulas during source migration.
- Do not drop attribution fields silently.
- Do not merge movement types into a single revenue event.
- Keep idempotent event IDs to control duplicates.
