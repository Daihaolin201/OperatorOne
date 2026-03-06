const els = {
  refreshBtn: document.getElementById("refreshBtn"),
  lastUpdated: document.getElementById("lastUpdated"),

  demoGateStatus: document.getElementById("demoGateStatus"),
  liveGateStatus: document.getElementById("liveGateStatus"),
  manualArmStatus: document.getElementById("manualArmStatus"),
  armOnBtn: document.getElementById("armOnBtn"),
  armOffBtn: document.getElementById("armOffBtn"),
  vercelStatus: document.getElementById("vercelStatus"),

  quickstartList: document.getElementById("quickstartList"),
  recommendedActions: document.getElementById("recommendedActions"),
  feedbackBar: document.getElementById("feedbackBar"),
  runPreflightBtn: document.getElementById("runPreflightBtn"),
  runRehearsalBtn: document.getElementById("runRehearsalBtn"),

  stageFlowTableBody: document.querySelector("#stageFlowTable tbody"),
  stageResultsTableBody: document.querySelector("#stageResultsTable tbody"),
  deploymentsTableBody: document.querySelector("#deploymentsTable tbody"),

  tabs: document.getElementById("tabs"),

  refreshIdeasBtn: document.getElementById("refreshIdeasBtn"),
  ideasTableBody: document.querySelector("#ideasTable tbody"),
  venturesTableBody: document.querySelector("#venturesTable tbody"),

  productMode: document.getElementById("productMode"),
  runProductBtn: document.getElementById("runProductBtn"),
  productSummary: document.getElementById("productSummary"),

  runMarketingSeoBtn: document.getElementById("runMarketingSeoBtn"),
  runMarketingContentBtn: document.getElementById("runMarketingContentBtn"),
  runMarketingCampaignBtn: document.getElementById("runMarketingCampaignBtn"),
  approveSelectedContentBtn: document.getElementById("approveSelectedContentBtn"),
  rejectSelectedContentBtn: document.getElementById("rejectSelectedContentBtn"),
  contentCandidatesTableBody: document.querySelector("#contentCandidatesTable tbody"),
  campaignCandidatesTableBody: document.querySelector("#campaignCandidatesTable tbody"),

  runSalesProspectingBtn: document.getElementById("runSalesProspectingBtn"),
  runSalesOutreachPlanBtn: document.getElementById("runSalesOutreachPlanBtn"),
  approveSalesOutreachBtn: document.getElementById("approveSalesOutreachBtn"),
  dispatchSalesSimBtn: document.getElementById("dispatchSalesSimBtn"),
  dispatchSalesLiveBtn: document.getElementById("dispatchSalesLiveBtn"),
  runSalesConversionSimBtn: document.getElementById("runSalesConversionSimBtn"),
  runSalesConversionLiveBtn: document.getElementById("runSalesConversionLiveBtn"),
  salesSegmentsTableBody: document.querySelector("#salesSegmentsTable tbody"),
  salesSummary: document.getElementById("salesSummary"),

  runOpsFullBtn: document.getElementById("runOpsFullBtn"),
  writebackOpsBtn: document.getElementById("writebackOpsBtn"),
  confirmIterateBtn: document.getElementById("confirmIterateBtn"),
  loopTodosTableBody: document.querySelector("#loopTodosTable tbody"),
  opsSummary: document.getElementById("opsSummary"),

  jobsTableBody: document.querySelector("#jobsTable tbody"),
  runsTableBody: document.querySelector("#runsTable tbody"),

  artifactPath: document.getElementById("artifactPath"),
  artifactContent: document.getElementById("artifactContent"),

  actionResult: document.getElementById("actionResult"),
};

const state = {
  snapshot: null,
  monitorSnapshot: null,
  jobs: [],
  selectedTab: "idea",
  lastJobsSignature: "",
};

const FAST_REFRESH_MS = 12000;
const JOB_POLL_MS = 2000;
const MONITOR_REFRESH_MS = 60000;
let fastTimer = null;
let jobTimer = null;
let monitorTimer = null;
let refreshInFlight = false;

