# OperatorOne Capability Matrix (Wave 4)

Generated at: `2026-03-07T22:37:27Z`

Overall status: **PARTIAL**

- Total agents: 5
- Capability points counted: 35
- Aggregate pass rate: 91.4%
- Verdict basis: 32 pass, 1 fail, 2 skip across agent-stage/openclaw plus reproducibility and handoff checks.

## Agent x Stage Matrix

| Agent | Stage1 | Stage2 | Stage3 | OpenClaw |
|---|---|---|---|---|
| op1_product | ✅ PASS | ⏭ SKIP | ⏭ SKIP | ✅ PASS |
| op1_marketing | ✅ PASS | ✅ PASS | ❌ FAIL | ✅ PASS |
| op1_sales | ✅ PASS | ✅ PASS | ✅ PASS | ✅ PASS |
| op1_operations | ✅ PASS | ✅ PASS | ✅ PASS | ✅ PASS |
| op1_ceo | ⏭ SKIP | ⏭ SKIP | ⏭ SKIP | ✅ PASS |

Notes:
- op1_product Stage2/Stage3 were argument-gated validator checks and therefore recorded as skip.
- op1_marketing Stage3 failed in verifier (`exit code 2`) due to missing `campaign_launch` key.
- op1_ceo uses `orchestrator_dryrun` instead of Stage1/2/3.

## Handoff Validation Results

Source: `handoffs/_meta/validation_report.latest.json`

| Contract | Status |
|---|---|
| marketing_to_sales | ✅ PASS |
| operations_to_marketing | ✅ PASS |
| operations_to_marketing_iterate | ✅ PASS |
| operations_to_product | ✅ PASS |
| operations_to_product_iterate | ✅ PASS |
| operations_to_sales | ✅ PASS |
| operations_to_sales_iterate | ✅ PASS |
| product_to_marketing | ✅ PASS |
| sales_to_operations | ✅ PASS |

Summary: 9/9 valid, 0 invalid.

## Reproducibility Results

Source: `test_results/reproducibility_report.json`

| # | Script | Agent | Level | Exit Code | Status |
|---|---|---|---|---|---|
| 1 | `workspaces/op1_operations/scripts/verify_stage1_reproducibility.py` | op1_operations | workspace | 0 | ✅ PASS |
| 2 | `workspaces/op1_operations/scripts/verify_stage2_feedback_reproducibility.py` | op1_operations | workspace | 0 | ✅ PASS |
| 3 | `workspaces/op1_operations/scripts/verify_stage3_reproducibility.py` | op1_operations | workspace | 0 | ✅ PASS |
| 4 | `workspaces/op1_operations/skills/track-traffic-signups-revenue-stage1/scripts/verify_stage1_reproducibility.py` | op1_operations | skill | 0 | ✅ PASS |
| 5 | `workspaces/op1_operations/skills/process-feedback-stage2/scripts/verify_stage2_feedback_reproducibility.py` | op1_operations | skill | 0 | ✅ PASS |
| 6 | `workspaces/op1_operations/skills/iterate-on-product-stage3/scripts/verify_stage3_reproducibility.py` | op1_operations | skill | 0 | ✅ PASS |
| 7 | `workspaces/op1_sales/scripts/verify_reproducibility_stage3.py` | op1_sales | workspace | 0 | ✅ PASS |
| 8 | `workspaces/op1_sales/skills/convert-early-customers-stage3/scripts/verify_reproducibility_stage3.py` | op1_sales | skill | 0 | ✅ PASS |

Summary: 8 pass, 0 fail.

## OpenClaw Invocation Results

Source: `test_results/openclaw_invocation_results.json`

| Agent | Status | Response Length | Notes |
|---|---|---|---|
| op1_product | ✅ PASS | 10557 | `json_status=ok`; `exit_code=-1` from macOS timeout wrapper behavior |
| op1_marketing | ✅ PASS | 10212 | `status=ok`, valid JSON |
| op1_sales | ✅ PASS | 10171 | `status=ok`, valid JSON |
| op1_operations | ✅ PASS | 10226 | `status=ok`, valid JSON |
| op1_ceo | ✅ PASS | 9744 | `status=ok`, valid JSON |

Summary: 5/5 successful invocations.

## CEO Orchestrator Dry-Run

Source: `test_results/ceo_dry_run_results.json`

- Dry-run status: ✅ PASS (`dry_run_exit_code=0`, `dry_run_status=pass`)
- Steps planned: 4
- Artifacts validated:
  - `workspaces/op1_ceo/research/ceo_orchestration/run.latest.json`
  - `workspaces/op1_ceo/research/ceo_orchestration/venture_state.latest.json`
  - `workspaces/op1_ceo/research/ceo_orchestration/orchestrator_summary.latest.json`
- Safety signal: 4 simulation markers found; 0 real-action patterns in stdout.

## Safety Compliance

- no_real_emails: ✅ true
- no_real_deploys: ✅ true
- backup_created: ✅ true
- Evidence:
  - Sales Stage 2 remained simulate-only (`NO_COMMIT_FOUND` safety signal from Task 6 results)
  - OpenClaw safety grep found 0 external delivery references
  - Backup manifest recorded 318 files before execution

## Overall Verdict

Final verdict: **PARTIAL**

Timestamp: `2026-03-07T22:37:27Z`

Rationale:
- Strong overall reliability: all 5 OpenClaw invocations pass, reproducibility is 8/8 pass, handoff contracts are 9/9 valid.
- One blocking failure remains: op1_marketing Stage3 verifier contract mismatch (`campaign_launch` missing).
- Product Stage2 and Stage3 remain intentional skip checks due to argument-gated validators requiring runtime deployment/input context.
