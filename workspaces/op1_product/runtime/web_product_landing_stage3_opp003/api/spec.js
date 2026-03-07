module.exports = (req, res) => {
          res.status(200).json({
  "project_id": "proj-opp-003-client-reporting-v1",
  "adapter": {
    "name": "client-reporting",
    "display_name": "Client Reporting Assistant",
    "description": "For agencies producing recurring client reports and KPI summaries.",
    "match_score": 1.0,
    "match_reason": "forced"
  },
  "source": {
    "opportunity_id": "opp_003",
    "stage": "stage2",
    "selection_reason": "explicit_opportunity",
    "decision_confidence": "high",
    "decision_weighted_score": 3.964
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