function safeText(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function asList(value) {
  return Array.isArray(value) ? value : [];
}

function statusClass(status) {
  const s = String(status || "unknown").toLowerCase();
  if (["passed", "ready", "succeeded", "success", "completed"].includes(s)) return "status-passed";
  if (["warning", "review_required", "running", "queued", "pending", "current"].includes(s)) return "status-warning";
  if (["failed", "blocked", "error"].includes(s)) return "status-failed";
  return "status-unknown";
}

function setPill(el, status, textOverride = null) {
  if (!el) return;
  el.className = `status-pill ${statusClass(status)}`;
  el.textContent = textOverride || String(status || "UNKNOWN").toUpperCase();
}

function formatTime(iso) {
  if (!iso) return "-";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return String(iso);
  }
}

function updateFeedback(message, kind = "info") {
  if (!els.feedbackBar) return;
  els.feedbackBar.textContent = message;
  if (kind === "error") {
    els.feedbackBar.className = "feedback status-failed";
  } else if (kind === "ok") {
    els.feedbackBar.className = "feedback status-passed";
  } else {
    els.feedbackBar.className = "feedback muted";
  }
}

async function getJSON(url) {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return await res.json();
}

async function postJSON(url, payload = {}) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const text = await res.text();
  let body = null;
  try {
    body = text ? JSON.parse(text) : {};
  } catch {
    body = { ok: false, raw: text };
  }
  if (!res.ok) {
    throw new Error(body?.error || `HTTP ${res.status}: ${text}`);
  }
  return body;
}

function activeVenture() {
  return state.snapshot?.activeVenture || null;
}

function activeVentureId() {
  return activeVenture()?.id || null;
}

function selectedContentIds() {
  const checks = document.querySelectorAll(".content-check:checked");
  const ids = [];
  checks.forEach((el) => {
    const value = String(el.value || "").trim();
    if (value) ids.push(value);
  });
  return ids;
}

function ensureActiveVentureOrAlert() {
  const id = activeVentureId();
  if (!id) {
    alert("请先在 Idea Board 创建并激活 venture。");
    return null;
  }
  return id;
}

function logActionResult(payload) {
  els.actionResult.textContent = JSON.stringify(payload, null, 2);
}

function renderTop() {
  const snapshot = state.snapshot || {};
  const monitor = state.monitorSnapshot || snapshot.monitor || {};
  const readiness = monitor?.readiness || {};

  if (snapshot.generatedAt) {
    els.lastUpdated.textContent = `更新于 ${formatTime(snapshot.generatedAt)}`;
  }

  setPill(els.demoGateStatus, readiness?.demo?.status || "unknown");
  setPill(els.liveGateStatus, readiness?.liveExternalContact?.status || "unknown");

  const arm = Boolean(snapshot.manualArmEnabled);
  setPill(els.manualArmStatus, arm ? "ready" : "review_required", arm ? "ON" : "OFF");

  const vercel = snapshot.vercel || {};
  const parts = [
    `installed=${vercel.installed ? "yes" : "no"}`,
    `auth=${vercel.authenticated ? "yes" : "no"}`,
  ];
  if (vercel.note) parts.push(`note=${vercel.note}`);
  els.vercelStatus.textContent = parts.join(" | ");
}

function renderGuide(snapshot) {
  const guide = snapshot?.guide || {};
  const quickstart = asList(guide.quickstart);
  els.quickstartList.innerHTML = "";
  for (const step of quickstart) {
    const li = document.createElement("li");
    li.textContent = safeText(step);
    els.quickstartList.appendChild(li);
  }

  const actions = asList(guide.nextRecommendedActions);
  els.recommendedActions.innerHTML = "";
  if (!actions.length) {
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.textContent = "暂无推荐动作。";
    els.recommendedActions.appendChild(empty);
    return;
  }

  for (const action of actions) {
    const box = document.createElement("div");
    box.className = "action-card";

    const title = document.createElement("div");
    title.className = "title";
    title.textContent = `${safeText(action.label)} (${safeText(action.stage)})`;

    const desc = document.createElement("div");
    desc.className = "desc";
    desc.textContent = safeText(action.description || "");

    const row = document.createElement("div");
    row.className = "row";

    const btn = document.createElement("button");
    btn.textContent = "执行此动作";
    btn.addEventListener("click", async () => {
      if (action.requiresUserChoice) {
        alert("这个动作需要你先在对应表格里选择具体项，再执行。\n例如：先选 campaign，再推进到 Sales。");
        return;
      }
      const payload = action.payload || {};
      try {
        await runStudioAction(payload, action.label);
      } catch (err) {
        updateFeedback(`执行失败: ${err.message}`, "error");
      }
    });

    row.appendChild(btn);

    box.appendChild(title);
    box.appendChild(desc);
    box.appendChild(row);
    els.recommendedActions.appendChild(box);
  }
}

