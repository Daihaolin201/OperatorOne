const els = {
  refreshBtn: document.getElementById("refreshBtn"),
  lastUpdated: document.getElementById("lastUpdated"),

  demoGateStatus: document.getElementById("demoGateStatus"),
  liveGateStatus: document.getElementById("liveGateStatus"),
  manualArmStatus: document.getElementById("manualArmStatus"),
  armOnBtn: document.getElementById("armOnBtn"),
  armOffBtn: document.getElementById("armOffBtn"),
  vercelStatus: document.getElementById("vercelStatus"),

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

  actionResult: document.getElementById("actionResult"),
};

let state = {
  snapshot: null,
  selectedTab: "idea",
};

const autoRefreshMs = 8000;
let autoRefreshTimer = null;

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
  if (["passed", "ready", "succeeded", "success"].includes(s)) return "status-passed";
  if (["warning", "review_required", "running", "queued"].includes(s)) return "status-warning";
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

function renderTop(snapshot) {
  els.lastUpdated.textContent = `更新于 ${formatTime(snapshot.generatedAt)}`;

  const monitor = snapshot.monitor || {};
  const readiness = monitor.readiness || {};
  setPill(els.demoGateStatus, readiness?.demo?.status || "unknown");
  setPill(els.liveGateStatus, readiness?.liveExternalContact?.status || "unknown");

  const arm = Boolean(snapshot.manualArmEnabled);
  setPill(els.manualArmStatus, arm ? "ready" : "review_required", arm ? "ON" : "OFF");

  const vercel = snapshot.vercel || {};
  const bits = [
    `installed=${vercel.installed ? "yes" : "no"}`,
    `auth=${vercel.authenticated ? "yes" : "no"}`,
  ];
  if (vercel.note) bits.push(`note=${vercel.note}`);
  els.vercelStatus.textContent = bits.join(" | ");
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
        const res = await runStudioAction({
          action: "create_venture",
          opportunityId: idea.opportunityId,
          name: `${idea.opportunityId} venture`,
          async: false,
        });
        logActionResult(res);
        await refreshStudio();
      } catch (err) {
        alert(`创建 venture 失败: ${err.message}`);
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
        const res = await runStudioAction({ action: "set_active_venture", ventureId: venture.id, async: false });
        logActionResult(res);
        await refreshStudio();
      } catch (err) {
        alert(`切换 venture 失败: ${err.message}`);
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
        const res = await runStudioAction({
          action: "select_marketing_campaign",
          ventureId: activeVentureId(),
          campaignId,
          async: false,
        });
        logActionResult(res);
        await refreshStudio();
      } catch (err) {
        alert(`选择 campaign 失败: ${err.message}`);
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
      <td>${safeText(seg.segment_name || seg.target_segment?.role || "-")}</td>
      <td>${safeText(scores.estimated_weekly_leads ?? scores.weekly_leads ?? "-")}</td>
      <td>${safeText(scores.estimated_weekly_mql ?? scores.weekly_mql ?? "-")}</td>
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
  };
  els.opsSummary.textContent = JSON.stringify(summary, null, 2);
}

