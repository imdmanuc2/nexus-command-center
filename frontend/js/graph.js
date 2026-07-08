let graph = { nodes: [], edges: [], counts: {} };
let selectedNodeId = null;
let highlightedNodeIds = new Set();
let highlightedEdgeKeys = new Set();
let searchQuery = "";
let graphRefreshTimer = null;
let activeNodeType = "all";
let canvasNodeTypes = new Set(["pool", "asic"]);
let liveWorkers = [];
let snapshots = [];
let timeMachineMode = false;
let manualPositions = {};

const typeOrder = {
  host: 1,
  server: 1,
  pool: 2,
  worker: 3,
  asic: 4,
  asset: 4,
  "coin-node-rpc": 5
};

function byId(id) { return document.getElementById(id); }
function safe(v, f = "Unknown") { return v === undefined || v === null || v === "" ? f : v; }

function formatSnapshotTime(value) {
  if (!value) return "Live";

  const raw = String(value);
  const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})-(\d{2})(\d{2})(\d{2})$/);

  if (!match) return raw;

  const [, y, mo, d, h, mi, se] = match;
  const date = new Date(`${y}-${mo}-${d}T${h}:${mi}:${se}`);

  return date.toLocaleString("en-US", {
    month: "2-digit",
    day: "2-digit",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    hour12: true
  });
}

function shortLabel(value, max = 18) {
  const text = safe(value, "");
  return text.length > max ? text.slice(0, max - 1) + "…" : text;
}
function nodeById(id) { return graph.nodes.find(n => n.id === id); }
function connectedEdges(id) { return graph.edges.filter(e => e.source === id || e.target === id); }

function toggleTvMode() {
  document.body.classList.toggle("tv-mode");
  const enabled = document.body.classList.contains("tv-mode");
  if (byId("tvModeToggle")) byId("tvModeToggle").textContent = enabled ? "Exit TV Mode" : "TV Mode";
}

function clearGraphSelection() {
  selectedNodeId = null;
  highlightedNodeIds = new Set();
  highlightedEdgeKeys = new Set();
  renderCanvas();
  renderNodes();
  renderRelationships();
}

function edgeKey(edge) {
  return `${edge.source}->${edge.target}:${edge.type}`;
}

async function loadImpactHighlight(nodeId) {
  highlightedNodeIds = new Set([nodeId]);
  highlightedEdgeKeys = new Set();

  // Always highlight direct neighbors so every click does something obvious.
  graph.edges.forEach(edge => {
    if (edge.source === nodeId || edge.target === nodeId) {
      highlightedNodeIds.add(edge.source);
      highlightedNodeIds.add(edge.target);
      highlightedEdgeKeys.add(edgeKey(edge));
    }
  });

  try {
    const res = await fetch(`/api/impact?nodeId=${encodeURIComponent(nodeId)}`);
    if (!res.ok) return;

    const impact = await res.json();

    (impact.affected || []).forEach(item => {
      if (item.node?.id) highlightedNodeIds.add(item.node.id);
    });

    graph.edges.forEach(edge => {
      if (highlightedNodeIds.has(edge.source) && highlightedNodeIds.has(edge.target)) {
        highlightedEdgeKeys.add(edgeKey(edge));
      }
    });
  } catch {}
}

function filteredNodes() {
  const q = searchQuery.trim().toLowerCase();
  if (!q) return graph.nodes;
  return graph.nodes.filter(n =>
    [n.id, n.type, n.label, n.status, JSON.stringify(n.properties || {})]
      .join(" ")
      .toLowerCase()
      .includes(q)
  );
}

