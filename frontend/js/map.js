let latestTopology = {};
let latestSystems = [];
let latestFound = [];
let latestWorkers = [];
let latestMiningSummary = {};

const PREVIEW_MINERS = 5;

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
  if (Array.isArray(payload.miners)) return payload.miners;
  return [];
}

function rawHashrate(worker) {
  return Number(worker.hashrate || worker.hashRate || worker.currentHashrate || 0);
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

function minerSystems() {
  return latestSystems
    .filter(system => {
      const name = `${system.asset?.name || ""}`.toLowerCase();
      const purpose = `${system.asset?.purpose || ""}`.toLowerCase();
      return name.includes("nano") || name.includes("asic") || name.includes("miner") || name.includes("mining system") || purpose.includes("mining");
    })
    .sort((a, b) => String(a.ip).localeCompare(String(b.ip), undefined, { numeric: true }));
}

function workerName(worker, index) {
  if (worker.friendlyName || worker.customName || worker.alias || worker.assetName) {
    return worker.friendlyName || worker.customName || worker.alias || worker.assetName;
  }

  const rawName = String(worker.name || worker.worker || worker.workerName || "").trim();
  const suffixNumber = Number(rawName);
  const systems = minerSystems();

  if (systems.length && suffixNumber > 0) {
    const matched = systems[suffixNumber - 1];
    if (matched?.asset?.name) return matched.asset.name;
  }

  return safe(worker.displayName || rawName, `Miner ${index + 1}`);
}

function workerFullName(worker) {
  return safe(worker.fullName || worker.address || worker.username || worker.login, "worker");
}

function workerShares(worker) {
  return Number(worker.sharesPerSecond || worker.shares_per_second || 0).toFixed(3);
}

function workerStatus(worker) {
  const text = `${worker.status || worker.state || ""}`.toLowerCase();
  if (worker.online === false || text.includes("offline") || text.includes("dead")) return "offline";
  return "online";
}

function sortedWorkers(workers) {
  return [...workers].sort((a, b) => rawHashrate(b) - rawHashrate(a));
}

function liveWorkerHost() {
  return (
    latestMiningSummary.host ||
    latestMiningSummary.serverIp ||
    latestMiningSummary.poolHost ||
    latestMiningSummary.apiHost ||
    "192.168.1.154"
  );
}

function poolWorkers(pool) {
  const poolId = `${pool.id || ""}`.toLowerCase();
  const coin = `${pool.coin?.symbol || ""}`.toLowerCase();

  // Workers endpoint currently does not include host.
  // Until backend adds worker.host, only attach workers to the live MiningCore host.
  if (`${pool.host}` !== `${liveWorkerHost()}`) {
    return [];
  }

  return latestWorkers.filter(worker => {
    const workerPool = `${worker.poolId || worker.pool || worker.coin || latestMiningSummary.poolId || ""}`.toLowerCase();
    if (!workerPool) return true;
    return workerPool.includes(poolId) || workerPool.includes(coin) || poolId.includes(workerPool);
  });
}

function renderMinerRow(worker, index, maxHashrate) {
  const pct = Math.max(4, Math.round((rawHashrate(worker) / maxHashrate) * 100));
  const status = workerStatus(worker);

  return `
    <button class="miner-live-row ${status}" data-kind="miner" data-worker-index="${latestWorkers.indexOf(worker)}">
      <div class="miner-live-name">
        <strong>${workerName(worker, index)}</strong>
        <span>${workerFullName(worker)}</span>
      </div>

      <div class="miner-live-stat">
        <b>${formatHashrate(rawHashrate(worker))}</b>
        <span>Hashrate</span>
      </div>

      <div class="miner-live-stat">
        <b>#${index + 1}</b>
        <span>Rank</span>
      </div>

      <div class="miner-live-stat">
        <b>${workerShares(worker)}</b>
        <span>Shares/sec</span>
      </div>

      <div class="miner-live-health">
        <span>${status.toUpperCase()}</span>
        <div class="miner-health-track">
          <div class="miner-health-bar" style="width:${pct}%"></div>
        </div>
      </div>
    </button>
  `;
}

function renderMinerPreview(workers, poolIndex, poolColumn) {
  if (!workers.length) {
    return `<div class="no-miners">No live miners reported by this pool.</div>`;
  }

  const sorted = sortedWorkers(workers);
  const maxHashrate = Math.max(...sorted.map(rawHashrate), 1);
  const preview = sorted.slice(0, PREVIEW_MINERS);

  return `
    <div class="miner-preview-head">
      <strong>Top ${Math.min(PREVIEW_MINERS, sorted.length)} Miners</strong>
      <button class="mini-btn"
              data-kind="pool-miners"
              data-pool-column="${poolColumn}"
              data-pool-index="${poolIndex}">
        View All ${sorted.length}
      </button>
    </div>
    ${preview.map((worker, index) => renderMinerRow(worker, index, maxHashrate)).join("")}
  `;
}

function renderPoolCard(pool, index, column) {
  const workers = poolWorkers(pool);
  const onlineWorkers = workers.filter(w => workerStatus(w) === "online").length;
  const totalHashrate = workers.reduce((sum, w) => sum + rawHashrate(w), 0);
  const mode = pool.mode || "unknown";
  const coin = pool.coin?.symbol || pool.id || "POOL";

  return `
    <div class="pool-card topology-pool-card clickable"
         data-kind="pool"
         data-pool-column="${column}"
         data-pool-index="${index}">
      <div class="pool-card-top">
        <span class="coin-badge">${coin}</span>
        <span class="pool-type ${mode === "solo" ? "solo" : "public"}">${mode.toUpperCase()}</span>
      </div>

      <strong>${safe(pool.name, `${coin} Pool`)}</strong>
      <small>${safe(pool.endpoint || pool.apiBase, "MiningCore API")}</small>

      <div class="pool-stats">
        <div><b>Status</b><span class="good">ONLINE</span></div>
        <div><b>Miners</b><span>${workers.length || pool.stats?.connectedMiners || 0}</span></div>
        <div><b>Hashrate</b><span>${formatHashrate(totalHashrate || pool.stats?.poolHashrate)}</span></div>
      </div>

      <div class="pool-stats">
        <div><b>Host</b><span>${safe(pool.host)}</span></div>
        <div><b>Stratum</b><span>${(pool.stratumPorts || []).join(", ") || "Pending"}</span></div>
        <div><b>Blocks</b><span>${safe(pool.stats?.totalBlocks, 0)}</span></div>
      </div>

      <div class="miner-row">
        ${renderMinerPreview(workers, index, column)}
      </div>
    </div>
  `;
}

function renderPoolColumn(title, subtitle, pools, column) {
  return `
    <div class="topology-column ${column}">
      <div class="topology-column-head">
        <h2>${title}</h2>
        <span>${subtitle}</span>
      </div>

      <div class="topology-pool-list">
        ${
          pools.length
            ? pools.map((pool, index) => renderPoolCard(pool, index, column)).join("")
            : `<div class="empty-pool">No ${title.toLowerCase()} discovered yet.</div>`
        }
      </div>
    </div>
  `;
}

function openPoolDrawer(pool) {
  const workers = sortedWorkers(poolWorkers(pool));
  const maxHashrate = Math.max(...workers.map(rawHashrate), 1);
  const mode = pool.mode || "unknown";
  const coin = pool.coin?.symbol || pool.id || "POOL";

  byId("drawerContent").innerHTML = `
    <h2>${safe(pool.name, `${coin} Pool`)}</h2>
    <p class="drawer-subtitle">${mode.toUpperCase()} pool on ${safe(pool.host)}</p>

    <div class="drawer-section"><label>Mode</label><strong>${mode.toUpperCase()}</strong></div>
    <div class="drawer-section"><label>Coin</label><strong>${coin}</strong></div>
    <div class="drawer-section"><label>Host</label><strong>${safe(pool.host)}</strong></div>
    <div class="drawer-section"><label>API</label><strong>${safe(pool.endpoint || pool.apiBase)}</strong></div>
    <div class="drawer-section"><label>Stratum Ports</label><strong>${(pool.stratumPorts || []).join(", ") || "Pending"}</strong></div>
    <div class="drawer-section"><label>Payout</label><strong>${safe(pool.payoutScheme)}</strong></div>
    <div class="drawer-section"><label>Pool Hashrate</label><strong>${formatHashrate(pool.stats?.poolHashrate)}</strong></div>
    <div class="drawer-section"><label>Connected Miners</label><strong>${workers.length || pool.stats?.connectedMiners || 0}</strong></div>

    <div class="drawer-section">
      <label>Miner List</label>
      <input id="minerSearch" class="miner-search" placeholder="Search miners..." autocomplete="off">
      <div id="drawerMinerList" class="drawer-miner-list">
        ${workers.map((worker, index) => renderMinerRow(worker, index, maxHashrate)).join("") || "<div class='no-miners'>No miners found.</div>"}
      </div>
    </div>
  `;

  byId("drawer")?.classList.add("open");
  byId("drawerBackdrop")?.classList.add("open");

  const input = byId("minerSearch");
  input?.addEventListener("input", () => {
    const q = input.value.toLowerCase();
    const filtered = workers.filter(w =>
      `${workerName(w, 0)} ${workerFullName(w)}`.toLowerCase().includes(q)
    );

    byId("drawerMinerList").innerHTML =
      filtered.map((worker, index) => renderMinerRow(worker, index, maxHashrate)).join("") ||
      "<div class='no-miners'>No miners match that search.</div>";

    bindMinerClicks();
  });

  bindMinerClicks();
}

function openMinerDrawer(workerIndex) {
  const worker = latestWorkers[Number(workerIndex)] || {};
  const status = workerStatus(worker);

  byId("drawerContent").innerHTML = `
    <h2>${workerName(worker, Number(workerIndex))}</h2>
    <p class="drawer-subtitle">Live MiningCore worker</p>

    <div class="drawer-section"><label>Status</label><strong class="${status === "online" ? "good" : ""}">${status.toUpperCase()}</strong></div>
    <div class="drawer-section"><label>Hashrate</label><strong>${formatHashrate(rawHashrate(worker))}</strong></div>
    <div class="drawer-section"><label>Shares/sec</label><strong>${workerShares(worker)}</strong></div>
    <div class="drawer-section"><label>Full Worker Name</label><strong>${workerFullName(worker)}</strong></div>
    <div class="drawer-section"><label>Raw Worker JSON</label><pre>${JSON.stringify(worker, null, 2)}</pre></div>
  `;

  byId("drawer")?.classList.add("open");
  byId("drawerBackdrop")?.classList.add("open");
}

function getPoolFromDataset(el) {
  const column = el.dataset.poolColumn;
  const index = Number(el.dataset.poolIndex);
  const list = column === "public" ? latestTopology.publicPools || [] : latestTopology.privatePools || [];
  return list[index];
}

function bindMinerClicks() {
  document.querySelectorAll("[data-kind='miner']").forEach(el => {
    el.onclick = event => {
      event.stopPropagation();
      openMinerDrawer(el.dataset.workerIndex);
    };
  });
}

function bindPoolClicks() {
  document.querySelectorAll("[data-kind='pool'], [data-kind='pool-miners']").forEach(el => {
    el.onclick = event => {
      event.stopPropagation();
      const pool = getPoolFromDataset(el);
      if (pool) openPoolDrawer(pool);
    };
  });
}

async function loadMap() {
  const target = byId("infraMap");
  byId("mapStatus").textContent = "Refreshing";

  try {
    const [topologyResult, workersResult, summaryResult] = await Promise.allSettled([
      fetchJson("/api/discovery/topology"),
      fetchJson("/api/mining/workers"),
      fetchJson("/api/mining/summary")
    ]);

    if (topologyResult.status !== "fulfilled") {
      throw new Error("Topology endpoint failed");
    }

    latestTopology = topologyResult.value.topology || {};
    latestSystems = topologyResult.value.discovery?.systems || [];
    latestFound = topologyResult.value.discovery?.found || [];
    latestWorkers = workersResult.status === "fulfilled" ? normalizeWorkers(workersResult.value) : [];
    latestMiningSummary = summaryResult.status === "fulfilled" ? summaryResult.value : {};

    const privatePools = latestTopology.privatePools || [];
    const publicPools = latestTopology.publicPools || [];

    byId("infraSubtitle").textContent =
      `${privatePools.length} private pool(s), ${publicPools.length} public pool(s), ${latestWorkers.length} live miner(s)`;

    target.innerHTML = `
      <div class="internet-node">
        <div class="internet-orb"></div>
        <strong>Internet / LAN</strong>
        <span>Network entry point</span>
      </div>

      <div class="vertical-line big"></div>

      <div class="topology-columns">
        ${renderPoolColumn("Private / Solo Pools", "Internal solo and private MiningCore pools", privatePools, "private")}
        ${renderPoolColumn("Public Pools", "Public pool services and shared mining operations", publicPools, "public")}
      </div>
    `;

    bindPoolClicks();
    bindMinerClicks();

    byId("mapStatus").textContent = "Live";
  } catch (err) {
    target.innerHTML = `<div class="empty-state"><h2>Map failed to load.</h2><p>${err.message}</p></div>`;
    byId("mapStatus").textContent = "Error";
  }
}

window.addEventListener("DOMContentLoaded", () => {
  byId("drawerClose")?.addEventListener("click", closeDrawer);
  byId("drawerBackdrop")?.addEventListener("click", closeDrawer);
  byId("refreshMap")?.addEventListener("click", loadMap);

  loadMap();
  setInterval(loadMap, 15000);
});
