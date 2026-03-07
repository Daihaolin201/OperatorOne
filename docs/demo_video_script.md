# CEOClaw Demo Video Script
**UK AI Agent Hackathon EP4 × OpenClaw — 5-10 min recording guide**

## Before Recording

Pre-open these browser tabs (do not close until recording ends):
- https://webproductlandingstage3validation.vercel.app
- https://webproductmodularinvoice.vercel.app
- https://github.com/Daihaolin201/OperatorOne/tree/dennis/automation-framework

Pre-run in terminal (so output is ready):
```bash
cd OperatorOne
git checkout dennis/automation-framework
```

---

## Section 1: Hook (0:00 – 0:45)

**Screen**: Browser — https://webproductlandingstage3validation.vercel.app

**Talking points:**
- "This is a real product deployed to Vercel — not a mockup."
- "It was built and deployed entirely by an AI agent pipeline, zero manual code."
- "Today I'll show you the CEO orchestrator that coordinates the 4 agents that made this happen."

---

## Section 2: Architecture Overview (0:45 – 2:00)

**Screen**: `README.md` (open in terminal with `cat README.md | head -80` or GitHub)

**Talking points:**
- OperatorOne has 4 specialist agents: Product → Marketing → Sales → Operations
- Each hands off a typed JSON contract to the next — like a real company with departments
- The CEO orchestrator (`run_ceo_multi_agent_orchestrator_v1.py`) coordinates the full loop
- Show architecture diagram in README

**Terminal commands:**
```bash
# Show the handoff contracts
ls handoffs/
cat handoffs/product_to_marketing.json | python3 -m json.tool | head -20
```

---

## Section 3: Real Business Results (2:00 – 3:30)

**Screen**: Terminal + browser tabs

**Talking points:**
- "The pipeline has already executed end-to-end — this is real data."
- Walk through the numbers: 13 prospects contacted, 6 replies, 1 customer, $49 MRR
- Show the 6 deployed Vercel URLs in README

**Terminal commands:**
```bash
# Show sales results
cat handoffs/sales_to_operations.json

# Show all deployed products
grep -A3 "deployed_urls" workspaces/op1_ceo/research/ceo_orchestration/venture_state.latest.json
```

**Browser**: Switch to https://webproductmodularinvoice.vercel.app — show it's a live product

---

## Section 4: CEO Orchestrator Live Run (3:30 – 6:00)

**Screen**: Terminal (full screen)

**Talking points:**
- "Now I'll run the CEO orchestrator — this is the command that kicks off the whole agent loop."
- Walk through each agent turn as it appears
- Explain the approval gate (`approval.json`)

**Terminal commands:**
```bash
# Show approval is granted
cat workspaces/op1_ceo/research/ceo_orchestration/approval.json

# Run the full orchestrator (simulation mode)
python3 workspaces/op1_ceo/scripts/run_ceo_multi_agent_orchestrator_v1.py --dry-run

# Inspect run log — show all 4 agent replies
python3 -c "
import json
d = json.load(open('workspaces/op1_ceo/research/ceo_orchestration/run.latest.json'))
print('STATUS:', d['status'])
for s in d['steps']:
    print(f\"--- {s['agent_id']} ({s['duration_ms']}ms) ---\")
    print(s['reply'][:300])
    print()
"
```

---

## Section 5: Venture State Snapshot (6:00 – 7:30)

**Screen**: Terminal

**Talking points:**
- "The orchestrator writes a `venture_state.latest.json` — a full KPI snapshot."
- Show MRR, prospects, deployed URLs, stage gates, next_actions
- "This is what makes the loop auditable and reversible — every run produces a full state artifact."

**Terminal commands:**
```bash
# Show venture state
cat workspaces/op1_ceo/research/ceo_orchestration/venture_state.latest.json

# Show the operations feedback loop feeding next_actions
cat handoffs/operations_to_product.json | python3 -m json.tool | head -40
```

---

## Section 6: Handoff Chain & Iteration Loop (7:30 – 9:30)

**Screen**: Terminal + file tree

**Talking points:**
- "Each agent writes a JSON contract that the next agent reads — not prompt chaining, actual data contracts."
- Walk through: product → marketing → sales → operations → back to product
- "Operations processed 10 feedback items and produced prioritised actions with expected MRR deltas."
- "The next cycle would be: tighten targeting, design low-risk pilot offer, simplify onboarding."

**Terminal commands:**
```bash
# Show all handoff contracts
ls -la handoffs/

# Show the iteration feedback
cat handoffs/operations_to_product.json | python3 -m json.tool

# Show marketing pipeline
python3 -c "
import json
d = json.load(open('handoffs/marketing_to_sales.json'))
print('Campaigns:', len(d['campaigns']))
print('Launch ready:', sum(1 for c in d['campaigns'] if c['status']=='launch_ready'))
print('Top channels:', d['lead_signals']['top_channels'])
"
```

**Closing talking points:**
- "OperatorOne shows what happens when you give OpenClaw a real business goal."
- "Not a toy agent — a coordinated pipeline that reached $49 MRR with real prospects."
- "The CEO orchestrator is the glue that makes it work as a system, not just individual agents."

---

## Technical Notes

- All commands run from repo root: `cd OperatorOne`
- `--dry-run` flag uses simulation mode — no OpenClaw API keys needed for judges to reproduce
- Real run requires `openclaw --profile operatorone` configured
- Handoff contracts are in `handoffs/` — all committed, versioned, reproducible
- Branch: `dennis/automation-framework`