function renderStageFlow(snapshot) {
  const rows = asList(snapshot.stageFlow);
  els.stageFlowTableBody.innerHTML = "";
  for (const row of rows) {
    const tr = document.createElement("tr");
    const lastRun = row.lastRun || {};
    tr.innerHTML = `
      <td>${safeText(row.stage)}</td>
      <td><span class="status-pill ${statusClass(row.state)}">${safeText(row.state).toUpperCase()}</span></td>
      <td>${safeText(row.narrative || "-")}</td>
      <td>${safeText(lastRun.action || "-")} / ${safeText(lastRun.status || "-")}</td>
    `;
    els.stageFlowTableBody.appendChild(tr);
  }
}

function summarizeStageOutput(summary) {
  if (!summary || typeof summary !== "object") return "-";
  const picks = [];
  if (summary.deploymentUrl) picks.push(`url=${summary.deploymentUrl}`);
  if (summary.previewPath) picks.push(`preview=${summary.previewPath}`);
  if (summary.vercelProject) picks.push(`project=${summary.vercelProject}`);
  if (summary.segmentIndex !== undefined) picks.push(`segment=${summary.segmentIndex}`);
  if (summary.todoCount !== undefined) picks.push(`todos=${summary.todoCount}`);
  if (summary.mode) picks.push(`mode=${summary.mode}`);
  if (!picks.length) {
    const keys = Object.keys(summary).slice(0, 4);
    return keys.map((k) => `${k}=${safeText(summary[k])}`).join(" | ") || "-";
  }
  return picks.join(" | ");
}

async function openArtifact(path) {
  if (!path) return;
  els.artifactPath.textContent = path;
  els.artifactContent.textContent = "加载中...";
  try {
    const data = await getJSON(`/api/studio/artifact?path=${encodeURIComponent(path)}`);
    if (data.binary) {
      els.artifactContent.textContent = `Binary file (size=${data.sizeBytes} bytes).\nPath: ${data.absolutePath}`;
    } else {
      els.artifactContent.textContent = data.content || "(empty)";
    }
  } catch (err) {
    els.artifactContent.textContent = `读取失败: ${err.message}`;
  }
}

function renderStageResults(snapshot) {
  const rows = asList(snapshot.stageResults);
  els.stageResultsTableBody.innerHTML = "";

  for (const row of rows) {
    const tr = document.createElement("tr");
    const run = row.run || {};
    tr.innerHTML = `
      <td>${safeText(row.stage)}</td>
      <td><span class="status-pill ${statusClass(run.status)}">${safeText(run.status).toUpperCase()}</span><br/><span class="small">${safeText(run.action || "-")}</span></td>
      <td>${safeText(summarizeStageOutput(row.summary))}</td>
      <td></td>
    `;

    const tdArt = tr.children[3];
    const artifacts = asList(row.artifacts).slice(0, 5);
    if (!artifacts.length) {
      tdArt.textContent = "-";
    } else {
      for (const art of artifacts) {
        const btn = document.createElement("button");
        btn.className = "secondary";
        btn.textContent = art.snapshotPath ? art.snapshotPath.split("/").pop() : art.type || "artifact";
        btn.addEventListener("click", () => openArtifact(art.snapshotPath || art.sourcePath));
        tdArt.appendChild(btn);
      }
    }

    els.stageResultsTableBody.appendChild(tr);
  }
}

