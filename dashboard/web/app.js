const els = {
  refreshBtn: document.getElementById("refreshBtn"),
  lastUpdated: document.getElementById("lastUpdated"),
  demoGateStatus: document.getElementById("demoGateStatus"),
  demoGateReasons: document.getElementById("demoGateReasons"),
  liveGateStatus: document.getElementById("liveGateStatus"),
  liveGateReasons: document.getElementById("liveGateReasons"),
  manualArmText: document.getElementById("manualArmText"),
  armOnBtn: document.getElementById("armOnBtn"),
  armOffBtn: document.getElementById("armOffBtn"),
  agentsTableBody: document.querySelector("#agentsTable tbody"),
  capabilitiesTableBody: document.querySelector("#capabilitiesTable tbody"),
  handoffsTableBody: document.querySelector("#handoffsTable tbody"),
  channelsSummary: document.getElementById("channelsSummary"),
  channelSelect: document.getElementById("channelSelect"),
  channelAccount: document.getElementById("channelAccount"),
  channelToken: document.getElementById("channelToken"),
  channelBotToken: document.getElementById("channelBotToken"),
  channelAppToken: document.getElementById("channelAppToken"),
  channelWebhookUrl: document.getElementById("channelWebhookUrl"),
  connectChannelBtn: document.getElementById("connectChannelBtn"),
  disconnectChannelBtn: document.getElementById("disconnectChannelBtn"),
  dryRunChannelBtn: document.getElementById("dryRunChannelBtn"),
  channelActionResult: document.getElementById("channelActionResult"),
  runSecretsAuditBtn: document.getElementById("runSecretsAuditBtn"),
  reloadSecretsBtn: document.getElementById("reloadSecretsBtn"),
  secretsResult: document.getElementById("secretsResult"),
  apiName: document.getElementById("apiName"),
  apiBaseUrl: document.getElementById("apiBaseUrl"),
  apiSecretRef: document.getElementById("apiSecretRef"),
  apiOwnerAgent: document.getElementById("apiOwnerAgent"),
  apiNotes: document.getElementById("apiNotes"),
  saveApiBtn: document.getElementById("saveApiBtn"),
  refreshApiBtn: document.getElementById("refreshApiBtn"),
  apiConnectorsTableBody: document.querySelector("#apiConnectorsTable tbody"),
  industryPatterns: document.getElementById("industryPatterns"),
};

let state = {
  snapshot: null,
};

function statusToClass(status) {
  const normalized = String(status || "unknown").toLowerCase();
  if (["passed", "ready"].includes(normalized)) return "status-passed";
  if (["warning", "review_required"].includes(normalized)) return "status-warning";
  if (["failed", "blocked"].includes(normalized)) return "status-failed";
  return "status-unknown";
}

function renderStatusPill(el, status) {
  const normalized = String(status || "UNKNOWN").toUpperCase();
  el.className = `status-pill ${statusToClass(status)}`;
  el.textContent = normalized;
}

function safeText(text) {
  if (text === null || text === undefined) return "";
  if (typeof text === "object") return JSON.stringify(text);
  return String(text);
}

function asList(value) {
  return Array.isArray(value) ? value : [];
}

async function getJSON(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`HTTP ${res.status}: ${txt}`);
  }
  return await res.json();
}

async function postJSON(url, payload = {}) {
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  const text = await res.text();
  let body = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = { ok: false, raw: text };
  }
  if (!res.ok) {
    throw new Error(body?.error || `HTTP ${res.status}: ${text}`);
  }
  return body;
}

function renderReasons(target, reasons) {
  target.innerHTML = "";
  const list = asList(reasons);
  if (list.length === 0) {
    const li = document.createElement("li");
    li.textContent = "无阻塞原因";
    target.appendChild(li);
    return;
  }
  for (const reason of list) {
    const li = document.createElement("li");
    li.textContent = safeText(reason);
    target.appendChild(li);
  }
}

