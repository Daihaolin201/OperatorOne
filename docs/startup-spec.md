# OperatorOne One-Click Startup Specification

**Last Updated:** 2026-03-07  
**Status:** Specification (not yet implemented)  
**Scope:** Define `dev up`, `dev status`, `dev down` behavior and health matrix for local development

---

## 1. Overview

The `dev` CLI provides a unified interface to manage OperatorOne's multi-service local development environment. It replaces the ad-hoc `start_operatorone.sh` script with a robust, composable startup workflow that includes:

- **Prerequisite validation** before attempting service startup
- **Concurrent service startup** with parallel health checks
- **Fail-fast diagnostics** with clear error messages
- **Graceful shutdown** of all services
- **Status reporting** across all services and the health matrix

---

## 2. Service Topology

The OperatorOne development environment consists of three services:

| Service | Type | Port | Working Dir | Command |
|---------|------|------|-------------|---------|
| `dashboard` | Python Flask | 8765 | `dashboard/` | `python3 server.py --host 127.0.0.1 --port 8765` |
| `platform-portal` | React/Vite | 5173 | `apps/platform-portal/` | `pnpm run dev` |
| `product-ui` | React/Vite | 5174 | `apps/product-ui/` | `pnpm run dev` |

---

## 3. Prerequisites Validation

Before attempting to start services, `dev up` MUST check:

### 3.1 System Requirements

| Requirement | Min Version | Check Command | Error Message |
|-------------|-------------|---------------|---------------|
| Python | 3.8 | `python3 --version` | `Python 3.8+ required (found X.Y)` |
| Node.js | 18.0 | `node --version` | `Node.js 18.0+ required (found X.Y)` |
| pnpm | 7.0 | `pnpm --version` | `pnpm 7.0+ required (found X.Y)` |

### 3.2 File and Directory Checks

| Check | Path | Behavior |
|-------|------|----------|
| Dashboard config exists | `dashboard/server.py` | Fail if missing |
| Platform portal exists | `apps/platform-portal/` | Fail if missing |
| Product UI exists | `apps/product-ui/` | Fail if missing |
| pnpm workspace configured | `pnpm-workspace.yaml` | Fail if missing |
| Node modules initialized | `node_modules/` | Warn if missing; do NOT auto-install |

### 3.3 Port Availability

Before starting any service, `dev up` MUST check that required ports are free:

- Port 8765 for `dashboard`
- Port 5173 for `platform-portal`
- Port 5174 for `product-ui`

**Check command:** `lsof -Pi :PORT -sTCP:LISTEN -t` (macOS/Linux) or `netstat -ano | findstr :PORT` (Windows)

**Fail-fast behavior:** If a port is in use, display the PID/process name and exit with non-zero code.

---

## 4. Service Startup

### 4.1 Startup Order and Concurrency

Services are started in the following order, with concurrency where safe:

1. **Sequential check:** Validate all prerequisites (section 3)
2. **Parallel startup:** Start all three services concurrently
   - Dashboard process starts
   - platform-portal process starts
   - product-ui process starts
3. **Parallel health check:** Wait for all services to report READY (section 5)

### 4.2 Process Management

- Each service runs as a **foreground subprocess** (not daemonized)
- Parent process must collect stdout/stderr from each child
- Parent must handle SIGTERM/SIGINT to gracefully shut down children (section 6)
- If any service exits before READY status is confirmed, `dev up` fails immediately

### 4.3 Startup Output Format

During startup, display:

```
[dev up] Starting OperatorOne services...
[dev up] ✓ Prerequisite checks passed
[dev up] Starting 3 services in parallel...
[dashboard]       Starting on http://127.0.0.1:8765
[platform-portal] Starting on http://127.0.0.1:5173
[product-ui]      Starting on http://127.0.0.1:5174
[dev up] Waiting for health endpoints...
[dashboard]       ✓ Health: /healthz → 200 OK (1ms)
[platform-portal] ✓ Readiness: /readyz → 200 OK (5ms)
[product-ui]      ✓ Readiness: /readyz → 200 OK (7ms)
[dev up] ✅ All services ready. Dev environment online.
[dev up] Press Ctrl+C to shut down.
```