function renderMissionStatus() {
  const nodes = graph.nodes || [];

  const idle = nodes.filter(n => liveNodeStatus(n) === "idle").length;
  const mining = nodes.filter(n => liveNodeStatus(n) === "mining").length;
  const offline = nodes.filter(n => ["offline", "error", "down"].includes(String(n.status || "").toLowerCase())).length;
  const warning = nodes.filter(n => ["warning", "degraded"].includes(String(n.status || "").toLowerCase())).length;

  const text = byId("missionStatusText");
  const banner = byId("missionStatusBanner");
  if (!text || !banner) return;

  banner.classList.remove("ok", "warn", "fault");

  if (offline > 0) {
    banner.classList.add("fault");
    text.textContent = `${offline} offline node(s) · ${warning} warning · ${idle} idle`;
  } else if (warning > 0 || idle > 0) {
    banner.classList.add("warn");
    text.textContent = `${mining} mining node(s) · ${idle} idle node(s) · ${warning} warning`;
  } else {
    banner.classList.add("ok");
    text.textContent = `${mining} mining node(s) · all critical systems healthy`;
  }
}

function renderSummary() {
  const c = graph.counts || {};
  byId("graphSummary").innerHTML = `
    <div class="asset-summary-card"><span>Nodes</span><strong>${c.nodes || graph.nodes.length}</strong></div>
    <div class="asset-summary-card"><span>Relationships</span><strong>${c.edges || graph.edges.length}</strong></div>
    <div class="asset-summary-card"><span>Assets</span><strong>${c.assets || 0}</strong></div>
    <div class="asset-summary-card"><span>Pools</span><strong>${c.pools || 0}</strong></div>
    <div class="asset-summary-card"><span>Workers</span><strong>${c.workers || 0}</strong></div>
  `;
}

function layoutNodes() {
  const nodes = graph.nodes
    .filter(n => canvasNodeTypes.has(n.type))
    .map(n => ({ ...n }));
  const groups = {};

  nodes.forEach(n => {
    const layer = typeOrder[n.type] || 6;
    groups[layer] ||= [];
    groups[layer].push(n);
  });

  Object.entries(groups).forEach(([layer, items]) => {
    items.forEach((n, i) => {
      n.x = 90 + (Number(layer) - 1) * 250;
      n.y = 90 + i * 130;
    });
  });

  return nodes;
}

function renderCanvas() {
  const nodes = layoutNodes().map(n => {
    if (manualPositions[n.id]) {
      n.x = manualPositions[n.id].x;
      n.y = manualPositions[n.id].y;
    }
    return n;
  });
  const nodeMap = Object.fromEntries(nodes.map(n => [n.id, n]));

  const edges = graph.edges
    .map(e => ({ ...e, sourceNode: nodeMap[e.source], targetNode: nodeMap[e.target] }))
    .filter(e => e.sourceNode && e.targetNode);

  const maxX = Math.max(...nodes.map(n => n.x), 900) + 180;
  const maxY = Math.max(...nodes.map(n => n.y), 460) + 100;

  byId("graphCanvas").innerHTML = `
    <svg viewBox="0 0 ${maxX} ${maxY}" class="infra-svg" id="infraSvgCanvas">
      <defs>
        <marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
          <path d="M0,0 L0,6 L9,3 z" fill="#60a5fa"></path>
        </marker>
      </defs>

      ${edges.map(e => {
        const active = highlightedEdgeKeys.has(edgeKey(e));
        const faded = selectedNodeId && !active;
        return `
        <line
          x1="${e.sourceNode.x + 85}" y1="${e.sourceNode.y + 37}"
          x2="${e.targetNode.x + 85}" y2="${e.targetNode.y + 37}"
          class="infra-link ${active ? "active" : ""} ${faded ? "faded" : ""}"
          marker-end="url(#arrow)"
        />
        <circle class="share-pulse ${active ? "active" : ""}" r="4">
          <animateMotion dur="2.2s" repeatCount="indefinite"
            path="M${e.sourceNode.x + 85},${e.sourceNode.y + 37} L${e.targetNode.x + 85},${e.targetNode.y + 37}" />
        </circle>
      `}).join("")}

      ${nodes.map(n => {
        const h = liveHashrateForNode(n);
        const liveStatus = liveNodeStatus(n);
        return `
        <g class="infra-node node-${n.type} status-${liveStatus} ${selectedNodeId === n.id ? "selected" : ""} ${highlightedNodeIds.has(n.id) ? "highlighted" : ""} ${selectedNodeId && !highlightedNodeIds.has(n.id) ? "faded" : ""}" data-id="${n.id}">
          <rect x="${n.x}" y="${n.y}" rx="16" ry="16" width="180" height="84"></rect>
          <circle cx="${n.x + 18}" cy="${n.y + 22}" r="6"></circle>
          <text x="${n.x + 34}" y="${n.y + 26}" class="infra-node-title">${shortLabel(n.label, 20)}</text>
          <text x="${n.x + 16}" y="${n.y + 54}" class="infra-node-type">${safe(n.type)}</text>
          <text x="${n.x + 16}" y="${n.y + 73}" class="infra-node-metric">${h > 0 ? formatHashrate(h) : liveStatus.toUpperCase()}</text>
        </g>
      `}).join("")}
    </svg>
  `;

  byId("infraSvgCanvas")?.addEventListener("click", () => {
    selectedNodeId = null;
    highlightedNodeIds = new Set();
    highlightedEdgeKeys = new Set();
    renderCanvas();
    renderNodes();
    renderRelationships();
  });

  enableDrag(nodes);

  document.querySelectorAll(".infra-node").forEach(el => {
    el.addEventListener("click", async (event) => {
      event.stopPropagation();
      selectedNodeId = el.dataset.id;
      await loadImpactHighlight(selectedNodeId);
      renderCanvas();
      renderNodes();
      renderRelationships();

      const node = nodeById(selectedNodeId);
      const impact = await fetchImpact(selectedNodeId);
      openInspector(node, impact);
    });
  });
}

