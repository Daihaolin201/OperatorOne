# Frontend Stack Baseline — OperatorOne

> **Status**: Authoritative  
> **Applies to**: `apps/platform-portal` · `apps/product-ui`  
> **Last updated**: 2026-03-07  
> **Rule**: Both apps MUST use identical tool versions. Divergence is forbidden.

---

## 1. Package Manager

| Tool | Version | Notes |
|------|---------|-------|
| **pnpm** | `^8.15.0` | Workspace root manager. `npm` and `yarn` are forbidden. |

Workspace root requires `pnpm-workspace.yaml` at repo root:

```yaml
# pnpm-workspace.yaml
packages:
  - "apps/*"
  - "packages/*"
```

All installs: `pnpm install`. CI must use `pnpm` only.

---

## 2. Workspace Structure

```
Code/OperatorOne/
├── pnpm-workspace.yaml          # pnpm monorepo declaration
├── package.json                 # root — scripts + devDependency hoisting
├── apps/
│   ├── platform-portal/         # Internal: dev / debug / demo dashboard
│   │   ├── package.json
│   │   ├── vite.config.ts
│   │   └── src/
│   └── product-ui/              # External: customer-facing product
│       ├── package.json
│       ├── vite.config.ts
│       └── src/
└── packages/
    ├── i18n/                    # Shared translation strings + i18next config
    │   └── package.json         # name: @op1/i18n
    └── api-client/              # Shared typed API client
        └── package.json         # name: @op1/api-client
```

> **Rule**: `apps/platform-portal` and `apps/product-ui` MUST NOT import from each other.  
> Both may only consume from `packages/*`.

---

## 3. Framework

| Tool | Version | Notes |
|------|---------|-------|
| **React** | `^18.3.0` | Functional components + hooks only. Class components forbidden. |
| **ReactDOM** | `^18.3.0` | Must match React version exactly. |
| **TypeScript** | `^5.4.0` | Strict mode enabled. `"strict": true` in `tsconfig.json`. |

Both apps share the same `tsconfig.base.json` at the root, then extend locally.

---

## 4. Build Tool

| Tool | Version | Notes |
|------|---------|-------|
| **Vite** | `^5.2.0` | Dev server + production bundler. Webpack and CRA are forbidden. |
| **@vitejs/plugin-react** | `^4.2.0` | Required for React Fast Refresh in Vite. |

**Build output**: Both apps build to static files (`dist/`). Each app is independently deployable — no server-side rendering.

```bash
# Per-app build
pnpm --filter platform-portal build   # → apps/platform-portal/dist/
pnpm --filter product-ui build        # → apps/product-ui/dist/
```

---

## 5. Testing

### 5.1 Unit & Integration — Vitest

| Tool | Version | Notes |
|------|---------|-------|
| **Vitest** | `^1.6.0` | Co-located with Vite config; replaces Jest. |
| **@testing-library/react** | `^15.0.0` | Component testing utilities. |
| **@testing-library/user-event** | `^14.5.0` | User interaction simulation. |
| **jsdom** | `^24.0.0` | Browser environment for Vitest. |

Test files: `src/**/*.test.ts` / `src/**/*.test.tsx` / `src/**/*.spec.ts`

```bash
pnpm --filter platform-portal test
pnpm --filter product-ui test
```

### 5.2 End-to-End — Playwright

| Tool | Version | Notes |
|------|---------|-------|
| **@playwright/test** | `^1.44.0` | Cross-browser e2e. Runs against built `dist/` served locally. |

E2e tests live in `apps/<name>/e2e/`. Each app maintains its own Playwright config.

```bash
pnpm --filter platform-portal e2e
pnpm --filter product-ui e2e
```

---

## 6. Linting & Formatting

| Tool | Version | Notes |
|------|---------|-------|
| **ESLint** | `^8.57.0` | Shared config at root. Extended per app. |
| **eslint-plugin-react** | `^7.34.0` | React-specific rules. |
| **eslint-plugin-react-hooks** | `^4.6.0` | Enforces Rules of Hooks. |
| **@typescript-eslint/parser** | `^7.9.0` | TypeScript-aware ESLint parser. |
| **@typescript-eslint/eslint-plugin** | `^7.9.0` | TypeScript lint rules. |
| **Prettier** | `^3.2.0` | Code formatter. ESLint defers formatting to Prettier. |
| **eslint-config-prettier** | `^9.1.0` | Disables ESLint rules that conflict with Prettier. |

Root `.eslintrc.base.json` is shared. Each app's `.eslintrc.json` extends it.  
Root `.prettierrc` is shared across all packages.

```bash
pnpm lint          # lint all workspaces
pnpm format        # format all workspaces
```

---

## 7. Internationalisation (i18n)

| Tool | Version | Notes |
|------|---------|-------|
| **i18next** | `^23.11.0` | Core i18n engine. |
| **react-i18next** | `^14.1.0` | React bindings for i18next. |
| **i18next-resources-to-backend** | `^1.2.0` | Lazy-loads locale JSON on demand. |

### 7.1 Locale Package

Translation strings live **exclusively** in `packages/i18n`:

