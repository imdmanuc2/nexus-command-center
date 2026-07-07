let graph = { nodes: [], edges: [], counts: {} };
let selectedNodeId = null;
let highlightedNodeIds = new Set();
let highlightedEdgeKeys = new Set();
let searchQuery = "";
let graphRefreshTimer = null;
let activeNodeType = "all";
let liveWorkers = [];
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

function shortLabel(value, max = 18) {
  const text = safe(value, "");
  return text.length > max ? text.slice(0, max - 1) + "…" : text;
}
function nodeById(id) { return graph.nodes.find(n => n.id === id); }
function connectedEdges(id) { return graph.edges.filter(e => e.source === id || e.target === id); }

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
  const nodes = graph.nodes.map(n => ({ ...n }));
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

async function loadGraph(rebuild = false) {
  try {
    byId("graphHealth").textContent = rebuild ? "Rebuilding..." : "Loading...";
    const res = await fetch(rebuild ? "/api/graph/rebuild" : "/api/graph/live");
    graph = await res.json();
    await loadSavedLayout();
    await loadLiveMetrics();

    renderSummary();
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
      document.querySelectorAll(".type-filter").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      activeNodeType = btn.dataset.type;
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

  loadGraph();
  graphRefreshTimer = setInterval(() => loadGraph(false), 15000);
});
