
const OPERATIONS_REFRESH_MS = 15000;

let operationsRefreshTimer = null;
let operationsConsoleTimer = null;
let operationsConsoleRunId = null;
let operationsConsoleLastEventId = 0;

function byId(id) {
  return document.getElementById(id);
}

function safe(value, fallback = "—") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }

  return value;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatNumber(value) {
  const numeric = Number(value || 0);

  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 2
  }).format(numeric);
}

function formatHashrate(value) {
  const numeric = Number(value || 0);

  const units = [
    ["EH/s", 1e18],
    ["PH/s", 1e15],
    ["TH/s", 1e12],
    ["GH/s", 1e9],
    ["MH/s", 1e6],
    ["KH/s", 1e3],
    ["H/s", 1]
  ];

  for (const [unit, divisor] of units) {
    if (numeric >= divisor || divisor === 1) {
      return `${(numeric / divisor).toFixed(
        numeric >= divisor * 100 ? 0 : 2
      )} ${unit}`;
    }
  }

  return "0 H/s";
}

function formatTime(value) {
  if (!value) return "—";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);

  return date.toLocaleString();
}

function statusMessage(overall) {
  const critical = Number(overall?.criticalAlerts || 0);
  const recommendations = Number(
    overall?.highPriorityRecommendations || 0
  );
  const failed = Number(overall?.failedOperations || 0);

  if (critical > 0) {
    return `${critical} critical alert${
      critical === 1 ? "" : "s"
    } require attention.`;
  }

  if (failed > 0) {
    return `${failed} automation run${
      failed === 1 ? "" : "s"
    } failed.`;
  }

  if (recommendations > 0) {
    return `${recommendations} high-priority recommendation${
      recommendations === 1 ? "" : "s"
    } available.`;
  }

  return "No critical operational issues are active.";
}

function stat(label, value) {
  return `
    <div>
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </div>
  `;
}

function emptyState(message) {
  return `
    <div class="operations-empty">
      ${escapeHtml(message)}
    </div>
  `;
}

function renderHero(data) {
  const overall = data.overall || {};
  const status = String(overall.status || "unknown").toLowerCase();
  const hero = byId("operationsHero");

  hero.className = `operations-hero status-${status}`;

  byId("operationsHealthScore").textContent =
    `${formatNumber(overall.healthScore)}%`;

  byId("operationsOverallStatus").textContent =
    status.toUpperCase();

  byId("operationsHealthExplanation").textContent =
    statusMessage(overall);

  byId("operationsFleetHealth").textContent =
    `${formatNumber(overall.fleetHealth)}%`;

  byId("operationsCriticalAlerts").textContent =
    formatNumber(overall.criticalAlerts);

  byId("operationsHighRecommendations").textContent =
    formatNumber(overall.highPriorityRecommendations);

  byId("operationsRunning").textContent =
    formatNumber(overall.runningOperations);
}

function renderInfrastructure(data) {
  const infrastructure = data.infrastructure || {};
  const assets = infrastructure.assets || {};
  const workers = infrastructure.workers || {};
  const pools = infrastructure.pools || {};
  const topology = infrastructure.topology || {};

  byId("operationsInfrastructure").innerHTML = [
    stat("Assets", formatNumber(assets.total)),
    stat("Active Workers", formatNumber(workers.active)),
    stat("Pools Online", `${formatNumber(pools.online)}/${formatNumber(pools.total)}`),
    stat("Topology Edges", formatNumber(topology.edges))
  ].join("");
}

function renderMining(data) {
  const mining = data.mining || {};
  const compute = mining.compute || {};

  byId("operationsMining").innerHTML = [
    stat("Fleet Hashrate", formatHashrate(mining.fleetHashrate)),
    stat("ASIC Workers", formatNumber(compute.asicWorkers)),
    stat("CPU Workers", formatNumber(compute.cpuWorkers)),
    stat("Mining Workloads", formatNumber(compute.miningWorkloads))
  ].join("");
}

