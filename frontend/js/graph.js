let graph = { nodes: [], edges: [], counts: {} };
let selectedNodeId = null;
let searchQuery = "";

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
function nodeById(id) { return graph.nodes.find(n => n.id === id); }
function connectedEdges(id) { return graph.edges.filter(e => e.source === id || e.target === id); }

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
      n.x = 120 + (Number(layer) - 1) * 220;
      n.y = 90 + i * 120;
    });
  });

  return nodes;
}

function renderCanvas() {
  const nodes = layoutNodes();
  const nodeMap = Object.fromEntries(nodes.map(n => [n.id, n]));

  const edges = graph.edges
    .map(e => ({ ...e, sourceNode: nodeMap[e.source], targetNode: nodeMap[e.target] }))
    .filter(e => e.sourceNode && e.targetNode);

  const maxX = Math.max(...nodes.map(n => n.x), 900) + 180;
  const maxY = Math.max(...nodes.map(n => n.y), 460) + 100;

  byId("graphCanvas").innerHTML = `
    <svg viewBox="0 0 ${maxX} ${maxY}" class="infra-svg">
      <defs>
        <marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">
          <path d="M0,0 L0,6 L9,3 z" fill="#60a5fa"></path>
        </marker>
      </defs>

      ${edges.map(e => `
        <line
          x1="${e.sourceNode.x + 70}" y1="${e.sourceNode.y + 28}"
          x2="${e.targetNode.x + 70}" y2="${e.targetNode.y + 28}"
          class="infra-link"
          marker-end="url(#arrow)"
        />
        <text
          x="${(e.sourceNode.x + e.targetNode.x) / 2 + 65}"
          y="${(e.sourceNode.y + e.targetNode.y) / 2 + 18}"
          class="infra-link-label">${e.type}</text>
      `).join("")}

      ${nodes.map(n => `
        <g class="infra-node ${selectedNodeId === n.id ? "selected" : ""}" data-id="${n.id}">
          <rect x="${n.x}" y="${n.y}" rx="16" ry="16" width="150" height="66"></rect>
          <circle cx="${n.x + 18}" cy="${n.y + 20}" r="6"></circle>
          <text x="${n.x + 34}" y="${n.y + 24}" class="infra-node-title">${safe(n.label, n.id)}</text>
          <text x="${n.x + 16}" y="${n.y + 49}" class="infra-node-type">${safe(n.type)}</text>
        </g>
      `).join("")}
    </svg>
  `;

  document.querySelectorAll(".infra-node").forEach(el => {
    el.addEventListener("click", () => {
      selectedNodeId = el.dataset.id;
      renderCanvas();
      renderNodes();
      renderRelationships();
    });
  });
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
    btn.addEventListener("click", () => {
      selectedNodeId = btn.dataset.id;
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

async function loadGraph() {
  try {
    byId("graphHealth").textContent = "Loading...";
    const res = await fetch("/api/graph/live");
    graph = await res.json();

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

  loadGraph();
});
