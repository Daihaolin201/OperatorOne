module.exports = (req, res) => {
          res.status(200).json({
  "project_id": "proj-opp-001-chargeback-response-v1",
  "adapter": {
    "name": "chargeback-response",
    "display_name": "Chargeback Response Assistant",
    "description": "For ecommerce operators responding to payment disputes and fraud losses.",
    "match_score": 1.0,
    "match_reason": "forced"
  },
  "source": {
    "opportunity_id": "opp_001",
    "stage": "stage2",
    "selection_reason": "top_advance_by_score",
    "decision_confidence": "high",
    "decision_weighted_score": 4.084
  },
  "metrics": {
    "success_metric": "Qualified intent captures",
    "target": "At least 5 qualified leads from first 20 targeted users in 14 days",
    "kill_criteria": [
      "Fewer than 2 qualified intent captures after 20 targeted visitors",
      "Core workflow completion rate below 20% in first-session usage"
    ]
  }
});
        };
