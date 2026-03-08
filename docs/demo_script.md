# OperatorOne CEOClaw Demo Script (5-10 Minutes)

**Title:** OperatorOne CEOClaw — The First CEO-in-a-Box for the Internet Business
**Target Duration:** 8 minutes 30 seconds
**Tone:** Technical, Professional, Results-Oriented

---

## 0. Opening Hook (30s)
**Shot:** Presenter (on-camera) or Title Card with Logo (`docs/assets/logo.png`)
**Narration:**
What if an AI could run your internet business? I'm not talking about a chatbot that answers emails. I'm talking about a CEO that scouts opportunities, builds landing pages, launches marketing campaigns, and manages the entire P&L. Today, we're introducing OperatorOne CEOClaw — the first closed-loop, multi-agent orchestrator powered by Z.AI's GLM-5, built for the UK AI Agent Hackathon EP4.

---

## 1. Problem + Solution (1 min)
**Shot:** Slide showing "The Fragile Business" (Manual Handoffs, Context Loss) vs "The Autonomous Venture" (Unified State, Closed Loop)
**Narration:**
Most AI applications today are point solutions. You have a writer, a coder, a researcher. But the glue — the strategy, the handoffs, the *accountability* — is still human. OperatorOne changes that. We've built a system that treats an entire internet business as a single, observable state machine. By utilizing the CEOClaw orchestrator, we've eliminated the friction between "thinking" and "executing," allowing a single model to govern the entire venture lifecycle.

---

## 2. System Overview (1 min)
**Shot:** Architecture diagram (`docs/assets/pipeline.png`)
**Narration:**
Our architecture is built on five pillars. At the center is the CEO Orchestrator. It doesn't just "prompt" other agents; it manages a global `venture_state.latest.json`. Surrounding it are four specialized department heads:
- **Product Agent:** Discovers and screens startup ideas.
- **Marketing Agent:** Conducts SEO experiments and launches campaigns.
- **Sales Agent:** Handles prospecting and outreach.
- **Operations Agent:** Tracks MRR and customer feedback loops.
Every transition is a validated handoff, ensuring no context is lost as the business grows.

---

## 3. Live Dashboard Demo (1.5 min)
**Shot:** Screen recording of Browser at `http://localhost:8765`. 
**Action:** Mouse hovers over "Run CEOClaw Demo" and clicks.
**Narration:**
Let's see it in action. This is the OperatorOne Dashboard. No complex CLI required — just one click to trigger the CEOClaw demo. As I click "Run," the `zai_preflight.py` gate immediately validates our Z.AI configuration. This isn't just a script; it's a production-grade pipeline. The dashboard provides a real-time window into the CEO's mind, showing us exactly which stage of the venture lifecycle is active.

---

## 4. Run Timeline (1 min)
**Shot:** Dashboard timeline progressing through Product -> Marketing -> Sales -> Operations.
**Narration:**
Watch the timeline. We're moving through the four stages in real-time. 
- **Stage 1 (Product):** The CEO identifies a high-margin opportunity in "Invoice Follow-up Automation."
- **Stage 2 (Marketing):** It generates 19 content drafts and validates them against SEO patterns.
- **Stage 3 (Sales):** 13 prospects are identified and 6 personalized Vercel URLs are deployed.
- **Stage 4 (Operations):** The system reconciles the $49 MRR and prepares the next iteration.
Each step is documented in the rehearsal evidence at `.sisyphus/evidence/task-13-e2e-rehearsal.json`.

---

## 5. GLM-5 Evidence (1 min)
**Shot:** Terminal screen. 
**Action:** `curl http://localhost:8765/replay | jq .model_usage`
**Narration:**
The core of this intelligence is Z.AI's GLM-5. We're not using standard GPT models here. Look at the replay data: we can see the `model_usage` block clearly identifies the `z.ai` provider and the `glm-5` model. With its 744B MoE architecture and 202K context window, GLM-5 handles the complex cross-departmental reasoning required to keep the `venture_state` consistent.

---

## 6. Handoff Chain (30s)
**Shot:** File browser showing `handoffs/` directory with 9 JSON files.
**Action:** Quickly open `handoffs/product_to_marketing.json`.
**Narration:**
Transparency is key. We don't hide the "magic" in hidden logs. Every departmental handoff is a physical JSON file in the `handoffs/` directory. You can audit exactly what the Product agent told the Marketing agent. This is how we ensure reproducibility and reliability in an autonomous system.

---

## 7. Real Results (1 min)
**Shot:** Displaying `workspaces/op1_ceo/research/ceo_orchestration/venture_state.latest.json` or the Summary Table.
**Narration:**
What are the results of a single CEOClaw run?
- **$49 MRR** generated from our first automated customer.
- **13 Prospects** identified and ranked.
- **6 Vercel URLs** live and serving landing pages.
- **19 Marketing drafts** ready for distribution.
This isn't a simulation. These are real artifacts, real prospects, and real revenue tracking handled entirely by the agentic fleet.

---

## 8. Extension Points + Z.AI Gold (30s)
**Shot:** Code editor showing `dashboard/zai_preflight.py`.
**Narration:**
We've built this to be extensible. Our Z.AI preflight gate ensures that any model swap or configuration change is caught before it costs you money. We've optimized the prompts for GLM-5's specific MoE architecture, competing for the Z.AI Gold bounty by proving that high-reasoning models can govern complex, multi-stage business workflows.

---

## 9. Closing (30s)
**Shot:** Presenter (on-camera)
**Narration:**
OperatorOne CEOClaw isn't just an agent; it's an operating system for your next venture. Check out the full repository and our technical docs in the link below. We are Team OperatorOne, and we're building the future of autonomous business. Thank you for watching, and we look forward to your judgment.

---

# Live Failure Recovery (Backup)

**Scenario:** The live run at `http://localhost:8765` stalls or returns an error.
**Recovery Steps:**
1. **Cancel Run:** Click the "Stop/Cancel" button on the dashboard.
2. **Hard Reset:** Run `python scripts/reset_generated_artifacts.py` in the terminal (off-camera).
3. **Trigger Manual Pipeline:** Use the recovery drill evidence at `.sisyphus/evidence/task-13-recovery-drill.json`.
4. **Narrative Shift:** "Even in autonomous systems, recovery is a first-class citizen. I've triggered a hard reset and manually resumed the pipeline from the last valid checkpoint. CEOClaw handles this gracefully by reconciling the `venture_state` against the existing handoff files."

**Backup Evidence:** 
- `.sisyphus/evidence/task-13-recovery-drill.json`
- `handoffs/_meta/validation_report.latest.json`
