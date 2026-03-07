# Landing Capability Research Notes (2026-03-03)

## Objective
Support `create_landing_pages_v1` design decisions for:
- conversion-focused page structure,
- evidence-backed messaging,
- multi-device compatibility baseline,
- performance + security constraints.

## Sources reviewed
1. **NNGroup — Homepage vs. Landing Page**
   - https://www.nngroup.com/articles/homepage-vs-landing-page/
   - Use: one-goal landing intent; reduce competing actions.

2. **Unbounce — Landing page best practices / Attention ratio**
   - https://unbounce.com/landing-page-articles/landing-page-best-practices/
   - https://unbounce.com/conversion-glossary/definition/attention-ratio/
   - Use: single primary CTA and message alignment.

3. **Google Ads Help — Landing page experience guidance**
   - https://support.google.com/google-ads/answer/2454010?hl=en
   - Use: relevance, transparency, navigation quality constraints.

4. **MDN — Responsive design**
   - https://developer.mozilla.org/en-US/docs/Learn_web_development/Core/CSS_layout/Responsive_Design
   - Use: media-query, fluid layout, content-fit baseline.

5. **web.dev — Responsive web design basics**
   - https://web.dev/articles/responsive-web-design-basics
   - Use: viewport meta and responsive content behavior.

6. **web.dev — Core Web Vitals**
   - https://web.dev/articles/vitals
   - https://web.dev/articles/lcp
   - https://web.dev/articles/inp
   - https://web.dev/articles/cls
   - Use: LCP/INP/CLS budget hooks in page spec.

7. **NNGroup — Scannable text / reading behavior**
   - https://www.nngroup.com/articles/scannable-text/
   - https://www.nngroup.com/articles/how-users-read-on-the-web/
   - Use: concise hierarchy and skimmable section checks.

8. **OWASP — HTTP headers / input validation**
   - https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html
   - https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html
   - Use: server-side validation, baseline secure response headers.

9. **MDN — security header references**
   - https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/X-Content-Type-Options
   - https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/X-Frame-Options
   - https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Referrer-Policy
   - https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Content-Security-Policy
   - Use: concrete header semantics and policy composition.

## Implementation mapping
- **single_primary_cta** gate ← conversion/attention-ratio guidance.
- **message_match_with_entry_intent** gate ← ad/landing continuity principle.
- **multi_device_compatibility_baseline** gate ← viewport + responsive markers + declared desktop/tablet/mobile profiles.
- **performance_baseline_hooks_present** gate ← explicit LCP/INP/CLS hooks.
- **security_headers_baseline_hooks_present** gate ← expected response-header baseline in page spec + page-strategy test.

## Notes
- External references are used as design guidance, not executable instructions.
- Landing generation and validation remain workspace-local and reversible.