```
packages/i18n/
├── package.json          # name: @op1/i18n
├── src/
│   ├── index.ts          # exports initI18n(), t, useTranslation re-exports
│   ├── locales/
│   │   ├── en/
│   │   │   └── common.json
│   │   └── zh/
│   │       └── common.json
│   └── config.ts         # shared i18next config
```

Both apps import `@op1/i18n` and call `initI18n()` at app bootstrap. Neither app may define its own translation strings inline.

### 7.2 Routing with Locale Prefix

- **Pattern**: `/:locale/*` where `locale ∈ { "en", "zh" }`
- `https://app.example.com/en/dashboard`
- `https://app.example.com/zh/dashboard`
- Redirect `/` → `/en/` (default locale) on both apps.

---

## 8. Routing

| Tool | Version | Notes |
|------|---------|-------|
| **react-router-dom** | `^6.23.0` | Declarative routing. v5 and below are forbidden. |

Both apps use `createBrowserRouter` (data router API). Each app wraps all routes under a locale-aware layout route that reads `:locale` from the URL and passes it to `@op1/i18n`.

```tsx
// Canonical route structure
createBrowserRouter([
  {
    path: "/:locale",
    element: <LocaleLayout />,     // reads :locale, calls i18n.changeLanguage
    children: [
      { path: "dashboard", element: <Dashboard /> },
      // ... app-specific routes
    ],
  },
  { index: true, element: <Navigate to="/en" replace /> },
])
```

---

## 9. Root `package.json` Scripts (canonical)

```json
{
  "scripts": {
    "dev:portal":    "pnpm --filter platform-portal dev",
    "dev:product":   "pnpm --filter product-ui dev",
    "build:portal":  "pnpm --filter platform-portal build",
    "build:product": "pnpm --filter product-ui build",
    "test":          "pnpm -r test",
    "e2e":           "pnpm -r e2e",
    "lint":          "pnpm -r lint",
    "format":        "pnpm -r format",
    "typecheck":     "pnpm -r typecheck"
  }
}
```

---

## 10. Pinned Version Summary

All versions below must be identical across `apps/platform-portal` and `apps/product-ui`.

| Dependency | Pinned Range | Category |
|-----------|-------------|---------|
| `react` | `^18.3.0` | Framework |
| `react-dom` | `^18.3.0` | Framework |
| `react-router-dom` | `^6.23.0` | Routing |
| `i18next` | `^23.11.0` | i18n |
| `react-i18next` | `^14.1.0` | i18n |
| `typescript` | `^5.4.0` | Language |
| `vite` | `^5.2.0` | Build |
| `@vitejs/plugin-react` | `^4.2.0` | Build |
| `vitest` | `^1.6.0` | Testing |
| `@playwright/test` | `^1.44.0` | Testing |
| `eslint` | `^8.57.0` | Lint |
| `prettier` | `^3.2.0` | Format |
| `pnpm` (engine) | `^8.15.0` | Package manager |

> **Enforcement**: A root-level CI step must run `pnpm ls --depth=0` for both apps and diff the versions of the above dependencies. Any mismatch fails the build.

---

## 11. Forbidden Patterns

The following are **hard rules**. Any violation must be rejected in code review and CI.

| # | Forbidden Pattern | Reason |
|---|------------------|--------|
| 1 | `import ... from '../../apps/product-ui/...'` (cross-app imports) | Apps are independently deployable; shared code must live in `packages/`. |
| 2 | Inline i18n strings (e.g., `<p>Welcome</p>` hardcoded in JSX) | All user-facing strings must go through `t()` from `@op1/i18n`. |
| 3 | Divergent tool versions between `apps/platform-portal` and `apps/product-ui` | Version parity is required; divergence creates hidden integration risks. |
| 4 | Using `npm` or `yarn` instead of `pnpm` | Only pnpm is the authorised package manager for this monorepo. |
| 5 | Routes without locale prefix (e.g., `/dashboard` instead of `/en/dashboard`) | Both apps must use `/:locale/*` to support bilingual routing. |
| 6 | Defining translation namespaces outside `packages/i18n/src/locales/` | Centralised strings prevent duplication and translation drift. |
| 7 | Class components in React code | Functional components + hooks only. Class components are a maintenance liability. |

---

## 12. Build Output Contract

Both apps must produce a self-contained static `dist/` directory:

```
apps/platform-portal/dist/
├── index.html
├── assets/
│   ├── index-[hash].js
│   └── index-[hash].css
└── ...

apps/product-ui/dist/
├── index.html
├── assets/
│   ├── index-[hash].js
│   └── index-[hash].css
└── ...
```

- No server-side rendering.
- No shared `dist/` — each app deploys independently.
- Both apps must pass a Lighthouse CI score ≥ 80 on Performance, Accessibility, Best Practices.

---

## 13. CI Enforcement Checklist

Every pull request touching `apps/` or `packages/` must pass:

- [ ] `pnpm typecheck` — zero TypeScript errors
- [ ] `pnpm lint` — zero ESLint errors
- [ ] `pnpm test` — all Vitest tests pass
- [ ] `pnpm build:portal && pnpm build:product` — both builds succeed
- [ ] Version parity check — dependency versions are identical across both apps
- [ ] Forbidden pattern scan — no cross-app imports, no inline strings

---

*This document is the authoritative frontend law for OperatorOne. Deviations require explicit Architecture Decision Record (ADR) and must be approved before implementation.*
