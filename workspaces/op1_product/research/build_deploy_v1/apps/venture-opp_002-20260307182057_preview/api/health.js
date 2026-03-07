module.exports = (req, res) => {
  res.status(200).json({
    status: "ok",
    service: "op1-product-web-build-deploy-v1.1",
    project_id: "proj-opp-002-chargeback-response-v1",
    from_opportunity_id: "opp_002",
    adapter: "chargeback-response",
    timestamp: new Date().toISOString()
  });
};
