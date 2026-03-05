# Send Outreach Capability Plan v1 (for op1_sales)

Generated: 2026-03-04

## 0) Search + analysis findings

### Internal signal findings
- Current GTM handoff already prioritizes outreach channels: `email_nurture`, `linkedin`, `organic_search`.
- Stage3 campaign objects are `launch_ready` but `auto_launch=false`; channel mix is explicitly modeled with experiment variants.
- Existing Stage1 skill (`identify-prospects-stage1`) already produces:
  - ranked segment queue
  - Top1→20 candidates
  - outreach draft snippets (A1/A2/B1)
- Sales scope requires outreach + follow-up, but current implementation stops at draft generation and does not execute sends.
- Runtime channel status currently has no configured outbound channel accounts in OpenClaw (`channels status --probe --json` returns empty channel map).

### External compliance/deliverability findings
- FTC CAN-SPAM requires: non-deceptive headers/subject, ad identification, valid postal address, clear opt-out path, and honoring opt-out within 10 business days.
- Google sender guidelines (Gmail): SPF/DKIM (and DMARC for larger senders), TLS, DNS hygiene, low spam rates, and sender alignment are required to reduce blocking/spam placement.

Implication: build `Send outreach` in two stages:
1) **Draft+queue+approval** (works immediately in hackathon mode)
2) **Controlled dispatch** (enabled only after channel config + compliance checks)

---

## 1) Capability definition (what "Send outreach" means)

A complete capability must cover 5 sub-capabilities:
1. **Queue**: choose who to contact next from scored prospects.
2. **Personalize**: generate message variants from ICP + pain signal + evidence URL.
3. **Dispatch**: send through channel adapters with manual safety gate.
4. **Track**: capture reply/outcome/opt-out and update next actions.
5. **Learn**: feed outcome metrics back to scoring + copy variants.

---

## 2) Build architecture

## 2.1 Inputs
- `workspaces/op1_sales/research/prospecting/prospect_queue.latest.json`
- `workspaces/op1_sales/research/prospecting/top1_20_outreach.latest.md`
- `handoffs/marketing_to_sales.json` (channel and experiment context)

## 2.2 Core data contracts
- `outreach_queue.latest.json`
  - lead_id, opportunity_id, priority_band
  - channel_plan (email/linkedin/manual)
  - message_variant (control/challenger)
  - evidence_url, assumptions
  - schedule_step, status
- `outreach_events.latest.jsonl`
  - sent, failed, replied, bounced, opted_out, booked_call
- `suppression_list.latest.json`
  - opted-out leads + do-not-contact flags

## 2.3 Execution modes
- `draft_only` (default): generate ready-to-send copy only.
- `approval_required`: human confirms each batch before dispatch.
- `dispatch_enabled`: only if compliance + channel checks pass.

---

## 3) Skill packaging plan

Create a new skill: `send-outreach-stage1`

### 3.1 Files
- `skills/send-outreach-stage1/SKILL.md`
- `skills/send-outreach-stage1/scripts/build_outreach_queue.py`
- `skills/send-outreach-stage1/scripts/render_outreach_pack.py`
- `skills/send-outreach-stage1/scripts/dispatch_outreach.py`
- `skills/send-outreach-stage1/scripts/process_replies.py`
- `skills/send-outreach-stage1/references/compliance-checklist.md`
- `skills/send-outreach-stage1/references/channel-playbooks.md`
- `skills/send-outreach-stage1/references/objection-taxonomy.md`

### 3.2 Trigger conditions in SKILL description
Use when user asks to:
- send outreach
- run outreach sequence/follow-up
- generate outreach pack and dispatch list
- process outreach replies and update next steps

---

## 4) 4-phase implementation plan

## Phase 1 — Queue + copy generation (no sending)
**Goal:** fast, safe, deterministic output.
- Build queue from Top1 20 leads.
- Generate channel-specific copy blocks:
  - Email: subject + body + CTA
  - LinkedIn: short DM + follow-up DM
- Output:
  - `outreach_queue.latest.json`
  - `outreach_pack.latest.md`

**Exit criteria:**
- 100% queue rows include evidence URL and outreach assumption.
- A1/A2/B1 variants generated for each lead.

## Phase 2 — Approval workflow
**Goal:** prevent accidental sends.
- Add batch approval artifact:
  - `outreach_batch.ready.json`
  - `outreach_batch.approved.json`
- `dispatch_outreach.py` refuses to send without approved batch file.

**Exit criteria:**
- Zero sends possible without explicit approval artifact.

## Phase 3 — Controlled dispatch adapters
**Goal:** selective real sending when infrastructure allows.
- Adapter abstraction:
  - `manual_export` (always available)
  - `openclaw_message` (only if channel configured)
- Per-run caps (e.g., max 20 sends/day in hackathon mode)
- Retry and backoff for transient failures.

**Exit criteria:**
- Dispatch logs produced for every attempt.
- Failure does not lose queue state.

## Phase 4 — Reply intelligence + learning loop
**Goal:** convert feedback to pipeline movement.
- Classify replies: positive / objection / not now / unsubscribe / irrelevant.
- Build next-step suggestions and follow-up tasks.
- Update `sales_to_operations.json` metrics and objections summary.

**Exit criteria:**
- Every reply updates lead state and next action.
- Objection taxonomy file is auto-refreshed.

---

## 5) Compliance + quality gates (hard requirements)

Before any real dispatch:
1. Opt-out handling enabled and tested.
2. Suppression list applied before queue export/send.
3. Sender identity + subject transparency checks pass.
4. Channel readiness check passes (auth/config present).
5. Daily send cap + frequency cap enabled.

Any failed gate => force fallback to `draft_only` mode.

---

## 6) Metrics (no vanity)

Primary:
- sent_count
- delivered_rate
- reply_rate
- qualified_reply_rate
- call_book_rate
- opt_out_rate

Diagnostic:
- bounce_rate
- spam-complaint proxy (where available)
- median time-to-first-reply
- A/B variant lift by band (A1/A2/B1)

---

## 7) Suggested timeline (hackathon tempo)

- Day 0: Phase 1 complete (queue + outreach pack)
- Day 1: Phase 2 complete (approval gates)
- Day 2: Phase 3 complete (manual_export + optional live channel adapter)
- Day 3: Phase 4 complete (reply processing + metrics loop)

---

## 8) Decision recommendation

Keep `identify-prospects-stage1` and `send-outreach-stage1` as separate skills, and link them through stable artifacts.

Reason:
- clearer boundaries and safer rollouts
- easier testing/debugging
- allows outreach execution to evolve without destabilizing prospect scoring
