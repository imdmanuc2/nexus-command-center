let latestPools = [];
let latestWorkers = [];
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

async function fetchJson(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path} returned ${res.status}`);
  return await res.json();
}

function normalizeWorkers(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload.workers)) return payload.workers;
  return [];
}

function formatHashrate(value) {
  const n = Number(value || 0);
  if (n >= 1e15) return `${(n / 1e15).toFixed(2)} PH/s`;
  if (n >= 1e12) return `${(n / 1e12).toFixed(2)} TH/s`;
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)} GH/s`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)} MH/s`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(2)} KH/s`;
  return `${n.toFixed(0)} H/s`;
}

function poolKey(pool) {
  return `${pool.id}@${pool.host}`;
}

function workersForPool(pool) {
  return latestWorkers.filter(w => {
    const workerPool = `${w.poolId || ""}`.toLowerCase();
    const workerHost = `${w.poolHost || w.host || ""}`;
    return workerPool === `${pool.id}`.toLowerCase() && workerHost === `${pool.host}`;
  });
}

function poolText(pool) {
  return [
    pool.id,
    pool.name,
    pool.mode,
    pool.visibility,
    pool.host,
    pool.apiBase,
    pool.endpoint,
    pool.address,
    pool.payoutScheme,
    pool.coin?.symbol,
    pool.coin?.name,
    ...(pool.stratumPorts || [])
  ].join(" ").toLowerCase();
}

function matchesFilter(pool) {
  if (activeFilter === "all") return true;
  if (activeFilter === "online") return true;
  if (activeFilter === "private") return pool.visibility === "private";
  return pool.mode === activeFilter || pool.visibility === activeFilter;
}

function filteredPools() {
  return latestPools.filter(pool => {
    const q = searchQuery.trim().toLowerCase();
    return (!q || poolText(pool).includes(q)) && matchesFilter(pool);
  });
}

function renderSummary() {
  const solo = latestPools.filter(p => p.mode === "solo").length;
  const pub = latestPools.filter(p => p.visibility === "public").length;
  const priv = latestPools.filter(p => p.visibility === "private").length;
  const miners = latestWorkers.length;

  byId("poolSummary").innerHTML = `
    <div class="asset-summary-card"><span>Total Pools</span><strong>${latestPools.length}</strong></div>
    <div class="asset-summary-card"><span>Solo</span><strong>${solo}</strong></div>
    <div class="asset-summary-card"><span>Public</span><strong>${pub}</strong></div>
    <div class="asset-summary-card"><span>Private</span><strong>${priv}</strong></div>
    <div class="asset-summary-card"><span>Live Miners</span><strong>${miners}</strong></div>
  `;
}

function renderPools() {
  const pools = filteredPools();

  byId("poolList").innerHTML = pools.map((pool, index) => {
    const workers = workersForPool(pool);
    const hashrate = workers.reduce((sum, w) => sum + Number(w.hashrate || 0), 0) || pool.stats?.poolHashrate || 0;
    const coin = pool.coin?.symbol || pool.id || "POOL";

    return `
      <div class="pool-management-card" data-key="${poolKey(pool)}">
        <div class="pool-card-top">
          <span class="coin-badge">${coin}</span>
          <span class="pool-type ${pool.mode === "solo" ? "solo" : "public"}">${safe(pool.mode, "unknown").toUpperCase()}</span>
        </div>

        <h2>${safe(pool.name, `${coin} Pool`)}</h2>
        <p>${safe(pool.coin?.name, "Unknown coin")} · ${safe(pool.coin?.algorithm, "Unknown algorithm")}</p>

        <div class="pool-stats">
          <div><b>Status</b><span class="good">ONLINE</span></div>
          <div><b>Host</b><span>${safe(pool.host)}</span></div>
          <div><b>Miners</b><span>${workers.length || pool.stats?.connectedMiners || 0}</span></div>
        </div>

        <div class="pool-stats">
          <div><b>Hashrate</b><span>${formatHashrate(hashrate)}</span></div>
          <div><b>Stratum</b><span>${(pool.stratumPorts || []).join(", ") || "Pending"}</span></div>
          <div><b>Fee</b><span>${safe(pool.poolFeePercent, 0)}%</span></div>
        </div>

        <div class="pool-actions">
          <button class="btn" data-action="details" data-key="${poolKey(pool)}">Details</button>
          <button class="btn" data-action="workers" data-key="${poolKey(pool)}">Workers</button>
          <button class="btn danger" data-action="disabled" data-key="${poolKey(pool)}">Disable Later</button>
        </div>
      </div>
    `;
  }).join("") || `
    <div class="empty-state">
      <h2>No pools match.</h2>
      <p>Try clearing search or changing the filter.</p>
    </div>
  `;

  document.querySelectorAll("[data-action='details'], [data-action='workers']").forEach(btn => {
    btn.addEventListener("click", event => {
      event.stopPropagation();
      const pool = latestPools.find(p => poolKey(p) === btn.dataset.key);
      if (pool) openPoolDrawer(pool);
    });
  });

  document.querySelectorAll(".pool-management-card").forEach(card => {
    card.addEventListener("click", () => {
      const pool = latestPools.find(p => poolKey(p) === card.dataset.key);
      if (pool) openPoolDrawer(pool);
    });
  });
}

