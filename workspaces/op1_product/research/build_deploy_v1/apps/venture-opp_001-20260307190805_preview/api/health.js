module.exports = (req, res) => {
  res.status(200).json({
    status: "ok",
    service: "op1-product-web-build-deploy-v1.1",
    project_id: "proj-opp-001-invoice-followup-v1",
    from_opportunity_id: "opp_001",
    adapter: "invoice-followup",
    timestamp: new Date().toISOString()
  });
};
