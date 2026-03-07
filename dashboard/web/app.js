const els = {
  refreshBtn: document.getElementById("refreshBtn"),
  lastUpdated: document.getElementById("lastUpdated"),
  uiModeSelect: document.getElementById("uiModeSelect"),
  langSelect: document.getElementById("langSelect"),

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
  judgeVentureSelect: document.getElementById("judgeVentureSelect"),
  judgeSwitchVentureBtn: document.getElementById("judgeSwitchVentureBtn"),
  judgeIdeaSelect: document.getElementById("judgeIdeaSelect"),
  judgeCreateVentureBtn: document.getElementById("judgeCreateVentureBtn"),
  judgeStageCard: document.getElementById("judgeStageCard"),
  judgeArtifactCards: document.getElementById("judgeArtifactCards"),
  judgePrimaryAction: document.getElementById("judgePrimaryAction"),

  quickstartList: document.getElementById("quickstartList"),
  workflowMap: document.getElementById("workflowMap"),
  workflowExplainer: document.getElementById("workflowExplainer"),
  capabilityWall: document.getElementById("capabilityWall"),
  recommendedActions: document.getElementById("recommendedActions"),
  feedbackBar: document.getElementById("feedbackBar"),
  runPreflightBtn: document.getElementById("runPreflightBtn"),
  runRehearsalBtn: document.getElementById("runRehearsalBtn"),
  resetDemoStateBtn: document.getElementById("resetDemoStateBtn"),

  promptStagePill: document.getElementById("promptStagePill"),
  promptStageProgress: document.getElementById("promptStageProgress"),
  promptPendingQuestions: document.getElementById("promptPendingQuestions"),
  promptInput: document.getElementById("promptInput"),
  promptQuickChips: document.getElementById("promptQuickChips"),
  submitPromptBtn: document.getElementById("submitPromptBtn"),
  promptClearBtn: document.getElementById("promptClearBtn"),
  promptResponse: document.getElementById("promptResponse"),
  promptHistory: document.getElementById("promptHistory"),

  marketingQuickSummary: document.getElementById("marketingQuickSummary"),
  marketingQuickContent: document.getElementById("marketingQuickContent"),
  marketingQuickCampaign: document.getElementById("marketingQuickCampaign"),
  salesOpsRealityBoard: document.getElementById("salesOpsRealityBoard"),

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
  productPageProfile: document.getElementById("productPageProfile"),
  productUseVercelPreview: document.getElementById("productUseVercelPreview"),
  runProductBtn: document.getElementById("runProductBtn"),
  productSummary: document.getElementById("productSummary"),

  runMarketingSeoBtn: document.getElementById("runMarketingSeoBtn"),
  runMarketingContentBtn: document.getElementById("runMarketingContentBtn"),
  runMarketingCampaignBtn: document.getElementById("runMarketingCampaignBtn"),
  marketingSummary: document.getElementById("marketingSummary"),
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
  jsonDialog: document.getElementById("jsonDialog"),
  jsonDialogTitle: document.getElementById("jsonDialogTitle"),
  jsonDialogContent: document.getElementById("jsonDialogContent"),
  jsonDialogCloseBtn: document.getElementById("jsonDialogCloseBtn"),
  toastContainer: document.getElementById("toastContainer"),
};

