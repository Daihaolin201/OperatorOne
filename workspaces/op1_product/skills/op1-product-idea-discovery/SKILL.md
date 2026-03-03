---
name: op1-product-idea-discovery
description: Discover startup opportunities from market signals and user pain evidence. Use when generating idea longlists, collecting problem evidence, mapping target segments, and building stage-1 opportunity records for product selection.
---

# Idea Discovery

1. Define search scope (industry, role, company size, geography, urgency window).
2. Run primary signal collection script:
   - `python3 scripts/search_startup_signals.py`
3. Run secondary-source collection script:
   - `python3 scripts/search_secondary_sources.py`
4. Build Stage-1 opportunities:
   - `python3 scripts/build_stage1_opportunities.py`
5. Validate each opportunity against `../../../framework/templates/stage1_opportunity_records.template.json` structure.
6. Capture only evidence-backed claims; reject speculation.
7. Fill hard-gate checks:
   - buyer clear
   - problem evidenced
   - reachable users
   - MVP in 14 days
7. Write output to `research/stage1_opportunity_records.json`.

## Quality bar
- Each opportunity has a specific buyer and workflow context.
- Each opportunity includes at least one time-loss or money-loss signal.
- Each opportunity includes cross-source corroboration (min 2 distinct sources when trust config requires it).
- Each opportunity includes a realistic first-20-users acquisition path.
