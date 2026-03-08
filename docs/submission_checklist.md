# OperatorOne CEOClaw — BUIDL Submission Checklist

**Challenge**: UK AI Agent Hackathon EP4 × OpenClaw — CEOClaw Challenge  
**Team**: Dennis & Bennett  
**Branch**: `dennis/automation-framework`  
**Date**: 2026-03-08  
**Repo**: `https://github.com/Daihaolin201/OperatorOne`

---

## 🔴 HARD GATES (Mandatory — submission blocked if any fail)

### HG-1: Public Repository

- [x] **Repo URL**: `https://github.com/Daihaolin201/OperatorOne`
- [x] Branch: `dennis/automation-framework`
- Verification: `git remote -v` → shows origin with github.com/Daihaolin201
- Status: **[PASS]**

```bash
git remote -v
# Expected: origin  https://github.com/Daihaolin201/OperatorOne.git (fetch)
#           origin  https://github.com/Daihaolin201/OperatorOne.git (push)
```

---

### HG-2: Demo Video

- [ ] **Video URL**: _[TO BE FILLED — link to recording]_
- [ ] Minimum duration: 5 minutes (target: ~6 minutes per demo script)
- [ ] Shows: dashboard one-click trigger, 4 stages, GLM-5 evidence
- [ ] Shows: simulation mode default, approval gate, cancel flow
- Script reference: `docs/demo_script.md` (921 words, 6.1 min, 10 sections, fallback included)
- Status: **[PENDING — video recording required]**

> ⚠️ **BLOCKER**: This hard gate cannot be automated. A human must record the demo video
> and update this checklist with the URL before final submission.
>
> Demo script is ready at `docs/demo_script.md`. All dashboard features are verified in T13.

---

### HG-3: README with Setup + Extensions

- [x] File: `README.md` exists
- [x] Contains: Quick Start commands
- [x] Contains: CEOClaw Extension Points section
- [x] Contains: Z.AI Evidence section
- [x] Contains: Hackathon Bounties table
- Verification: `grep -c "Extension Points" README.md` → ≥ 1
- Status: **[PASS]**

```bash
grep -c "Extension Points" README.md
# Expected: ≥ 1 (README has both English and Chinese sections = 2)
```

---

### HG-4: Example Runs

- [x] Pipeline can be triggered: `python3 workspaces/op1_ceo/scripts/run_ceo_multi_agent_orchestrator_v1.py --dry-run`
- [x] Dashboard API endpoint: `POST http://127.0.0.1:8765/api/runs`
- [x] Evidence: `.sisyphus/evidence/task-13-e2e-rehearsal.json` (4 stages, all succeeded)
- Verification: `python3 ... --dry-run` exits 0; evidence JSON shows `status: succeeded`
- Status: **[PASS]**

```bash
python3 workspaces/op1_ceo/scripts/run_ceo_multi_agent_orchestrator_v1.py --dry-run
# Expected: exit 0

# Evidence file verification:
python3 -c "
import json
data = json.load(open('.sisyphus/evidence/task-13-e2e-rehearsal.json'))
assert data['status'] == 'succeeded'
assert data['stage_count'] == 4
assert data['handoff_count'] == 9
print('Evidence OK:', data['run_id'], data['status'], data['stage_count'], 'stages')
"
```

---

### HG-5: Z.AI GLM Evidence

- [x] GLM-5 is core model: `dashboard/zai_preflight.py` raises `ZAIPreflightError` on bad config
- [x] Replay JSON shows `model_usage.model = "glm-5"` and `provider = "z.ai"`
- [x] No silent fallback to other providers
- Verification: `python3 -m pytest dashboard/tests/ -q` → 8/8 pass
- Status: **[PASS]**

```bash
python3 -m pytest dashboard/tests/ -q
# Expected: 8 passed in <1s

# GLM evidence verification:
python3 -c "
import json
data = json.load(open('.sisyphus/evidence/task-13-e2e-rehearsal.json'))
mu = data['model_usage']
assert mu['model'] == 'glm-5', f'Expected glm-5, got {mu[\"model\"]}'
assert mu['provider'] == 'z.ai', f'Expected z.ai, got {mu[\"provider\"]}'
print('GLM-5 OK: model=%s provider=%s calls=%d' % (mu['model'], mu['provider'], mu['total_calls']))
"
```

---

## 🟡 STRONG PREFERENCES (Should have — judges look for these)

### SP-1: CEOClaw Multi-Agent Loop

- [x] 4 specialist agents: Product, Marketing, Sales, Operations
- [x] CEO orchestrator coordinates and routes all stages
- [x] Multi-cycle loop until MRR target or max_cycles exhausted
- Evidence: `.sisyphus/evidence/task-13-e2e-rehearsal.json` (T13 rehearsal confirms 4-stage loop)
- Status: **[PASS]**

