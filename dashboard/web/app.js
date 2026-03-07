const els = {
  refreshBtn: document.getElementById("refreshBtn"),
  lastUpdated: document.getElementById("lastUpdated"),
  uiModeSelect: document.getElementById("uiModeSelect"),

  demoGateStatus: document.getElementById("demoGateStatus"),
  liveGateStatus: document.getElementById("liveGateStatus"),
  manualArmStatus: document.getElementById("manualArmStatus"),
  armOnBtn: document.getElementById("armOnBtn"),
  armOffBtn: document.getElementById("armOffBtn"),
  vercelStatus: document.getElementById("vercelStatus"),
  vercelAuditSummary: document.getElementById("vercelAuditSummary"),
  capabilitySummary: document.getElementById("capabilitySummary"),
  globalRunStatus: document.getElementById("globalRunStatus"),
  globalRunError: document.getElementById("globalRunError"),

  judgeVentureCard: document.getElementById("judgeVentureCard"),
  judgeStageCard: document.getElementById("judgeStageCard"),
  judgeArtifactCards: document.getElementById("judgeArtifactCards"),
  judgePrimaryAction: document.getElementById("judgePrimaryAction"),

  quickstartList: document.getElementById("quickstartList"),
  recommendedActions: document.getElementById("recommendedActions"),
  feedbackBar: document.getElementById("feedbackBar"),
  runPreflightBtn: document.getElementById("runPreflightBtn"),
  runRehearsalBtn: document.getElementById("runRehearsalBtn"),
  resetDemoStateBtn: document.getElementById("resetDemoStateBtn"),

  stageFlowTableBody: document.querySelector("#stageFlowTable tbody"),
  stageResultsTableBody: document.querySelector("#stageResultsTable tbody"),
  deploymentsTableBody: document.querySelector("#deploymentsTable tbody"),
  goToMarketPreview: document.getElementById("goToMarketPreview"),
  goToMarketLanding: document.getElementById("goToMarketLanding"),
  goToMarketSales: document.getElementById("goToMarketSales"),

  tabs: document.getElementById("tabs"),
  refreshIdeasBtn: document.getElementById("refreshIdeasBtn"),
  ideaModeSelect: document.getElementById("ideaModeSelect"),
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
  toastContainer: document.getElementById("toastContainer"),
};