function renderAlerts(data) {
  const alerts = data.alerts?.active || [];
  const target = byId("operationsAlerts");

  if (!alerts.length) {
    target.innerHTML = emptyState("No active alerts.");
    return;
  }

  target.innerHTML = alerts.slice(0, 8).map(alert => `
    <div class="operations-list-item">
      <span class="operations-severity ${escapeHtml(
        String(alert.severity || "info").toLowerCase()
      )}">
        ${escapeHtml(alert.severity || "info")}
      </span>

      <div>
        <strong>${escapeHtml(alert.title || "Platform alert")}</strong>
        <p>${escapeHtml(alert.message || "")}</p>
      </div>

      <small>
        ${escapeHtml(formatTime(alert.lastSeenAt || alert.firstSeenAt))}
      </small>
    </div>
  `).join("");
}

function renderRecommendations(data) {
  const recommendations =
    data.recommendations?.highPriority || [];

  const target = byId("operationsRecommendations");

  if (!recommendations.length) {
    target.innerHTML = emptyState(
      "No high-priority recommendations."
    );
    return;
  }

  target.innerHTML = recommendations.slice(0, 8).map(item => `
    <div class="operations-list-item">
      <span class="operations-priority ${escapeHtml(
        String(item.priority || "low").toLowerCase()
      )}">
        ${escapeHtml(item.priority || "low")}
      </span>

      <div>
        <strong>${escapeHtml(item.title || "Recommendation")}</strong>
        <p>${escapeHtml(
          item.recommendedAction || item.explanation || ""
        )}</p>
      </div>

      <small>
        ${Math.round(Number(item.confidence || 0) * 100)}%
      </small>
    </div>
  `).join("");
}

function renderQueue(data) {
  const operations = data.operations || {};
  const queue = operations.queue || {};

  byId("operationsQueueSummary").innerHTML = [
    stat("Approval", formatNumber(queue.pendingApprovalCount)),
    stat("Queued", formatNumber(queue.queuedCount)),
    stat("Running", formatNumber(queue.runningCount)),
    stat("Completed", formatNumber(queue.completedCount)),
    stat("Failed", formatNumber(queue.failedCount))
  ].join("");

  const runs = operations.recentRuns || [];
  const target = byId("operationsRuns");

  if (!runs.length) {
    target.innerHTML = emptyState("No automation runs yet.");
    return;
  }

  target.innerHTML = runs.slice(0, 10).map(run => `
    <div class="operations-list-item operations-run-item" data-operation-run="${escapeHtml(run.runId)}">
      <span class="operations-run-status ${escapeHtml(
        String(run.status || "queued").toLowerCase()
      )}">
        ${escapeHtml(run.status || "queued")}
      </span>

      <div>
        <strong>${escapeHtml(run.actionId || "Automation")}</strong>
        <p>
          ${escapeHtml(run.entityType || "platform")}
          ·
          ${escapeHtml(run.entityId || "primary")}
        </p>
      </div>

      <small>
        ${escapeHtml(formatTime(run.requestedAt))}
      </small>
    </div>
  `).join("");
}

function renderTimeline(data) {
  const entries = data.timeline?.latest || [];
  const target = byId("operationsTimeline");

  if (!entries.length) {
    target.innerHTML = emptyState("No recent timeline activity.");
    return;
  }

  target.innerHTML = entries.slice(0, 12).map(entry => `
    <div class="operations-list-item">
      <span class="operations-timeline-symbol">
        ${escapeHtml(
          String(entry.sourceType || "event")
            .slice(0, 2)
            .toUpperCase()
        )}
      </span>

      <div>
        <strong>${escapeHtml(entry.title || entry.eventType || "Event")}</strong>
        <p>${escapeHtml(entry.message || "")}</p>
      </div>

      <time>
        ${escapeHtml(formatTime(entry.occurredAt))}
      </time>
    </div>
  `).join("");
}

