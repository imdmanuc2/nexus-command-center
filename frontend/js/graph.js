let graph = { nodes: [], edges: [], counts: {} };
let selectedNodeId = null;
let searchQuery = "";

function byId(id) {
  return document.getElementById(id);
}

function safe(value, fallback = "Unknown") {
  return value === undefined || value === null || value === "" ? fallback : value;
}

function connectedEdges(nodeId) {
  return graph.edges.filter(e => e.source === nodeId || e.target === nodeId);
}

function nodeById(id) {
  return graph.nodes.find(n => n.id === id);
}

function filteredNodes() {
  const q = searchQuery.trim().toLowerCase();
  if (!q) return graph.nodes;

  return graph.nodes.filter(n =>
    [
      n.id,
      n.type,
      n.label,
      n.status,
      JSON.stringify(n.properties || {})
    ].join(" ").toLowerCase().includes(q)
  );
}

function renderSummary() {
  const counts = graph.counts || {};
  byId("graphSummary").innerHTML = `
    <div class="asset-summary-card"><span>Nodes</span><strong>${counts.nodes || graph.nodes.length}</strong></div>
    <div class="asset-summary-card"><span>Edges</span><strong>${counts.edges || graph.edges.length}</strong></div>
    <div class="asset-summary-card"><span>Assets</span><strong>${counts.assets || 0}</strong></div>
    <div class="asset-summary-card"><span>Pools</span><strong>${counts.pools || 0}</strong></div>
    <div class="asset-summary-card"><span>Workers</span><strong>${counts.workers || 0}</strong></div>
  `;
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
  `).join("") || `<div class="empty-state"><h2>No nodes match.</h2></div>`;

  document.querySelectorAll(".graph-node").forEach(btn => {
    btn.addEventListener("click", () => {
      selectedNodeId = btn.dataset.id;
      renderNodes();
      renderRelationships();
    });
  });
}

function renderRelationships() {
  if (!selectedNodeId) {
    byId("graphRelationships").innerHTML = "Select a node.";
    return;
  }

  const node = nodeById(selectedNodeId);
  const edges = connectedEdges(selectedNodeId);

  byId("graphRelationships").innerHTML = `
    <div class="asset-drawer-section">
      <h3>${safe(node?.label, selectedNodeId)}</h3>
      <div class="asset-detail-grid">
        <div class="asset-detail-field"><label>Node ID</label><strong>${selectedNodeId}</strong></div>
        <div class="asset-detail-field"><label>Type</label><strong>${safe(node?.type)}</strong></div>
        <div class="asset-detail-field"><label>Status</label><strong>${safe(node?.status)}</strong></div>
      </div>
    </div>

    <div class="asset-drawer-section">
      <h3>Connected Relationships</h3>
      <ul class="service-list">
        ${
          edges.map(edge => {
            const otherId = edge.source === selectedNodeId ? edge.target : edge.source;
            const other = nodeById(otherId);
            return `
              <li>
                <span>${safe(edge.type)}</span>
                <b>${safe(other?.label, otherId)}</b>
              </li>
            `;
          }).join("") || "<li>No relationships found.</li>"
        }
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
    const res = await fetch("/api/graph");
    graph = await res.json();

    renderSummary();
    renderNodes();
    renderRelationships();

    byId("graphHealth").textContent = "Live";
  } catch (err) {
    byId("graphHealth").textContent = "Error";
    byId("graphNodes").innerHTML = `<div class="empty-state"><h2>Graph failed.</h2><p>${err.message}</p></div>`;
  }
}

window.addEventListener("DOMContentLoaded", () => {
  byId("graphSearch")?.addEventListener("input", e => {
    searchQuery = e.target.value;
    renderNodes();
  });

  loadGraph();
});
