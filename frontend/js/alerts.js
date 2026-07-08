let alertFilter = "all";
let alertEvents = [];

function byId(id) {
  return document.getElementById(id);
}

function formatAlertTime(value) {
  try {
    return new Date(value).toLocaleString("en-US", {
      month: "2-digit",
      day: "2-digit",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
      second: "2-digit",
      hour12: true
    });
  } catch {
    return value || "";
  }
}

function severityIcon(severity) {
  if (severity === "critical") return "🚨";
  if (severity === "warning") return "⚠";
  if (severity === "success") return "✓";
  return "ℹ";
}

function renderAlertSummary() {
  const total = alertEvents.length;
  const critical = alertEvents.filter(e => e.severity === "critical").length;
  const warnings = alertEvents.filter(e => e.severity === "warning").length;
  const latest = alertEvents.at(-1);

  byId("alertTotal").textContent = total;
  byId("alertCritical").textContent = critical;
  byId("alertWarnings").textContent = warnings;
  byId("alertLatest").textContent = latest ? formatAlertTime(latest.time).split(", ")[1] : "—";
}

function renderAlerts() {
  const list = byId("alertList");

  const filtered = alertEvents
    .slice()
    .reverse()
    .filter(e => alertFilter === "all" || e.severity === alertFilter);

  list.innerHTML = filtered.map((e, index) => `
    <button class="alert-row ${e.severity || "info"}" data-index="${alertEvents.indexOf(e)}">
      <span class="alert-icon">${severityIcon(e.severity)}</span>
      <span>
        <strong>${e.message || "Event"}</strong>
        <small>${formatAlertTime(e.time)} • ${e.type || "event"}${e.assetName ? ` • ${e.assetName}` : ""}${e.workerId ? ` / Worker ${e.workerId}` : ""}</small>
      </span>
    </button>
  `).join("") || `<div class="empty-state">No matching events.</div>`;

  list.querySelectorAll(".alert-row").forEach(row => {
    row.addEventListener("click", () => {
      const event = alertEvents[Number(row.dataset.index)];
      renderAlertDetail(event);
    });
  });
}

function renderAlertDetail(e) {
  if (!e) return;

  byId("alertDetail").innerHTML = `
    <div class="alert-detail-card ${e.severity || "info"}">
      <h3>${severityIcon(e.severity)} ${e.message || "Event"}</h3>
      <div class="asset-detail-grid">
        <div class="asset-detail-field"><label>Severity</label><strong>${(e.severity || "info").toUpperCase()}</strong></div>
        <div class="asset-detail-field"><label>Type</label><strong>${e.type || "event"}</strong></div>
        <div class="asset-detail-field"><label>Time</label><strong>${formatAlertTime(e.time)}</strong></div>
        <div class="asset-detail-field"><label>Miner</label><strong>${e.assetName || "Not set"}</strong></div>
        <div class="asset-detail-field"><label>Worker</label><strong>${e.workerId || "Not set"}</strong></div>
        <div class="asset-detail-field"><label>Pool</label><strong>${e.poolGroup || e.poolId || "Not set"}</strong></div>
        <div class="asset-detail-field"><label>Hashrate</label><strong>${e.hashrate ? Number(e.hashrate / 1e12).toFixed(2) + " TH/s" : "Not set"}</strong></div>
      </div>
      <pre>${JSON.stringify(e, null, 2)}</pre>
    </div>
  `;
}

async function loadAlerts() {
  const res = await fetch("/api/events/live");
  if (!res.ok) return;

  alertEvents = await res.json();
  renderAlertSummary();
  renderAlerts();
}

window.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".alert-filter").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".alert-filter").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      alertFilter = btn.dataset.severity;
      renderAlerts();
    });
  });

  byId("refreshAlerts")?.addEventListener("click", loadAlerts);

  loadAlerts();
  setInterval(loadAlerts, 3000);
});
