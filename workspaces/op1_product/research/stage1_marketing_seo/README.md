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

Canonical input artifacts:
- `input/product_snapshot.latest.json`
- `input/delta.latest.json`
- `input/mirror.latest/`

Mode:
- `shadow` (default)
- `publish=false`
- `index=false`
- `continuous=true`

Capability contract:
- Full-product ingestion first (lossless mirror), then SEO experiment computation.
- No pre-filtering of product artifacts before sync.
- Continuous queue lifecycle: `candidate -> drafted -> scored -> ready -> shadow_validated -> promoted|dropped`.
- No hard binding to a single business project.