function svgPoint(svg, event) {
  const pt = svg.createSVGPoint();
  pt.x = event.clientX;
  pt.y = event.clientY;
  return pt.matrixTransform(svg.getScreenCTM().inverse());
}

let dragState = null;

function enableDrag(nodes) {
  const svg = byId("infraSvgCanvas");
  if (!svg) return;

  const nodeMap = Object.fromEntries(nodes.map(n => [n.id, n]));

  document.querySelectorAll(".infra-node").forEach(el => {
    const nodeId = el.dataset.id;

    el.addEventListener("mousedown", event => {
      event.stopPropagation();
      event.preventDefault();

      const node = nodeMap[nodeId];
      const point = svgPoint(svg, event);

      dragState = {
        nodeId,
        offsetX: point.x - node.x,
        offsetY: point.y - node.y
      };

      el.classList.add("dragging");
    });
  });

  svg.onmousemove = event => {
    if (!dragState) return;

    const point = svgPoint(svg, event);

    manualPositions[dragState.nodeId] = {
      x: Math.max(20, point.x - dragState.offsetX),
      y: Math.max(20, point.y - dragState.offsetY)
    };

    renderCanvas();
  };

  svg.onmouseup = async () => {
    if (dragState) {
      dragState = null;
      document.querySelectorAll(".infra-node.dragging").forEach(n => n.classList.remove("dragging"));
      await saveGraphLayout();
    }
  };

  svg.onmouseleave = async () => {
    if (dragState) {
      dragState = null;
      document.querySelectorAll(".infra-node.dragging").forEach(n => n.classList.remove("dragging"));
      await saveGraphLayout();
    }
  };
}

function renderNodes() {
  const nodes = filteredNodes();

  byId("graphNodes").innerHTML = nodes.map(node => `
    <button class="graph-node ${selectedNodeId === node.id ? "active" : ""}" data-id="${node.id}">
      <div>
        <strong>${safe(node.label, node.id)}</strong>
        <span>${node.id}</span>
      </div>
      <b>${safe(node.type)}</b>
    </button>
  `).join("");

  document.querySelectorAll(".graph-node").forEach(btn => {
    btn.addEventListener("click", async () => {
      selectedNodeId = btn.dataset.id;
      await loadImpactHighlight(selectedNodeId);
      renderNodes();
      renderCanvas();
      renderRelationships();

      const node = nodeById(selectedNodeId);
      const impact = await fetchImpact(selectedNodeId);
      openInspector(node, impact);
    });
  });
}

