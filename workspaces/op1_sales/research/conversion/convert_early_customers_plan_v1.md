# Convert Early Customers Capability Plan v1

Generated: 2026-03-04
Owner: op1_sales

## 0) Search + analysis summary

### Internal findings (OperatorOne data)
- Stage1 and Stage2 are already in place:
  - Stage1 identifies and ranks prospects.
  - Stage2 builds outreach queue, approval-gated dispatch, reply processing, and metrics rollup.
- Product Stage3 blueprint already defines a conversion target and constraints:
  - 14-day pilot, sample target 20.
  - Success target includes paid starts / paid-start commitments.
  - Pricing hypotheses exist (invoice and chargeback variants).
- Marketing handoff has channel priority (`email_nurture`, `linkedin`, `organic_search`) and BOFU campaign context.

### External findings (web fetch)
- Conversion/closing practice:
  - Need explicit close asks + objection handling flow (listen → clarify → respond → confirm).
  - Fast follow-up and fewer touches correlate with higher close efficiency.
- Onboarding practice:
  - Early value delivery in onboarding strongly affects trial-to-paid conversion.
- Metrics practice:
  - Track New Business MRR / ASP / conversion flow, not vanity activity.
- Compliance/deliverability:
  - CAN-SPAM requirements (identity, subject truthfulness, opt-out, physical address).
  - Gmail sender requirements (SPF/DKIM, TLS, DNS hygiene, low spam rates).

Constraint observed:
- `web_search` tool unavailable in current runtime (missing Brave API key), so external research used `web_fetch`.

---

## 1) Capability definition (what “Convert early customers” must do)

A complete Stage3 conversion capability must produce:
1. **Conversion pipeline state** (from replied lead to paid start)
2. **Deal strategy + close plan per lead**
3. **Pilot onboarding + time-to-value tracking**
4. **Commitment capture** (paid start or signed paid-start commitment)
5. **Objection-to-playbook loop** (learn and improve)
6. **Revenue-grade reporting** (customers converted, ASP proxy, objection impact)

---

## 2) Proposed architecture

## 2.1 Inputs
- `workspaces/op1_sales/research/outreach/outreach_queue.resolved.latest.json`
- `workspaces/op1_sales/research/outreach/outreach_events.latest.jsonl`
- `workspaces/op1_sales/research/outreach/outreach_replies.processed.latest.json`
- `handoffs/marketing_to_sales.json`
- `workspaces/op1_product/research/stage3_mvp_scope/project_blueprint.json`
- `workspaces/op1_product/research/build_deploy_v1/project_spec*.json`

## 2.2 New Stage3 outputs
- `workspaces/op1_sales/research/conversion/conversion_pipeline.latest.json`
- `workspaces/op1_sales/research/conversion/close_plan.latest.md`
- `workspaces/op1_sales/research/conversion/pilot_onboarding.latest.json`
- `workspaces/op1_sales/research/conversion/conversion_events.latest.jsonl`
- `workspaces/op1_sales/research/conversion/objection_playbook.latest.md`
- `workspaces/op1_sales/research/conversion/conversion_scoreboard.latest.md`

## 2.3 Core state model
Lead/customer stages:
- `qualified_interest`
- `discovery_scheduled`
- `discovery_completed`
- `pilot_offered`
- `pilot_active`
- `pilot_value_confirmed`
- `commercial_terms_sent`
- `commitment_received`
- `paid_started`
- `closed_lost`

Each record keeps:
- current stage + stage timestamps
- champion confidence
- value evidence (pain baseline, pilot outcome)
- objection stack + status
- close next-best-action + due date

---

## 3) Implementation plan (phased)

## Phase A — Conversion state engine (foundation)
Goal: unify all “interested” leads into explicit conversion stages.

Build script:
- `workspaces/op1_sales/scripts/build_conversion_pipeline_stage3.py`

What it does:
- Ingest Stage2 events/replies.
- Promote eligible leads into conversion stages.
- Compute conversion readiness score per lead:
  - pain intensity
  - urgency/timing
  - authority signal
  - budget signal
  - pilot fit

Exit criteria:
- 100% conversion leads have explicit stage + next action.

## Phase B — Close-plan generator
Goal: convert each active opportunity into actionable close tasks.

Build script:
- `workspaces/op1_sales/scripts/generate_close_plan_stage3.py`

What it does:
- Generate per-lead close plan:
  - value recap
  - objection response script
  - ask type (pilot start / paid start / paid-start commitment)
  - deadline + follow-up sequence
- Output markdown brief for operator execution.

Exit criteria:
- Every lead in `pilot_offered+` has a concrete close ask and date.

## Phase C — Pilot onboarding + TTV tracker
Goal: reduce drop-off between “interested” and “paid”.

Build script:
- `workspaces/op1_sales/scripts/run_pilot_onboarding_stage3.py`

What it does:
- Create onboarding checklist per lead from product blueprint.
- Track first value timestamp (time-to-first-value / TTFV).
- Trigger rescue sequence when onboarding stalls.

Exit criteria:
- 90%+ pilot-active leads have onboarding status + TTFV captured.

## Phase D — Commitment and revenue capture
Goal: reliably capture “converted” outcomes and reasons for loss.

Build script:
- `workspaces/op1_sales/scripts/process_conversion_signals_stage3.py`

What it does:
- Parse commitment signals from replies/notes:
  - paid start
  - signed paid-start commitment
  - closed-lost reason
- Update conversion pipeline + scoreboard + handoff.

Exit criteria:
- Conversions and losses are explicitly recorded with reason codes.

## Phase E — Learning loop
Goal: improve conversion rate each cycle.

Build script:
- `workspaces/op1_sales/scripts/refresh_objection_playbook_stage3.py`

What it does:
- Rank top objection clusters (budget/integration/trust/timing).
- Tie each objection to winning response patterns.
- Produce weekly playbook update.

Exit criteria:
- Objection playbook auto-updates from real outcomes.

---

## 4) Metrics for Stage3 (no vanity)

Primary:
- `qualified_interest_to_pilot_rate`
- `pilot_to_commitment_rate`
- `commitment_to_paid_start_rate`
- `time_to_first_value_median`
- `time_to_paid_start_median`

Revenue/quality:
- `new_customers_converted`
- `new_business_mrr_proxy`
- `asp_proxy`
- `objection_resolution_rate`
- `closed_lost_reason_mix`

Guardrails:
- `opt_out_rate`
- `no_response_after_offer_rate`
- `onboarding_stall_rate`

---

## 5) Operational rules

- Keep Stage3 deterministic and file-based like Stage2.
- No “sent = converted” assumption.
- Conversion requires explicit commitment evidence.
- Always preserve evidence URLs and assumption logs.
- Maintain suppression rules from Stage2 through Stage3.

---

## 6) Recommended execution order (immediate)

1. Build Phase A + B first (pipeline + close plan).
2. Then Phase C (onboarding/TTFV).
3. Then Phase D + E (commitment parsing + learning loop).

This yields fastest path to measurable early customer conversion while staying compatible with current hackathon constraints.