---

## 5. Health and Readiness Endpoints

### 5.1 Health Check Policy

Each service MUST expose health endpoints:

| Service | Liveness Endpoint | Readiness Endpoint | Port | Timeout | Polling Interval |
|---------|-------------------|-------------------|------|---------|------------------|
| `dashboard` | `GET /api/health` | `GET /api/health` | 8765 | 30s | 1s |
| `platform-portal` | `GET /healthz` | `GET /readyz` | 5173 | 30s | 1s |
| `product-ui` | `GET /healthz` | `GET /readyz` | 5174 | 30s | 1s |

### 5.2 Health Endpoint Behavior

#### Dashboard (`GET /api/health`)

**Response (200 OK):**
```json
{
  "ok": true,
  "service": "operatorone-dashboard",
  "ts": "2026-03-07T10:30:45.123456+00:00",
  "profile": "operatorone"
}
```

**Expected status:** Responds with 200 OK within 30 seconds of startup.

#### React Apps (Vite)

**Endpoints:**
- `GET /healthz` — Basic liveness check (should return 200 immediately once server is listening)
- `GET /readyz` — Readiness check (should return 200 once dev server is ready to serve static assets)

**Response (200 OK):**
```json
{
  "ok": true
}
```

### 5.3 Timeout Policy

- **Per-service timeout:** 30 seconds max from startup to first 200 response
- **Per-request timeout:** 5 seconds per individual health check request
- **Overall `dev up` timeout:** 120 seconds (safety limit in case of unusual system load)

**Fail-fast behavior:** If a service does not respond within 30 seconds, log the failure and exit `dev up` with non-zero code.

---

## 6. `dev status` Command

The `dev status` command reports the current state of all services WITHOUT starting them.

### 6.1 Output Format

```
[dev status] Checking service status...

Service: dashboard (Flask)
  Port: 8765
  Status: ✓ READY
  Health: /api/health → 200 OK (response time: 1ms)
  URL: http://127.0.0.1:8765
  PID: 12345

Service: platform-portal (Vite)
  Port: 5173
  Status: ✓ READY
  Health: /readyz → 200 OK (response time: 3ms)
  URL: http://127.0.0.1:5173
  PID: 12346

Service: product-ui (Vite)
  Port: 5174
  Status: ✓ READY
  Health: /readyz → 200 OK (response time: 5ms)
  URL: http://127.0.0.1:5174
  PID: 12347

[dev status] ✅ All services ready.
```

### 6.2 Status Values

- `✓ READY` — Service is running and responding to health checks
- `⚠ STARTING` — Service is running but has not yet responded to health checks
- `✗ FAILED` — Service exited unexpectedly or health checks timed out
- `○ STOPPED` — Service is not running (port is free)

### 6.3 Exit Codes

- `0` — All services are READY
- `1` — At least one service is not READY
- `2` — Invalid usage (e.g., missing arguments)

---

## 7. `dev down` Command

The `dev down` command gracefully shuts down all running services.

### 7.1 Shutdown Sequence

1. Send SIGTERM to all service processes
2. Wait up to 10 seconds for graceful shutdown
3. If any process has not exited after 10 seconds, send SIGKILL
4. Wait up to 5 seconds for cleanup
5. Report final status

### 7.2 Output Format

```
[dev down] Shutting down OperatorOne services...
[dashboard]       Received SIGTERM (PID 12345)
[platform-portal] Received SIGTERM (PID 12346)
[product-ui]      Received SIGTERM (PID 12347)
[dev down] Waiting for graceful shutdown (10s timeout)...
[dashboard]       ✓ Exited cleanly (exit code 0)
[platform-portal] ✓ Exited cleanly (exit code 0)
[product-ui]      ✓ Exited cleanly (exit code 0)
[dev down] ✅ All services shut down.
```

### 7.3 Exit Code

- `0` — All services shut down cleanly
- `1` — One or more services required SIGKILL

---

## 8. Per-Service Readiness Matrix

This matrix defines what "READY" means for each service and what key features must be available at that point.

### 8.1 Dashboard (Python Flask)

**READY state definition:** Flask application has started, request handler is initialized, and `/api/health` endpoint responds with 200 OK.

