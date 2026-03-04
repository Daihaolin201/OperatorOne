# Stage 1 — Marketing SEO Experiments (Continuous Shadow)

Canonical outputs:
- `run.latest.json`
- `state.latest.json`
- `context_index.latest.json`
- `keyword_graph.latest.csv`
- `experiments.backlog.latest.json`
- `experiments.queue.latest.json`
- `scoreboard.latest.json`
- `decision_log.latest.md`

Mode:
- `shadow` (default)
- `publish=false`
- `index=false`
- `continuous=true`

Capability contract:
- Project-agnostic ingestion from upstream `op1_product` artifacts.
- Continuous queue lifecycle: `candidate -> drafted -> scored -> ready -> shadow_validated -> promoted|dropped`.
- No hard binding to a single business project.
