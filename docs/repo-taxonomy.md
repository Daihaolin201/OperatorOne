# OperatorOne Repository Taxonomy & Ownership

This document defines the top-level domains, ownership boundaries, and dependency rules for the OperatorOne repository.

## Top-Level Domains

| Domain | Description | Primary Owner |
|---|---|---|
| `apps/` | End-user applications (internal platform and external product UIs). | `op1_product` |
| `services/` | Backend services and long-running processes. | `op1_manager` |
| `packages/` | Shared internal libraries (i18n, API clients, shared logic). | `op1_manager` |
| `contracts/` | Typed schema definitions and shared protocol interfaces. | `op1_manager` |
| `workspaces/` | Isolated agent execution environments and stage research artifacts. | Individual Specialist Agents |
| `docs/` | System architecture, runbooks, and collaboration protocols. | `op1_manager` |
| `scripts/` | Repository-level automation, validation, and hygiene scripts. | `op1_manager` |
| `handoffs/` | Inter-agent JSON contracts (the system's primary data bus). | Specialist Agents (Producers) |
| `dashboard/` | Local monitor and venture studio web application. | `op1_manager` |
| `official-site/` | Official project introduction and landing site. | `op1_marketing` |
| `openclaw/` | Profile sync scripts, manifests, and safety guards. | `op1_manager` |

## Ownership Boundaries

### Specialist Agent Workspaces (`workspaces/op1_*`)
Each specialist agent owns its respective workspace. Cross-workspace edits are generally forbidden unless performing system-wide integration or refactoring.
- **op1_product**: Owns idea discovery, web build/deploy artifacts.
- **op1_marketing**: Owns SEO, content, and campaign research.
- **op1_sales**: Owns prospecting and outreach data.
- **op1_operations**: Owns KPI tracking, feedback, and iteration logic.
- **op1_ceo**: Owns high-level orchestration execution logs. *Note: `op1_ceo` is active but currently omitted from the root README topology table.*

### Control Plane (`workspaces/op1_manager`)
The manager workspace owns the "connective tissue" of the repository: docs, shared packages, and cross-agent audit logs.

## Forbidden Dependency Patterns

To maintain modularity and prevent circular dependencies, the following patterns are strictly forbidden:

1. **No Cross-App Imports**: Files in `apps/` must not import directly from other apps in `apps/`.
2. **Apps Cannot Import from Workspaces**: Applications must consume logic via `packages/` or `contracts/`, never directly from agent research folders.
3. **Packages Cannot Import from Apps**: Shared packages must be agnostic of the specific applications consuming them.
4. **Workspaces Cannot Import from Apps**: Agent execution logic must be decoupled from the UI/Frontend layers.
5. **No Direct Workspace-to-Workspace Imports**: Agents must communicate solely through the `handoffs/` contract layer or shared `packages/`. Direct file imports between `workspaces/op1_product` and `workspaces/op1_marketing` (and others) are prohibited.

## Discrepancy Notes
- `workspaces/op1_ceo` is a functional workspace used for running the multi-agent orchestrator but is not currently listed in the root `README.md` agent topology table. Taxonomy updates should treat it as a top-level orchestrator domain.
