---
name: op1-marketing-content-publish-stage2
description: Run and operate OperatorOne Marketing Stage2 content publishing in shadow/review mode. Use when asked to publish content without auto-posting, generate Stage2 drafts from Stage1 SEO outputs, apply manual approve/revision decisions, verify queue integrity, or update marketing_to_sales handoff statuses.
---

# Stage2 Content Publish Operator (Shadow + Manual Review)

## Objective
Build and operate Stage2 content publishing as an experiment loop:
- Generate drafts from Stage1 SEO queue
- Run quality gates
- Route items into `approved` / `review_ready` / `needs_revision`
- Keep auto publish disabled
- Sync `../../handoffs/marketing_to_sales.json`

## Run Stage2 generation
From workspace root:

```bash
./scripts/run_marketing_content_stage2.sh
```

Useful variants:

```bash
# Force recompute
./scripts/run_marketing_content_stage2.sh --force

# Include Stage1 hold candidates
./scripts/run_marketing_content_stage2.sh --force --include-hold

# Raise score floor for stricter QA
./scripts/run_marketing_content_stage2.sh --force --min-score 90
```

## Apply manual review decisions
Use manual review script (no auto publish involved):

```bash
# Approve all review-ready items
./scripts/review_marketing_content_stage2.sh --approve-all --note "editorial pass"

# Mixed decision batch
./scripts/review_marketing_content_stage2.sh \
  --approve cnt_a,cnt_b \
  --reject cnt_c \
  --reason "tighten evidence" \
  --note "pass 1"
```

## Validate outputs
Run deterministic contract checks:

```bash
python3 {baseDir}/scripts/verify_stage2_contract.py
```

Interpretation:
- `checks_failed = 0` => output contract is consistent
- non-zero failures => inspect `publish.queue.latest.json`, `content.backlog.latest.json`, and `run.latest.json`

## Required artifact set
See `references/output-contract.md` for full contract.

Primary artifacts:
- `research/stage2_content_publish/run.latest.json`
- `research/stage2_content_publish/state.latest.json`
- `research/stage2_content_publish/content.backlog.latest.json`
- `research/stage2_content_publish/publish.queue.latest.json`
- `research/stage2_content_publish/qa.latest.json`
- `research/stage2_content_publish/decision_log.latest.md`
- `research/stage2_content_publish/review_log.latest.json`
- `research/stage2_content_publish/drafts/`

## Guardrails
- Keep `auto_publish=false` in this stage.
- Treat Stage2 as generation + review orchestration only.
- If Stage1 is unhealthy (`run.latest.json.status` not `passed|no_change`), stop and report upstream status.
- If completeness gate blocks the run, report missing input requirements from `run.latest.json.input_sync.completeness`.

## References
- `references/output-contract.md`
- `references/review-playbook.md`
