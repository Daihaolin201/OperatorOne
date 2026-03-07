module.exports = (req, res) => {
          res.status(200).json({
  "project_id": "proj-opp-001-invoice-followup-v1",
  "adapter": {
    "name": "invoice-followup",
    "display_name": "Invoice Follow-up Assistant",
    "description": "For service businesses handling overdue invoices and manual collection follow-up.",
    "match_score": 0.429,
    "match_reason": "keyword_match"
  },
  "source": {
    "opportunity_id": "opp_001",
    "stage": "stage2",
    "selection_reason": "explicit_opportunity",
    "decision_confidence": "low",
    "decision_weighted_score": 1.894
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