const state = {
  snapshot: null,
  monitorSnapshot: null,
  jobs: [],
  selectedTab: "idea",
  lastJobsSignature: "",
  uiMode: localStorage.getItem("op1.uiMode") || "judge",
  lang: localStorage.getItem("op1.lang") || "bi",
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

const STATIC_TEXT_CACHE = new WeakMap();
const STATIC_ATTR_CACHE = new WeakMap();

function hasCjk(text) {
  return /[\u3400-\u9fff]/.test(String(text || ""));
}

function splitBilingualParts(text) {
  const raw = String(text || "");
  if (!raw.includes(" / ")) return null;
  const parts = raw
    .split(/\s+\/\s+/)
    .map((p) => p.trim())
    .filter(Boolean);
  if (parts.length !== 2) return null;

  const [a, b] = parts;
  const aZh = hasCjk(a);
  const bZh = hasCjk(b);

  if (aZh && !bZh) return { zh: a, en: b };
  if (!aZh && bZh) return { zh: b, en: a };
  return { zh: a, en: b };
}

function localizeBilingualText(text) {
  const raw = String(text || "");
  const m = raw.match(/^(\s*)([\s\S]*?)(\s*)$/);
  const prefix = m ? m[1] : "";
  const core = m ? m[2] : raw;
  const suffix = m ? m[3] : "";

  const parts = splitBilingualParts(core);
  if (!parts) return raw;

  const zh = parts.zh || parts.en || "";
  const en = parts.en || parts.zh || "";

  let out = core;
  if (state.lang === "zh") out = zh || en;
  else if (state.lang === "en") out = en || zh;
  else out = zh && en && zh !== en ? `${zh} / ${en}` : zh || en;

  return `${prefix}${out}${suffix}`;
}

function safeText(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return JSON.stringify(value);
  return localizeBilingualText(String(value));
}

function asList(value) {
  return Array.isArray(value) ? value : [];
}

function tr(zh, en) {
  const z = safeText(zh || "");
  const e = safeText(en || "");
  if (state.lang === "zh") return z || e;
  if (state.lang === "en") return e || z;
  if (!z) return e;
  if (!e) return z;
  return `${z} / ${e}`;
}

function statusClass(status) {
  const s = String(status || "unknown").toLowerCase();
  if (["passed", "ready", "succeeded", "success", "completed"].includes(s)) return "status-passed";
  if (["warning", "review_required", "running", "queued", "pending", "current", "awaiting_confirmation"].includes(s)) return "status-warning";
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

const MESSAGE_TRANSLATIONS = [
  ["正在加载 Studio 快照", "Loading Studio snapshot"],
  ["Studio 已就绪", "Studio is ready"],
  ["初始化失败", "Initialization failed"],
  ["刷新失败", "Refresh failed"],
  ["执行失败", "Execution failed"],
  ["提问失败", "Question failed"],
  ["已回答你的问题", "Question answered"],
  ["请先在 Idea Board 创建并激活 venture", "Please create and activate a venture in Idea Board first"],
  ["请先勾选内容项", "Please select content items first"],
  ["切换项目失败", "Switch venture failed"],
  ["创建项目失败", "Create venture failed"],
  ["刷新 ideas 失败", "Refresh ideas failed"],
  ["执行 Product 失败", "Run Product failed"],
  ["营销SEO失败", "Marketing SEO failed"],
  ["内容生成失败", "Content generation failed"],
  ["campaign生成失败", "Campaign generation failed"],
  ["内容审批失败", "Content approval failed"],
  ["内容驳回失败", "Content rejection failed"],
  ["prospecting 失败", "Prospecting failed"],
  ["outreach plan 失败", "Outreach plan failed"],
  ["approve outreach 失败", "Approve outreach failed"],
  ["dispatch simulate 失败", "Dispatch simulate failed"],
  ["dispatch live 失败", "Dispatch live failed"],
  ["conversion simulate 失败", "Conversion simulate failed"],
  ["conversion live 失败", "Conversion live failed"],
  ["operations full 失败", "Operations full failed"],
  ["ops writeback 失败", "Ops writeback failed"],
  ["确认下一轮失败", "Confirm next cycle failed"],
  ["设置 manual arm 失败", "Failed to set manual arm"],
  ["Manual arm 已设置为 ON", "Manual arm set to ON"],
  ["Manual arm 已设置为 OFF", "Manual arm set to OFF"],
  ["预检查失败", "Preflight failed"],
  ["彩排失败", "Rehearsal failed"],
  ["重置失败", "Reset failed"],
  ["演示历史已重置", "Demo history reset"],
  ["当前没有阻塞型用户提问", "No blocking user questions"],
  ["当前无运行中的任务", "No running jobs"],
  ["最近错误", "Latest error"],
  ["建议", "Suggestion"],
  ["请先", "Please first"],
];

function localizeMessage(message) {
  const raw = localizeBilingualText(safeText(message || ""));
  if (!raw) return raw;
  if (state.lang === "zh") return raw;

  let translated = raw;
  for (const [zh, en] of MESSAGE_TRANSLATIONS) {
    translated = translated.split(zh).join(state.lang === "en" ? en : `${zh} / ${en}`);
  }

  if (state.lang === "en") return translated;
  if (translated === raw) return raw;
  return translated;
}

function updateFeedback(message, kind = "info") {
  if (!els.feedbackBar) return;
  els.feedbackBar.textContent = localizeMessage(message);
  if (kind === "error") {
    els.feedbackBar.className = "feedback status-failed";
  } else if (kind === "ok") {
    els.feedbackBar.className = "feedback status-passed";
  } else {
    els.feedbackBar.className = "feedback muted";
  }
}

const WORKFLOW_STAGES = [
  {
    id: "PRODUCT",
    title: "Product",
    why: "把机会变成可演示网页（landing + preview/deploy） / Turn opportunities into demo-ready pages.",
    capabilities: ["Generate startup ideas", "Build & deploy simple web products", "Create landing pages"],
  },
  {
    id: "MARKETING",
    title: "Marketing",
    why: "验证增长叙事，产出内容与campaign输入 / Validate growth narrative and generate campaign inputs.",
    capabilities: ["Run SEO experiments", "Publish content", "Launch campaigns"],
  },
  {
    id: "SALES",
    title: "Sales",
    why: "把流量变成线索、对话和首批付费客户 / Convert traffic into leads and early customers.",
    capabilities: ["Identify prospects", "Send outreach", "Convert early customers"],
  },
  {
    id: "OPERATIONS",
    title: "Operations",
    why: "跟踪指标、处理反馈、形成迭代闭环 / Track metrics, process feedback, and close the iteration loop.",
    capabilities: ["Track traffic/signups/revenue", "Process feedback", "Iterate on product"],
  },
];

const CAPABILITY_HINTS = {
  product_generate_startup_ideas: "证明系统会发现并筛选可行商业机会 / Discover and prioritize viable opportunities.",
  product_build_deploy_simple_web: "证明系统能把想法快速变成可运行网页 / Turn ideas into runnable web products quickly.",
  product_create_landing_pages: "证明系统能产出可转化落地页与文案结构 / Build conversion-oriented landing pages.",
  marketing_run_seo_experiments: "证明系统能做增长实验设计与关键词验证 / Design growth experiments and keyword validation.",
  marketing_publish_content: "证明系统能批量产出可发布内容资产 / Generate publish-ready content assets at scale.",
  marketing_launch_campaigns: "证明系统能从内容生成可执行 campaign / Convert content into executable campaigns.",
  sales_identify_prospects: "证明系统能定位可成交人群和线索池 / Identify qualified prospect segments.",
  sales_send_outreach: "证明系统能生成并执行外联动作 / Plan and execute outreach actions.",
  sales_convert_early_customers: "证明系统能推动从线索到付费转化 / Drive conversion from lead to paid customer.",
  operations_track_traffic_signups_revenue: "证明系统能跟踪业务核心指标（流量/注册/MRR） / Track core business metrics.",
  operations_process_feedback: "证明系统能处理用户反馈并做优先级 / Process feedback and prioritize improvements.",
  operations_iterate_on_product: "证明系统能把反馈回写到下一轮产品迭代 / Feed insights into next product cycle.",
};

function showToast(message, kind = "info") {
  if (!els.toastContainer) return;
  const item = document.createElement("div");
  item.className = `toast ${kind === "error" ? "error" : kind === "ok" ? "ok" : ""}`;
  item.textContent = localizeMessage(message);
  els.toastContainer.appendChild(item);
  setTimeout(() => item.remove(), 4200);
}

function openJsonDialog(title, payload) {
  if (!els.jsonDialog || !els.jsonDialogContent) return;
  if (els.jsonDialogTitle) els.jsonDialogTitle.textContent = title || tr("详情", "Details");
  els.jsonDialogContent.textContent = typeof payload === "string" ? payload : JSON.stringify(payload || {}, null, 2);
  try {
    els.jsonDialog.showModal();
  } catch {
    els.jsonDialog.setAttribute("open", "open");
  }
}

function closeJsonDialog() {
  if (!els.jsonDialog) return;
  try {
    els.jsonDialog.close();
  } catch {
    els.jsonDialog.removeAttribute("open");
  }
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
    alert(tr("请先在 Idea Board 创建并激活 venture。", "Please create and activate a venture in Idea Board first."));
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

function localizeStaticDomText(root = document.body) {
  if (!root) return;

  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  while (true) {
    const node = walker.nextNode();
    if (!node) break;

    const parent = node.parentElement;
    if (!parent) continue;
    if (["SCRIPT", "STYLE", "PRE", "CODE", "TEXTAREA"].includes(parent.tagName)) continue;

    const original = STATIC_TEXT_CACHE.has(node) ? STATIC_TEXT_CACHE.get(node) : node.nodeValue;
    if (!STATIC_TEXT_CACHE.has(node)) STATIC_TEXT_CACHE.set(node, original);

    if (!String(original || "").includes(" / ")) continue;
    node.nodeValue = localizeBilingualText(String(original || ""));
  }

  const attrs = ["placeholder", "title", "aria-label"];
  const all = root.querySelectorAll("*");
  all.forEach((el) => {
    let cache = STATIC_ATTR_CACHE.get(el);
    if (!cache) {
      cache = {};
      STATIC_ATTR_CACHE.set(el, cache);
    }

    attrs.forEach((attr) => {
      if (!el.hasAttribute(attr)) return;
      if (!(attr in cache)) cache[attr] = el.getAttribute(attr) || "";
      const original = String(cache[attr] || "");
      if (!original.includes(" / ")) return;
      el.setAttribute(attr, localizeBilingualText(original));
    });
  });
}

function applyLanguageMode() {
  if (els.langSelect && els.langSelect.value !== state.lang) {
    els.langSelect.value = state.lang;
  }
  document.documentElement.lang = state.lang === "en" ? "en" : "zh-CN";
  localizeStaticDomText(document.body);
}

function renderTop() {
  const snapshot = state.snapshot || {};
  const monitor = state.monitorSnapshot || snapshot.monitor || {};
  const readiness = monitor?.readiness || {};

  if (snapshot.generatedAt && els.lastUpdated) {
    els.lastUpdated.textContent = tr(`更新于 ${formatTime(snapshot.generatedAt)}`, `Updated at ${formatTime(snapshot.generatedAt)}`);
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
    els.vercelAuditSummary.textContent = tr(
      `审计 audit: total=${audit.projectCount ?? "-"}, keep=${audit.keep ?? "-"}, review=${audit.review ?? "-"}, cleanup=${audit.cleanupCandidates ?? "-"}`,
      `Audit: total=${audit.projectCount ?? "-"}, keep=${audit.keep ?? "-"}, review=${audit.review ?? "-"}, cleanup=${audit.cleanupCandidates ?? "-"}`
    );
  }

  const capFromMonitor = {
    total: asList(monitor.capabilities).length,
    passed: asList(monitor.capabilities).filter((x) => x?.status === "passed").length,
  };
  const cap = capFromMonitor.total > 0 ? capFromMonitor : snapshot.capabilitySummary || {};
  if (els.capabilitySummary) {
    els.capabilitySummary.textContent = tr(`${cap.passed || 0}/${cap.total || 0} 已通过`, `${cap.passed || 0}/${cap.total || 0} passed`);
  }

  const run = snapshot.globalRunState || {};
  if (els.globalRunStatus) {
    if (["queued", "running"].includes(run.status)) {
      const seconds = Math.max(0, Math.round((Number(run.elapsedMs) || 0) / 1000));
      els.globalRunStatus.textContent = tr(
        `正在执行 ${safeText(run.runningAction)}（${seconds}s，${safeText(run.runningCount)} 个任务）`,
        `Running ${safeText(run.runningAction)} (${seconds}s, ${safeText(run.runningCount)} jobs)`
      );
    } else {
      els.globalRunStatus.textContent = tr("当前无运行中的任务。", "No running jobs right now.");
    }
  }
  if (els.globalRunError) {
    if (run.lastError) {
      const hint = run.lastFailedAction
        ? tr(
            `建议：retry ${safeText(run.lastFailedAction)}，或先执行 stage_preflight 再重试。`,
            `Suggestion: retry ${safeText(run.lastFailedAction)} or run stage_preflight first.`
          )
        : tr("建议：先看 Jobs/Stage Timeline 定位错误后重试。", "Suggestion: inspect Jobs/Timeline first, then retry.");
      const errText = String(run.lastError || "").replace(/\s+/g, " ").trim();
      const shortErr = errText.length > 180 ? `${errText.slice(0, 180)}...` : errText;
      els.globalRunError.textContent = tr(`最近错误：${safeText(shortErr)} | ${hint}`, `Latest error: ${safeText(shortErr)} | ${hint}`);
    } else {
      els.globalRunError.textContent = tr("最近错误：无", "Latest error: none");
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
  const primary = guide.primaryRecommendedAction || actions[0] || null;

  const sameAction = (a, b) => {
    if (!a || !b) return false;
    if (String(a.action || "") !== String(b.action || "")) return false;
    try {
      return JSON.stringify(a.payload || {}) === JSON.stringify(b.payload || {});
    } catch {
      return false;
    }
  };

  const secondaryActions = (() => {
    if (!primary) return actions;
    let removed = false;
    return actions.filter((item) => {
      if (!removed && sameAction(item, primary)) {
        removed = true;
        return false;
      }
      return true;
    });
  })();

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
      const isTransitionConfirm = String(action?.payload?.action || "") === "confirm_stage_transition";
      if (action.requiresUserChoice && !isTransitionConfirm) {
        alert("这个动作需要你先在对应列表里选定具体项再执行。\n例如：先从 Marketing 快速处理里选 campaign，再推进 Sales。\n如果是阶段迁移，请直接在“下一步唯一动作”里确认。\n");
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
    if (!secondaryActions.length) {
      const empty = document.createElement("div");
      empty.className = "muted";
      empty.textContent = primary ? "暂无后续动作（先完成“下一步唯一动作”）。" : "暂无推荐动作。";
      els.recommendedActions.appendChild(empty);
    } else {
      for (const action of secondaryActions) renderActionCard(action, els.recommendedActions);
    }
  }

  if (els.judgePrimaryAction) {
    els.judgePrimaryAction.innerHTML = "";
    if (primary) {
      renderActionCard(primary, els.judgePrimaryAction);
    } else {
      const empty = document.createElement("div");
      empty.className = "muted";
      empty.textContent = "暂无唯一动作。";
      els.judgePrimaryAction.appendChild(empty);
    }
  }
}

function renderPromptPanel(snapshot) {
  const panel = snapshot?.userPromptPanel || {};
  const progress = panel.progress || {};
  const pendingTransition = panel.pendingTransition || null;

  if (els.promptStagePill) {
    const stageLabel = safeText(progress.stage || "UNKNOWN").toUpperCase();
    setPill(els.promptStagePill, "current", stageLabel);
  }
  if (els.promptStageProgress) {
    const idx = Number(progress.index) || 0;
    const total = Number(progress.total) || 0;
    let text = idx && total ? `当前进度：${idx}/${total}` : "当前进度：--";
    if (pendingTransition) {
      text += ` · 待确认迁移：${safeText(pendingTransition.fromStage || "?")} → ${safeText(
        pendingTransition.toStage || "?"
      )}`;
    }
    els.promptStageProgress.textContent = text;
  }
  if (els.promptInput && panel.placeholder) {
    els.promptInput.placeholder = safeText(panel.placeholder);
  }

  if (els.promptPendingQuestions) {
    els.promptPendingQuestions.innerHTML = "";
    const questions = asList(panel.pendingQuestions);
    if (!questions.length) {
      const empty = document.createElement("div");
      empty.className = "muted";
      empty.textContent = "当前没有阻塞型用户提问。";
      els.promptPendingQuestions.appendChild(empty);
    } else {
      for (const q of questions) {
        const card = document.createElement("div");
        card.className = "action-card";

        const title = document.createElement("div");
        title.className = "title";
        title.textContent = `[${safeText(q.priority || "info")}] ${safeText(q.question)}`;

        const reason = document.createElement("div");
        reason.className = "desc";
        reason.textContent = safeText(q.reason || "");

        card.appendChild(title);
        card.appendChild(reason);

        const action = q.suggestedAction;
        if (action && action.payload) {
          const row = document.createElement("div");
          row.className = "row";
          const btn = document.createElement("button");
          btn.className = "secondary";
          btn.textContent = `执行建议：${safeText(action.label || action.action)}`;
          btn.addEventListener("click", async () => {
            if (action.requiresUserChoice) {
              alert("这个建议动作需要你先选定具体项。");
              return;
            }
            const payload = { ...(action.payload || {}) };
            if (!payload.ventureId && activeVentureId()) payload.ventureId = activeVentureId();
            try {
              await runStudioAction(payload, `执行建议动作 ${safeText(action.label || action.action)}`);
            } catch (err) {
              updateFeedback(`执行建议动作失败: ${err.message}`, "error");
            }
          });
          row.appendChild(btn);
          card.appendChild(row);
        }

        els.promptPendingQuestions.appendChild(card);
      }
    }
  }

  const history = asList(panel.history);
  if (els.promptHistory) {
    els.promptHistory.innerHTML = "";
    if (!history.length) {
      const empty = document.createElement("div");
      empty.className = "muted";
      empty.textContent = "暂无提问记录。";
      els.promptHistory.appendChild(empty);
    } else {
      for (const item of history) {
        const card = document.createElement("div");
        card.className = "action-card";

        const title = document.createElement("div");
        title.className = "title";
        const modeLabel = safeText(item.mode || "fallback");
        title.textContent = `${safeText(formatTime(item.createdAt))} · ${safeText(item.stage || "-")} · ${modeLabel}`;

        const q = document.createElement("div");
        q.className = "desc";
        q.textContent = `Q: ${safeText(item.prompt || "")}`;

        const a = document.createElement("div");
        a.className = "small";
        a.textContent = `A: ${safeText(item.reply || "")}`;

        card.appendChild(title);
        card.appendChild(q);
        card.appendChild(a);
        els.promptHistory.appendChild(card);
      }
    }
  }

  if (els.promptResponse) {
    const current = String(els.promptResponse.textContent || "").trim();
    if (!current || current === "--") {
      const latest = history[0];
      if (latest?.reply) {
        els.promptResponse.textContent = safeText(latest.reply);
      }
    }
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

function renderWorkflowGuide(snapshot) {
  const stageFlow = asList(snapshot.stageFlow);
  const current = stageFlow.find((x) => x.state === "current")?.stage || "IDEA_POOL";

  if (els.workflowMap) {
    els.workflowMap.innerHTML = "";
    for (const s of WORKFLOW_STAGES) {
      const box = document.createElement("div");
      box.className = `workflow-stage ${s.id === current ? "current" : ""}`;
      const h = document.createElement("div");
      h.className = "title";
      h.textContent = safeText(`${s.title}`);
      const p = document.createElement("div");
      p.className = "small";
      p.textContent = safeText(s.why);
      const ul = document.createElement("ul");
      for (const cap of s.capabilities) {
        const li = document.createElement("li");
        li.textContent = cap;
        ul.appendChild(li);
      }
      box.appendChild(h);
      box.appendChild(p);
      box.appendChild(ul);
      els.workflowMap.appendChild(box);
    }
  }

  if (els.workflowExplainer) {
    const guide = {
      currentStage: current,
      whyNow: (WORKFLOW_STAGES.find((x) => x.id === current) || {}).why || null,
      targetMilestone: "$100 MRR",
      executionLoop: "idea → product → marketing → sales → operations → iterate",
      capabilityChain: {
        product: {
          does: "生成网页与落地页，并形成 Product→Marketing handoff",
          output: ["workspaces/op1_product/.../landing_package.json", "handoffs/product_to_marketing.json"],
          consumedBy: "Marketing",
        },
        marketing: {
          does: "做 SEO/content/campaign，并把可销售素材交给 Sales",
          output: ["publish.queue.latest.json", "campaigns.queue.latest.json", "handoffs/marketing_to_sales.json"],
          consumedBy: "Sales",
        },
        sales: {
          does: "找线索、外联、转化，形成成交信号与运营输入",
          output: ["conversion_scoreboard.latest.json", "handoffs/sales_to_operations.json"],
          consumedBy: "Operations",
        },
        operations: {
          does: "汇总流量/注册/MRR 与反馈，回写下轮改进",
          output: ["stage1_scoreboard.latest.json", "operations_to_*_iterate.json"],
          consumedBy: "下一轮 Product/Marketing/Sales",
        },
      },
    };
    els.workflowExplainer.textContent = JSON.stringify(guide, null, 2);
  }
}

function renderCapabilityWall(snapshot) {
  if (!els.capabilityWall) return;
  const caps = asList(snapshot?.monitor?.capabilities);
  els.capabilityWall.innerHTML = "";

  if (!caps.length) {
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.textContent = tr("能力快照暂不可用。", "Capability snapshot is unavailable.");
    els.capabilityWall.appendChild(empty);
    return;
  }

  const toMetricLine = (metrics) => {
    if (!metrics || typeof metrics !== "object") return "-";
    const entries = Object.entries(metrics).filter(([, v]) => ["string", "number", "boolean"].includes(typeof v));
    return entries
      .slice(0, 3)
      .map(([k, v]) => `${k}=${v}`)
      .join(" | ");
  };

  for (const cap of caps) {
    const card = document.createElement("div");
    card.className = "cap-card";

    const title = document.createElement("div");
    title.className = "title";
    title.textContent = safeText(cap.label || cap.id);

    const status = document.createElement("span");
    status.className = `status-pill ${statusClass(cap.status)}`;
    status.textContent = String(cap.status || "unknown").toUpperCase();

    const hint = document.createElement("div");
    hint.className = "small";
    hint.textContent = safeText(CAPABILITY_HINTS[cap.id] || "该能力对应 CEOClaw 端到端链路中的一个执行环节。 / This capability maps to one execution segment in the CEOClaw end-to-end chain.");

    const metrics = document.createElement("div");
    metrics.className = "small";
    metrics.textContent = toMetricLine(cap.metrics);

    const row = document.createElement("div");
    row.className = "row wrap";
    for (const ev of asList(cap.evidence).slice(0, 2)) {
      if (!ev?.path) continue;
      const btn = document.createElement("button");
      btn.className = "secondary";
      btn.textContent = `证据: ${safeText((ev.path || "").split("/").slice(-1)[0])}`;
      btn.addEventListener("click", () => openArtifact(ev.path));
      row.appendChild(btn);
    }

    card.appendChild(title);
    card.appendChild(status);
    card.appendChild(hint);
    card.appendChild(metrics);
    card.appendChild(row);
    els.capabilityWall.appendChild(card);
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

  if (els.judgeVentureSelect) {
    els.judgeVentureSelect.innerHTML = "";
    for (const v of asList(snapshot.ventures)) {
      const opt = document.createElement("option");
      opt.value = v.id || "";
      opt.textContent = `${safeText(v.name || v.id)} (${safeText(v.stage || "-")})`;
      if (v.id && v.id === snapshot.activeVentureId) opt.selected = true;
      els.judgeVentureSelect.appendChild(opt);
    }
    if (!asList(snapshot.ventures).length) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "暂无 Venture";
      els.judgeVentureSelect.appendChild(opt);
    }
  }

  if (els.judgeIdeaSelect) {
    els.judgeIdeaSelect.innerHTML = "";
    for (const idea of asList(snapshot.ideas)) {
      const opp = idea.opportunity_id || idea.id || "";
      const opt = document.createElement("option");
      opt.value = opp;
      opt.textContent = `${safeText(opp)} | ${safeText(idea.title || idea.problem || idea.one_liner || "startup idea")}`;
      els.judgeIdeaSelect.appendChild(opt);
    }
    if (!asList(snapshot.ideas).length) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "暂无 idea（先刷新）";
      els.judgeIdeaSelect.appendChild(opt);
    }
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
        btn.addEventListener("click", () => openArtifactEntry(item));
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

  const relay = summary.agentRelay || {};
  const relayCompliance = relay.compliance || {};
  const relayProviders = asList(relayCompliance.providersSeen || []).filter(Boolean);
  if (relayProviders.length) picks.push(`relay_provider=${relayProviders.join(",")}`);
  if (relayCompliance.ok === true) picks.push("relay_model=ok");
  if (relayCompliance.ok === false) picks.push("relay_model=non_compliant");

  if (!picks.length) {
    const keys = Object.keys(summary).slice(0, 4);
    return keys.map((k) => `${k}=${safeText(summary[k])}`).join(" | ") || "-";
  }
  return picks.join(" | ");
}

function artifactRawUrl(path) {
  return `/api/studio/artifact/raw?path=${encodeURIComponent(path)}`;
}

function artifactReadableUrl(path) {
  return `/api/studio/artifact/readable?path=${encodeURIComponent(path)}`;
}

function openArtifactEntry(item) {
  if (!item || typeof item !== "object") return;
  if (item.kind === "url" && item.url) {
    openUrlWithFallback(item.url, item.label || "链接");
    return;
  }
  if (item.kind === "preview" && item.path) {
    openUrlWithFallback(`/api/studio/preview?path=${encodeURIComponent(item.path)}`, item.label || "预览");
    return;
  }
  if (item.kind === "file" && item.path) {
    if (item.previewable) {
      openUrlWithFallback(`/api/studio/preview?path=${encodeURIComponent(item.path)}`, item.label || "预览");
    } else {
      openArtifact(item.path);
      showToast(`已加载产物：${item.label || item.path}`, "ok");
    }
  }
}

function openUrlWithFallback(url, label = "链接") {
  const win = window.open(url, "_blank", "noopener,noreferrer");
  if (!win) {
    openJsonDialog("浏览器阻止了新窗口", {
      label,
      url,
      hint: "请手动复制这个 URL 到新标签页打开，或关闭浏览器弹窗拦截后重试。",
    });
  }
}

async function openArtifact(path) {
  if (!path) return;

  // In judge mode, always open a visible page instead of writing into hidden builder panel.
  if (state.uiMode === "judge") {
    openUrlWithFallback(artifactReadableUrl(path), path);
    return;
  }

  if (!els.artifactContent) {
    openUrlWithFallback(artifactReadableUrl(path), path);
    return;
  }

  if (els.artifactPath) els.artifactPath.textContent = path;
  els.artifactContent.textContent = "加载中...";
  try {
    const data = await getJSON(`/api/studio/artifact?path=${encodeURIComponent(path)}`);
    if (data.binary) {
      els.artifactContent.textContent = `Binary file (size=${data.sizeBytes} bytes).\nPath: ${data.path}`;
      openJsonDialog("二进制产物", { path: data.path, sizeBytes: data.sizeBytes, binary: true });
    } else {
      els.artifactContent.textContent = data.content || "(empty)";
      showToast(`已加载产物：${path}`, "ok");
    }
  } catch (err) {
    const msg = `读取失败: ${err.message}`;
    els.artifactContent.textContent = msg;
    showToast(msg, "error");
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
            openUrlWithFallback(`/api/studio/preview?path=${encodeURIComponent(p)}`, "HTML 预览");
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
      btn.addEventListener("click", () => openUrlWithFallback(`/api/studio/preview?path=${encodeURIComponent(previewPath)}`, "Preview"));
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
      webProductPreviewPath: links.productPreviewPath || null,
      landingPreviewPath: links.landingPreviewPath || null,
      vercelProject: links.vercelProject || null,
      vercelEnv: links.vercelEnv || null,
      lastProductAction: venture.lastActions?.product || null,
      note: "如果希望 simulation 也同步 Vercel，请勾选 'simulation 时也同步到 Vercel preview'。",
    },
    null,
    2
  );
}

function renderMarketing(snapshot) {
  const ctx = snapshot.activeContext?.marketing || {};

  if (els.marketingSummary) {
    els.marketingSummary.textContent = JSON.stringify(
      {
        stage2Status: ctx.stage2Status || null,
        stage3Status: ctx.stage3Status || null,
        queueCounts: ctx.queueCounts || {},
        blockers: ctx.blockers || [],
        hint:
          asList(ctx.campaignCandidates).length === 0
            ? "当前没有可选 campaign。可继续运行 SEO/content，或直接进入 Sales prospecting（fallback 路线）。"
            : "请选择一个 campaign 作为 Sales 输入。",
      },
      null,
      2
    );
  }

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
        <td></td>
      `;
      const tdDetail = tr.children[6];
      const btn = document.createElement("button");
      btn.className = "secondary";
      btn.textContent = "展开";
      btn.addEventListener("click", () => openJsonDialog(`Publish content: ${cid}`, item));
      tdDetail.appendChild(btn);
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
        <td></td>
      `;

      const tdDetail = tr.children[4];
      const detailBtn = document.createElement("button");
      detailBtn.className = "secondary";
      detailBtn.textContent = "展开";
      detailBtn.addEventListener("click", () => openJsonDialog(`Campaign: ${campaignId}`, row));
      tdDetail.appendChild(detailBtn);

      const tdAction = tr.children[5];
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

function stageArtifactItems(snapshot, stage) {
  const cards = asList(snapshot?.stageArtifactCards);
  const hit = cards.find((x) => String(x?.stage || "").toUpperCase() === String(stage || "").toUpperCase());
  return asList(hit?.items).slice(0, 4);
}

function renderMarketingQuick(snapshot) {
  const venture = snapshot.activeVenture || null;
  const stage = String(venture?.stage || "");
  const inMarketing = stage === "MARKETING";
  const canSelectCampaign = ["MARKETING", "SALES"].includes(stage);
  const ctx = snapshot.activeContext?.marketing || {};
  const content = asList(ctx.contentCandidates);
  const campaigns = asList(ctx.campaignCandidates);
  const selectedCampaign = venture?.selections?.campaignId || null;

  if (els.marketingQuickSummary) {
    if (!venture) {
      els.marketingQuickSummary.textContent = "暂无 active venture。请先创建项目。";
    } else {
      const blockers = asList(ctx.blockers)
        .map((x) => x?.message)
        .filter(Boolean)
        .slice(0, 2)
        .join(" | ");
      const blockerText = blockers ? ` | blocker: ${blockers}` : "";
      els.marketingQuickSummary.textContent = `stage=${stage} | content=${content.length} | campaign=${campaigns.length} | selected=${selectedCampaign || "-"}${blockerText}`;
    }
  }

  if (els.marketingQuickContent) {
    els.marketingQuickContent.innerHTML = "";

    const head = document.createElement("div");
    head.className = "action-card";
    head.innerHTML = `<div class="title">Publish content（快速查看/处理）</div><div class="desc">Top ${Math.min(content.length, 5)} 项，可直接展开、批准、驳回。</div>`;
    const headRow = document.createElement("div");
    headRow.className = "row wrap";

    const refreshBtn = document.createElement("button");
    refreshBtn.textContent = "刷新 Publish content";
    refreshBtn.disabled = !inMarketing;
    if (!inMarketing) refreshBtn.title = `当前 stage=${stage}，仅 MARKETING 可运行`;
    refreshBtn.addEventListener("click", async () => {
      try {
        await runStudioAction(
          { action: "run_marketing_content", ventureId: activeVentureId(), mode: "review", async: true },
          "刷新 Publish content"
        );
      } catch (err) {
        updateFeedback(`刷新 Publish content 失败: ${err.message}`, "error");
      }
    });
    headRow.appendChild(refreshBtn);
    head.appendChild(headRow);
    els.marketingQuickContent.appendChild(head);

    if (!content.length) {
      const empty = document.createElement("div");
      empty.className = "muted";
      empty.textContent = "暂无 Publish content 候选。";
      els.marketingQuickContent.appendChild(empty);
    }

    for (const item of content.slice(0, 5)) {
      const cid = item.content_id || item.id || "";
      const box = document.createElement("div");
      box.className = "action-card";

      const title = document.createElement("div");
      title.className = "title";
      title.textContent = `${safeText(cid)} [${safeText(item._bucket || "-")}]`;

      const desc = document.createElement("div");
      desc.className = "desc";
      desc.textContent = `${safeText(item.topic || "-")} | kw=${safeText(item.primary_keyword || "-")} | score=${safeText(item.priority_score ?? "-")}`;

      const row = document.createElement("div");
      row.className = "row wrap";

      const detailBtn = document.createElement("button");
      detailBtn.className = "secondary";
      detailBtn.textContent = "展开";
      detailBtn.addEventListener("click", () => openJsonDialog(`Publish content: ${cid}`, item));
      row.appendChild(detailBtn);

      const approveBtn = document.createElement("button");
      approveBtn.textContent = "批准";
      approveBtn.disabled = !inMarketing || !cid;
      if (!inMarketing) approveBtn.title = `当前 stage=${stage}，仅 MARKETING 可审批`;
      approveBtn.addEventListener("click", async () => {
        try {
          await runStudioAction(
            {
              action: "review_marketing_content",
              ventureId: activeVentureId(),
              approveIds: [cid],
              rejectIds: [],
              note: "quick_approve_single",
              reason: "manual_review_requested_changes",
              async: true,
            },
            `批准内容 ${cid}`
          );
        } catch (err) {
          updateFeedback(`批准内容失败: ${err.message}`, "error");
        }
      });
      row.appendChild(approveBtn);

      const rejectBtn = document.createElement("button");
      rejectBtn.className = "secondary";
      rejectBtn.textContent = "驳回";
      rejectBtn.disabled = !inMarketing || !cid;
      if (!inMarketing) rejectBtn.title = `当前 stage=${stage}，仅 MARKETING 可审批`;
      rejectBtn.addEventListener("click", async () => {
        try {
          await runStudioAction(
            {
              action: "review_marketing_content",
              ventureId: activeVentureId(),
              approveIds: [],
              rejectIds: [cid],
              note: "quick_reject_single",
              reason: "manual_review_requested_changes",
              async: true,
            },
            `驳回内容 ${cid}`
          );
        } catch (err) {
          updateFeedback(`驳回内容失败: ${err.message}`, "error");
        }
      });
      row.appendChild(rejectBtn);

      box.appendChild(title);
      box.appendChild(desc);
      box.appendChild(row);
      els.marketingQuickContent.appendChild(box);
    }
  }

  if (els.marketingQuickCampaign) {
    els.marketingQuickCampaign.innerHTML = "";

    const head = document.createElement("div");
    head.className = "action-card";
    head.innerHTML = `<div class="title">Launch campaigns（快速查看/切换 Sales 输入）</div><div class="desc">Top ${Math.min(campaigns.length, 5)} 项，可直接设为 Sales 输入。</div>`;
    const headRow = document.createElement("div");
    headRow.className = "row wrap";

    const refreshBtn = document.createElement("button");
    refreshBtn.textContent = "刷新 Launch campaigns";
    refreshBtn.disabled = !inMarketing;
    if (!inMarketing) refreshBtn.title = `当前 stage=${stage}，仅 MARKETING 可运行`;
    refreshBtn.addEventListener("click", async () => {
      try {
        await runStudioAction(
          { action: "run_marketing_campaign", ventureId: activeVentureId(), mode: "review", async: true },
          "刷新 Launch campaigns"
        );
      } catch (err) {
        updateFeedback(`刷新 Launch campaigns 失败: ${err.message}`, "error");
      }
    });
    headRow.appendChild(refreshBtn);
    head.appendChild(headRow);
    els.marketingQuickCampaign.appendChild(head);

    if (!campaigns.length) {
      const empty = document.createElement("div");
      empty.className = "muted";
      empty.textContent = "暂无 campaign 候选。可继续跑 SEO/content，或直接走 Sales fallback。";
      els.marketingQuickCampaign.appendChild(empty);
    }

    for (const row of campaigns.slice(0, 5)) {
      const campaignId = row.campaign_id || row.id || "";
      const box = document.createElement("div");
      box.className = "action-card";

      const title = document.createElement("div");
      title.className = "title";
      title.textContent = `${safeText(campaignId)}${campaignId && campaignId === selectedCampaign ? " · 当前选中" : ""}`;

      const desc = document.createElement("div");
      desc.className = "desc";
      desc.textContent = `bucket=${safeText(row._bucket || "-")} | kw=${safeText(row.primary_keyword || "-")} | readiness=${safeText(
        row.readiness_score ?? "-"
      )}`;

      const actions = document.createElement("div");
      actions.className = "row wrap";

      const detailBtn = document.createElement("button");
      detailBtn.className = "secondary";
      detailBtn.textContent = "展开";
      detailBtn.addEventListener("click", () => openJsonDialog(`Campaign: ${campaignId}`, row));
      actions.appendChild(detailBtn);

      const selectBtn = document.createElement("button");
      selectBtn.textContent = campaignId === selectedCampaign ? "已选中" : "设为 Sales 输入";
      selectBtn.disabled = !campaignId || !canSelectCampaign || campaignId === selectedCampaign;
      if (!canSelectCampaign) {
        selectBtn.title = `当前 stage=${stage}，仅 MARKETING/SALES 可更换 campaign`;
      }
      selectBtn.addEventListener("click", async () => {
        try {
          await runStudioAction(
            {
              action: "select_marketing_campaign",
              ventureId: activeVentureId(),
              campaignId,
              async: false,
            },
            `切换 campaign: ${campaignId}`
          );
        } catch (err) {
          updateFeedback(`选择 campaign 失败: ${err.message}`, "error");
        }
      });
      actions.appendChild(selectBtn);

      box.appendChild(title);
      box.appendChild(desc);
      box.appendChild(actions);
      els.marketingQuickCampaign.appendChild(box);
    }
  }
}

function renderSalesOpsReality(snapshot) {
  if (!els.salesOpsRealityBoard) return;
  els.salesOpsRealityBoard.innerHTML = "";

  const venture = snapshot.activeVenture || null;
  if (!venture) {
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.textContent = "暂无 active venture。";
    els.salesOpsRealityBoard.appendChild(empty);
    return;
  }

  const sales = snapshot.activeContext?.sales || {};
  const ops = snapshot.activeContext?.operations || {};
  const segments = asList(sales.segments);
  const topSeg = segments[0] || {};
  const topScores = topSeg.scores || {};
  const dispatchSummary = sales.outreachDispatch?.summary || {};

  const salesCard = document.createElement("div");
  salesCard.className = "action-card";
  salesCard.innerHTML = `
    <div class="title">Sales 真实能力（线索 → 外联 → 转化）</div>
    <div class="quick-metrics">
      <div class="quick-metric">线索分层：segments=${safeText(segments.length)}，top_weekly_leads=${safeText(topScores.estimated_weekly_leads ?? "-")}</div>
      <div class="quick-metric">外联批次：messages=${safeText(sales.outreachBatchReady?.message_count ?? "-")}，status=${safeText(
        sales.outreachBatchReady?.status || "-"
      )}</div>
      <div class="quick-metric">发送执行：mode=${safeText(sales.outreachDispatch?.mode || "-")}，processed=${safeText(
        dispatchSummary.processed ?? "-"
      )}</div>
      <div class="quick-metric">转化闭环：${safeText(sales.closeMotion?.headline || "暂无 close motion")}</div>
    </div>
  `;
  const salesActions = document.createElement("div");
  salesActions.className = "row wrap";
  for (const item of stageArtifactItems(snapshot, "SALES")) {
    const btn = document.createElement("button");
    btn.className = "secondary";
    btn.textContent = safeText(item.label || "Sales 证据");
    btn.addEventListener("click", () => openArtifactEntry(item));
    salesActions.appendChild(btn);
  }
  salesCard.appendChild(salesActions);
  els.salesOpsRealityBoard.appendChild(salesCard);

  const stage1 = ops.stage1 || {};
  const stage2 = ops.stage2 || {};
  const stage3 = ops.stage3 || {};
  const opsCard = document.createElement("div");
  opsCard.className = "action-card";
  opsCard.innerHTML = `
    <div class="title">Operations 真实能力（跟踪 → 反馈 → 迭代）</div>
    <div class="quick-metrics">
      <div class="quick-metric">流量与营收：sessions=${safeText(stage1.sessions ?? "-")}，qualified_signups=${safeText(
        stage1.qualified_signups ?? "-"
      )}，net_new_mrr=${safeText(stage1.net_new_mrr ?? "-")}</div>
      <div class="quick-metric">反馈处理：feedback_items=${safeText(stage2.feedback_items_total ?? "-")}，themes=${safeText(
        stage2.themes_total ?? "-"
      )}，expected_mrr_delta_30d=${safeText(stage2.expected_mrr_delta_30d ?? "-")}</div>
      <div class="quick-metric">迭代输出：experiments=${safeText(stage3.experiments_planned ?? "-")}，ship=${safeText(
        stage3.ship_count ?? "-"
      )}，iterate=${safeText(stage3.iterate_count ?? "-")}</div>
    </div>
  `;
  const opsActions = document.createElement("div");
  opsActions.className = "row wrap";
  for (const item of stageArtifactItems(snapshot, "OPERATIONS")) {
    const btn = document.createElement("button");
    btn.className = "secondary";
    btn.textContent = safeText(item.label || "Operations 证据");
    btn.addEventListener("click", () => openArtifactEntry(item));
    opsActions.appendChild(btn);
  }
  opsCard.appendChild(opsActions);
  els.salesOpsRealityBoard.appendChild(opsCard);
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
  renderPromptPanel(snapshot);
  renderWorkflowGuide(snapshot);
  renderCapabilityWall(snapshot);
  renderJudgeFocus(snapshot);
  renderStageFlow(snapshot);
  renderStageResults(snapshot);
  renderDeployments(snapshot);
  renderGoToMarketPreview(snapshot);
  renderIdeas(snapshot);
  renderVentures(snapshot);
  renderProduct(snapshot);
  renderMarketing(snapshot);
  renderMarketingQuick(snapshot);
  renderSales(snapshot);
  renderOps(snapshot);
  renderSalesOpsReality(snapshot);
  renderJobsFromList(snapshot.jobs || []);
  renderRuns(snapshot);
  localizeStaticDomText(document.body);
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

async function submitUserPrompt() {
  const text = String(els.promptInput?.value || "").trim();
  if (!text) {
    updateFeedback("请输入问题后再提交。", "error");
    return;
  }

  const payload = {
    action: "submit_user_prompt",
    prompt: text,
    async: false,
  };
  const ventureId = activeVentureId();
  if (ventureId) payload.ventureId = ventureId;

  updateFeedback("正在分析你的问题…", "info");
  try {
    const res = await postJSON("/api/studio/action", payload);
    logActionResult(res);
    const result = res?.result || {};
    if (els.promptResponse) {
      const mode = String(result.mode || "fallback");
      const risks = asList(result.riskFlags).map((x) => safeText(x));
      const asks = asList(result.questionsForUser).map((x) => safeText(x));
      let text = safeText(result.reply || "未返回回答。");
      text += `\n\n[来源] ${mode === "llm" ? "Copilot" : "规则引擎"}`;
      if (risks.length) {
        text += "\n[风险]";
        risks.slice(0, 5).forEach((r) => {
          text += `\n- ${r}`;
        });
      }
      if (asks.length) {
        text += "\n[待确认]";
        asks.slice(0, 5).forEach((q) => {
          text += `\n- ${q}`;
        });
      }
      els.promptResponse.textContent = text;
    }
    updateFeedback("已生成阶段建议。", "ok");
    showToast("已回答你的问题", "ok");
    await refreshFastSnapshot();
  } catch (err) {
    updateFeedback(`提问失败: ${err.message}`, "error");
    showToast(`提问失败: ${err.message}`, "error");
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

  if (els.langSelect) {
    els.langSelect.value = state.lang;
    els.langSelect.addEventListener("change", async () => {
      state.lang = els.langSelect.value || "bi";
      localStorage.setItem("op1.lang", state.lang);
      applyLanguageMode();
      await refreshFastSnapshot();
      await pollJobs();
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

  if (els.submitPromptBtn) {
    els.submitPromptBtn.addEventListener("click", () => {
      submitUserPrompt().catch((err) => updateFeedback(`提问失败: ${err.message}`, "error"));
    });
  }

  if (els.promptClearBtn) {
    els.promptClearBtn.addEventListener("click", () => {
      if (els.promptInput) els.promptInput.value = "";
      if (els.promptResponse) els.promptResponse.textContent = "--";
    });
  }

  if (els.promptInput) {
    els.promptInput.addEventListener("keydown", (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
        event.preventDefault();
        submitUserPrompt().catch((err) => updateFeedback(`提问失败: ${err.message}`, "error"));
      }
    });
  }

  if (els.promptQuickChips) {
    const chips = Array.from(els.promptQuickChips.querySelectorAll("button[data-prompt]"));
    for (const chip of chips) {
      chip.addEventListener("click", () => {
        const prompt = String(chip.getAttribute("data-prompt") || "").trim();
        if (!prompt) return;
        if (els.promptInput) els.promptInput.value = prompt;
        submitUserPrompt().catch((err) => updateFeedback(`提问失败: ${err.message}`, "error"));
      });
    }
  }

  if (els.judgeSwitchVentureBtn) {
    els.judgeSwitchVentureBtn.addEventListener("click", async () => {
      const ventureId = els.judgeVentureSelect?.value;
      if (!ventureId) {
        updateFeedback("没有可切换的 venture。", "error");
        return;
      }
      try {
        await runStudioAction({ action: "set_active_venture", ventureId, async: false }, "切换项目");
      } catch (err) {
        updateFeedback(`切换项目失败: ${err.message}`, "error");
      }
    });
  }

  if (els.judgeCreateVentureBtn) {
    els.judgeCreateVentureBtn.addEventListener("click", async () => {
      const opp = els.judgeIdeaSelect?.value;
      if (!opp) {
        updateFeedback("没有可用 idea，请先刷新 ideas。", "error");
        return;
      }
      try {
        await runStudioAction({ action: "create_venture", opportunityId: opp, async: false }, "创建项目");
      } catch (err) {
        updateFeedback(`创建项目失败: ${err.message}`, "error");
      }
    });
  }

  if (els.jsonDialogCloseBtn) {
    els.jsonDialogCloseBtn.addEventListener("click", () => closeJsonDialog());
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

      const requestedMode = els.productMode.value;
      const useVercelPreview = Boolean(els.productUseVercelPreview?.checked);
      const pageProfile = (els.productPageProfile?.value || "").trim();

      const mode = requestedMode === "live" || useVercelPreview ? "live" : "simulation";
      const payload = { action: "run_product", ventureId, mode, deployTarget: "preview", async: true };
      if (pageProfile) payload.pageProfile = pageProfile;

      if (mode === "live") {
        const msg = useVercelPreview && requestedMode !== "live"
          ? "你选择了 simulation 同步到 Vercel preview，这会执行安全预览部署（非 production）。确认继续？"
          : "将执行 live-preview 部署（会写入 Vercel preview）。确认继续？";
        const ok = confirm(msg);
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
  applyLanguageMode();
  bindEvents();
  updateFeedback(tr("正在加载 Studio 快照…", "Loading Studio snapshot..."), "info");
  await refreshFastSnapshot();
  await refreshMonitorSnapshot(true);
  await refreshFastSnapshot();
  await pollJobs();
  startTimers();
  updateFeedback(tr("Studio 已就绪。建议按“下一步推荐动作”执行。", "Studio is ready. Follow the recommended next action."), "ok");
}

main().catch((err) => {
  console.error(err);
  updateFeedback(tr(`初始化失败: ${err.message}`, `Initialization failed: ${err.message}`), "error");
});