---

### SP-2: Typed Handoff Contracts

- [x] 9 JSON contracts in `handoffs/`
- [x] All carry `contract_version`, `generated_at`, `generated_by` fields
- Verification: `python3 scripts/validate_handoffs.py --repo-root .` → 9/9 PASS
- Status: **[PASS]**

```bash
python3 scripts/validate_handoffs.py --repo-root .
# Expected: 9/9 handoffs valid

ls handoffs/*.json | wc -l
# Expected: 9
```

---

### SP-3: Simulation-First Safety Guardrail

- [x] Mode defaults to `simulation` in all dashboard API runs
- [x] No live outreach without `approval.json` set
- [x] Cancel and timeout controls present in dashboard
- Evidence: T13 rehearsal runs all use `mode: simulation` (see task-13-e2e-rehearsal.json)
- Status: **[PASS]**

---

### SP-4: Dashboard Web Interface

- [x] `http://localhost:8765` serves run CTA (one-click trigger)
- [x] Run timeline visible after click (4-stage progress)
- [x] Cancel and timeout controls present
- [x] `/api/health` health endpoint responds `{"ok": true}`
- Status: **[PASS]**

```bash
# Start server and verify
python3 dashboard/server.py --host 127.0.0.1 --port 8765 &
sleep 2
curl -s http://127.0.0.1:8765/api/health | python3 -m json.tool
# Expected: {"ok": true, "service": "operatorone-dashboard"}
kill %1
```

---

### SP-5: CI Green on Critical Path

- [x] Workflow: `.github/workflows/ci.yml` has `ceoclaw-critical-path` job
- [x] pytest 8/8 pass
- [x] handoffs 9/9 pass
- [x] health smoke pass
- Evidence: `.sisyphus/evidence/task-17-ci-pass.txt`
- Status: **[PASS]**

```bash
# Verify CI evidence
cat .sisyphus/evidence/task-17-ci-pass.txt
```

---

## 🟢 EVIDENCE INDEX

| Evidence File | Task | Content | Mode |
|---|---|---|---|
| `.sisyphus/evidence/task-13-e2e-rehearsal.json` | T13 | E2E run: 4 stages, GLM-5, 9 handoffs, all succeeded | SIMULATION |
| `.sisyphus/evidence/task-13-recovery-drill.json` | T13 | Recovery drill: cancel + fresh run → succeeded | SIMULATION |
| `.sisyphus/evidence/task-14-readme-repro.md` | T14 | README Judge Quick Path repro audit | SIMULATION |
| `.sisyphus/evidence/task-15-demo-script-checklist.md` | T15 | Demo script completeness check (10 sections, 6.1 min) | N/A |
| `.sisyphus/evidence/task-15-demo-fallback.md` | T15 | Demo fallback flow verification | SIMULATION |
| `.sisyphus/evidence/task-17-ci-pass.txt` | T17 | CI: pytest 8/8, handoffs 9/9, health smoke OK | SIMULATION |
| `dashboard/.runtime/studio/replays/*.json` | T12 | Per-run replay with model_usage (runtime, gitignored) | SIMULATION |
| `.sisyphus/evidence/task-16-submission-checklist.md` | T16 | This checklist audit results | N/A |
| `.sisyphus/evidence/task-16-submission-negative.md` | T16 | Negative test: missing video URL detection | N/A |

---

## 🔵 QUICK VERIFICATION (3-minute judge path)

```bash
# ── Step 1: Verify GLM-5 preflight gate ───────────────────────────────
python3 dashboard/zai_preflight.py
# Expected: ZAI_API_KEY set, model=glm-5, provider=z.ai → PASS

# ── Step 2: Run 4-agent pipeline (dry run) ────────────────────────────
python3 workspaces/op1_ceo/scripts/run_ceo_multi_agent_orchestrator_v1.py --dry-run
# Expected: exit 0, 4 stages logged

# ── Step 3: Start dashboard server ────────────────────────────────────
python3 dashboard/server.py --host 127.0.0.1 --port 8765 &
SERVER_PID=$!
sleep 2

# ── Step 4: Trigger a simulation run ──────────────────────────────────
curl -s -X POST http://127.0.0.1:8765/api/runs \
  -H "Content-Type: application/json" \
  -d '{"mode":"simulation"}' | python3 -m json.tool
# Expected: {"run_id": "...", "status": "succeeded", "mode": "simulation"}

# ── Step 5: Run test suite ────────────────────────────────────────────
python3 -m pytest dashboard/tests/ -q
# Expected: 8 passed

# ── Step 6: Validate all handoff contracts ────────────────────────────
python3 scripts/validate_handoffs.py --repo-root .
# Expected: 9/9 PASS

# ── Cleanup ───────────────────────────────────────────────────────────
kill $SERVER_PID 2>/dev/null
```

