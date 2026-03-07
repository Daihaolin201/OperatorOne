module.exports = (req, res) => {
          res.status(200).json({
  "project_id": "proj-opp-006-client-reporting-v1",
  "adapter": {
    "name": "client-reporting",
    "display_name": "Client Reporting Assistant",
    "description": "For agencies producing recurring client reports and KPI summaries.",
    "match_score": 0.167,
    "match_reason": "keyword_match"
  },
  "source": {
    "opportunity_id": "opp_006",
    "stage": "stage2",
    "selection_reason": "explicit_opportunity",
    "decision_confidence": "high",
    "decision_weighted_score": 3.904
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
