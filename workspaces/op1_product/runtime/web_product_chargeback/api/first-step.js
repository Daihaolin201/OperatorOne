const PRODUCT_SPEC = {
  "project_id": "proj-opp-001-chargeback-response-v1",
  "problem_statement": "Chargeback disputes are handled ad hoc, causing avoidable revenue loss and missed response deadlines.",
  "value_proposition": "Respond to chargebacks faster with an evidence-first workflow. Designed for Ecommerce operator teams in Ecommerce to validate demand quickly.",
  "adapter": "chargeback-response",
  "rules": [
    {
      "id": "chargeback-burst",
      "priority": 10,
      "keywords": [
        "chargeback",
        "dispute",
        "seven",
        "many",
        "burst"
      ],
      "first_step": "Prioritize disputes by amount and deadline, then submit one complete proof bundle for the highest-value case today.",
      "next_steps": [
        "Attach delivery confirmation, customer communication, and order metadata.",
        "Use a consistent evidence template across all cases.",
        "Track won/lost outcomes to refine fraud prevention rules."
      ]
    },
    {
      "id": "friendly-fraud",
      "priority": 8,
      "keywords": [
        "delivered",
        "friendly fraud",
        "not received",
        "unauthorized"
      ],
      "first_step": "Generate a customer-communication timeline and pair it with proof-of-delivery before submitting the dispute.",
      "next_steps": [
        "Highlight transaction authorization evidence.",
        "Bundle policy acceptance and tracking milestones.",
        "Flag repeat offenders for future order review."
      ]
    }
  ],
  "default_response": {
    "first_step": "Create one evidence checklist and apply it to every open dispute this week.",
    "next_steps": [
      "Sort cases by financial impact.",
      "Automate evidence collection where possible.",
      "Review dispute reason trends weekly."
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
