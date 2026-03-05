# Industry benchmark notes used in Stage1 design

The implementation aligns with commonly recommended patterns across modern analytics stacks:

- **Tracking plan first** (event/property contract before instrumentation)
- **Canonical event model** (event_name + timestamp + distinct_id + properties)
- **Attribution layering** (first-touch, session-touch, event-touch)
- **MRR movement accounting** (new/expansion/contraction/churn/reactivation)
- **Metric centralization** (single dictionary to prevent metric drift)
- **Data quality gates** (schema completeness, duplicates, freshness)
- **Reproducibility checks** (hash + required-key validation)

This is implemented in adapter form so that simulated sources can be replaced with live sources without changing metric definitions.
