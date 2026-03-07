# Z.AI Integration Evidence

This folder stores machine-generated verification artifacts proving that OperatorOne is using Z.AI GLM as a core runtime component.

Primary report:

- `core_integration_report.latest.json`

Generate / refresh:

```bash
python3 scripts/verify_zai_core_integration.py --repo-root . --profile operatorone --probe-all-agents
```

Strict probe (temporarily disable fallbacks, then auto-restore):

```bash
python3 scripts/verify_zai_core_integration.py \
  --repo-root . \
  --profile operatorone \
  --probe-all-agents \
  --probe-without-fallback
```

Notes:

- Reports include provider/model metadata and probe results.
- Reports never include raw API key values.