| Feature | Readiness Gate | Details |
|---------|----------------|---------|
| HTTP server listening | REQUIRED | Must bind to 127.0.0.1:8765 |
| `/api/health` endpoint | REQUIRED | Must return `{ "ok": true, ... }` |
| Monitor cache initialization | REQUIRED | Background cache thread must be started |
| Studio snapshot capability | READY | `GET /api/studio/fast-snapshot` should succeed |
| Database/artifact loading | READY | All handoff files should be readable |

### 8.2 Platform Portal (React/Vite)

**READY state definition:** Vite dev server has compiled the app bundle, HMR (hot module replacement) is enabled, and `/readyz` endpoint responds with 200 OK.

| Feature | Readiness Gate | Details |
|---------|----------------|---------|
| HTTP server listening | REQUIRED | Must bind to 127.0.0.1:5173 |
| `/healthz` endpoint | REQUIRED | Basic server alive check |
| `/readyz` endpoint | REQUIRED | App bundle compiled and ready to serve |
| HMR enabled | READY | Hot module replacement server should be ready |
| Static assets served | READY | Root `/` should return index.html |

### 8.3 Product UI (React/Vite)

**READY state definition:** Vite dev server has compiled the app bundle, HMR is enabled, and `/readyz` endpoint responds with 200 OK.

| Feature | Readiness Gate | Details |
|---------|----------------|---------|
| HTTP server listening | REQUIRED | Must bind to 127.0.0.1:5174 |
| `/healthz` endpoint | REQUIRED | Basic server alive check |
| `/readyz` endpoint | REQUIRED | App bundle compiled and ready to serve |
| HMR enabled | READY | Hot module replacement server should be ready |
| Static assets served | READY | Root `/` should return index.html |

---

## 9. Fail-Fast Diagnostics

When a service fails to start or becomes unavailable, `dev up` must display clear diagnostic information:

### 9.1 Prerequisite Failure Example

```
[dev up] ✗ Prerequisite check failed: Python 3.8+ required (found 3.7.10)
[dev up] Install Python 3.8 or later from https://www.python.org/downloads/
[dev up] Exiting.
```

### 9.2 Port Conflict Example

```
[dev up] ✗ Port 8765 is already in use.
[dev up] Process: python3 (PID 9999)
[dev up] Kill the process with: kill 9999
[dev up] Or run on a different port with: dev up --dashboard-port 8766
[dev up] Exiting.
```

### 9.3 Service Startup Failure Example

```
[dev up] ✗ dashboard service failed to start.
[dashboard] Error: ModuleNotFoundError: No module named 'flask'
[dashboard] stdout/stderr:
  Traceback (most recent call last):
    ...
[dev up] Remediation: Run 'pip3 install -r dashboard/requirements.txt' in the repo root.
[dev up] Exiting.
```

### 9.4 Health Check Timeout Example

```
[dev up] ⚠ Waiting for services to report READY...
[dashboard]       ✓ READY (1ms)
[platform-portal] ⚠ Waiting for /readyz (8s elapsed)
[product-ui]      ✓ READY (5ms)
[platform-portal] ✗ Health check timeout (>30s). Service may not be running correctly.
[platform-portal] Last error: Connection refused on http://127.0.0.1:5173/readyz
[dev up] Remediation: Check service logs above. Try 'pnpm install' in apps/platform-portal.
[dev up] Exiting.
```

### 9.5 Service Crash During Ready Check Example

```
[dev up] Starting 3 services in parallel...
[dashboard]       Starting on http://127.0.0.1:8765
[platform-portal] Starting on http://127.0.0.1:5173
[product-ui]      Starting on http://127.0.0.1:5174
[dev up] Waiting for health endpoints...
[dashboard]       ✓ READY (1ms)
[platform-portal] Starting up...
[product-ui]      ✓ READY (7ms)
[platform-portal] ✗ Process exited unexpectedly (exit code 1).
[product-ui]      stderr: ... error output ...
[dev up] Service startup failed. See logs above.
[dev up] Exiting.
```

---

## 10. Configuration and Customization

The `dev` CLI should support optional flags to override defaults:

