---
name: op1-product-idea-discovery
description: Discover startup opportunities from market signals and user pain evidence. Use when generating idea longlists, collecting corroborated problem evidence, mapping target segments, and producing Stage-1 opportunity records.
---

# Idea Discovery (Stage 1)

1. Define search scope (industry, role, company size, geography, urgency window).
2. Collect primary signals:
   - `python3 scripts/search_startup_signals.py`
3. Collect secondary corroboration:
   - `python3 scripts/search_secondary_sources.py`
4. Build Stage-1 opportunities:
   - `python3 scripts/build_stage1_opportunities.py`
5. Validate structure against:
   - `../../framework/templates/stage1_opportunity_records.template.json`
6. Keep only evidence-backed claims; remove speculation.
7. Ensure each opportunity has hard-gate fields filled (`buyer_clear`, `problem_evidenced`, `reachable_users`, `mvp_in_14_days`).
8. Write output to `research/stage1_opportunity_records.json`.

## Quality bar
- Each opportunity names a concrete buyer and workflow context.
- Each opportunity includes at least one money-loss or time-cost signal.
- Cross-source corroboration is present when trust config requires it.
- First-20-users acquisition path is explicit and realistic.