function renderJobs(snapshot) {
  const jobs = asList(snapshot.jobs);
  els.jobsTableBody.innerHTML = "";

  for (const job of jobs) {
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
  renderTop(snapshot);
  renderIdeas(snapshot);
  renderVentures(snapshot);
  renderProduct(snapshot);
  renderMarketing(snapshot);
  renderSales(snapshot);
  renderOps(snapshot);
  renderJobs(snapshot);
  renderRuns(snapshot);
}

function logActionResult(payload) {
  els.actionResult.textContent = JSON.stringify(payload, null, 2);
}

async function refreshStudio() {
  const data = await getJSON("/api/studio/snapshot");
  renderSnapshot(data.snapshot);
}

async function runStudioAction(payload) {
  const res = await postJSON("/api/studio/action", payload);
  return res;
}

async function runActionAndRefresh(payload, opts = { immediateRefresh: true }) {
  const res = await runStudioAction(payload);
  logActionResult(res);
  if (opts.immediateRefresh) {
    await refreshStudio();
  }
  return res;
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
    refreshStudio().catch((err) => alert(`刷新失败: ${err.message}`));
  });

  els.armOnBtn.addEventListener("click", async () => {
    try {
      await postJSON("/api/runtime-flags/manual-arm", { enabled: true });
      await refreshStudio();
    } catch (err) {
      alert(`设置 manual arm 失败: ${err.message}`);
    }
  });

  els.armOffBtn.addEventListener("click", async () => {
    try {
      await postJSON("/api/runtime-flags/manual-arm", { enabled: false });
      await refreshStudio();
    } catch (err) {
      alert(`设置 manual arm 失败: ${err.message}`);
    }
  });

  els.refreshIdeasBtn.addEventListener("click", async () => {
    try {
      const res = await runActionAndRefresh({ action: "refresh_ideas", async: true });
      logActionResult(res);
    } catch (err) {
      alert(`刷新 ideas 失败: ${err.message}`);
    }
  });

  els.runProductBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;

    const mode = els.productMode.value;
    const payload = {
      action: "run_product",
      ventureId,
      mode,
      async: true,
    };
    if (mode === "live") {
      const ok = confirm("将执行 live 部署（可能触发 Vercel）。确认继续？");
      if (!ok) return;
      payload.confirmLive = true;
    }

    try {
      const res = await runActionAndRefresh(payload);
      logActionResult(res);
    } catch (err) {
      alert(`执行 Product 失败: ${err.message}`);
    }
  });

  els.runMarketingSeoBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;
    try {
      const res = await runActionAndRefresh({ action: "run_marketing_seo", ventureId, mode: "shadow", async: true });
      logActionResult(res);
    } catch (err) {
      alert(`营销SEO失败: ${err.message}`);
    }
  });

  els.runMarketingContentBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;
    try {
      const res = await runActionAndRefresh({ action: "run_marketing_content", ventureId, mode: "review", async: true });
      logActionResult(res);
    } catch (err) {
      alert(`内容生成失败: ${err.message}`);
    }
  });

  els.runMarketingCampaignBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;
    try {
      const res = await runActionAndRefresh({ action: "run_marketing_campaign", ventureId, mode: "review", async: true });
      logActionResult(res);
    } catch (err) {
      alert(`campaign生成失败: ${err.message}`);
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
      const res = await runActionAndRefresh({
        action: "review_marketing_content",
        ventureId,
        approveIds: ids,
        rejectIds: [],
        note: "approved_from_studio",
        async: true,
      });
      logActionResult(res);
    } catch (err) {
      alert(`内容审批失败: ${err.message}`);
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
      const res = await runActionAndRefresh({
        action: "review_marketing_content",
        ventureId,
        approveIds: [],
        rejectIds: ids,
        reason: "studio_manual_reject",
        async: true,
      });
      logActionResult(res);
    } catch (err) {
      alert(`内容驳回失败: ${err.message}`);
    }
  });

  els.runSalesProspectingBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;
    try {
      const res = await runActionAndRefresh({ action: "run_sales_prospecting", ventureId, async: true });
      logActionResult(res);
    } catch (err) {
      alert(`prospecting 失败: ${err.message}`);
    }
  });

  els.runSalesOutreachPlanBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;
    try {
      const res = await runActionAndRefresh({ action: "run_sales_outreach_plan", ventureId, async: true });
      logActionResult(res);
    } catch (err) {
      alert(`outreach plan 失败: ${err.message}`);
    }
  });

  els.approveSalesOutreachBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;
    try {
      const res = await runActionAndRefresh({
        action: "approve_sales_outreach",
        ventureId,
        approver: "studio_user",
        note: "approved in studio",
        async: true,
      });
      logActionResult(res);
    } catch (err) {
      alert(`approve outreach 失败: ${err.message}`);
    }
  });

  els.dispatchSalesSimBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;
    try {
      const res = await runActionAndRefresh({
        action: "dispatch_sales_outreach",
        ventureId,
        mode: "simulate",
        async: true,
      });
      logActionResult(res);
    } catch (err) {
      alert(`dispatch simulate 失败: ${err.message}`);
    }
  });

  els.dispatchSalesLiveBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;
    const ok = confirm("将执行 commit 外联（live）。确认继续？");
    if (!ok) return;
    try {
      const res = await runActionAndRefresh({
        action: "dispatch_sales_outreach",
        ventureId,
        mode: "commit",
        confirmLive: true,
        async: true,
      });
      logActionResult(res);
    } catch (err) {
      alert(`dispatch live 失败: ${err.message}`);
    }
  });

  els.runSalesConversionSimBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;
    try {
      const res = await runActionAndRefresh({
        action: "run_sales_conversion",
        ventureId,
        mode: "simulate",
        async: true,
      });
      logActionResult(res);
    } catch (err) {
      alert(`conversion simulate 失败: ${err.message}`);
    }
  });

  els.runSalesConversionLiveBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;
    const ok = confirm("将执行 conversion commit（live）。确认继续？");
    if (!ok) return;
    try {
      const res = await runActionAndRefresh({
        action: "run_sales_conversion",
        ventureId,
        mode: "commit",
        confirmLive: true,
        async: true,
      });
      logActionResult(res);
    } catch (err) {
      alert(`conversion live 失败: ${err.message}`);
    }
  });

  els.runOpsFullBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;
    try {
      const res = await runActionAndRefresh({ action: "run_operations_full", ventureId, async: true });
      logActionResult(res);
    } catch (err) {
      alert(`operations full 失败: ${err.message}`);
    }
  });

  els.writebackOpsBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;
    try {
      const res = await runActionAndRefresh({ action: "writeback_operations", ventureId, async: true });
      logActionResult(res);
    } catch (err) {
      alert(`ops writeback 失败: ${err.message}`);
    }
  });

  els.confirmIterateBtn.addEventListener("click", async () => {
    const ventureId = ensureActiveVentureOrAlert();
    if (!ventureId) return;
    const note = prompt("请输入进入下一轮的确认说明", "approved_next_cycle");
    if (note === null) return;
    try {
      const res = await runActionAndRefresh({
        action: "confirm_iterate",
        ventureId,
        note,
        async: false,
      });
      logActionResult(res);
    } catch (err) {
      alert(`确认下一轮失败: ${err.message}`);
    }
  });
}

function startAutoRefresh() {
  if (autoRefreshTimer) clearInterval(autoRefreshTimer);
  autoRefreshTimer = setInterval(() => {
    refreshStudio().catch(() => {
      // silent background refresh failure
    });
  }, autoRefreshMs);
}

async function main() {
  bindEvents();
  await refreshStudio();
  startAutoRefresh();
}

main().catch((err) => {
  console.error(err);
  alert(`初始化失败: ${err.message}`);
});