| Flag | Purpose | Example |
|------|---------|---------|
| `--dashboard-port PORT` | Override dashboard port | `dev up --dashboard-port 9000` |
| `--portal-port PORT` | Override platform-portal port | `dev up --portal-port 5200` |
| `--product-port PORT` | Override product-ui port | `dev up --product-port 5201` |
| `--timeout SECONDS` | Override overall timeout | `dev up --timeout 60` |
| `--skip-health-check` | Start services without waiting for READY | `dev up --skip-health-check` |
| `--verbose` | Print detailed debug logs | `dev up --verbose` |

---

## 11. Integration with Existing Infrastructure

### 11.1 Relationship to `start_operatorone.sh`

The existing `start_operatorone.sh` script:
- Currently starts only the dashboard
- Does NOT start the React apps
- Will be **superseded** by the new `dev up` CLI

**Migration path:** The `dev` CLI will eventually replace this script entirely, but both may coexist during the transition.

### 11.2 Relationship to `openclaw` Profile

The `dev` CLI runs independently of OpenClaw. However:
- Dashboard reads from `openclaw --profile operatorone status` in its monitor APIs
- The `dev up` command is agnostic to OpenClaw state
- OpenClaw setup is a separate prerequisite (documented in `docs/runbook.md`)

### 11.3 Relationship to pnpm Workspace

All three services are part of the pnpm monorepo:
- Dashboard is in the root `dashboard/` dir
- Apps are in `apps/`
- The workspace is defined in `pnpm-workspace.yaml`

**Note:** `dev up` does NOT run `pnpm install` automatically. Users must have dependencies installed before running `dev up`.

---

## 12. Error Handling and Recovery

### 12.1 Transient Failures

If a health check times out once but succeeds on retry:
- Wait up to 30 seconds total
- Retry every 1 second
- Consider the service READY once it responds

### 12.2 Partial Startup

If one service starts but another fails:
- DO NOT consider the environment ready
- Shut down running services gracefully
- Report which service(s) failed
- Exit with non-zero code

### 12.3 Cleanup on Interrupt

If the user sends SIGINT (Ctrl+C) while `dev up` is starting:
- Immediately send SIGTERM to all child processes
- Wait up to 10 seconds for graceful shutdown
- Exit with code 130 (interrupted)

---

## 13. Success Criteria and Verification

A successful `dev up` will:

1. ✓ Validate all prerequisites (Python, Node.js, pnpm, files, ports)
2. ✓ Start all three services concurrently
3. ✓ Poll health endpoints until all services report READY
4. ✓ Display clear startup progress and final status
5. ✓ Remain running, aggregating stdout/stderr from all services
6. ✓ Handle Ctrl+C gracefully, shutting down all services
7. ✓ Exit with code 0 once all services are READY

A successful `dev status` will:

1. ✓ Check the health of all services without starting them
2. ✓ Report per-service status and response times
3. ✓ Exit with code 0 if all are READY, code 1 otherwise

A successful `dev down` will:

1. ✓ Send SIGTERM to all running services
2. ✓ Wait up to 10 seconds for graceful shutdown
3. ✓ Use SIGKILL for stubborn processes
4. ✓ Report final status
5. ✓ Exit with code 0

---

## 14. Future Enhancements (Out of Scope)

This specification is baseline for T3. Future enhancements include:

- [ ] Environment variable overrides for all service config
- [ ] Persistent state and recovery (e.g., save PIDs and re-check on next invocation)
- [ ] Log aggregation and filtering (e.g., `dev logs dashboard`)
- [ ] Integration with external monitoring/alerting
- [ ] Hot reload of config files without full service restart
- [ ] Service dependency injection (e.g., `dev up dashboard` to start only one)

---

## References

- `docs/runbook.md` — Daily operations and troubleshooting
- `dashboard/server.py` — Dashboard implementation (health endpoints)
- `start_operatorone.sh` — Current startup script (to be superseded)
- `.sisyphus/plans/operatorone-reorg-oneclick-bilingual.md` — Original project plan

---

**Document Version:** 1.0  
**Last Updated:** 2026-03-07  
**Next Review:** After T7 (dev CLI implementation)