function renderQuickActions(data) {
  const actions = data.quickActions || [];
  const target = byId("operationsQuickActions");

  if (!actions.length) {
    target.innerHTML = emptyState("No quick actions are available.");
    return;
  }

  target.innerHTML = actions.map(action => `
    <div class="operations-action">
      <div>
        <strong>${escapeHtml(action.label || action.actionId)}</strong>
        <small>
          ${escapeHtml(action.riskLevel || "low")} risk
          ${action.requiresApproval ? " · approval required" : ""}
        </small>
      </div>

      <button
        type="button"
        disabled
        title="Execution controls arrive with the Operator Actions package."
      >
        Preview
      </button>
    </div>
  `).join("");
}

function renderOperationsCenter(data) {
  renderHero(data);
  renderInfrastructure(data);
  renderMining(data);
  renderAlerts(data);
  renderRecommendations(data);
  renderQueue(data);
  renderTimeline(data);
  renderQuickActions(data);

  byId("operationsUpdated").textContent =
    `Updated ${formatTime(data.generatedAt)}`;

  byId("operationsLiveDot").className =
    "operations-live-dot online";

  byId("operationsError").hidden = true;
}

async function loadOperationsCenter() {
  try {
    const response = await fetch(
      "/api/platform/operations-center",
      {
        cache: "no-store"
      }
    );

    if (!response.ok) {
      throw new Error(
        `Operations Center API returned ${response.status}`
      );
    }

    const payload = await response.json();

    if (payload.status !== "ok") {
      throw new Error(
        payload.error || "Operations Center data is unavailable."
      );
    }

    renderOperationsCenter(payload);
  } catch (error) {
    byId("operationsLiveDot").className =
      "operations-live-dot error";

    byId("operationsUpdated").textContent =
      "Platform unavailable";

    const target = byId("operationsError");
    target.hidden = false;
    target.textContent = error.message || String(error);
  }
}

function scheduleOperationsRefresh() {
  if (operationsRefreshTimer) {
    window.clearInterval(operationsRefreshTimer);
  }

  operationsRefreshTimer = window.setInterval(
    loadOperationsCenter,
    OPERATIONS_REFRESH_MS
  );
}

document.addEventListener("DOMContentLoaded", () => {
  renderNav("Operations Center");
  loadOperationsCenter();
  scheduleOperationsRefresh();
});

let selectedOperationsAction = null;
let operationsControlMessageTimer = null;

function runControlButtons(run) {
  if (run.status === "pending-approval") {
    return `<div class="operations-run-controls"><button class="approve" data-run-control="approve" data-run-id="${escapeHtml(run.runId)}">Approve</button><button class="reject" data-run-control="reject" data-run-id="${escapeHtml(run.runId)}">Reject</button></div>`;
  }
  if (run.status === "queued") {
    return `<div class="operations-run-controls"><button class="cancel" data-run-control="cancel" data-run-id="${escapeHtml(run.runId)}">Cancel</button></div>`;
  }
  return `<small>${escapeHtml(formatTime(run.completedAt || run.requestedAt))}</small>`;
}

function renderQueue(data) {
  const operations = data.operations || {};
  const queue = operations.queue || {};
  byId("operationsQueueSummary").innerHTML = [
    stat("Approval", formatNumber(queue.pendingApprovalCount)),
    stat("Queued", formatNumber(queue.queuedCount)),
    stat("Running", formatNumber(queue.runningCount)),
    stat("Completed", formatNumber(queue.completedCount)),
    stat("Failed", formatNumber(queue.failedCount))
  ].join("");
  const runs = operations.recentRuns || [];
  const target = byId("operationsRuns");
  if (!runs.length) { target.innerHTML = emptyState("No automation runs yet."); return; }
  target.innerHTML = runs.slice(0, 12).map(run => `
    <div class="operations-list-item">
      <span class="operations-run-status ${escapeHtml(String(run.status || "queued").toLowerCase())}">${escapeHtml(run.status || "queued")}</span>
      <div><strong>${escapeHtml(run.actionId || "Automation")}</strong><p>${escapeHtml(run.entityType || "platform")} · ${escapeHtml(run.entityId || "primary")} ${run.dryRun ? " · dry run" : " · live"}</p></div>
      ${runControlButtons(run)}
    </div>`).join("");
}