---

## ⚠️ SIMULATION vs LIVE DISTINCTION

All runs in the submission evidence are in **simulation mode** unless explicitly marked otherwise.

| Item | Type | Detail |
|---|---|---|
| MRR $49 | **LIVE** (from past pipeline run) | Generated by GLM-5 orchestrator, stored in `venture_state.latest.json` |
| 13 prospects, 6 replies | **LIVE** (from past pipeline run) | No new outreach sent during submission prep |
| 6 Vercel URLs | **LIVE** (deployed) | Publicly accessible, deployed by `op1_product` agent |
| T13 rehearsal runs | **SIMULATION** | Dashboard triggered, no external calls made |
| T17 CI evidence | **SIMULATION** | Local dry-run matching CI commands |
| T12 replay files | **SIMULATION** | Dashboard server replays, runtime only |
| Demo video (HG-2) | **SIMULATION** | Dashboard demo in simulation mode per script |

> **Rule**: Any item marked LIVE reflects past real execution. Nothing marked SIMULATION
> triggers external API calls, email outreach, or deployments.

---

## 📋 THIRD-PARTY REVIEWER GUIDE

If you are a hackathon judge reviewing this submission:

### 1. Fastest path to GLM-5 evidence (30 seconds)

```bash
python3 -c "
import json
d = json.load(open('.sisyphus/evidence/task-13-e2e-rehearsal.json'))
m = d['model_usage']
print(f'Model: {m[\"model\"]} | Provider: {m[\"provider\"]} | API calls: {m[\"total_calls\"]}')
print(f'Run: {d[\"run_id\"]} | Status: {d[\"status\"]} | Stages: {d[\"stage_count\"]}')
"
```

### 2. Fastest path to agent loop evidence (30 seconds)

```bash
python3 scripts/validate_handoffs.py --repo-root .
# 9 typed JSON contracts = complete 4-agent loop with feedback
```

### 3. Fastest path to dashboard demo (2 minutes)

```bash
python3 dashboard/server.py --host 127.0.0.1 --port 8765 &
sleep 2
# Open http://localhost:8765 in browser
# Click "Run CEOClaw" → watch 4-stage timeline
kill %1
```

### 4. Demo video (5-6 minutes)

Watch the submitted video. It covers:
- One-click dashboard trigger
- 4-stage agent progression (Product → Marketing → Sales → Operations)
- GLM-5 model usage evidence panel
- Simulation mode indicator
- Cancel/timeout controls
- Live MRR and Vercel URLs

### Key files to inspect

| File | What it proves |
|---|---|
| `dashboard/zai_preflight.py` | Hard Z.AI gate — raises on bad config |
| `dashboard/zai_glm_provider.py` | Direct Z.AI API interface |
| `handoffs/*.json` | 9 typed inter-agent contracts |
| `workspaces/op1_ceo/scripts/run_ceo_multi_agent_orchestrator_v1.py` | CEO orchestrator loop |
| `.sisyphus/evidence/task-13-e2e-rehearsal.json` | Verified E2E run with GLM-5 |
| `docs/demo_script.md` | Full 6-minute demo script |
| `README.md` | Quick Start, Extension Points, Z.AI Evidence |

---

## ✅ SUBMISSION STATUS SUMMARY

| Gate | Item | Status |
|---|---|---|
| 🔴 HG-1 | Public Repo (`github.com/Daihaolin201/OperatorOne`) | **PASS** |
| 🔴 HG-2 | Demo Video (≥5 min, shows dashboard + GLM-5) | **PENDING** |
| 🔴 HG-3 | README with Setup + Extension Points | **PASS** |
| 🔴 HG-4 | Example Runs (dry-run + T13 evidence) | **PASS** |
| 🔴 HG-5 | Z.AI GLM-5 Evidence (pytest 8/8) | **PASS** |
| 🟡 SP-1 | Multi-Agent Loop (4 specialists + CEO) | **PASS** |
| 🟡 SP-2 | Typed Handoff Contracts (9/9) | **PASS** |
| 🟡 SP-3 | Simulation-First Safety Guardrail | **PASS** |
| 🟡 SP-4 | Dashboard Web Interface | **PASS** |
| 🟡 SP-5 | CI Green on Critical Path | **PASS** |

**Overall: 9/10 items confirmed. 1 PENDING (HG-2 — video URL required before final submission).**