async function fetchImpact(nodeId) {
  try {
    const res = await fetch(`/api/impact?nodeId=${encodeURIComponent(nodeId)}`);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

async function loadLiveMetrics() {
  try {
    const res = await fetch("/api/mining/workers");
    if (res.ok) {
      const payload = await res.json();
      liveWorkers = payload.workers || [];
    }
  } catch {}
}

function workerForNode(node) {
  const props = node.properties || {};
  const workerName = props.workerName || props.name || props.workerId;
  return liveWorkers.find(w =>
    w.workerName === workerName ||
    w.name === workerName ||
    w.workerId === props.workerId ||
    w.assetName === node.label
  );
}

function liveHashrateForNode(node) {
  if (!node) return 0;

  const props = node.properties || {};

  if (node.type === "worker") {
    return Number(props.hashrate || workerForNode(node)?.hashrate || 0);
  }

  if (node.type === "asic") {
    const worker = liveWorkers.find(w => w.assetName === node.label || w.assetIp === props.ip);
    return Number(worker?.hashrate || 0);
  }

  if (node.type === "pool") {
    return liveWorkers
      .filter(w => w.poolId === props.id && w.poolHost === props.host)
      .reduce((sum, w) => sum + Number(w.hashrate || 0), 0);
  }

  return 0;
}

function liveNodeStatus(node) {
  const h = liveHashrateForNode(node);
  if (["worker", "asic", "pool"].includes(node.type)) {
    return h > 0 ? "mining" : "idle";
  }
  return node.status || "online";
}

function formatHashrate(value) {
  const n = Number(value || 0);
  if (n >= 1e12) return `${(n / 1e12).toFixed(2)} TH/s`;
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)} GH/s`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)} MH/s`;
  return `${n.toFixed(0)} H/s`;
}


function openInspector(node, impact) {
  const props = node?.properties || {};
  const hashrate = liveHashrateForNode(node);
  const affectedTypes = impact?.affectedByType || {};

  byId("inspectorContent").innerHTML = `
    <h2>${safe(node?.label, "Selected Node")}</h2>
    <p class="drawer-subtitle">${safe(node?.type).toUpperCase()} • ${safe(node?.status, "online")}</p>

    <div class="asset-drawer-section">
      <h3>Live Status</h3>
      <div class="asset-detail-grid">
        <div class="asset-detail-field"><label>Hashrate</label><strong>${formatHashrate(hashrate)}</strong></div>
        <div class="asset-detail-field"><label>Status</label><strong>${safe(liveNodeStatus(node)).toUpperCase()}</strong></div>
        <div class="asset-detail-field"><label>Risk</label><strong>${safe(impact?.risk, "Unknown").toUpperCase()}</strong></div>
        <div class="asset-detail-field"><label>Affected</label><strong>${impact?.affectedCount ?? 0}</strong></div>
      </div>
    </div>

    <div class="asset-drawer-section">
      <h3>Identity</h3>
      <div class="asset-detail-grid">
        <div class="asset-detail-field"><label>Node ID</label><strong>${safe(node?.id)}</strong></div>
        <div class="asset-detail-field"><label>IP</label><strong>${safe(props.ip || props.host || props.poolHost, "Not set")}</strong></div>
        <div class="asset-detail-field"><label>Pool</label><strong>${safe(props.poolGroup || props.poolId || props.id, "Not set")}</strong></div>
        <div class="asset-detail-field"><label>Worker</label><strong>${safe(props.workerName || props.workerId, "Not set")}</strong></div>
      </div>
    </div>

    <div class="asset-drawer-section">
      <h3>Blast Radius</h3>
      <ul class="service-list">
        ${
          Object.entries(affectedTypes).map(([type, count]) =>
            `<li><span>${type}</span><b>${count}</b></li>`
          ).join("") || "<li>No downstream impact detected.</li>"
        }
      </ul>
    </div>

    <div class="asset-drawer-section">
      <h3>Raw Properties</h3>
      <pre>${JSON.stringify(props, null, 2)}</pre>
    </div>
  `;

  byId("inspectorPanel")?.classList.add("open");
  byId("inspectorBackdrop")?.classList.add("open");
}

