const PRODUCT_SPEC = {
  "project_id": "proj-opp-005-invoice-followup-v1",
  "problem_statement": "Expense reimbursement remains chaotic and fraud-prone with manual checks.",
  "value_proposition": "Turn overdue invoices into a daily follow-up action queue",
  "adapter": "invoice-followup",
  "rules": [
    {
      "id": "invoice-overdue",
      "priority": 10,
      "keywords": [
        "overdue",
        "invoice",
        "payment",
        "late"
      ],
      "first_step": "Send one structured reminder today with invoice amount, due date, and a clear 48-hour action deadline.",
      "next_steps": [
        "Schedule auto-follow-up in 48 hours if unpaid.",
        "Escalate tone after second miss while preserving professionalism.",
        "Log response status to avoid duplicate chasing."
      ]
    },
    {
      "id": "invoice-ghosting",
      "priority": 30,
      "keywords": [
        "ghost",
        "ghosting",
        "ignoring",
        "no reply",
        "silent",
        "invoice",
        "payment"
      ],
      "first_step": "Switch to a final polite escalation template with a concrete payment link and escalation date.",
      "next_steps": [
        "Use one channel change (email -> phone or SMS).",
        "Offer one short payment plan option to remove friction.",
        "Mark account for pause-of-service trigger if no response by deadline."
      ]
    }
  ],
  "default_response": {
    "first_step": "Map unpaid invoices by age bucket (0-7, 8-30, 31+) and start with the highest-value overdue account.",
    "next_steps": [
      "Use one template per age bucket.",
      "Track responses and paid/unpaid status daily.",
      "Escalate only after predefined no-response window."
    ]
  },
  "metrics": {
    "success_metric": "Qualified intent captures",
    "target": "At least 5 qualified leads from first 20 targeted users in 14 days",
    "kill_criteria": [
      "Fewer than 2 qualified intent captures after 20 targeted visitors",
      "Core workflow completion rate below 20% in first-session usage"
    ]
  }
};

        function parseBody(req) {
          if (!req.body) return {};
          if (typeof req.body === "object") return req.body;
          try { return JSON.parse(req.body); } catch (e) { return {}; }
        }

        function keywordScore(rule, normalizedInput) {
          const keywords = Array.isArray(rule.keywords) ? rule.keywords : [];
          let hits = 0;
          for (const kw of keywords) {
            const token = String(kw || "").toLowerCase().trim();
            if (!token) continue;
            if (normalizedInput.includes(token)) hits += 1;
          }
          const priority = Number(rule.priority || 0);
          return hits + (priority / 100);
        }

        function chooseRule(input) {
          const normalized = String(input || "").toLowerCase();
          const rules = Array.isArray(PRODUCT_SPEC.rules) ? PRODUCT_SPEC.rules : [];
          let bestRule = null;
          let bestScore = 0;

          for (const rule of rules) {
            const score = keywordScore(rule, normalized);
            if (score > bestScore) {
              bestRule = rule;
              bestScore = score;
            }
          }

          return bestScore > 0 ? bestRule : null;
        }

        module.exports = (req, res) => {
          if (req.method !== "POST") {
            res.status(405).json({ error: "Method not allowed" });
            return;
          }

          const body = parseBody(req);
          const input = String(body.input || "").trim();
          if (!input || input.length < 8) {
            res.status(400).json({ error: "input is required (min 8 chars)" });
            return;
          }
          if (input.length > 2000) {
            res.status(400).json({ error: "input is too long (max 2000 chars)" });
            return;
          }

          const matched = chooseRule(input);
          const defaultResponse = PRODUCT_SPEC.default_response || {};
          const firstStep = matched?.first_step || defaultResponse.first_step || "Define one focused first step.";
          const nextSteps = Array.isArray(matched?.next_steps) && matched.next_steps.length > 0
            ? matched.next_steps
            : (Array.isArray(defaultResponse.next_steps) ? defaultResponse.next_steps : []);

          res.status(200).json({
            first_step: firstStep,
            next_steps: nextSteps,
            rule_id: matched?.id || "default",
            context: {
              project_id: PRODUCT_SPEC.project_id,
              adapter: PRODUCT_SPEC.adapter,
              metric: PRODUCT_SPEC.metrics?.success_metric || null,
              target: PRODUCT_SPEC.metrics?.target || null
            }
          });
        };
