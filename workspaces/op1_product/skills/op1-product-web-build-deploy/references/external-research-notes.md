# External Research Notes (2026-03-03)

These references informed v1.1 hardening decisions.

1. Vercel CLI deploy docs
   - URL: https://vercel.com/docs/cli/deploy
   - Useful points used:
     - CLI deploy URL is emitted on stdout.
     - CI-style scripting should check exit code and parse stderr/stdout separately.

2. Twelve-Factor App: Config
   - URL: https://12factor.net/config
   - Useful points used:
     - Keep environment-specific config out of code.
     - Avoid embedding credentials in repository files.

3. Practical test automation perspective
   - URL: https://martinfowler.com/articles/practical-test-pyramid.html
   - Useful points used:
     - Add layered tests with fast feedback loops.
     - Keep fast endpoint checks (smoke) plus behavior checks (business tests).

4. Vercel CLI rollback docs
   - URL: https://vercel.com/docs/cli/rollback
   - Useful points used:
     - `vercel rollback` can revert production to previous deployment.
     - Rollback should be treated as an explicit post-failure safety step (best effort in automation).

5. Shopify landing page guide
   - URL: https://www.shopify.com/blog/landing-page
   - Useful points used:
     - Good landing pages keep one clear goal and one obvious CTA.
     - Hero + value proposition + CTA are baseline structure.

6. Unbounce landing page best practices
   - URL: https://unbounce.com/landing-page-articles/landing-page-best-practices/
   - Useful points used:
     - Keep message match, minimize distractions, and run iterative tests.
     - Treat templates as starting points, then optimize with evidence.

7. Atomic Design (Brad Frost)
   - URL: https://bradfrost.com/blog/post/atomic-web-design/
   - Useful points used:
     - Build interfaces as modular systems (atoms → molecules → organisms).
     - Reusable components improve consistency and scalability.

8. Design systems overview (Interaction Design Foundation)
   - URL: https://www.interaction-design.org/literature/topics/design-systems
   - Useful points used:
     - Design systems combine reusable components + standards.
     - Teams use them to scale consistent digital output.

Implementation mapping:
- add explicit deployment health gate before broader tests.
- split spec flow into project spec (business logic) and page spec (layout/module strategy).
- scaffold pages by module order/profile instead of one fixed skeleton.
- keep one explicit primary CTA and validate uniqueness via page-strategy tests.
- smoke tests validate deployment/service health quickly.
- business-rule tests validate domain behavior from adapter rules.
- on post-deploy pipeline failure, trigger best-effort rollback attempt.
- run report includes layered checks + safety metadata for auditability.

9. MDN responsive design guidance
   - URL: https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/CSS_layout/Responsive_Design
   - Useful points used:
     - Responsive design should cover known and unknown device sizes.
     - Media-query breakpoints should be content-driven, not device-name hardcoding.

10. web.dev responsive web design basics
   - URL: https://web.dev/articles/responsive-web-design-basics
   - Useful points used:
     - Require viewport meta for correct mobile/tablet rendering behavior.
     - Prevent overflow and include responsive CSS markers as baseline checks.

11. web.dev Core Web Vitals
   - URL: https://web.dev/articles/vitals
   - Useful points used:
     - Keep explicit LCP/INP/CLS budget hooks in test metadata.

Implementation mapping (landing capability extension):
- add Mode-C landing contract with preflight gates (opportunity/scope/evidence).
- emit evidence traceability map before downstream handoff.
- include multi-device compatibility baseline checks in page-strategy tests.
- keep performance budget hooks in `page_spec.testing` for auditability.

12. OWASP HTTP Headers Cheat Sheet
   - URL: https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html
   - Useful points used:
     - Add a minimal secure header baseline (nosniff/frame/referrer/CSP) for browser-rendered pages.

13. OWASP Input Validation Cheat Sheet
   - URL: https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html
   - Useful points used:
     - Enforce server-side min/max length and syntactic validation for endpoint inputs.

14. MDN security header references
   - URLs:
     - https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/X-Content-Type-Options
     - https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/X-Frame-Options
     - https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Referrer-Policy
     - https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy
   - Useful points used:
     - Validate exact header intent and include policy fragments in deployment baseline checks.