function renderQuickActions(data) {
  const actions = data.quickActions || [];
  const target = byId("operationsQuickActions");
  if (!actions.length) { target.innerHTML = emptyState("No quick actions are available."); return; }
  target.innerHTML = actions.map(action => `
    <div class="operations-action"><div><strong>${escapeHtml(action.label || action.actionId)}</strong><small>${escapeHtml(action.riskLevel || "low")} risk${action.requiresApproval ? " · approval required" : ""}</small></div><button type="button" data-action-request="${escapeHtml(action.actionId)}">Run</button></div>`).join("");
}

function showControlMessage(message) {
  const target = byId("operationsControlMessage");
  target.textContent = message;
  target.hidden = false;
  if (operationsControlMessageTimer) window.clearTimeout(operationsControlMessageTimer);
  operationsControlMessageTimer = window.setTimeout(() => { target.hidden = true; }, 6000);
}

function openActionModal(action) {
  selectedOperationsAction = action;
  byId("operationsActionTitle").textContent = action.label || action.actionId;
  byId("operationsActionDescription").textContent = action.description || "Request this Platform action.";
  byId("operationsActionEntityType").value = action.entityType || "platform";
  byId("operationsActionEntityId").value = action.entityId || "primary";
  byId("operationsActionDryRun").checked = true;
  byId("operationsActionDryRun").disabled = action.supportsDryRun === false;
  byId("operationsActionWarning").textContent = action.requiresApproval ? "Live execution requires operator approval. Dry runs queue immediately." : "Dry run is selected by default.";
  byId("operationsActionModal").hidden = false;
}

function closeActionModal() { byId("operationsActionModal").hidden = true; selectedOperationsAction = null; }

