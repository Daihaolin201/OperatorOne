function parseBody(req) {
  if (!req.body) return {};
  if (typeof req.body === "object") return req.body;
  try { return JSON.parse(req.body); } catch (e) { return {}; }
}

function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

module.exports = (req, res) => {
  if (req.method !== "POST") {
    res.status(405).json({ error: "Method not allowed" });
    return;
  }

  const body = parseBody(req);
  const email = String(body.email || "").trim().toLowerCase();
  if (!email || email.length > 254 || !isValidEmail(email)) {
    res.status(400).json({ error: "Valid email is required" });
    return;
  }

  res.status(200).json({
    accepted: true,
    project_id: "proj-opp-002-chargeback-response-v1",
    message: "Join pilot confirmed. You're on the early-access list."
  });
};