function renderDeployments(snapshot) {
  const rows = asList(snapshot.deployments);
  els.deploymentsTableBody.innerHTML = "";
  for (const row of rows) {
    const tr = document.createElement("tr");
    const url = row.url || row.previewPath || "-";
    tr.innerHTML = `
      <td>${safeText(formatTime(row.createdAt))}</td>
      <td>${safeText(row.mode)}</td>
      <td>${safeText(row.project || "-")}</td>
      <td>${safeText(url)}</td>
    `;
    els.deploymentsTableBody.appendChild(tr);
  }
}

function renderIdeas(snapshot) {
  const ideas = asList(snapshot.ideas);
  els.ideasTableBody.innerHTML = "";

  for (const idea of ideas) {
    const tr = document.createElement("tr");

    const motivation = [
      idea?.motivation?.leadPainEvidence,
      idea?.motivation?.distributionEntry,
      idea?.motivation?.budgetSignal,
    ]
      .filter(Boolean)
      .slice(0, 2)
      .join(" | ");

    const risk = asList(idea.riskSummary).slice(0, 2).join(" | ");

    tr.innerHTML = `
      <td>${safeText(idea.opportunityId)}</td>
      <td>${safeText(idea.coreProblem || idea.title)}</td>
      <td>${safeText(motivation || "-")}</td>
      <td>${safeText(risk || "-")}</td>
      <td>${safeText(idea.feasibilityScore ?? "-")}</td>
      <td></td>
    `;

    const tdAction = tr.children[5];
    const btn = document.createElement("button");
    btn.textContent = "创建 Venture";
    btn.addEventListener("click", async () => {
      try {
        await runStudioAction(
          {
            action: "create_venture",
            opportunityId: idea.opportunityId,
            name: `${idea.opportunityId} venture`,
            async: false,
          },
          "创建 venture"
        );
      } catch (err) {
        updateFeedback(`创建 venture 失败: ${err.message}`, "error");
      }
    });
    tdAction.appendChild(btn);

    els.ideasTableBody.appendChild(tr);
  }
}

