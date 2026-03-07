# OperatorOne Monorepo Architecture

> **Scope**: This document covers the web application monorepo layer (`apps/`, `packages/`).
> For the multi-agent execution system architecture, see [`docs/architecture.md`](./docs/architecture.md).

---

## Repository Layout

```
operator-one/
├── apps/
│   ├── portal/            # @op1/portal — Internal platform (ops/admin) — port 3000
│   └── product/           # @op1/product — External product app (customers) — port 3001
├── packages/
│   ├── ui/                # @op1/ui — Shared React components (peerDep: react)
│   ├── i18n/              # @op1/i18n — zh/en locale JSON + TypeScript types (no build step)
│   ├── types/             # @op1/types — Shared TypeScript contracts/DTOs
│   ├── vitest-config/     # @op1/vitest-config — Shared test config (base + UI)
│   └── config/
│       ├── eslint/        # @op1/eslint-config
│       ├── typescript/    # @op1/typescript-config
│       └── tailwind/      # @op1/tailwind-config
├── turbo.json             # Turborepo task pipeline + boundary enforcement
├── pnpm-workspace.yaml    # pnpm workspace definition
├── package.json           # Root scripts
├── docker-compose.yml     # Dev backing services (Postgres, Redis, Mailpit)
└── .github/
    ├── CODEOWNERS         # Ownership boundaries
    └── workflows/ci.yml   # CI pipeline (build · lint · typecheck · test · boundaries)
```

---

## App Separation: Portal vs Product

| | `apps/portal` | `apps/product` |
|---|---|---|
| **Audience** | Internal — ops team, Dennis & Bennett | External — customers, users |
| **Port** | 3000 | 3001 |
| **Turbo tag** | `internal`, `app` | `external`, `app` |
| **Brand color** | Slate (`portal-*`) | Indigo (`product-*`) |
| **Deploy target** | Private/authenticated deployment | Public Vercel deployment |
| **Access to** | All shared packages | All shared packages |

The `turbo boundaries` feature (enabled in root `turbo.json`) prevents cross-contamination:
- Packages tagged `internal-only` cannot be depended on from `external` apps
- Packages tagged `external-only` cannot be depended on from `internal` apps
- Both apps share: `@op1/ui`, `@op1/i18n`, `@op1/types`

---

## Shared Packages

### `@op1/types`
**Purpose**: Single source of truth for all TypeScript interfaces shared across apps.

Key exports:
- `AgentRole`, `AgentStatus`, `AgentHeartbeat` — agent topology types
- `HandoffContract`, `HandoffDirection` — mirrors `handoffs/*.json` schema
- `Venture`, `Opportunity` — venture/studio domain objects
- `User`, `Session` — auth types
- `ApiResponse<T>`, `ApiSuccess<T>`, `ApiError` — HTTP response envelope

### `@op1/i18n`
**Purpose**: Bilingual (zh/en) locale strings shared across apps. **No build step** — raw JSON exports consumed directly.

Structure:
```
src/locales/
├── en/
│   ├── common.json       # Shared UI strings
│   ├── navigation.json   # Nav labels
│   ├── auth.json         # Auth flow strings
│   └── errors.json       # Error messages
└── zh/
    └── (mirrors en/)
```

Usage in apps:
```typescript
// src/i18n/request.ts (per-app)
import(`@op1/i18n/locales/${locale}/common.json`)
```

Type safety via `I18nResources` interface in `@op1/i18n/types`.

### `@op1/ui`
**Purpose**: Shared React component library. **Zero runtime deps** — Tailwind classes only, no CSS-in-JS.

Components: `Button`, `Badge`, `Card`, `Spinner`, `StatusDot`

Note: `react` and `react-dom` are **peer dependencies** to prevent dual-React issues.

### `@op1/vitest-config`
**Purpose**: Shared Vitest configurations to enable Turborepo test caching.

- `baseConfig` — Node environment, for pure TS packages
- `uiConfig` — jsdom + React Testing Library, for component packages

### Config packages
- `@op1/typescript-config` — Base, Next.js, and React library tsconfig presets
- `@op1/eslint-config` — Base, Next.js, and React internal ESLint flat configs
- `@op1/tailwind-config` — Shared theme tokens (brand, portal, product colors)

---

## i18n Architecture

Both apps use **next-intl v4** with the App Router pattern:

```
app/
└── [locale]/          # Dynamic locale segment
    ├── layout.tsx     # Provides NextIntlClientProvider
    └── page.tsx       # Uses useTranslations()
```

Locale routing: `as-needed` prefix (English URLs are clean; `/zh/...` for Chinese).

Supported locales: `en` (default), `zh`

Adding a new locale:
1. Add locale to `@op1/i18n/src/types.ts` → `locales` array
2. Create `src/locales/{locale}/` with all JSON files
3. Update `routing.ts` in each app (automatically picks up from `@op1/i18n/types`)

---

## Development Workflow

### One-command start (all apps)
```bash
pnpm dev
```

### Single app
```bash
pnpm dev:portal    # portal only — http://localhost:3000
pnpm dev:product   # product only — http://localhost:3001
```

### Start backing services
```bash
docker compose up -d
# Postgres:  localhost:5432
# Redis:     localhost:6379
# Mailpit:   http://localhost:8025
```

### Full quality check
```bash
pnpm build && pnpm lint && pnpm typecheck && pnpm test
```

---

## CI Pipeline

All jobs run on pull requests and pushes to `main`.

| Job | What it does |
|---|---|
| `ci` | Build → Lint → Typecheck → Test (all `--affected`) |
| `boundaries` | `turbo boundaries` — enforces tag-based dependency rules |
| `change-hygiene` | Runs `scripts/change_hygiene_guard.py` to detect mixed source+generated churn in PRs |

Turborepo remote caching: configure `TURBO_TOKEN` and `TURBO_TEAM` secrets in GitHub for build speed.

---

## Boundary Enforcement

Three layers of isolation:

1. **`turbo boundaries`** — tag-based rules in each `turbo.json`
   - Portal: `["internal", "app"]`
   - Product: `["external", "app"]`
   - Blocks importing packages with conflicting tags

2. **`CODEOWNERS`** — review requirements by area
   - Shared packages: both owners required
   - App-specific: respective owner

3. **`pnpm` strict hoisting** — prevents phantom dependencies

---

## Adding a New Shared Package

```bash
mkdir -p packages/my-package/src
# Create package.json with name: "@op1/my-package"
# Add to relevant apps' dependencies as: "workspace:*"
# Turbo will automatically include it in the build graph
```

---

## Relation to Agent System

The monorepo web layer (`apps/`, `packages/`) is **separate** from the agent execution system (`workspaces/`). They share:

- `@op1/types` — The portal/dashboard reads agent heartbeats and venture state using these types
- `handoffs/*.json` — The portal will eventually provide a UI for reviewing/approving handoffs
- `dashboard/` — The existing Python dashboard remains operational; the portal is its eventual Next.js successor

The agent workspaces do **not** depend on any `packages/*` — they are pure Python/JSON workflows.
