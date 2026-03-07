# OperatorOne × CEOClaw: Demo Video Script

This script provides a structured 5–10 minute recording guide for the OperatorOne × CEOClaw hackathon submission.

## Pre-recording Checklist
- [ ] Terminal font size: 14pt+ (readable on 1080p).
- [ ] Repo status: Cloned and on branch `dennis/automation-framework`.
- [ ] Browser tabs pre-loaded:
  - https://webproductmodularinvoice.vercel.app
  - https://webproductmodularchargeback.vercel.app
  - https://webproductlandingstage3validation.vercel.app
- [ ] JSON files exist in `handoffs/` and `workspaces/op1_ceo/research/ceo_orchestration/`.
- [ ] Microphone check: Speak clearly and pace yourself.

## Recording Tips
- Use 1080p resolution.
- Keep the terminal full-screen when running commands.
- Pause for 1-2 seconds after a command finishes before speaking the next point.
- Focus on the *system* and *results*, not just the code.
- Avoid AI-sounding filler; speak like a human operator.

---

## Segment 1: Intro (0:00–1:00)
**Visual:** Show README.md in a browser or code editor, focused on the "CEOClaw" and "Real Results" sections.

### Talking Points
- Welcome the judges to the OperatorOne submission for the CEOClaw Challenge (£1,000 prize).
- Team: Dennis & Bennett.
- What is CEOClaw? It's our multi-agent CEO orchestrator that runs an internet business from idea to first customers.
- Key highlight: This isn't just a prototype. We've achieved real results: **$49 MRR** from a live customer.

---

## Segment 2: Architecture Walkthrough (1:00–2:30)
**Visual:** Terminal.

### Terminal Commands
```bash
ls workspaces/
ls handoffs/
```

### Talking Points
- Show the 5 workspaces: `op1_product`, `op1_marketing`, `op1_sales`, `op1_operations`, and the `op1_ceo` manager.
- Explain the "Stage-gated handoff" design: Agents don't just talk; they produce structured JSON contracts.
- Mention the 9 handoff contracts that define the business pipeline.
- Highlight the iteration loop: Operations feedback feeds back to Product/Marketing/Sales for the next cycle.

---

## Segment 3: CEO Orchestrator Live Demo (2:30–5:00)
**Visual:** Terminal (Main Demo).

### Terminal Commands
```bash
# Run the orchestrator in dry-run mode
python3 workspaces/op1_ceo/scripts/run_ceo_multi_agent_orchestrator_v1.py --dry-run

# Inspect the summary and venture state
cat workspaces/op1_ceo/research/ceo_orchestration/orchestrator_summary.latest.json | python3 -m json.tool
cat workspaces/op1_ceo/research/ceo_orchestration/venture_state.latest.json | python3 -m json.tool
```

### Talking Points
- Run the orchestrator script. Explain that `--dry-run` simulates the 4-agent sequence (Product → Marketing → Sales → Operations).
- Show the output: Realistic simulation replies generated from real historical handoff data.
- Open `venture_state.latest.json`: Point out `mrr_usd: 49.0` and the list of `deployed_urls`.
- This is the "control plane" for the entire venture.

---

## Segment 4: Real Evidence (5:00–7:00)
**Visual:** Browser (Vercel Tabs) + Terminal.

### URLs to Show
- https://webproductmodularinvoice.vercel.app
- https://webproductmodularchargeback.vercel.app
- https://webproductlandingstage3validation.vercel.app

### Terminal Commands
```bash
cat handoffs/sales_to_operations.json | python3 -m json.tool | head -30
```

### Talking Points
- Flip through the 3 pre-loaded Vercel tabs. These are 3 of the **6 live products** deployed by our Product agent.
- Show `sales_to_operations.json` in the terminal.
- Cite the real numbers: **13 prospects** contacted, **6 replies** received, **1 customer** converted.
- This is the evidence of the system working in the wild to generate **$49 MRR**.

---

## Segment 5: The Iteration Loop (7:00–8:30)
**Visual:** Terminal.

### Terminal Commands
```bash
cat handoffs/operations_to_product.json | python3 -m json.tool | head -30
```

### Talking Points
- How do we grow? The Iteration Loop.
- Show `operations_to_product.json`: 10 feedback items with P2/P3 priority.
- Explain how the Operations agent analyzes sales data/objections and feeds improvements back to Product for the next cycle.
- This creates a self-improving business flywheel.

---

## Segment 6: Close + Call to Action (8:30–9:30)
**Visual:** Terminal with the clone command.

### Talking Points
- Summary: We're at **$49 MRR**. The path to $100 is clear as the next automated cycle runs.
- Judges can verify everything themselves. The repo is designed to be cloned and run in under 60 seconds.
- Thank the judges for their time.

### Clone Command (Show on screen)
```bash
git clone https://github.com/Daihaolin201/OperatorOne
cd OperatorOne
git checkout dennis/automation-framework
python3 workspaces/op1_ceo/scripts/run_ceo_multi_agent_orchestrator_v1.py --dry-run
```
