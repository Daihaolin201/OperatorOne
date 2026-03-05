const PRODUCT_SPEC = {
  "project_id": "proj-opp-003-client-reporting-v1",
  "problem_statement": "Agencies rebuild client reports manually each cycle, creating delays, inconsistency, and low client confidence.",
  "value_proposition": "Ship client-ready monthly reporting with one repeatable workflow",
  "adapter": "client-reporting",
  "rules": [
    {
      "id": "monthly-reporting",
      "priority": 10,
      "keywords": [
        "monthly",
        "report",
        "client",
        "manual"
      ],
      "first_step": "Define a one-page KPI summary template before adding channel-specific detail.",
      "next_steps": [
        "Standardize metric definitions across clients.",
        "Auto-fill narrative sections from KPI deltas.",
        "Collect client questions to improve the next template iteration."
      ]
    },
    {
      "id": "unclear-performance",
      "priority": 8,
      "keywords": [
        "confusing",
        "unclear",
        "explaining",
        "results"
      ],
      "first_step": "Rewrite report output into business outcomes first, then append technical metrics.",
      "next_steps": [
        "Map each KPI to an explicit business decision.",
        "Highlight one win and one risk every cycle.",
        "Use consistent visuals for comparability."
      ]
    }
  ],
  "default_response": {
    "first_step": "Start with one reusable reporting structure and avoid custom format changes per client.",
    "next_steps": [
      "Lock metric glossary.",
      "Automate export collection.",
      "Review report quality with a short QA checklist."
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
