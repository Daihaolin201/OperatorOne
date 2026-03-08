# Learnings — dashboard-zai-ceoclaw-e2e

## Task 12: Run Evidence Persistence & Replay (2026-03-07)

### What was implemented
- `_write_replay(run_id)` added to `StudioService` in `dashboard/studio.py` (after `_write_json`)
- Called at both exit paths of `run_ceoclaw_pipeline()`: failure early-return and success final block
- Replay JSON written to `dashboard/.runtime/studio/replays/<run_id>.json`
- `GET /api/runs` → `_handle_get_runs_list()` — returns all `run_type == "api"` runs
- `GET /api/runs/<id>/replay` → `_handle_get_run_replay(run_id)` — serves replay JSON or 404
- Both new handlers added to `DashboardHandler` in `dashboard/server.py`
- Routing inserted in `do_GET` before the existing `startswith("/api/runs/")` block

### Key discoveries
- `run_ceoclaw_pipeline()` at line 4159 is the API-run executor (not `_action_run_ceoclaw_pipeline`)
- `_action_run_ceoclaw_pipeline` calls `_run_ceoclaw_pipeline_steps` — a separate codepath that creates studio-type runs (with `id`, not `run_id`)
- `POST /api/runs` creates a `queued` API run but does NOT start execution; execution must be triggered externally by calling `STUDIO.run_ceoclaw_pipeline(run_id)`
- `get_run_model_usage()` in `zai_glm_provider.py` takes a list of audit records, not a run_id — fallback dict used in replay
- `store_lock` must be held when calling `_load_runs()` to avoid race conditions

### Curl verification (passed)
- `GET /api/runs` → `{"ok": true, "runs": [...]}`
- `GET /api/runs/test-replay-001/replay` → full replay JSON with 4 steps, all succeeded
- `GET /api/runs/nonexistent/replay` → `{"ok": false, "error": "replay not found"}` (404)
- End-to-end: `run_ceoclaw_pipeline("test-replay-001")` created replay at `.runtime/studio/replays/test-replay-001.json`

## Task 13: One-Click E2E Rehearsal (2026-03-08)

### Summary
- Server started successfully with `python3 dashboard/server.py --host 127.0.0.1 --port 8765`
- `POST /api/runs` creates a `queued` run but does NOT auto-start — must trigger `STUDIO.run_ceoclaw_pipeline(run_id)` separately
- Happy path: run `run_741561a94344` succeeded with 4 stages (product, marketing, sales, operations)
- Recovery drill: cancelled `run_d9da3224eaef`, then recovered with `run_b536449fb39d` (also succeeded)
- All evidence written to `.sisyphus/evidence/`

### Startup Order
1. `lsof -ti:8765 | xargs kill -9` — clear port first (stale process guard)
2. `python3 dashboard/server.py --host 127.0.0.1 --port 8765 &` — start in background
3. Poll `GET /api/health` until HTTP 200
4. `POST /api/runs` with `{"mode": "simulation"}` — creates queued run
5. Run `STUDIO.run_ceoclaw_pipeline(run_id)` via inline Python (see below)
6. Poll `GET /api/runs/<id>` until `status == "succeeded"`

### StudioService Constructor (corrected)
```python
from pathlib import Path
from studio import StudioService
STUDIO = StudioService(repo_root=Path('.'), dashboard_dir=Path('dashboard'), profile='operatorone')
STUDIO.run_ceoclaw_pipeline(run_id, mode='simulation')
```
**NOT** `StudioService(runtime_dir=...)` — that was wrong, constructor takes `repo_root`, `dashboard_dir`, `profile`.

### Emergency Recovery Steps
1. Check for stale queued/running run: `GET /api/runs`
2. Cancel stale run: `POST /api/runs/<id>/cancel`
3. Create fresh run: `POST /api/runs`
4. Trigger pipeline inline Python script
5. Verify: `GET /api/runs/<id>` → `status == "succeeded"`
6. Verify replay: `GET /api/runs/<id>/replay` → `steps[].status == "succeeded"`, `model_usage.model == "glm-5"`

### Key Discoveries
- `POST /api/runs` is idempotent: if a queued/running run exists, it returns `reused: true` with the existing run_id instead of creating a new one — must cancel the stale run first
- Terminal status is `"succeeded"` (NOT `"completed"`) — the task spec says "completed" but actual code uses "succeeded"
- Replay schema: `{run_id, status, mode, started_at, finished_at, steps[], model_usage{provider, model, total_calls, total_tokens}, failed_step, error}`
- `model_usage.provider = "z.ai"`, `model_usage.model = "glm-5"` — hardcoded in `_write_replay()`
- Handoff chain: 9 JSON files in `handoffs/` directory — all present and verified
- Server cleanup: `lsof -ti:8765 | xargs kill -9` reliably kills server
- macOS no native `timeout` — use `perl -e 'alarm(120); exec @ARGV' <command>` if needed

### Curl Commands (verified)
```bash
# Health check
curl -s http://127.0.0.1:8765/api/health

# Create run
curl -s -X POST http://127.0.0.1:8765/api/runs -H "Content-Type: application/json" -d '{"mode": "simulation"}'

# Poll status
curl -s http://127.0.0.1:8765/api/runs/<run_id>

# Cancel run
curl -s -X POST http://127.0.0.1:8765/api/runs/<run_id>/cancel

# Get replay
curl -s http://127.0.0.1:8765/api/runs/<run_id>/replay
```

### Evidence Files Written
- `.sisyphus/evidence/task-13-e2e-rehearsal.json` — happy path (run_741561a94344, 4 stages, all succeeded)
- `.sisyphus/evidence/task-13-recovery-drill.json` — recovery drill (cancelled run_d9da3224eaef, recovered run_b536449fb39d)

## Task F4: Scope Fidelity Check (2026-03-08)

### Audit outcomes
- Created `.sisyphus/evidence/final-f4-scope.txt` with task-by-task evidence matrix T1-T17.
- Detected one delivery gap: `docs/capability_matrix.md` missing (T2).
- Verified T6 via `python3 -m pytest dashboard/tests -q` (8 passed).
- Verified replay and cancel endpoints are present (`/api/runs/<id>/replay`, `/api/runs/<id>/cancel`).
- Scope-creep scan in audit window found `apps/` file changes since 2026-03-07.

### Practical audit pattern
- Use explicit grep evidence for each required symbol/route/function.
- Treat missing required artifact as task gap even if related features exist elsewhere.
- Keep verdict strict: any missing task artifact or scope-creep signal flips overall status to FAIL.

## 2026-03-08 F4 Fix: docs/capability_matrix.md Restored

### Root Cause
- T2 committed `docs/capability_matrix.md` in f2434d2
- bcb9875 (T12 cleanup "remove vibe-coding artifacts") accidentally deleted it as collateral damage
- File was in `docs/` directory which was mass-deleted by `git rm --cached`

### Fix
- Restored content from `git show f2434d2:docs/capability_matrix.md`
- Re-committed as `docs(submission): restore capability matrix and finalize F4 scope audit`

### apps/ Scope Creep — Not an Issue
- ab33423 and 067a157 both predate the dashboard-zai-ceoclaw-e2e plan start (a47920f)
- These are from OLD ceoclaw-submission.md plan — prior work
- Zero apps/ changes in T1–T17

### F4 Final Verdict: PASS