function closeInspector() {
  byId("inspectorPanel")?.classList.remove("open");
  byId("inspectorBackdrop")?.classList.remove("open");
}

async function renderRelationships() {
  if (!selectedNodeId) {
    byId("graphRelationships").innerHTML = "Select a node.";
    return;
  }

  const node = nodeById(selectedNodeId);
  const edges = connectedEdges(selectedNodeId);
  const impact = await fetchImpact(selectedNodeId);
  const affectedTypes = impact?.affectedByType || {};

  byId("graphRelationships").innerHTML = `
    <div class="asset-drawer-section">
      <h3>${safe(node?.label, selectedNodeId)}</h3>
      <div class="asset-detail-grid">
        <div class="asset-detail-field"><label>Node ID</label><strong>${selectedNodeId}</strong></div>
        <div class="asset-detail-field"><label>Type</label><strong>${safe(node?.type)}</strong></div>
        <div class="asset-detail-field"><label>Status</label><strong>${safe(node?.status)}</strong></div>
      </div>
    </div>

    <div class="asset-drawer-section impact-card">
      <h3>Blast Radius</h3>
      <div class="asset-detail-grid">
        <div class="asset-detail-field"><label>Risk</label><strong>${safe(impact?.risk, "Unknown").toUpperCase()}</strong></div>
        <div class="asset-detail-field"><label>Affected Objects</label><strong>${impact?.affectedCount ?? 0}</strong></div>
        <div class="asset-detail-field"><label>Hashrate Impact</label><strong>${formatHashrate(impact?.estimatedHashrateLoss || 0)}</strong></div>
        <div class="asset-detail-field"><label>Affected Types</label><strong>${Object.entries(affectedTypes).map(([k,v]) => `${k}: ${v}`).join(", ") || "None"}</strong></div>
      </div>
    </div>

    <div class="asset-drawer-section">
      <h3>Relationships</h3>
      <ul class="service-list">
        ${edges.map(edge => {
          const otherId = edge.source === selectedNodeId ? edge.target : edge.source;
          const other = nodeById(otherId);
          return `<li><span>${safe(edge.type)}</span><b>${safe(other?.label, otherId)}</b></li>`;
        }).join("") || "<li>No relationships found.</li>"}
      </ul>
    </div>

    <div class="asset-drawer-section">
      <h3>Properties</h3>
      <pre>${JSON.stringify(node?.properties || {}, null, 2)}</pre>
    </div>
  `;
}

async function loadSavedLayout() {
  try {
    const res = await fetch("/api/graph/layout");
    if (res.ok) manualPositions = await res.json();
  } catch {}
}

async function saveGraphLayout() {
  await fetch("/api/graph/layout/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(manualPositions)
  });
  byId("graphHealth").textContent = "Layout Saved";
  setTimeout(() => byId("graphHealth").textContent = "Live", 1200);
}

async function resetGraphLayout() {
  manualPositions = {};
  await fetch("/api/graph/layout/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({})
  });
  renderCanvas();
  renderNodes();
  renderRelationships();
}


async function loadSnapshots() {
  try {
    const res = await fetch("/api/snapshots");
    if (!res.ok) return;

    const payload = await res.json();
    snapshots = payload.snapshots || [];

    const slider = byId("snapshotSlider");
    if (!slider) return;

    slider.max = Math.max(0, snapshots.length - 1);
    slider.value = Math.max(0, snapshots.length - 1);

    byId("snapshotLabel").textContent = snapshots.length
      ? formatSnapshotTime(snapshots[snapshots.length - 1].createdAt)
      : "Live";
  } catch {}
}

async function loadSnapshotByIndex(index) {
  const snap = snapshots[index];
  if (!snap) return;

  const res = await fetch(`/api/snapshot?file=${encodeURIComponent(snap.file)}`);
  if (!res.ok) return;

  graph = await res.json();
  timeMachineMode = true;

  byId("graphHealth").textContent = "Replay";
  byId("snapshotLabel").textContent = formatSnapshotTime(snap.createdAt);

  renderSummary();
  renderCanvas();
  renderNodes();
  renderRelationships();
}