const state = {
  snapshot: null,
  monitorSnapshot: null,
  jobs: [],
  selectedTab: "idea",
  lastJobsSignature: "",
  uiMode: localStorage.getItem("op1.uiMode") || "judge",
  actionStates: {},
  actionStatusEls: {},
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

function normalizeActionState(status) {
  const s = String(status || "idle").toLowerCase();
  if (s === "passed") return "succeeded";
  if (["queued", "running", "succeeded", "failed", "idle"].includes(s)) return s;
  return "idle";
}

function actionStateLabel(status) {
  const s = normalizeActionState(status);
  return {
    idle: "idle",
    queued: "queued",
    running: "running",
    succeeded: "done",
    failed: "failed",
  }[s];
}

function renderActionStatusBadges() {
  Object.entries(state.actionStatusEls).forEach(([action, nodes]) => {
    const current = state.actionStates[action] || { status: "idle" };
    const label = actionStateLabel(current.status);
    nodes.forEach((el) => {
      el.textContent = label;
      el.className = `action-status ${statusClass(current.status)}`;
      el.title = current.message || "";
    });
  });
}

function setActionState(action, status, message = null) {
  if (!action) return;
  state.actionStates[action] = { status: normalizeActionState(status), message };
  renderActionStatusBadges();
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

function showToast(message, kind = "info") {
  if (!els.toastContainer) return;
  const item = document.createElement("div");
  item.className = `toast ${kind === "error" ? "error" : kind === "ok" ? "ok" : ""}`;
  item.textContent = message;
  els.toastContainer.appendChild(item);
  setTimeout(() => item.remove(), 4200);
}

function logActionResult(payload) {
  if (els.actionResult) {
    els.actionResult.textContent = JSON.stringify(payload, null, 2);
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

function ensureActiveVentureOrAlert() {
  const id = activeVentureId();
  if (!id) {
    alert("请先在 Idea Board 创建并激活 venture。");
    return null;
  }
  return id;
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

function applyUiMode() {
  document.body.dataset.mode = state.uiMode;
  if (els.uiModeSelect && els.uiModeSelect.value !== state.uiMode) {
    els.uiModeSelect.value = state.uiMode;
  }
}

function renderTop() {
  const snapshot = state.snapshot || {};
  const monitor = state.monitorSnapshot || snapshot.monitor || {};
  const readiness = monitor?.readiness || {};

  if (snapshot.generatedAt && els.lastUpdated) {
    els.lastUpdated.textContent = `更新于 ${formatTime(snapshot.generatedAt)}`;
  }

  setPill(els.demoGateStatus, readiness?.demo?.status || "unknown");
  setPill(els.liveGateStatus, readiness?.liveExternalContact?.status || "unknown");

  const arm = Boolean(snapshot.manualArmEnabled);
  setPill(els.manualArmStatus, arm ? "ready" : "review_required", arm ? "ON" : "OFF");

  const vercel = snapshot.vercel || {};
  const vercelBits = [
    `installed=${vercel.installed ? "yes" : "no"}`,
    `auth=${vercel.authenticated ? "yes" : "no"}`,
  ];
  if (vercel.note) vercelBits.push(`note=${vercel.note}`);
  if (els.vercelStatus) els.vercelStatus.textContent = vercelBits.join(" | ");

  const audit = snapshot.vercelAuditSummary || {};
  if (els.vercelAuditSummary) {
    els.vercelAuditSummary.textContent = `audit: total=${audit.projectCount ?? "-"}, keep=${audit.keep ?? "-"}, review=${audit.review ?? "-"}, cleanup=${audit.cleanupCandidates ?? "-"}`;
  }

  const capFromMonitor = {
    total: asList(monitor.capabilities).length,
    passed: asList(monitor.capabilities).filter((x) => x?.status === "passed").length,
  };
  const cap = capFromMonitor.total > 0 ? capFromMonitor : snapshot.capabilitySummary || {};
  if (els.capabilitySummary) {
    els.capabilitySummary.textContent = `${cap.passed || 0}/${cap.total || 0} passed`;
  }

  const run = snapshot.globalRunState || {};
  if (els.globalRunStatus) {
    if (["queued", "running"].includes(run.status)) {
      const seconds = Math.max(0, Math.round((Number(run.elapsedMs) || 0) / 1000));
      els.globalRunStatus.textContent = `正在执行 ${safeText(run.runningAction)}（${seconds}s，${safeText(run.runningCount)} 个任务）`;
    } else {
      els.globalRunStatus.textContent = "当前无运行中的任务。";
    }
  }
  if (els.globalRunError) {
    if (run.lastError) {
      const hint = run.lastFailedAction
        ? `建议：retry ${safeText(run.lastFailedAction)}，或先执行 stage_preflight 再重试。`
        : "建议：先看 Jobs/Stage Timeline 定位错误后重试。";
      els.globalRunError.textContent = `最近错误：${safeText(run.lastError)} | ${hint}`;
    } else {
      els.globalRunError.textContent = "最近错误：无";
    }
  }
}

function renderGuide(snapshot) {
  const guide = snapshot?.guide || {};
  const quickstart = asList(guide.quickstart);
  if (els.quickstartList) {
    els.quickstartList.innerHTML = "";
    for (const step of quickstart) {
      const li = document.createElement("li");
      li.textContent = safeText(step);
      els.quickstartList.appendChild(li);
    }
  }

  state.actionStates = guide.actionStates || state.actionStates || {};
  renderActionStatusBadges();

  const actions = asList(guide.nextRecommendedActions);
  const renderActionCard = (action, target) => {
    const box = document.createElement("div");
    box.className = "action-card";

    const title = document.createElement("div");
    title.className = "title";
    title.textContent = `${safeText(action.label)} (${safeText(action.stage)})`;

    const status = document.createElement("span");
    status.className = `action-status ${statusClass((state.actionStates[action.action] || {}).status)}`;
    status.textContent = actionStateLabel((state.actionStates[action.action] || {}).status);

    const desc = document.createElement("div");
    desc.className = "desc";
    desc.textContent = safeText(action.description || "");

    const row = document.createElement("div");
    row.className = "row";

    const btn = document.createElement("button");
    btn.textContent = "执行此动作";
    btn.addEventListener("click", async () => {
      if (action.requiresUserChoice) {
        alert("这个动作需要先在对应表格里选择具体项，再执行。\n例如：先选 campaign 再推进到 Sales。");
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
    row.appendChild(status);
    box.appendChild(title);
    box.appendChild(desc);
    box.appendChild(row);
    target.appendChild(box);
  };

  if (els.recommendedActions) {
    els.recommendedActions.innerHTML = "";
    if (!actions.length) {
      const empty = document.createElement("div");
      empty.className = "muted";
      empty.textContent = "暂无推荐动作。";
      els.recommendedActions.appendChild(empty);
    } else {
      for (const action of actions) renderActionCard(action, els.recommendedActions);
    }
  }

  if (els.judgePrimaryAction) {
    els.judgePrimaryAction.innerHTML = "";
    const primary = guide.primaryRecommendedAction || actions[0];
    if (primary) renderActionCard(primary, els.judgePrimaryAction);
  }
}

function renderStageFlow(snapshot) {
  if (!els.stageFlowTableBody) return;
  els.stageFlowTableBody.innerHTML = "";
  for (const row of asList(snapshot.stageFlow)) {
    const tr = document.createElement("tr");
    const run = row.lastRun || {};
    tr.innerHTML = `
      <td>${safeText(row.stage)}</td>
      <td><span class="status-pill ${statusClass(row.state)}">${safeText(row.state).toUpperCase()}</span></td>
      <td>${safeText(row.narrative || "-")}</td>
      <td>${safeText(run.action || "-")} / ${safeText(run.status || "-")}</td>
    `;
    els.stageFlowTableBody.appendChild(tr);
  }
}

function renderJudgeFocus(snapshot) {
  const venture = snapshot.activeVenture || {};
  if (els.judgeVentureCard) {
    els.judgeVentureCard.textContent = JSON.stringify(
      {
        ventureId: venture.id || null,
        name: venture.name || null,
        opportunityId: venture.opportunityId || null,
        cycle: venture.cycle || 1,
        status: venture.status || null,
      },
      null,
      2
    );
  }

  const current = asList(snapshot.stageFlow).find((x) => x.state === "current") || null;
  if (els.judgeStageCard) {
    els.judgeStageCard.textContent = JSON.stringify(
      {
        currentStage: current?.stage || null,
        narrative: current?.narrative || null,
        lastRun: current?.lastRun?.action || null,
        lastStatus: current?.lastRun?.status || null,
      },
      null,
      2
    );
  }

  if (els.judgeArtifactCards) {
    els.judgeArtifactCards.innerHTML = "";
    for (const card of asList(snapshot.stageArtifactCards)) {
      const box = document.createElement("div");
      box.className = "action-card";
      const title = document.createElement("div");
      title.className = "title";
      title.textContent = safeText(card.title || card.stage);
      box.appendChild(title);

      const row = document.createElement("div");
      row.className = "row wrap";
      const items = asList(card.items);
      if (!items.length) {
        const muted = document.createElement("div");
        muted.className = "muted";
        muted.textContent = "暂无可打开产物（先运行该阶段）";
        row.appendChild(muted);
      }

      for (const item of items) {
        const btn = document.createElement("button");
        btn.className = "secondary";
        btn.textContent = safeText(item.label);
        btn.addEventListener("click", () => {
          if (item.kind === "url" && item.url) {
            window.open(item.url, "_blank", "noopener,noreferrer");
            return;
          }
          if (item.kind === "preview" && item.path) {
            window.open(`/api/studio/preview?path=${encodeURIComponent(item.path)}`, "_blank", "noopener,noreferrer");
            return;
          }
          if (item.kind === "file" && item.path) {
            if (item.previewable) {
              window.open(`/api/studio/preview?path=${encodeURIComponent(item.path)}`, "_blank", "noopener,noreferrer");
            } else {
              openArtifact(item.path);
              showToast(`已加载产物：${item.label}`, "ok");
            }
          }
        });
        row.appendChild(btn);
      }
      box.appendChild(row);
      els.judgeArtifactCards.appendChild(box);
    }
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
  if (summary.totalChecks !== undefined) picks.push(`checks=${summary.totalChecks}`);
  if (summary.failedChecks !== undefined) picks.push(`failed=${summary.failedChecks}`);
  if (!picks.length) {
    const keys = Object.keys(summary).slice(0, 4);
    return keys.map((k) => `${k}=${safeText(summary[k])}`).join(" | ") || "-";
  }
  return picks.join(" | ");
}

async function openArtifact(path) {
  if (!path || !els.artifactContent) return;
  if (els.artifactPath) els.artifactPath.textContent = path;
  els.artifactContent.textContent = "加载中...";
  try {
    const data = await getJSON(`/api/studio/artifact?path=${encodeURIComponent(path)}`);
    if (data.binary) {
      els.artifactContent.textContent = `Binary file (size=${data.sizeBytes} bytes).\nPath: ${data.path}`;
    } else {
      els.artifactContent.textContent = data.content || "(empty)";
    }
  } catch (err) {
    els.artifactContent.textContent = `读取失败: ${err.message}`;
  }
}

function renderStageResults(snapshot) {
  if (!els.stageResultsTableBody) return;
  els.stageResultsTableBody.innerHTML = "";

  for (const row of asList(snapshot.stageResults)) {
    const tr = document.createElement("tr");
    const run = row.run || {};
    tr.innerHTML = `
      <td>${safeText(row.stage)}</td>
      <td><span class="status-pill ${statusClass(run.status)}">${safeText(run.status).toUpperCase()}</span><br/><span class="small">${safeText(run.action || "-")}</span></td>
      <td></td>
      <td></td>
    `;

    const tdSummary = tr.children[2];
    tdSummary.textContent = summarizeStageOutput(row.summary);
    if (row.summary && row.summary.deploymentUrl) {
      const br = document.createElement("br");
      const a = document.createElement("a");
      a.href = row.summary.deploymentUrl;
      a.target = "_blank";
      a.rel = "noreferrer";
      a.className = "linkish";
      a.textContent = "Open Deployment";
      tdSummary.appendChild(br);
      tdSummary.appendChild(a);
    }

    const tdArt = tr.children[3];
    const artifacts = asList(row.artifacts).slice(0, 5);
    if (!artifacts.length) {
      tdArt.textContent = "-";
    } else {
      for (const art of artifacts) {
        const btn = document.createElement("button");
        btn.className = "secondary";
        btn.textContent = (art.snapshotPath || art.sourcePath || "artifact").split("/").pop();
        btn.addEventListener("click", () => {
          const p = art.snapshotPath || art.sourcePath;
          if (!p) return;
          if (String(p).endsWith(".html") || String(p).endsWith(".htm")) {
            window.open(`/api/studio/preview?path=${encodeURIComponent(p)}`, "_blank", "noopener,noreferrer");
            return;
          }
          openArtifact(p);
        });
        tdArt.appendChild(btn);
      }
    }

    els.stageResultsTableBody.appendChild(tr);
  }
}

function renderDeployments(snapshot) {
  if (!els.deploymentsTableBody) return;
  els.deploymentsTableBody.innerHTML = "";

  for (const row of asList(snapshot.deployments)) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${safeText(formatTime(row.createdAt))}</td>
      <td>${safeText(row.mode)} / ${safeText(row.env || "preview")}</td>
      <td>${safeText(row.project || "-")}</td>
      <td></td>
    `;

    const td = tr.children[3];
    const url = row.url;
    const previewPath = row.previewPath;
    if (url) {
      const a = document.createElement("a");
      a.href = url;
      a.target = "_blank";
      a.rel = "noreferrer";
      a.textContent = "Open URL";
      a.className = "linkish";
      td.appendChild(a);
    } else if (previewPath) {
      const btn = document.createElement("button");
      btn.className = "secondary";
      btn.textContent = "Open Preview";
      btn.addEventListener("click", () => window.open(`/api/studio/preview?path=${encodeURIComponent(previewPath)}`, "_blank", "noopener,noreferrer"));
      td.appendChild(btn);
    } else {
      td.textContent = "-";
    }

    if (row.project) {
      const a2 = document.createElement("a");
      a2.href = `https://vercel.com/dashboard/projects/${encodeURIComponent(row.project)}`;
      a2.target = "_blank";
      a2.rel = "noreferrer";
      a2.textContent = " Open in Vercel";
      a2.className = "linkish";
      td.appendChild(document.createElement("br"));
      td.appendChild(a2);
    }

    els.deploymentsTableBody.appendChild(tr);
  }
}

function renderGoToMarketPreview(snapshot) {
  if (!els.goToMarketPreview) return;
  const p = snapshot.goToMarketPreview || {};
  const pack = snapshot.messagePack || {};

  const left = {
    valueProposition: pack?.messagePack?.valueProposition || p.landingHeadline || null,
    primaryCta: pack?.messagePack?.primaryCta || p.landingCta || null,
    proofPoint: pack?.messagePack?.proofPoint || null,
  };
  const right = {
    adCopy: p.adPreview || pack?.campaign?.adCopy || null,
    salesOpening: p.salesOpening || pack?.sales?.opening || null,
    campaignId: p.campaignId || null,
    contentId: p.contentId || null,
  };
  const payload = {
    alignment: p.messageMatch || pack.alignment || null,
    utmLinks: p.utmLinks || pack.utmLinks || null,
  };

  if (els.goToMarketLanding) els.goToMarketLanding.textContent = JSON.stringify(left, null, 2);
  if (els.goToMarketSales) els.goToMarketSales.textContent = JSON.stringify(right, null, 2);
  els.goToMarketPreview.textContent = JSON.stringify(payload, null, 2);
}

function renderIdeas(snapshot) {
  if (!els.ideasTableBody) return;
  els.ideasTableBody.innerHTML = "";

  for (const idea of asList(snapshot.ideas)) {
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
  if (!els.venturesTableBody) return;
  els.venturesTableBody.innerHTML = "";
  const activeId = snapshot.activeVentureId;

  for (const venture of asList(snapshot.ventures)) {
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
  if (!els.productSummary) return;
  const venture = snapshot.activeVenture;
  if (!venture) {
    els.productSummary.textContent = "请先在 Idea Board 创建并激活一个 venture。";
    return;
  }
  const links = venture.links || {};
  els.productSummary.textContent = JSON.stringify(
    {
      ventureId: venture.id,
      stage: venture.stage,
      opportunityId: venture.opportunityId,
      productDeploymentUrl: links.productDeploymentUrl || null,
      productPreviewPath: links.productPreviewPath || null,
      vercelProject: links.vercelProject || null,
      lastProductAction: venture.lastActions?.product || null,
    },
    null,
    2
  );
}

function renderMarketing(snapshot) {
  const ctx = snapshot.activeContext?.marketing || {};

  if (els.contentCandidatesTableBody) {
    els.contentCandidatesTableBody.innerHTML = "";
    for (const item of asList(ctx.contentCandidates)) {
      const tr = document.createElement("tr");
      const cid = item.content_id || item.id || "";
      tr.innerHTML = `
        <td><input type="checkbox" class="content-check" value="${safeText(cid)}" /></td>
        <td>${safeText(cid)}</td>
        <td>${safeText(item._bucket || "-")}</td>
        <td>${safeText(item.topic || "-")}</td>
        <td>${safeText(item.primary_keyword || "-")}</td>
        <td>${safeText(item.priority_score ?? "-")}</td>
      `;
      els.contentCandidatesTableBody.appendChild(tr);
    }
  }

  if (els.campaignCandidatesTableBody) {
    els.campaignCandidatesTableBody.innerHTML = "";
    for (const row of asList(ctx.campaignCandidates)) {
      const tr = document.createElement("tr");
      const campaignId = row.campaign_id || row.id || "";
      tr.innerHTML = `
        <td>${safeText(campaignId)}</td>
        <td>${safeText(row._bucket || "-")}</td>
        <td>${safeText(row.primary_keyword || "-")}</td>
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
}

function renderSales(snapshot) {
  if (els.salesSegmentsTableBody) {
    els.salesSegmentsTableBody.innerHTML = "";
    for (const seg of asList(snapshot.activeContext?.sales?.segments)) {
      const tr = document.createElement("tr");
      const scores = seg.scores || {};
      tr.innerHTML = `
        <td>${safeText(seg.segmentIndex)}</td>
        <td>${safeText(seg.segment_name || "-")}</td>
        <td>${safeText(scores.estimated_weekly_leads ?? "-")}</td>
        <td>${safeText(scores.estimated_weekly_mql ?? "-")}</td>
      `;
      els.salesSegmentsTableBody.appendChild(tr);
    }
  }

  if (els.salesSummary) {
    els.salesSummary.textContent = JSON.stringify(
      {
        outreachBatchReady: snapshot.activeContext?.sales?.outreachBatchReady || null,
        outreachDispatch: snapshot.activeContext?.sales?.outreachDispatch || null,
        closeMotion: snapshot.activeContext?.sales?.closeMotion || null,
      },
      null,
      2
    );
  }
}

function renderOps(snapshot) {
  if (els.loopTodosTableBody) {
    els.loopTodosTableBody.innerHTML = "";
    for (const todo of asList(snapshot.loopTodos)) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${safeText(todo.team)}</td>
        <td>${safeText(todo.priority)}</td>
        <td>${safeText(todo.title)}</td>
        <td>${safeText(todo.sourceFile)}</td>
      `;
      els.loopTodosTableBody.appendChild(tr);
    }
  }

  if (els.opsSummary) {
    els.opsSummary.textContent = JSON.stringify(
      {
        operations: snapshot.activeContext?.operations || {},
        todoCount: asList(snapshot.loopTodos).length,
        crossAgentInsights: snapshot.crossAgentInsights || [],
      },
      null,
      2
    );
  }
}

function renderJobsFromList(jobs) {
  if (!els.jobsTableBody) return;
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
  if (!els.runsTableBody) return;
  els.runsTableBody.innerHTML = "";
  for (const run of asList(snapshot.recentRuns)) {
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
  renderJudgeFocus(snapshot);
  renderStageFlow(snapshot);
  renderStageResults(snapshot);
  renderDeployments(snapshot);
  renderGoToMarketPreview(snapshot);
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

    const activeId = activeVentureId();
    for (const j of jobs) {
      if (activeId && j.ventureId && j.ventureId !== activeId) continue;
      if (!j.action) continue;
      setActionState(j.action, j.status, j.error || null);
    }

    const sig = jobs.map((j) => `${j.id}:${j.status}`).join("|");
    const running = jobs.filter((j) => ["queued", "running"].includes(String(j.status))).length;

    if (running > 0) {
      updateFeedback(`有 ${running} 个任务正在执行…`, "info");
    } else if (state.lastJobsSignature && state.lastJobsSignature !== sig) {
      updateFeedback("任务状态已更新，正在刷新页面数据。", "ok");
      showToast("任务执行完成，已刷新最新结果。", "ok");
      await refreshFastSnapshot();
    }

    state.lastJobsSignature = sig;
  } catch (err) {
    console.warn("pollJobs failed", err);
  }
}

async function runStudioAction(payload, label = "动作") {
  updateFeedback(`${label} 已提交…`, "info");
  if (payload?.action) setActionState(payload.action, "queued");

  try {
    const res = await postJSON("/api/studio/action", payload);
    logActionResult(res);

    if (res.async) {
      const jobId = res?.job?.id;
      if (payload?.action) setActionState(payload.action, res?.job?.status || "queued");
      if (res.duplicate) {
        updateFeedback(`${label} 复用了已有执行任务${jobId ? ` (${jobId})` : ""}。`, "info");
        showToast(`${label} 复用已有任务`, "info");
      } else {
        updateFeedback(`${label} 已入队${jobId ? ` (${jobId})` : ""}，稍后自动更新。`, "info");
        showToast(`${label} 已入队`, "info");
      }
    } else {
      if (payload?.action) setActionState(payload.action, "succeeded");
      updateFeedback(`${label} 已完成。`, "ok");
      showToast(`${label} 已完成`, "ok");
    }

    await refreshFastSnapshot();
    return res;
  } catch (err) {
    if (payload?.action) setActionState(payload.action, "failed", err?.message || String(err));
    showToast(`${label} 失败：${err?.message || err}`, "error");
    throw err;
  }
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

function bindActionStatusBadges() {
  const bindings = [
    [els.runPreflightBtn, "stage_preflight"],
    [els.runRehearsalBtn, "rehearsal_e2e"],
    [els.refreshIdeasBtn, "refresh_ideas"],
    [els.runProductBtn, "run_product"],
    [els.runMarketingSeoBtn, "run_marketing_seo"],
    [els.runMarketingContentBtn, "run_marketing_content"],
    [els.runMarketingCampaignBtn, "run_marketing_campaign"],
    [els.runSalesProspectingBtn, "run_sales_prospecting"],
    [els.runSalesOutreachPlanBtn, "run_sales_outreach_plan"],
    [els.approveSalesOutreachBtn, "approve_sales_outreach"],
    [els.dispatchSalesSimBtn, "dispatch_sales_outreach"],
    [els.runSalesConversionSimBtn, "run_sales_conversion"],
    [els.runOpsFullBtn, "run_operations_full"],
    [els.writebackOpsBtn, "writeback_operations"],
  ];

  bindings.forEach(([btn, action]) => {
    if (!btn || !action) return;
    const span = document.createElement("span");
    span.className = "action-status status-unknown";
    span.textContent = "idle";
    btn.insertAdjacentElement("afterend", span);
    state.actionStatusEls[action] = state.actionStatusEls[action] || [];
    state.actionStatusEls[action].push(span);
  });
}

function bindEvents() {
  bindTabs();
  bindActionStatusBadges();

  if (els.uiModeSelect) {
    els.uiModeSelect.value = state.uiMode;
    els.uiModeSelect.addEventListener("change", () => {
      state.uiMode = els.uiModeSelect.value;
      localStorage.setItem("op1.uiMode", state.uiMode);
      applyUiMode();
    });
  }

  if (els.refreshBtn) {
    els.refreshBtn.addEventListener("click", () => {
      refreshStudio({ forceMonitor: true }).catch((err) => updateFeedback(`刷新失败: ${err.message}`, "error"));
    });
  }

  if (els.armOnBtn) {
    els.armOnBtn.addEventListener("click", async () => {
      try {
        await postJSON("/api/runtime-flags/manual-arm", { enabled: true });
        updateFeedback("Manual arm 已设置为 ON。", "ok");
        await refreshStudio({ forceMonitor: true });
      } catch (err) {
        updateFeedback(`设置 manual arm 失败: ${err.message}`, "error");
      }
    });
  }

  if (els.armOffBtn) {
    els.armOffBtn.addEventListener("click", async () => {
      try {
        await postJSON("/api/runtime-flags/manual-arm", { enabled: false });
        updateFeedback("Manual arm 已设置为 OFF。", "ok");
        await refreshStudio({ forceMonitor: true });
      } catch (err) {
        updateFeedback(`设置 manual arm 失败: ${err.message}`, "error");
      }
    });
  }

  if (els.runPreflightBtn) {
    els.runPreflightBtn.addEventListener("click", async () => {
      const ventureId = activeVentureId();
      try {
        await runStudioAction({ action: "stage_preflight", ventureId, async: true }, "运行演示前预检查");
      } catch (err) {
        updateFeedback(`预检查失败: ${err.message}`, "error");
      }
    });
  }

  if (els.runRehearsalBtn) {
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
  }

  if (els.resetDemoStateBtn) {
    els.resetDemoStateBtn.addEventListener("click", async () => {
      const ok = confirm("将清空 Studio 演示历史（ventures/runs/jobs关联展示），保留 idea 数据。继续吗？");
      if (!ok) return;
      try {
        await runStudioAction({ action: "reset_demo_state", keepIdeas: true, async: false }, "重置演示历史");
        showToast("演示历史已重置", "ok");
      } catch (err) {
        updateFeedback(`重置失败: ${err.message}`, "error");
      }
    });
  }

  if (els.refreshIdeasBtn) {
    els.refreshIdeasBtn.addEventListener("click", async () => {
      try {
        await runStudioAction(
          { action: "refresh_ideas", mode: els.ideaModeSelect?.value || "deterministic", async: true },
          "刷新 startup ideas"
        );
      } catch (err) {
        updateFeedback(`刷新 ideas 失败: ${err.message}`, "error");
      }
    });
  }

  if (els.runProductBtn) {
    els.runProductBtn.addEventListener("click", async () => {
      const ventureId = ensureActiveVentureOrAlert();
      if (!ventureId) return;

      const mode = els.productMode.value;
      const payload = { action: "run_product", ventureId, mode, deployTarget: "preview", async: true };
      if (mode === "live") {
        const ok = confirm("将执行 live 部署（会写入 Vercel）。确认继续？");
        if (!ok) return;
        payload.confirmLive = true;
      }

      try {
        await runStudioAction(payload, `执行 Product (${mode})`);
      } catch (err) {
        updateFeedback(`执行 Product 失败: ${err.message}`, "error");
      }
    });
  }

  if (els.runMarketingSeoBtn) {
    els.runMarketingSeoBtn.addEventListener("click", async () => {
      const ventureId = ensureActiveVentureOrAlert();
      if (!ventureId) return;
      try {
        await runStudioAction({ action: "run_marketing_seo", ventureId, mode: "shadow", async: true }, "Run SEO experiments");
      } catch (err) {
        updateFeedback(`营销SEO失败: ${err.message}`, "error");
      }
    });
  }

  if (els.runMarketingContentBtn) {
    els.runMarketingContentBtn.addEventListener("click", async () => {
      const ventureId = ensureActiveVentureOrAlert();
      if (!ventureId) return;
      try {
        await runStudioAction({ action: "run_marketing_content", ventureId, mode: "review", async: true }, "生成内容候选");
      } catch (err) {
        updateFeedback(`内容生成失败: ${err.message}`, "error");
      }
    });
  }

  if (els.runMarketingCampaignBtn) {
    els.runMarketingCampaignBtn.addEventListener("click", async () => {
      const ventureId = ensureActiveVentureOrAlert();
      if (!ventureId) return;
      try {
        await runStudioAction({ action: "run_marketing_campaign", ventureId, mode: "review", async: true }, "生成 campaign 候选");
      } catch (err) {
        updateFeedback(`campaign生成失败: ${err.message}`, "error");
      }
    });
  }

  if (els.approveSelectedContentBtn) {
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
  }

  if (els.rejectSelectedContentBtn) {
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
  }

  if (els.runSalesProspectingBtn) {
    els.runSalesProspectingBtn.addEventListener("click", async () => {
      const ventureId = ensureActiveVentureOrAlert();
      if (!ventureId) return;
      try {
        await runStudioAction({ action: "run_sales_prospecting", ventureId, async: true }, "Identify prospects");
      } catch (err) {
        updateFeedback(`prospecting 失败: ${err.message}`, "error");
      }
    });
  }

  if (els.runSalesOutreachPlanBtn) {
    els.runSalesOutreachPlanBtn.addEventListener("click", async () => {
      const ventureId = ensureActiveVentureOrAlert();
      if (!ventureId) return;
      try {
        await runStudioAction({ action: "run_sales_outreach_plan", ventureId, async: true }, "规划 Send outreach");
      } catch (err) {
        updateFeedback(`outreach plan 失败: ${err.message}`, "error");
      }
    });
  }

  if (els.approveSalesOutreachBtn) {
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
  }

  if (els.dispatchSalesSimBtn) {
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
  }

  if (els.dispatchSalesLiveBtn) {
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
  }

  if (els.runSalesConversionSimBtn) {
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
  }

  if (els.runSalesConversionLiveBtn) {
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
  }

  if (els.runOpsFullBtn) {
    els.runOpsFullBtn.addEventListener("click", async () => {
      const ventureId = ensureActiveVentureOrAlert();
      if (!ventureId) return;
      try {
        await runStudioAction({ action: "run_operations_full", ventureId, async: true }, "Run operations full");
      } catch (err) {
        updateFeedback(`operations full 失败: ${err.message}`, "error");
      }
    });
  }

  if (els.writebackOpsBtn) {
    els.writebackOpsBtn.addEventListener("click", async () => {
      const ventureId = ensureActiveVentureOrAlert();
      if (!ventureId) return;
      try {
        await runStudioAction({ action: "writeback_operations", ventureId, async: true }, "回写下一轮待办");
      } catch (err) {
        updateFeedback(`ops writeback 失败: ${err.message}`, "error");
      }
    });
  }

  if (els.confirmIterateBtn) {
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
  applyUiMode();
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