async function postAutomation(path, body) {
  const response = await fetch(path, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
  const payload = await response.json();
  if (!response.ok || payload.status === "error") throw new Error(payload.error || `Request failed: ${response.status}`);
  return payload;
}

async function requestSelectedAction() {
  if (!selectedOperationsAction) return;
  const payload = await postAutomation("/api/platform/automation/request", {
    actionId: selectedOperationsAction.actionId,
    entityType: byId("operationsActionEntityType").value.trim(),
    entityId: byId("operationsActionEntityId").value.trim(),
    requestedBy: byId("operationsActionRequestedBy").value.trim() || "operator",
    dryRun: byId("operationsActionDryRun").checked,
    inputPayload: {}
  });
  closeActionModal();
  showControlMessage(`${payload.run.actionId} requested: ${payload.run.status}.`);
  await postAutomation("/api/platform/automation/process", {limit: 25});
  await loadOperationsCenter();
}

async function controlRun(action, runId) {
  let message = "";
  if (action === "approve") { message = window.prompt("Approval note (optional):", "Approved from Operations Center"); if (message === null) return; }
  if (action === "reject") { message = window.prompt("Reason for rejection:", "Rejected by operator"); if (message === null) return; }
  if (action === "cancel") { if (!window.confirm("Cancel this queued automation run?")) return; message = "Cancelled by operator"; }
  const actorFields = {approve: "approvedBy", reject: "rejectedBy", cancel: "cancelledBy"};
  await postAutomation(`/api/platform/automation/${action}`, {runId, [actorFields[action]]: "operator", message});
  if (action === "approve") await postAutomation("/api/platform/automation/process", {limit: 25});
  showControlMessage(`Run ${runId} ${action}d.`);
  await loadOperationsCenter();
}


function closeOperationsConsole() {
  byId("operationsConsoleDrawer").hidden = true;
  operationsConsoleRunId = null;
  operationsConsoleLastEventId = 0;
  if (operationsConsoleTimer) window.clearTimeout(operationsConsoleTimer);
}

function consoleEventHtml(event) {
  return `<div class="operations-console-event ${escapeHtml(event.level || "info")}">
    <time>${escapeHtml(new Date(event.occurredAt).toLocaleTimeString())}</time>
    <span>${escapeHtml(event.stage || event.eventType)}</span>
    <p>${escapeHtml(event.message || "")}</p>
  </div>`;
}

async function pollOperationsConsole() {
  if (!operationsConsoleRunId) return;
  try {
    const response = await fetch(`/api/platform/operation-session?runId=${encodeURIComponent(operationsConsoleRunId)}&afterEventId=${operationsConsoleLastEventId}`, {cache: "no-store"});
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Unable to load operation session");
    const session = payload.session;
    byId("operationsConsoleTitle").textContent = `${session.actionId} · ${session.entityId}`;
    byId("operationsConsoleStatus").textContent = session.status;
    byId("operationsConsoleStatus").className = `operations-run-status ${session.status}`;
    byId("operationsConsolePercent").textContent = `${session.progressPercent}%`;
    byId("operationsConsoleProgress").style.width = `${session.progressPercent}%`;
    byId("operationsConsoleSummary").textContent = session.summary || session.currentStage;
    if (payload.events.length) {
      byId("operationsConsoleTimeline").insertAdjacentHTML("beforeend", payload.events.map(consoleEventHtml).join(""));
      operationsConsoleLastEventId = payload.lastEventId;
      byId("operationsConsoleTimeline").scrollTop = byId("operationsConsoleTimeline").scrollHeight;
    }
    byId("operationsConsoleJson").textContent = JSON.stringify(payload, null, 2);
    if (!["completed", "failed", "cancelled", "rejected"].includes(session.status)) {
      operationsConsoleTimer = window.setTimeout(pollOperationsConsole, 1200);
    }
  } catch (error) {
    byId("operationsConsoleSummary").textContent = error.message;
  }
}

function openOperationsConsole(runId) {
  operationsConsoleRunId = runId;
  operationsConsoleLastEventId = 0;
  byId("operationsConsoleTimeline").innerHTML = "";
  byId("operationsConsoleJson").textContent = "";
  byId("operationsConsoleDrawer").hidden = false;
  pollOperationsConsole();
}

document.addEventListener("click", event => {
  const runItem = event.target.closest("[data-operation-run]");
  if (runItem && !event.target.closest("button")) { openOperationsConsole(runItem.dataset.operationRun); return; }
  const tabButton = event.target.closest("[data-console-tab]");
  if (tabButton) {
    document.querySelectorAll("[data-console-tab]").forEach(button => button.classList.toggle("active", button === tabButton));
    byId("operationsConsoleTimeline").hidden = tabButton.dataset.consoleTab !== "timeline";
    byId("operationsConsoleJson").hidden = tabButton.dataset.consoleTab !== "json";
    return;
  }
  const requestButton = event.target.closest("[data-action-request]");
  if (requestButton) {
    fetch("/api/platform/operations-center", {cache: "no-store"}).then(r => r.json()).then(data => {
      const action = (data.quickActions || []).find(item => item.actionId === requestButton.dataset.actionRequest);
      if (action) openActionModal(action);
    }).catch(error => showControlMessage(error.message));
    return;
  }
  const controlButton = event.target.closest("[data-run-control]");
  if (controlButton) controlRun(controlButton.dataset.runControl, controlButton.dataset.runId).catch(error => showControlMessage(error.message));
});

document.addEventListener("DOMContentLoaded", () => {
  byId("operationsActionClose").addEventListener("click", closeActionModal);
  byId("operationsConsoleClose").addEventListener("click", closeOperationsConsole);
  byId("operationsActionSubmit").addEventListener("click", () => requestSelectedAction().catch(error => showControlMessage(error.message)));
});