async function returnToLiveMode() {
  timeMachineMode = false;
  await loadGraph(false);
}


function formatEventTime(value) {
  try {
    return new Date(value).toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "2-digit",
      second: "2-digit",
      hour12: true
    });
  } catch {
    return "";
  }
}

async function loadEvents() {
  try {
    const res = await fetch("/api/events/live");
    if (!res.ok) return;

    const events = await res.json();
    const feed = byId("eventFeed");
    if (!feed) return;

    feed.innerHTML = events.slice().reverse().slice(0, 18).map(e => `
      <div class="live-event ${e.severity || "info"}">
        <span>${formatEventTime(e.time)}</span>
        <strong>${e.message}</strong>
      </div>
    `).join("") || `<div class="live-event info empty"><strong>No events yet.</strong></div>`;
  } catch {}
}

async function loadGraph(rebuild = false) {
  try {
    if (timeMachineMode && !rebuild) return;
    byId("graphHealth").textContent = rebuild ? "Rebuilding..." : "Loading...";
    const res = await fetch(rebuild ? "/api/graph/rebuild" : "/api/graph/live");
    graph = await res.json();
    await loadSavedLayout();
    await loadLiveMetrics();

    renderSummary();
    renderMissionStatus();
    renderCanvas();
    renderNodes();
    renderRelationships();

    byId("graphHealth").textContent = "Live";
  } catch (err) {
    byId("graphHealth").textContent = "Error";
    byId("graphNodes").innerHTML = `<div class="empty-state"><h2>Explorer failed.</h2><p>${err.message}</p></div>`;
  }
}

window.addEventListener("DOMContentLoaded", () => {
  byId("graphSearch")?.addEventListener("input", e => {
    searchQuery = e.target.value;
    renderNodes();
  });

  byId("clearGraphSelection")?.addEventListener("click", clearGraphSelection);
  byId("tvModeToggle")?.addEventListener("click", toggleTvMode);
  byId("tvExitFloating")?.addEventListener("click", toggleTvMode);
  byId("saveGraphLayout")?.addEventListener("click", saveGraphLayout);
  byId("resetGraphLayout")?.addEventListener("click", resetGraphLayout);

  byId("showAllNodes")?.addEventListener("click", () => {
    activeNodeType = "all";
    searchQuery = "";
    if (byId("graphSearch")) byId("graphSearch").value = "";
    document.querySelectorAll(".type-filter").forEach(b => b.classList.remove("active"));
    document.querySelector(".type-filter[data-type='all']")?.classList.add("active");
    renderNodes();
  });

  document.querySelectorAll(".type-filter").forEach(btn => {
    btn.addEventListener("click", () => {
      const type = btn.dataset.type;
      activeNodeType = type;

      document.querySelectorAll(".type-filter").forEach(b => {
        b.classList.toggle("active", b.dataset.type === type);
      });

      renderNodes();
    });
  });

  byId("rebuildGraph")?.addEventListener("click", async () => {
    await loadGraph(true);
  });

  byId("autoRefreshGraph")?.addEventListener("change", e => {
    if (graphRefreshTimer) clearInterval(graphRefreshTimer);

    if (e.target.checked) {
      graphRefreshTimer = setInterval(() => loadGraph(false), 15000);
    }
  });

  byId("closeInspector")?.addEventListener("click", closeInspector);
  byId("inspectorBackdrop")?.addEventListener("click", closeInspector);

  byId("snapshotSlider")?.addEventListener("input", e => {
    loadSnapshotByIndex(Number(e.target.value));
  });

  byId("returnToLive")?.addEventListener("click", returnToLiveMode);

  loadSnapshots();
  loadGraph();
  loadEvents();
  graphRefreshTimer = setInterval(() => loadGraph(false), 15000);
  setInterval(loadEvents, 3000);
});
