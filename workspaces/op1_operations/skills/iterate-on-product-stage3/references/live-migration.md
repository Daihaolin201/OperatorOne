# Stage3 live migration guide

Goal: keep Stage3 decision/iteration logic stable while replacing simulated rollouts with real experiment platform events.

## Replace adapters

Edit `config/stage3_iteration_adapters.v1.json`:
- keep stage1/stage2 adapters enabled
- switch `live_experiment_platform.enabled` to true
- point path to real event export (or adapter output)

## Migration checklist

1. Keep contracts and decision policy unchanged on first live run.
2. Keep weights and guardrail thresholds unchanged on first live run.
3. Run with fixed `STAGE3_AS_OF` and strict reproducibility.
4. Compare decision distribution (ship/iterate/rollback/park) before and after migration.
5. Recalibrate only after stable live cycles.

## Non-negotiable guardrails

- Do not remove guardrail checks when migrating to live systems.
- Do not alter decision precedence in same release as source migration.
- Do not ship without reproducibility pass for delivery builds.
