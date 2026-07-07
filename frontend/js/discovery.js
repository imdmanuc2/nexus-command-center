let latestSystems = [];
let latestFound = [];
let activeFilter = "all";
let searchQuery = "";

function byId(id) {
  return document.getElementById(id);
}

function safe(value, fallback = "Unknown") {
  return value === undefined || value === null || value === "" ? fallback : value;
}

function closeDrawer() {
  byId("drawer")?.classList.remove("open");
  byId("drawerBackdrop")?.classList.remove("open");
}

function systemText(system) {
  return [
    system.ip,
    system.primaryRole,
    system.profile?.hostname,
    system.profile?.assetType,
    system.asset?.name,
    system.asset?.purpose,
    ...(system.roles || []).map(r => r.label),
    ...(system.fingerprints || []).map(f => `${f.label} ${f.endpoint}`),
    ...latestFound.filter(f => f.ip === system.ip).map(f => `${f.service} ${f.port}`)
  ].join(" ").toLowerCase();
}

function matchesFilter(system) {
  const text = systemText(system);

  if (activeFilter === "all") return true;
  if (activeFilter === "mining") return text.includes("mining") || text.includes("stratum") || text.includes("pool");
  if (activeFilter === "node") return text.includes("node") || text.includes("blockchain");
  if (activeFilter === "dashboard") return text.includes("dashboard") || text.includes("web interface");
  if (activeFilter === "healthy") return system.health?.level === "healthy";

  return true;
}

function filteredSystems() {
  return latestSystems.filter(system => {
    const q = searchQuery.trim().toLowerCase();
    return (!q || systemText(system).includes(q)) && matchesFilter(system);
  });
}

function renderSummary(discovery) {
  const summary = discovery.summary || {};
  const healthy = latestSystems.filter(s => s.health?.level === "healthy").length;

  byId("discoverySummary").innerHTML = `
    <div class="asset-summary-card"><span>Targets</span><strong>${(discovery.targets || []).length}</strong></div>
    <div class="asset-summary-card"><span>Systems</span><strong>${latestSystems.length}</strong></div>
    <div class="asset-summary-card"><span>Healthy</span><strong>${healthy}</strong></div>
    <div class="asset-summary-card"><span>Mining Backends</span><strong>${summary.miningBackends || 0}</strong></div>
    <div class="asset-summary-card"><span>Nodes</span><strong>${summary.blockchainNodes || 0}</strong></div>
  `;
}

function rolePills(system) {
  return (system.roles || []).map(role =>
    `<span class="discovery-pill">${role.label} ${role.confidence}%</span>`
  ).join("");
}

function renderSystems() {
  const systems = filteredSystems();

  byId("discoveryList").innerHTML = systems.map(system => {
    const services = latestFound.filter(f => f.ip === system.ip);

    return `
      <div class="discovery-card" data-ip="${system.ip}">
        <div class="discovery-card-head">
          <div>
            <h2>${safe(system.asset?.name, system.ip)}</h2>
            <p>${safe(system.primaryRole)}</p>
          </div>
          <span class="asset-profile-status">${safe(system.health?.label, "Unknown")}</span>
        </div>

        <div class="pool-stats">
          <div><b>IP</b><span>${system.ip}</span></div>
          <div><b>Services</b><span>${services.length}</span></div>
          <div><b>Health</b><span class="good">${safe(system.health?.score, 0)}%</span></div>
        </div>

        <div class="discovery-pills">
          ${rolePills(system)}
        </div>

        <small>${services.map(s => `${s.service}:${s.port}`).join(" · ")}</small>
      </div>
    `;
  }).join("") || `
    <div class="empty-state">
      <h2>No discovery results match.</h2>
      <p>Try clearing search or changing the filter.</p>
    </div>
  `;

  document.querySelectorAll(".discovery-card").forEach(card => {
    card.addEventListener("click", () => {
      const system = latestSystems.find(s => s.ip === card.dataset.ip);
      if (system) openDrawer(system);
    });
  });
}

function openDrawer(system) {
  const services = latestFound.filter(f => f.ip === system.ip);

  byId("drawerContent").innerHTML = `
    <div class="asset-profile-head">
      <div>
        <h2>${safe(system.asset?.name, system.ip)}</h2>
        <p class="drawer-subtitle">${safe(system.primaryRole)}</p>
      </div>
      <span class="asset-profile-status">${safe(system.health?.label, "Unknown")}</span>
    </div>

    <div class="asset-drawer-section">
      <h3>System</h3>
      <div class="asset-detail-grid">
        <div class="asset-detail-field"><label>IP Address</label><strong>${system.ip}</strong></div>
        <div class="asset-detail-field"><label>Hostname</label><strong>${safe(system.profile?.hostname, "Not resolved")}</strong></div>
        <div class="asset-detail-field"><label>Asset Type</label><strong>${safe(system.profile?.assetType)}</strong></div>
        <div class="asset-detail-field"><label>Nexus Agent</label><strong>${safe(system.profile?.agent, "Not installed")}</strong></div>
      </div>
    </div>

    <div class="asset-drawer-section">
      <h3>Health Checks</h3>
      <ul class="service-list">
        ${(system.health?.checks || []).map(c => `<li><span>${c.name}</span><b>${c.status}</b></li>`).join("") || "<li>No health checks.</li>"}
      </ul>
    </div>

    <div class="asset-drawer-section">
      <h3>Fingerprints</h3>
      <ul class="service-list">
        ${(system.fingerprints || []).map(f => `<li><span>${f.label}</span><b>${f.confidence}%</b></li>`).join("") || "<li>No fingerprints.</li>"}
      </ul>
    </div>

    <div class="asset-drawer-section">
      <h3>Open Services</h3>
      <ul class="service-list">
        ${services.map(s => `<li><span>${s.service}</span><b>:${s.port}</b></li>`).join("") || "<li>No services discovered.</li>"}
      </ul>
    </div>
  `;

  byId("drawer")?.classList.add("open");
  byId("drawerBackdrop")?.classList.add("open");
}

async function loadDiscovery() {
  byId("discoveryStatus").textContent = "Scanning";

  try {
    const res = await fetch("/api/discovery/scan");
    const data = await res.json();
    const discovery = data.discovery || data;

    latestSystems = discovery.systems || [];
    latestFound = discovery.found || [];

    renderSummary(discovery);
    renderSystems();

    byId("discoveryStatus").textContent = "Live";
  } catch (err) {
    byId("discoveryList").innerHTML = `<div class="empty-state"><h2>Discovery failed.</h2><p>${err.message}</p></div>`;
    byId("discoveryStatus").textContent = "Error";
  }
}

window.addEventListener("DOMContentLoaded", () => {
  byId("drawerClose")?.addEventListener("click", closeDrawer);
  byId("drawerBackdrop")?.addEventListener("click", closeDrawer);
  byId("runScan")?.addEventListener("click", loadDiscovery);

  byId("discoverySearch")?.addEventListener("input", event => {
    searchQuery = event.target.value;
    renderSystems();
  });

  document.querySelectorAll(".asset-filter").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".asset-filter").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      activeFilter = btn.dataset.filter;
      renderSystems();
    });
  });

  loadDiscovery();
});
