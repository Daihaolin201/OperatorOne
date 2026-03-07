# Stage2 workflow (Process feedback)

## 1) Bootstrap defaults

```bash
python3 workspaces/op1_operations/skills/process-feedback-stage2/scripts/bootstrap_stage2_feedback_contracts.py --repo-root /path/to/OperatorOne
```

Use `--force` to overwrite existing workspace defaults.

## 2) Run pipeline

```bash
python3 workspaces/op1_operations/skills/process-feedback-stage2/scripts/run_stage2_feedback.py --repo-root /path/to/OperatorOne
```

Execution order:
1. `ingest_stage2_feedback.py`
2. `normalize_stage2_feedback.py`
3. `cluster_stage2_feedback.py`
4. `score_stage2_feedback.py`
5. `prioritize_stage2_feedback.py`
6. `build_stage2_feedback_scoreboard.py`
7. `verify_stage2_feedback_reproducibility.py`

## 3) Validate completion

Required outputs under `workspaces/op1_operations/research/stage2_feedback`:
- `stage2_feedback_scoreboard.latest.json`
- `stage2_feedback_scoreboard.latest.md`
- `weekly_feedback_snapshot.latest.md`
- `reproducibility_report.latest.json`
- `run_stage2.latest.json`

Success criteria:
- `run_stage2.latest.json.status == passed`
- `reproducibility_report.latest.json.status == passed`
- `capability_status` in scoreboard shows all implemented

## 4) Deterministic strict rerun

```bash
export STAGE2_AS_OF="2026-03-05T12:00:00Z"
python3 workspaces/op1_operations/skills/process-feedback-stage2/scripts/run_stage2_feedback.py \
  --repo-root /path/to/OperatorOne \
  --strict-repro
```

Require strict pass with `changed_files_vs_baseline = []`.