function renderVentures(snapshot) {
  const ventures = asList(snapshot.ventures);
  const activeId = snapshot.activeVentureId;
  els.venturesTableBody.innerHTML = "";

  for (const venture of ventures) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${safeText(venture.name)} ${venture.id === activeId ? '<span class="tag">active</span>' : ""}</td>
      <td>${safeText(venture.opportunityId)}</td>
      <td>${safeText(venture.stage)}</td>
      <td>${safeText(venture.cycle || 1)}</td>
      <td>${safeText(venture.status || "-")}</td>
      <td></td>
    `;

    const tdAction = tr.children[5];
    const btn = document.createElement("button");
    btn.className = "secondary";
    btn.textContent = venture.id === activeId ? "当前" : "设为当前";
    btn.disabled = venture.id === activeId;
    btn.addEventListener("click", async () => {
      try {
        await runStudioAction({ action: "set_active_venture", ventureId: venture.id, async: false }, "切换 venture");
      } catch (err) {
        updateFeedback(`切换 venture 失败: ${err.message}`, "error");
      }
    });
    tdAction.appendChild(btn);

    els.venturesTableBody.appendChild(tr);
  }
}

function renderProduct(snapshot) {
  const venture = snapshot.activeVenture;
  if (!venture) {
    els.productSummary.textContent = "请先在 Idea Board 创建并激活一个 venture。";
    return;
  }

  const links = venture.links || {};
  const summary = {
    ventureId: venture.id,
    stage: venture.stage,
    opportunityId: venture.opportunityId,
    productDeploymentUrl: links.productDeploymentUrl || null,
    productPreviewPath: links.productPreviewPath || null,
    vercelProject: links.vercelProject || null,
    lastProductAction: venture.lastActions?.product || null,
  };
  els.productSummary.textContent = JSON.stringify(summary, null, 2);
}

function renderMarketing(snapshot) {
  const ctx = snapshot.activeContext?.marketing || {};
  const content = asList(ctx.contentCandidates);
  const campaigns = asList(ctx.campaignCandidates);

  els.contentCandidatesTableBody.innerHTML = "";
  for (const item of content) {
    const tr = document.createElement("tr");
    const cid = item.content_id || item.id || "";
    const topic = item.topic || item.primary_keyword || item.intent || "-";
    tr.innerHTML = `
      <td><input type="checkbox" class="content-check" value="${safeText(cid)}" /></td>
      <td>${safeText(cid)}</td>
      <td>${safeText(item._bucket || item.queue_state || "-")}</td>
      <td>${safeText(topic)}</td>
      <td>${safeText(item.primary_keyword || item.keyword || "-")}</td>
      <td>${safeText(item.priority_score ?? item.score ?? "-")}</td>
    `;
    els.contentCandidatesTableBody.appendChild(tr);
  }

  els.campaignCandidatesTableBody.innerHTML = "";
  for (const row of campaigns) {
    const tr = document.createElement("tr");
    const campaignId = row.campaign_id || row.id || "";
    tr.innerHTML = `
      <td>${safeText(campaignId)}</td>
      <td>${safeText(row._bucket || row.queue_state || "-")}</td>
      <td>${safeText(row.primary_keyword || row.keyword || "-")}</td>
      <td>${safeText(row.readiness_score ?? "-")}</td>
      <td></td>
    `;

    const tdAction = tr.children[4];
    const btn = document.createElement("button");
    btn.textContent = "选为 Sales 输入";
    btn.addEventListener("click", async () => {
      try {
        await runStudioAction(
          {
            action: "select_marketing_campaign",
            ventureId: activeVentureId(),
            campaignId,
            async: false,
          },
          "选择 campaign"
        );
      } catch (err) {
        updateFeedback(`选择 campaign 失败: ${err.message}`, "error");
      }
    });
    tdAction.appendChild(btn);

    els.campaignCandidatesTableBody.appendChild(tr);
  }
}

function renderSales(snapshot) {
  const segments = asList(snapshot.activeContext?.sales?.segments);
  els.salesSegmentsTableBody.innerHTML = "";
  for (const seg of segments) {
    const scores = seg.scores || {};
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${safeText(seg.segmentIndex)}</td>
      <td>${safeText(seg.segment_name || "-")}</td>
      <td>${safeText(scores.estimated_weekly_leads ?? "-")}</td>
      <td>${safeText(scores.estimated_weekly_mql ?? "-")}</td>
    `;
    els.salesSegmentsTableBody.appendChild(tr);
  }

  const summary = {
    outreachBatchReady: snapshot.activeContext?.sales?.outreachBatchReady || null,
    outreachDispatch: snapshot.activeContext?.sales?.outreachDispatch || null,
    closeMotion: snapshot.activeContext?.sales?.closeMotion || null,
  };
  els.salesSummary.textContent = JSON.stringify(summary, null, 2);
}

function renderOps(snapshot) {
  const todos = asList(snapshot.loopTodos);
  els.loopTodosTableBody.innerHTML = "";

  for (const todo of todos) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${safeText(todo.team)}</td>
      <td>${safeText(todo.priority)}</td>
      <td>${safeText(todo.title)}</td>
      <td>${safeText(todo.sourceFile)}</td>
    `;
    els.loopTodosTableBody.appendChild(tr);
  }

  const summary = {
    operations: snapshot.activeContext?.operations || {},
    todoCount: todos.length,
    insights: snapshot.crossAgentInsights || [],
  };
  els.opsSummary.textContent = JSON.stringify(summary, null, 2);
}

function renderJobsFromList(jobs) {
  els.jobsTableBody.innerHTML = "";
  for (const job of asList(jobs)) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${safeText(job.id)}</td>
      <td>${safeText(job.action)}</td>
      <td><span class="status-pill ${statusClass(job.status)}">${safeText(job.status).toUpperCase()}</span></td>
      <td>${safeText(job.ventureId || "-")}</td>
      <td>${safeText(formatTime(job.createdAt))}</td>
    `;
    els.jobsTableBody.appendChild(tr);
  }
}

