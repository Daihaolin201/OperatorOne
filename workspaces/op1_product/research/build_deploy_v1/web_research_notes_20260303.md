# Web Research Notes — Build & Deploy Hardening (2026-03-03)

## Sources consulted
1. Vercel CLI deploy docs: https://vercel.com/docs/cli/deploy
2. Twelve-Factor App (Config): https://12factor.net/config
3. Practical testing perspective: https://martinfowler.com/articles/practical-test-pyramid.html

## Applied decisions
- Keep deployment script parse-friendly (stdout URL + exit-code checks).
- Keep credentials out of code and generated artifacts.
- Add layered verification:
  - smoke tests for reachability/API health
  - business-rule tests for domain behavior

## Impact on framework
- Introduced adapter-driven project spec.
- Added business-test stage to run pipeline.
- Upgraded contract from v1 to v1.1 for multi-project robustness.