function renderAgents(agents) {
  els.agentsTableBody.innerHTML = "";
  for (const agent of asList(agents)) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${safeText(agent.agent)}</td>
      <td><span class="status-pill ${statusToClass(agent.status)}">${String(agent.status || "UNKNOWN").toUpperCase()}</span></td>
      <td>${safeText(agent.passed || 0)}</td>
      <td>${safeText(agent.warning || 0)}</td>
      <td>${safeText(agent.failed || 0)}</td>
      <td>${safeText(agent.capabilityTotal || 0)}</td>
    `;
    els.agentsTableBody.appendChild(tr);
  }
}

function shortMetrics(metrics) {
  if (!metrics || typeof metrics !== "object") return "-";
  const keys = Object.keys(metrics).slice(0, 4);
  return keys
    .map((k) => `${k}: ${typeof metrics[k] === "object" ? JSON.stringify(metrics[k]).slice(0, 64) : String(metrics[k])}`)
    .join(" | ");
}

function renderCapabilities(capabilities) {
  els.capabilitiesTableBody.innerHTML = "";
  for (const cap of asList(capabilities)) {
    const evidence = asList(cap.evidence)
      .map((item) => safeText(item.path || ""))
      .join("\n");

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${safeText(cap.agent)}</td>
      <td>${safeText(cap.label)}</td>
      <td><span class="status-pill ${statusToClass(cap.status)}">${String(cap.status || "UNKNOWN").toUpperCase()}</span></td>
      <td>${shortMetrics(cap.metrics)}</td>
      <td>${safeText(cap.updatedAt || "-")}</td>
      <td><pre class="small">${safeText(evidence || "-")}</pre></td>
    `;
    els.capabilitiesTableBody.appendChild(tr);
  }
}

