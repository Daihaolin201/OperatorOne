# Manual Review Playbook

## Goal
Move Stage2 assets from `review_ready` to either:
- `approved` (ready for downstream coordination)
- `needs_revision` (requires rework)

## Typical flow
1. Run generation cycle:
   - `./scripts/run_marketing_content_stage2.sh --force`
2. Inspect queue and drafts:
   - `research/stage2_content_publish/publish.queue.latest.json`
   - `research/stage2_content_publish/drafts/*.md`
3. Apply decisions:
   - approve all: `./scripts/review_marketing_content_stage2.sh --approve-all --note "editorial pass"`
   - mixed: `--approve ... --reject ... --reason ...`
4. Verify contract:
   - `python3 {baseDir}/scripts/verify_stage2_contract.py`

## Decision guidance
Approve when:
- content intent/angle aligns with selected keyword and ICP
- source pointers are present
- QA checks pass and no policy risk flags are active

Request revision when:
- framing is weak for the target intent
- supporting evidence should be tightened or clarified
- wording makes overconfident claims

## Audit trail
Each review action writes:
- `research/stage2_content_publish/review_log.latest.json`
- `content.backlog.latest.json.last_manual_review`
- `publish.queue.latest.json.last_manual_review`