function renderRuns(snapshot) {
  const runs = asList(snapshot.recentRuns);
  els.runsTableBody.innerHTML = "";
  for (const run of runs) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${safeText(formatTime(run.createdAt))}</td>
      <td>${safeText(run.stage)}</td>
      <td>${safeText(run.action)}</td>
      <td>${safeText(run.mode)}</td>
      <td><span class="status-pill ${statusClass(run.status)}">${safeText(run.status).toUpperCase()}</span></td>
    `;
    els.runsTableBody.appendChild(tr);
  }
}

function renderSnapshot(snapshot) {
  state.snapshot = snapshot;
  renderTop();
  renderGuide(snapshot);
  renderStageFlow(snapshot);
  renderStageResults(snapshot);
  renderDeployments(snapshot);
  renderIdeas(snapshot);
  renderVentures(snapshot);
  renderProduct(snapshot);
  renderMarketing(snapshot);
  renderSales(snapshot);
  renderOps(snapshot);
  renderJobsFromList(snapshot.jobs || []);
  renderRuns(snapshot);
}

async function refreshFastSnapshot() {
  const data = await getJSON("/api/studio/fast-snapshot");
  renderSnapshot(data.snapshot);
  return data;
}

async function refreshMonitorSnapshot(refresh = false) {
  const url = refresh ? "/api/monitor/cached-snapshot?refresh=1" : "/api/monitor/cached-snapshot";
  const data = await getJSON(url);
  state.monitorSnapshot = data.snapshot || null;
  renderTop();
  return data;
}

async function refreshStudio({ forceMonitor = false } = {}) {
  if (refreshInFlight) return;
  refreshInFlight = true;
  try {
    await refreshFastSnapshot();
    await refreshMonitorSnapshot(forceMonitor);
  } finally {
    refreshInFlight = false;
  }
}

async function pollJobs() {
  try {
    const data = await getJSON("/api/studio/jobs");
    const jobs = asList(data.jobs);
    state.jobs = jobs;
    renderJobsFromList(jobs);

    const sig = jobs.map((j) => `${j.id}:${j.status}`).join("|");
    const running = jobs.filter((j) => ["queued", "running"].includes(String(j.status))).length;

    if (running > 0) {
      updateFeedback(`有 ${running} 个任务正在执行…`, "info");
    } else if (state.lastJobsSignature && state.lastJobsSignature !== sig) {
      updateFeedback("任务状态已更新，正在刷新页面数据。", "ok");
      await refreshFastSnapshot();
    }

    state.lastJobsSignature = sig;
  } catch (err) {
    console.warn("pollJobs failed", err);
  }
}

async function runStudioAction(payload, label = "动作") {
  updateFeedback(`${label} 已提交…`, "info");
  const res = await postJSON("/api/studio/action", payload);
  logActionResult(res);

  if (res.async) {
    const jobId = res?.job?.id;
    if (res.duplicate) {
      updateFeedback(`${label} 复用了已有执行任务${jobId ? ` (${jobId})` : ""}。`, "info");
    } else {
      updateFeedback(`${label} 已入队${jobId ? ` (${jobId})` : ""}，稍后自动更新。`, "info");
    }
  } else {
    updateFeedback(`${label} 已完成。`, "ok");
  }

  await refreshFastSnapshot();
  return res;
}

function bindTabs() {
  const tabButtons = document.querySelectorAll(".tab");
  const panels = document.querySelectorAll(".tab-panel");

  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const tab = btn.dataset.tab;
      if (!tab) return;
      state.selectedTab = tab;

      tabButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      panels.forEach((p) => {
        if (p.id === `tab-${tab}`) p.classList.add("active");
        else p.classList.remove("active");
      });
    });
  });
}

function bindEvents() {
  bindTabs();

  els.refreshBtn.addEventListener("click", () => {
    refreshStudio({ forceMonitor: true }).catch((err) => updateFeedback(`刷新失败: ${err.message}`, "error"));
  });

  els.armOnBtn.addEventListener("click", async () => {
    try {
      await postJSON("/api/runtime-flags/manual-arm", { enabled: true });
      updateFeedback("Manual arm 已设置为 ON。", "ok");
      await refreshStudio({ forceMonitor: true });
    } catch (err) {
      updateFeedback(`设置 manual arm 失败: ${err.message}`, "error");
    }
  });

  els.armOffBtn.addEventListener("click", async () => {
    try {
      await postJSON("/api/runtime-flags/manual-arm", { enabled: false });
      updateFeedback("Manual arm 已设置为 OFF。", "ok");
      await refreshStudio({ forceMonitor: true });
    } catch (err) {
      updateFeedback(`设置 manual arm 失败: ${err.message}`, "error");
    }
  });

  els.runPreflightBtn.addEventListener("click", async () => {
    const ventureId = activeVentureId();
    try {
      await runStudioAction({ action: "stage_preflight", ventureId, async: true }, "运行演示前预检查");
    } catch (err) {
      updateFeedback(`预检查失败: ${err.message}`, "error");
    }
  });

  els.runRehearsalBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;
    const ok = confirm("将按 simulation 串行执行全流程彩排，可能耗时较长。继续吗？");
    if (!ok) return;
    try {
      await runStudioAction({ action: "rehearsal_e2e", ventureId, async: true }, "一键彩排");
    } catch (err) {
      updateFeedback(`彩排失败: ${err.message}`, "error");
    }
  });

  els.refreshIdeasBtn.addEventListener("click", async () => {
    try {
      await runStudioAction({ action: "refresh_ideas", async: true }, "刷新 startup ideas");
    } catch (err) {
      updateFeedback(`刷新 ideas 失败: ${err.message}`, "error");
    }
  });

  els.runProductBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;

    const mode = els.productMode.value;
    const payload = { action: "run_product", ventureId, mode, async: true };
    if (mode === "live") {
      const ok = confirm("将执行 live 部署（可能触发 Vercel）。确认继续？");
      if (!ok) return;
      payload.confirmLive = true;
    }

    try {
      await runStudioAction(payload, `执行 Product (${mode})`);
    } catch (err) {
      updateFeedback(`执行 Product 失败: ${err.message}`, "error");
    }
  });

  els.runMarketingSeoBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;
    try {
      await runStudioAction({ action: "run_marketing_seo", ventureId, mode: "shadow", async: true }, "Run SEO experiments");
    } catch (err) {
      updateFeedback(`营销SEO失败: ${err.message}`, "error");
    }
  });

  els.runMarketingContentBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;
    try {
      await runStudioAction({ action: "run_marketing_content", ventureId, mode: "review", async: true }, "生成内容候选");
    } catch (err) {
      updateFeedback(`内容生成失败: ${err.message}`, "error");
    }
  });

  els.runMarketingCampaignBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;
    try {
      await runStudioAction({ action: "run_marketing_campaign", ventureId, mode: "review", async: true }, "生成 campaign 候选");
    } catch (err) {
      updateFeedback(`campaign生成失败: ${err.message}`, "error");
    }
  });

  els.approveSelectedContentBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;
    const ids = selectedContentIds();
    if (!ids.length) {
      alert("请先勾选内容项");
      return;
    }
    try {
      await runStudioAction(
        {
          action: "review_marketing_content",
          ventureId,
          approveIds: ids,
          rejectIds: [],
          note: "approved_from_studio",
          async: true,
        },
        "审批内容"
      );
    } catch (err) {
      updateFeedback(`内容审批失败: ${err.message}`, "error");
    }
  });

  els.rejectSelectedContentBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;
    const ids = selectedContentIds();
    if (!ids.length) {
      alert("请先勾选内容项");
      return;
    }
    try {
      await runStudioAction(
        {
          action: "review_marketing_content",
          ventureId,
          approveIds: [],
          rejectIds: ids,
          reason: "studio_manual_reject",
          async: true,
        },
        "驳回内容"
      );
    } catch (err) {
      updateFeedback(`内容驳回失败: ${err.message}`, "error");
    }
  });

  els.runSalesProspectingBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;
    try {
      await runStudioAction({ action: "run_sales_prospecting", ventureId, async: true }, "Identify prospects");
    } catch (err) {
      updateFeedback(`prospecting 失败: ${err.message}`, "error");
    }
  });

  els.runSalesOutreachPlanBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;
    try {
      await runStudioAction({ action: "run_sales_outreach_plan", ventureId, async: true }, "规划 Send outreach");
    } catch (err) {
      updateFeedback(`outreach plan 失败: ${err.message}`, "error");
    }
  });

  els.approveSalesOutreachBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;
    try {
      await runStudioAction(
        {
          action: "approve_sales_outreach",
          ventureId,
          approver: "studio_user",
          note: "approved in studio",
          async: true,
        },
        "批准外联批次"
      );
    } catch (err) {
      updateFeedback(`approve outreach 失败: ${err.message}`, "error");
    }
  });

  els.dispatchSalesSimBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;
    try {
      await runStudioAction(
        {
          action: "dispatch_sales_outreach",
          ventureId,
          mode: "simulate",
          async: true,
        },
        "Dispatch simulate"
      );
    } catch (err) {
      updateFeedback(`dispatch simulate 失败: ${err.message}`, "error");
    }
  });

  els.dispatchSalesLiveBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;
    const ok = confirm("将执行 commit 外联（live）。确认继续？");
    if (!ok) return;
    try {
      await runStudioAction(
        {
          action: "dispatch_sales_outreach",
          ventureId,
          mode: "commit",
          confirmLive: true,
          async: true,
        },
        "Dispatch commit"
      );
    } catch (err) {
      updateFeedback(`dispatch live 失败: ${err.message}`, "error");
    }
  });

  els.runSalesConversionSimBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;
    try {
      await runStudioAction(
        {
          action: "run_sales_conversion",
          ventureId,
          mode: "simulate",
          async: true,
        },
        "Convert simulate"
      );
    } catch (err) {
      updateFeedback(`conversion simulate 失败: ${err.message}`, "error");
    }
  });

  els.runSalesConversionLiveBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;
    const ok = confirm("将执行 conversion commit（live）。确认继续？");
    if (!ok) return;
    try {
      await runStudioAction(
        {
          action: "run_sales_conversion",
          ventureId,
          mode: "commit",
          confirmLive: true,
          async: true,
        },
        "Convert commit"
      );
    } catch (err) {
      updateFeedback(`conversion live 失败: ${err.message}`, "error");
    }
  });

  els.runOpsFullBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;
    try {
      await runStudioAction({ action: "run_operations_full", ventureId, async: true }, "Run operations full");
    } catch (err) {
      updateFeedback(`operations full 失败: ${err.message}`, "error");
    }
  });

  els.writebackOpsBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;
    try {
      await runStudioAction({ action: "writeback_operations", ventureId, async: true }, "回写下一轮待办");
    } catch (err) {
      updateFeedback(`ops writeback 失败: ${err.message}`, "error");
    }
  });

  els.confirmIterateBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;
    const note = prompt("请输入进入下一轮的确认说明", "approved_next_cycle");
    if (note === null) return;
    try {
      await runStudioAction({ action: "confirm_iterate", ventureId, note, async: false }, "确认进入下一轮");
    } catch (err) {
      updateFeedback(`确认下一轮失败: ${err.message}`, "error");
    }
  });
}

function startTimers() {
  if (fastTimer) clearInterval(fastTimer);
  if (jobTimer) clearInterval(jobTimer);
  if (monitorTimer) clearInterval(monitorTimer);

  fastTimer = setInterval(() => {
    refreshFastSnapshot().catch(() => {});
  }, FAST_REFRESH_MS);

  jobTimer = setInterval(() => {
    pollJobs().catch(() => {});
  }, JOB_POLL_MS);

  monitorTimer = setInterval(() => {
    refreshMonitorSnapshot(false).catch(() => {});
  }, MONITOR_REFRESH_MS);
}

async function main() {
  bindEvents();
  updateFeedback("正在加载 Studio 快照…", "info");
  await refreshFastSnapshot();
  await refreshMonitorSnapshot(false);
  await pollJobs();
  startTimers();
  updateFeedback("Studio 已就绪。建议按“下一步推荐动作”执行。", "ok");
}

main().catch((err) => {
  console.error(err);
  updateFeedback(`初始化失败: ${err.message}`, "error");
});