function renderHandoffs(handoffs) {
  const items = asList(handoffs?.items);
  els.handoffsTableBody.innerHTML = "";
  for (const item of items) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${safeText(item.name)}</td>
      <td><span class="status-pill ${statusToClass(item.status)}">${String(item.status || "UNKNOWN").toUpperCase()}</span></td>
      <td>${safeText(item.from || "-")}</td>
      <td>${safeText(item.to || "-")}</td>
      <td>${safeText(item.generatedAt || "-")}</td>
      <td>${safeText(item.path || "-")}</td>
    `;
    els.handoffsTableBody.appendChild(tr);
  }
}

function renderChannelsSummary(snapshot) {
  const channelsStatus = snapshot?.runtime?.channelsStatus?.data || {};
  const channelsList = snapshot?.runtime?.channelsList?.data || {};
  const summary = {
    status: channelsStatus,
    list: channelsList,
  };
  els.channelsSummary.textContent = JSON.stringify(summary, null, 2);
}

function renderIndustryPatterns(snapshot) {
  const patterns = asList(snapshot?.industryPatterns?.patterns);
  els.industryPatterns.innerHTML = "";
  for (const p of patterns) {
    const li = document.createElement("li");
    li.innerHTML = `
      <strong>${safeText(p.name)}</strong><br />
      <span class="small">Source: ${safeText(p.source)}</span><br />
      <span>${safeText(p.why)}</span><br />
      <span class="small">落地: ${safeText(p.applied)}</span>
    `;
    els.industryPatterns.appendChild(li);
  }
}

function renderApiConnectors(snapshot) {
  const items = asList(snapshot?.runtimeState?.apiConnectors?.items);
  els.apiConnectorsTableBody.innerHTML = "";

  for (const item of items) {
    const tr = document.createElement("tr");
    const tdAction = document.createElement("td");
    const btn = document.createElement("button");
    btn.className = "secondary";
    btn.textContent = "删除";
    btn.addEventListener("click", async () => {
      try {
        await postJSON("/api/integrations/api-connectors/delete", { id: item.id });
        await refreshAll();
      } catch (err) {
        alert(`删除失败: ${err.message}`);
      }
    });
    tdAction.appendChild(btn);

    tr.innerHTML = `
      <td>${safeText(item.id)}</td>
      <td>${safeText(item.name)}</td>
      <td>${safeText(item.baseUrl || "-")}</td>
      <td>${safeText(item.secretRef || "-")}</td>
      <td>${safeText(item.ownerAgent || "-")}</td>
    `;
    tr.appendChild(tdAction);
    els.apiConnectorsTableBody.appendChild(tr);
  }
}

function renderSnapshot(snapshot) {
  state.snapshot = snapshot;

  els.lastUpdated.textContent = `更新于 ${snapshot.generatedAt}`;

  renderStatusPill(els.demoGateStatus, snapshot.readiness?.demo?.status);
  renderStatusPill(els.liveGateStatus, snapshot.readiness?.liveExternalContact?.status);
  renderReasons(els.demoGateReasons, snapshot.readiness?.demo?.reasons);
  renderReasons(els.liveGateReasons, snapshot.readiness?.liveExternalContact?.reasons);

  const armEnabled = Boolean(snapshot.runtimeState?.flags?.manualArmEnabled);
  renderStatusPill(els.manualArmText, armEnabled ? "ready" : "review_required");
  els.manualArmText.textContent = armEnabled ? "ON" : "OFF";

  renderAgents(snapshot.agents);
  renderCapabilities(snapshot.capabilities);
  renderHandoffs(snapshot.handoffs);
  renderChannelsSummary(snapshot);
  renderApiConnectors(snapshot);
  renderIndustryPatterns(snapshot);
}

async function refreshAll() {
  const data = await getJSON("/api/snapshot");
  renderSnapshot(data.snapshot);
}

function collectChannelPayload() {
  const channel = els.channelSelect.value;
  const payload = {
    channel,
  };

  const account = els.channelAccount.value.trim();
  if (account) payload.account = account;

  const token = els.channelToken.value.trim();
  const botToken = els.channelBotToken.value.trim();
  const appToken = els.channelAppToken.value.trim();
  const webhookUrl = els.channelWebhookUrl.value.trim();

  if (token) payload.token = token;
  if (botToken) payload.botToken = botToken;
  if (appToken) payload.appToken = appToken;
  if (webhookUrl) payload.webhookUrl = webhookUrl;

  return payload;
}

async function connectChannel(dryRun = false) {
  const payload = collectChannelPayload();
  payload.dryRun = dryRun;
  const res = await postJSON("/api/integrations/channel/connect", payload);
  els.channelActionResult.textContent = JSON.stringify(res, null, 2);
  if (!dryRun) await refreshAll();
}

async function disconnectChannel() {
  const payload = {
    channel: els.channelSelect.value,
  };
  const account = els.channelAccount.value.trim();
  if (account) payload.account = account;
  payload.delete = true;

  const res = await postJSON("/api/integrations/channel/disconnect", payload);
  els.channelActionResult.textContent = JSON.stringify(res, null, 2);
  await refreshAll();
}

async function runSecretsAudit() {
  const res = await postJSON("/api/integrations/secrets/audit", {});
  els.secretsResult.textContent = JSON.stringify(res, null, 2);
  await refreshAll();
}

async function reloadSecrets() {
  const res = await postJSON("/api/integrations/secrets/reload", {});
  els.secretsResult.textContent = JSON.stringify(res, null, 2);
  await refreshAll();
}

async function saveApiConnector() {
  const payload = {
    name: els.apiName.value.trim(),
    baseUrl: els.apiBaseUrl.value.trim(),
    secretRef: els.apiSecretRef.value.trim(),
    ownerAgent: els.apiOwnerAgent.value,
    notes: els.apiNotes.value.trim(),
  };
  if (!payload.name) {
    alert("请填写 API 名称");
    return;
  }
  await postJSON("/api/integrations/api-connectors/upsert", payload);
  els.apiName.value = "";
  els.apiBaseUrl.value = "";
  els.apiSecretRef.value = "";
  els.apiNotes.value = "";
  await refreshAll();
}

async function setManualArm(enabled) {
  await postJSON("/api/runtime-flags/manual-arm", { enabled });
  await refreshAll();
}

function bindEvents() {
  els.refreshBtn.addEventListener("click", () => {
    refreshAll().catch((err) => alert(`刷新失败: ${err.message}`));
  });

  els.armOnBtn.addEventListener("click", () => {
    setManualArm(true).catch((err) => alert(`设置失败: ${err.message}`));
  });

  els.armOffBtn.addEventListener("click", () => {
    setManualArm(false).catch((err) => alert(`设置失败: ${err.message}`));
  });

  els.connectChannelBtn.addEventListener("click", () => {
    connectChannel(false).catch((err) => {
      els.channelActionResult.textContent = `接入失败: ${err.message}`;
    });
  });

  els.disconnectChannelBtn.addEventListener("click", () => {
    disconnectChannel().catch((err) => {
      els.channelActionResult.textContent = `断开失败: ${err.message}`;
    });
  });

  els.dryRunChannelBtn.addEventListener("click", () => {
    connectChannel(true).catch((err) => {
      els.channelActionResult.textContent = `预览失败: ${err.message}`;
    });
  });

  els.runSecretsAuditBtn.addEventListener("click", () => {
    runSecretsAudit().catch((err) => {
      els.secretsResult.textContent = `secrets audit 失败: ${err.message}`;
    });
  });

  els.reloadSecretsBtn.addEventListener("click", () => {
    reloadSecrets().catch((err) => {
      els.secretsResult.textContent = `secrets reload 失败: ${err.message}`;
    });
  });

  els.saveApiBtn.addEventListener("click", () => {
    saveApiConnector().catch((err) => alert(`保存失败: ${err.message}`));
  });

  els.refreshApiBtn.addEventListener("click", () => {
    refreshAll().catch((err) => alert(`刷新失败: ${err.message}`));
  });
}

async function main() {
  bindEvents();
  await refreshAll();
}

main().catch((err) => {
  console.error(err);
  alert(`初始化失败: ${err.message}`);
});
