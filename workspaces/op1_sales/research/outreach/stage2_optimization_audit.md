# Stage2 Optimization Audit (Send Outreach)

Generated: 2026-03-05

## Why optimization was needed
A critical misclassification was found in reply processing:
- Example: `"No thanks ... not interested"`
- Old classifier output: `positive/interested`
- Expected output: `rejection/no_interest`

This created false-positive discovery progression.

## Changes applied

### 1) Reply classifier upgraded
- File: `workspaces/op1_sales/scripts/process_outreach_replies_stage2.py`
- Skill copy: `workspaces/op1_sales/skills/send-outreach-stage2/scripts/process_outreach_replies_stage2.py`
- New classifier version: `stage2-reply-v2`

Key improvements:
- Introduced regex-based intent detection with explicit precedence:
  1. unsubscribe
  2. converted
  3. rejection
  4. not_now
  5. objections
  6. booked_call
  7. interested
  8. other
- Rejection rules now catch `not interested/no thanks/already use` before positive intent.

### 2) Traceability improved
- Reply events now include `classifier_version` field.
- Processed report now includes `classifier_version` header.

### 3) Handoff note hygiene improved
- Reply processor note in `sales_to_operations.json` now de-duplicates prior reply-processor entries before appending a new one.

### 4) Deterministic validator added
- New script:
  - `workspaces/op1_sales/scripts/validate_stage2_reply_classifier.py`
  - skill copy: `workspaces/op1_sales/skills/send-outreach-stage2/scripts/validate_stage2_reply_classifier.py`
- Covers core intents:
  - positive booked call
  - rejection/no_interest
  - not_now/timing
  - unsubscribe
  - objection/budget
  - converted

### 5) Skill docs updated
- Added reference: `references/reply-classification.md`
- Added validation step to `send-outreach-stage2/SKILL.md`

## Verification evidence

- Validator result: `Stage2 reply classifier validation PASSED`
- Sample inbox replay check:
  - `rpl-005` (`No thanks ... not interested`) now classified as:
    - category: `rejection`
    - detail: `no_interest`

## Packaging status
- Repackaged skill artifact:
  - `workspaces/op1_sales/skills/dist/send-outreach-stage2.skill`
