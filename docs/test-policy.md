# OperatorOne Test Policy

> **Status**: Active — established 2026-03-07  
> **Scope**: All code in `apps/`, `packages/`, and `scripts/` under the OperatorOne monorepo

---

## 1. Test Level Ownership

| Level | Framework | Owners | Location | When to Run |
|-------|-----------|--------|----------|-------------|
| **Unit** | Vitest | Per-package / per-app developers | `apps/*/src/**/*.test.{ts,tsx}`, `packages/*/src/**/*.test.{ts,tsx}` | Every commit; CI `test` job |
| **Integration** | Vitest | Cross-module feature teams | `apps/*/src/**/*.integration.test.{ts,tsx}`, `packages/*/src/**/*.integration.test.{ts,tsx}` | Every PR; CI `test` job |
| **E2E** | Playwright | Full-stack / QA | `apps/*/e2e/**/*.spec.{ts,tsx}` | Pre-merge on main; CI `e2e` job (future) |

### Supplemental: Python Validators

| Script | Type | Owner | Command |
|--------|------|-------|---------|
| `scripts/validate_handoffs.py` | Contract validation | Automation framework | `python3 scripts/validate_handoffs.py --repo-root .` |
| `scripts/change_hygiene_guard.py` | Pre-commit hygiene | All contributors | `python3 scripts/change_hygiene_guard.py --staged` |
| `workspaces/op1_product/scripts/landing_contract_test.py` | Landing contract | op1_product team | `python3 scripts/landing_contract_test.py --landing-package <path> --out <report>` |

---

## 2. Framework Decisions

### Frontend (apps/ and packages/)

| Concern | Decision | Rationale |
|---------|----------|-----------|
| Unit + Integration runner | **Vitest** | Native Vite integration; fast HMR-aware watch mode; ESM-first |
| Component testing | **Vitest** + React Testing Library | Co-located with source; no separate Jest config needed |
| E2E testing | **Playwright** | Both apps (platform-portal + product-ui); multi-browser; CI-ready |
| Coverage | **Vitest** `coverage.provider = 'v8'` | Low overhead; lcov output for CI |
| TypeScript | **tsc --noEmit** (separate typecheck job) | Type errors separated from test failures |

### Python (scripts/)

| Concern | Decision | Rationale |
|---------|----------|-----------|
| Validator scripts | **pytest** (future) + direct script execution (now) | Existing validators are standalone CLI scripts; pytest integration planned for T9 |
| Contract validation | `validate_handoffs.py` (production validator) | Already stable; runs in CI `contracts` job |

---

## 3. Test Organization Rules

### File naming

```
src/
  components/
    Button.tsx
    Button.test.tsx          # unit test — same directory
    Button.integration.test.tsx  # integration test — same directory

e2e/
  platform-portal/
    auth.spec.ts             # e2e test — in apps/platform-portal/e2e/
  product-ui/
    landing.spec.ts          # e2e test — in apps/product-ui/e2e/
```

### Rules

1. **Unit tests live next to source files** — no `__tests__` subdirectories unless the module has 10+ test files.
2. **Integration tests** use the `.integration.test.ts` suffix and may import from sibling packages via `@op1/*` aliases.
3. **E2E tests** live in `apps/<app-name>/e2e/` and must not import production source code directly (use API calls / DOM only).
4. **No cross-app imports** — `apps/platform-portal` must never import from `apps/product-ui` or vice versa. Shared logic belongs in `packages/`.
5. **Shared test utilities** belong in `packages/test-utils` (to be created in T9).
6. **Every new public function/component** shipped to production must have at least one unit test.
7. **Python validator scripts** must exit 0 on a clean repo state; non-zero exits block CI.

---

## 4. CI Job Map

| CI Job | What it runs | Status |
|--------|-------------|--------|
| `lint` | ESLint on `apps/` and `packages/` | Placeholder — active after T8 |
| `typecheck` | `tsc --noEmit` on all TS packages | Placeholder — active after T8 |
| `test` | Vitest unit + integration | Placeholder — active after T9 |
| `contracts` | `python3 scripts/validate_handoffs.py --repo-root .` | **Active now** |
| `hygiene` | `python3 scripts/change_hygiene_guard.py --staged` | Pre-commit; documented in CI |

---

## 5. Pre-commit Hook

The `change_hygiene_guard.py` script is the designated pre-commit quality gate.  
It **blocks commits** that mix source code changes with generated artifact churn in the same changeset.

Install as a pre-commit hook:
```bash
ln -sf ../../scripts/change_hygiene_guard_hook.sh .git/hooks/pre-commit
```

*(Hook wrapper script to be created in T9.)*

---

## 6. Coverage Targets (enforced in T9+)

| Scope | Minimum Line Coverage |
|-------|-----------------------|
| `packages/ui` | 80% |
| `packages/i18n` | 90% |
| `packages/types` | 95% |
| `apps/platform-portal` | 70% |
| `apps/product-ui` | 70% |

Coverage is **informational only** until T9; thresholds are enforced from T9 onwards.

---

*This policy is owned by the OperatorOne automation-framework team.*  
*Last updated: 2026-03-07*
