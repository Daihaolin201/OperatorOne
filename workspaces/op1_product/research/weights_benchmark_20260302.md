# Scoring Weights Benchmark (2026-03-02)

## External references reviewed
1. Intercom — RICE framework (Reach, Impact, Confidence, Effort)
   - https://www.intercom.com/blog/rice-simple-prioritization-for-product-managers/
2. ProductPlan — ICE model (Impact, Confidence, Ease) + caveats
   - https://www.productplan.com/glossary/ice-scoring-model/
3. ProductPlan — RICE model overview
   - https://www.productplan.com/glossary/rice-scoring-model/
4. SVPG (Marty Cagan) — Four Big Risks (value, usability, feasibility, business viability)
   - https://www.svpg.com/four-big-risks/
5. Interaction Design Foundation + NNGroup — desirability/feasibility/viability framing
   - https://www.interaction-design.org/literature/topics/design-thinking
   - https://www.nngroup.com/articles/design-thinking/
6. First Round (Superhuman PMF engine) — leading indicator + confidence in evidence
   - https://review.firstround.com/how-superhuman-built-an-engine-to-find-product-market-fit/

---

## Assessment of current weights
Current:
- pain_intensity 0.25
- willingness_to_pay 0.25
- mvp_speed 0.20
- acquisition_reachability 0.15
- competitive_whitespace 0.10
- recurring_usage 0.05

Verdict: **Reasonable baseline for early revenue search**.
- Strong on value + viability (pain + pay = 50%)
- Includes effort/speed and reach dimensions (RICE-consistent directionally)
- Gap: confidence is not explicit in score (only implicit via evidence gates)
- Gap: recurring usage is slightly underweighted for MRR-oriented goals

---

## Recommended v2 (industry-common + advanced hybrid)
### Base weights
- pain_intensity: **0.24**
- willingness_to_pay: **0.24**
- mvp_speed: **0.18**
- acquisition_reachability: **0.16**
- competitive_whitespace: **0.08**
- recurring_usage: **0.10**

Rationale:
- Keep value/viability dominant (48%)
- Keep speed+reach high for fast experimentation (34%)
- Raise recurring for MRR context
- Lower whitespace to avoid over-indexing on abstract differentiation early

### Confidence adjustment (recommended)
Apply multiplier after base score (RICE-aligned):
- High confidence: ×1.00
- Medium confidence: ×0.80
- Low confidence: ×0.50

Confidence derived from:
- distinct source count
- evidence quality
- interview/real user signal presence

Final:
`final_score = base_weighted_score * confidence_multiplier`

---

## Practical migration path
1. Keep current schema, update only base weights first.
2. Add `confidence_level` in stage2 decision log.
3. Multiply base score by confidence multiplier.
4. Re-rank and compare with previous top candidates.
