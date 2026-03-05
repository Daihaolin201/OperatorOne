# Compliance and Safety Gates

Apply these gates before any commit-mode dispatch.

## Hard gates
1. Approved batch exists and `approved=true`.
2. Suppression list is loaded and enforced.
3. Low-fit (`needs_review`) leads are excluded from dispatch.
4. Frequency cap is enforced (`frequency_cap_hours`).
5. Daily cap is enforced (`max_send_per_day`).

## Channel/data readiness gates
1. Channel account is configured in runtime (if direct provider send is expected).
2. Contact target exists for direct route (`email` or `linkedin` target field).
3. If no direct target, fallback only to manual bundle.

## Policy guardrails
- Keep subject lines non-deceptive.
- Support unsubscribe handling and persist opted-out leads.
- Do not re-send to suppressed leads.
- Track every outreach assumption and evidence URL.
