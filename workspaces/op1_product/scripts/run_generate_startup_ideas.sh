#!/usr/bin/env bash
set -euo pipefail

# 1) collect market signals
python3 scripts/search_startup_signals.py

# 2) collect secondary-source corroboration signals
python3 scripts/search_secondary_sources.py

# 3) build stage-1 opportunity records
python3 scripts/build_stage1_opportunities.py

# 4) produce stage-2 scoring (heuristic baseline)
python3 scripts/score_stage2.py

echo "Pipeline complete."