function openPoolDrawer(pool) {
  const workers = workersForPool(pool);
  const coin = pool.coin?.symbol || pool.id || "POOL";

  byId("drawerContent").innerHTML = `
    <div class="asset-profile-head">
      <div>
        <h2>${safe(pool.name, `${coin} Pool`)}</h2>
        <p class="drawer-subtitle">${safe(pool.visibility).toUpperCase()} · ${safe(pool.mode).toUpperCase()}</p>
      </div>
      <span class="asset-profile-status">ONLINE</span>
    </div>

    <div class="asset-drawer-section">
      <h3>Pool Identity</h3>
      <div class="asset-detail-grid">
        <div class="asset-detail-field"><label>Pool Key</label><strong>${poolKey(pool)}</strong></div>
        <div class="asset-detail-field"><label>Coin</label><strong>${coin}</strong></div>
        <div class="asset-detail-field"><label>Coin Name</label><strong>${safe(pool.coin?.name)}</strong></div>
        <div class="asset-detail-field"><label>Algorithm</label><strong>${safe(pool.coin?.algorithm)}</strong></div>
      </div>
    </div>

    <div class="asset-drawer-section">
      <h3>Hosting</h3>
      <div class="asset-detail-grid">
        <div class="asset-detail-field"><label>Host</label><strong>${safe(pool.host)}</strong></div>
        <div class="asset-detail-field"><label>API Base</label><strong>${safe(pool.apiBase)}</strong></div>
        <div class="asset-detail-field"><label>Endpoint</label><strong>${safe(pool.endpoint)}</strong></div>
        <div class="asset-detail-field"><label>Stratum Ports</label><strong>${(pool.stratumPorts || []).join(", ") || "Pending"}</strong></div>
      </div>
    </div>

    <div class="asset-drawer-section">
      <h3>Mining</h3>
      <div class="asset-detail-grid">
        <div class="asset-detail-field"><label>Payout Scheme</label><strong>${safe(pool.payoutScheme)}</strong></div>
        <div class="asset-detail-field"><label>Pool Fee</label><strong>${safe(pool.poolFeePercent, 0)}%</strong></div>
        <div class="asset-detail-field"><label>Connected Miners</label><strong>${workers.length || pool.stats?.connectedMiners || 0}</strong></div>
        <div class="asset-detail-field"><label>Pool Hashrate</label><strong>${formatHashrate(pool.stats?.poolHashrate)}</strong></div>
      </div>
    </div>

    <div class="asset-drawer-section">
      <h3>Wallet</h3>
      <p class="pool-wallet">${safe(pool.address, "No wallet address found")}</p>
    </div>

    <div class="asset-drawer-section">
      <h3>Connected Workers</h3>
      <ul class="service-list">
        ${
          workers.map(w => `
            <li>
              <span>${safe(w.displayName || w.assetName || w.name)}</span>
              <b>${formatHashrate(w.hashrate)}</b>
            </li>
          `).join("") || "<li>No live workers connected.</li>"
        }
      </ul>
    </div>

    <div class="asset-drawer-section">
      <h3>Lifecycle Actions</h3>
      <div class="drawer-actions">
        <button class="btn">Validate</button>
        <button class="btn">View Config</button>
        <button class="btn">View Logs</button>
        <button class="btn danger">Disable Later</button>
      </div>
    </div>
  `;

  byId("drawer")?.classList.add("open");
  byId("drawerBackdrop")?.classList.add("open");
}

async function loadPools() {
  try {
    byId("poolStatus").textContent = "Refreshing";

    const [topology, workers] = await Promise.all([
      fetchJson("/api/discovery/topology"),
      fetchJson("/api/mining/workers")
    ]);

    latestPools = topology.topology?.pools || [];
    latestWorkers = normalizeWorkers(workers);

    renderSummary();
    renderPools();

    byId("poolStatus").textContent = "Live";
  } catch (err) {
    byId("poolList").innerHTML = `<div class="empty-state"><h2>Pools failed to load.</h2><p>${err.message}</p></div>`;
    byId("poolStatus").textContent = "Error";
  }
}

window.addEventListener("DOMContentLoaded", () => {
  byId("drawerClose")?.addEventListener("click", closeDrawer);
  byId("drawerBackdrop")?.addEventListener("click", closeDrawer);

  byId("poolSearch")?.addEventListener("input", event => {
    searchQuery = event.target.value;
    renderPools();
  });

  document.querySelectorAll(".asset-filter").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".asset-filter").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      activeFilter = btn.dataset.filter;
      renderPools();
    });
  });

  loadPools();
  setInterval(loadPools, 15000);
});
