# Live migration guide (Stage2)

Goal: keep Stage2 scoring/queue logic stable while replacing simulated adapters with live systems.

## Replace adapters

Edit `config/feedback_source_adapters.v1.json`:
- disable simulated adapters (`enabled=false`)
- enable live adapters with same canonical fields

Typical live replacements:
- outreach replies -> CRM/email provider event export
- conversion events -> CRM lifecycle/billing events
- pipeline pains -> interview/support transcripts
- product runtime feedback -> in-app feedback events

## Migration checklist

1. Keep feedback contract and taxonomy unchanged during migration.
2. Keep priority weights unchanged for first live run.
3. Run deterministic strict check with fixed `STAGE2_AS_OF`.
4. Compare scoreboards and explain major shifts by source composition.
5. Recalibrate thresholds only after at least one stable live cycle.

## Non-negotiable guardrails

- Do not change formulas and data source in the same release.
- Do not remove source traceability (`source_adapter`, `source_ref`).
- Do not bypass reproducibility checks for delivery.
