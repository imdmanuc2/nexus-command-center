let graph = { nodes: [], edges: [], counts: {} };
let selectedNodeId = null;
let highlightedNodeIds = new Set();
let highlightedEdgeKeys = new Set();
let searchQuery = "";
let graphRefreshTimer = null;
let activeNodeType = "all";
const canvasAssetCategories = new Set([
  "pool",
  "asic",
  "blockchain",
  "server",
  "unknown"
]);
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

function propertyText(value) {
  if (value === undefined || value === null) return "";

  if (typeof value === "string" || typeof value === "number") {
    return String(value);
  }

  if (Array.isArray(value)) {
    return value.map(propertyText).filter(Boolean).join(" ");
  }

  if (typeof value === "object") {
    return Object.values(value)
      .map(propertyText)
      .filter(Boolean)
      .join(" ");
  }

  return "";
}

function inventoryOpenPorts(node) {
  const props = node?.properties || {};

  const candidates = [
    props.openPorts,
    props.ports,
    props.port,
    props.rpcPort,
    props.p2pPort,
    props.services
  ];

  const ports = [];

  candidates.forEach(candidate => {
    if (Array.isArray(candidate)) {
      candidate.forEach(item => {
        if (typeof item === "object" && item !== null) {
          const port = Number(item.port);
          if (Number.isFinite(port)) ports.push(port);
        } else {
          const port = Number(item);
          if (Number.isFinite(port)) ports.push(port);
        }
      });
    } else {
      const port = Number(candidate);
      if (Number.isFinite(port)) ports.push(port);
    }
  });

  return [...new Set(ports)];
}

function canonicalAssetType(node) {
  const type = String(node?.type || "").trim().toLowerCase();
  const props = node?.properties || {};

  const explicit = String(
    props.assetType ||
    props.asset_type ||
    props.canonicalType ||
    props.canonical_type ||
    props.deviceType ||
    ""
  ).trim().toLowerCase();

  const id = String(node?.id || "").toLowerCase();
  const label = String(node?.label || "").toLowerCase();
  const role = String(
    props.primaryRole ||
    props.primary_role ||
    props.role ||
    ""
  ).toLowerCase();

  const ports = inventoryOpenPorts(node);

  /*
   * Explicit backend classification always wins.
   */
  if (["pool", "mining-pool", "solo-pool", "public-pool"].includes(explicit)) {
    return "pool";
  }

  if (["asic", "miner", "asic-miner"].includes(explicit)) {
    return "asic";
  }

  if ([
    "blockchain",
    "blockchain-node",
    "coin-node",
    "bitcoin-node",
    "bitcoin-core",
    "bch-node"
  ].includes(explicit)) {
    return "blockchain";
  }

  if (["server", "host", "infrastructure-node"].includes(explicit)) {
    return "server";
  }

  /*
   * Native graph object types are the next most trustworthy signal.
   * A pool containing the word BCH must remain a pool.
   * An ASIC related to a pool must remain an ASIC.
   */
  if (type === "pool" || id.startsWith("pool-")) {
    return "pool";
  }

  if (
    type === "asic" ||
    id.startsWith("asset-") && (
      label.includes("nano") ||
      label.includes("mining system") ||
      role.includes("asic") ||
      role.includes("miner")
    )
  ) {
    return "asic";
  }

  if (
    type === "blockchain-node" ||
    type === "coin-node-rpc" ||
    id.startsWith("blockchain-") ||
    id.startsWith("coin-node-")
  ) {
    return "blockchain";
  }

  /*
   * Discovery systems may still arrive as infrastructure-node or unknown.
   * Only use ports and role for those generic graph objects.
   */
  if (
    role.includes("blockchain") ||
    role.includes("bitcoin core") ||
    role.includes("btc node") ||
    role.includes("bitcoin node") ||
    role.includes("bch node") ||
    ports.includes(8332) ||
    ports.includes(8333)
  ) {
    return "blockchain";
  }

  if (
    role.includes("asic") ||
    role.includes("miner") ||
    label.includes("nano 3") ||
    label.includes("mining system")
  ) {
    return "asic";
  }

  if (
    role.includes("pool") ||
    role.includes("mining backend") ||
    label.includes("solo pool") ||
    label.includes("public pool")
  ) {
    return "pool";
  }

  if (
    type === "server" ||
    type === "host" ||
    type === "infrastructure-node"
  ) {
    return "server";
  }

  return "unknown";
}

function inventoryCategory(node) {
  return canonicalAssetType(node);
}

function blockchainDisplayName(node) {
  const props = node?.properties || {};
  const text = [
    node?.label,
    node?.id,
    propertyText(props)
  ].join(" ").toLowerCase();

  if (
    text.includes("bitcoin cash") ||
    text.includes("bch") ||
    inventoryOpenPorts(node).includes(8334)
  ) {
    return "Bitcoin Cash Node";
  }

  if (
    text.includes("bitcoin") ||
    text.includes("btc") ||
    inventoryOpenPorts(node).includes(8332) ||
    inventoryOpenPorts(node).includes(8333)
  ) {
    return "Bitcoin Core";
  }

  return "Blockchain Node";
}

function inventoryTypeLabel(node) {
  const category = inventoryCategory(node);

  if (category === "blockchain") return blockchainDisplayName(node);
  if (category === "pool") return "Mining Pool";
  if (category === "asic") return "ASIC Miner";
  if (category === "server") return "Server";

  return "Unknown Asset";
}

function inventoryIdentity(node) {
  const props = node?.properties || {};
  const category = inventoryCategory(node);

  const ip = String(
    props.ip ||
    props.assetIp ||
    props.host ||
    props.poolHost ||
    ""
  ).trim().toLowerCase();

  const label = String(node?.label || node?.id || "")
    .trim()
    .toLowerCase();

  /*
   * Pools are logical services and must remain separate from physical
   * devices even when they share a host IP.
   *
   * Blockchain RPC/P2P graph objects on the same IP should collapse into
   * one blockchain asset.
   */
  if (category === "pool") {
    return `pool:${node?.id || label}`;
  }

  if (category === "blockchain" && ip) {
    return `blockchain:${ip}`;
  }

  if (category === "asic" && ip) {
    return `asic:${ip}`;
  }

  if (category === "server" && ip) {
    return `server:${ip}`;
  }

  return `${category}:${label}`;
}

function inventoryPriority(node) {
  const type = String(node?.type || "").toLowerCase();

  if (type === "asic") return 100;
  if (type === "blockchain-node") return 95;
  if (type === "coin-node-rpc") return 90;
  if (type === "pool") return 85;
  if (type === "infrastructure-node") return 80;
  if (type === "server") return 75;
  if (type === "host") return 20;
  if (type === "worker") return 0;

  return 40;
}

function normalizedInventoryNodes() {
  const inventory = new Map();

  /*
   * Workers are operational records, not separate infrastructure assets.
   * Host nodes representing known ASICs are also suppressed because the
   * real ASIC graph node is preferred below.
   */
  graph.nodes.forEach(node => {
    const type = String(node?.type || "").toLowerCase();
    const props = node?.properties || {};

    /*
     * Workers and internal host identities remain available to the
     * relationship engine, but are not standalone managed assets.
     */
    if (
      type === "worker" ||
      type === "coin-node-rpc" ||
      props.internalGraphNode === true
    ) {
      return;
    }

    const category = inventoryCategory(node);
    const key = inventoryIdentity(node);
    const existing = inventory.get(key);

    if (!existing || inventoryPriority(node) > inventoryPriority(existing)) {
      inventory.set(key, node);
    }
  });

  return Array.from(inventory.values()).sort((a, b) => {
    const order = {
      blockchain: 1,
      pool: 2,
      asic: 3,
      server: 4,
      unknown: 5
    };

    const categoryDifference =
      (order[inventoryCategory(a)] || 99) -
      (order[inventoryCategory(b)] || 99);

    if (categoryDifference !== 0) {
      return categoryDifference;
    }

    return String(a.label || a.id).localeCompare(
      String(b.label || b.id),
      undefined,
      { numeric: true }
    );
  });
}

function filteredNodes() {
  const q = searchQuery.trim().toLowerCase();

  return normalizedInventoryNodes().filter(node => {
    const category = inventoryCategory(node);

    if (activeNodeType !== "all" && category !== activeNodeType) {
      return false;
    }

    if (!q) {
      return true;
    }

    return [
      node.id,
      node.type,
      inventoryTypeLabel(node),
      node.label,
      node.status,
      JSON.stringify(node.properties || {})
    ]
      .join(" ")
      .toLowerCase()
      .includes(q);
  });
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

function isManagedInfrastructureNode(node) {
  const props = node?.properties || {};
  const category = inventoryCategory(node);
  const type = String(node?.type || "").toLowerCase();

  /*
   * Pools and ASICs are already managed operational objects produced
   * by the live MiningCore graph.
   */
  if (category === "pool" || category === "asic") {
    return true;
  }

  /*
   * Discovery candidates do not enter the graph until the operator
   * chooses Add. Added systems should carry managed=true, but we also
   * accept persisted infrastructure nodes for backward compatibility.
   */
  if (
    props.managed === true ||
    props.lifecycleStatus === "managed" ||
    props.lifecycle_status === "managed"
  ) {
    return true;
  }

  if (
    ["infrastructure-node", "blockchain-node", "coin-node-rpc"].includes(type) &&
    (
      props.addedAt ||
      props.added_at ||
      props.friendlyName ||
      props.assetType
    )
  ) {
    return true;
  }

  return false;
}


let canvasViewMode = localStorage.getItem(
  "nexusCanvasViewMode"
) || "auto";

let expandedPoolClusters = new Set();

function canvasManagedNodes() {
  return normalizedInventoryNodes()
    .filter(node =>
      canvasAssetCategories.has(inventoryCategory(node)) &&
      isManagedInfrastructureNode(node)
    )
    .map(node => ({ ...node }));
}

function canvasAsicNodes(nodes = canvasManagedNodes()) {
  return nodes.filter(node =>
    inventoryCategory(node) === "asic"
  );
}

function resolvedCanvasViewMode(nodes = canvasManagedNodes()) {
  if (canvasViewMode !== "auto") {
    return canvasViewMode;
  }

  const asicCount = canvasAsicNodes(nodes).length;

  /*
   * Small fleets retain the full engineering view.
   * Large fleets automatically collapse miners into pool clusters.
   */
  return asicCount > 50
    ? "overview"
    : "engineering";
}

function canvasPoolForAsic(asicNode) {
  const directEdge = graph.edges.find(edge =>
    String(edge.type || "").toUpperCase() === "MINES_ON" &&
    edge.source === asicNode.id
  );

  if (directEdge) {
    return graph.nodes.find(node =>
      node.id === directEdge.target
    ) || null;
  }

  const props = asicNode?.properties || {};
  const poolId = String(
    props.livePoolId ||
    props.poolId ||
    ""
  ).toLowerCase();

  const poolHost = String(
    props.livePoolHost ||
    props.poolHost ||
    ""
  );

  return graph.nodes.find(node => {
    if (inventoryCategory(node) !== "pool") {
      return false;
    }

    const nodeProps = node.properties || {};

    const nodePoolId = String(
      nodeProps.id ||
      nodeProps.poolId ||
      ""
    ).toLowerCase();

    const nodeHost = String(
      nodeProps.host ||
      nodeProps.poolHost ||
      ""
    );

    const poolSuffix = poolId.split("-").pop();

    const idMatches = (
      nodePoolId === poolId ||
      poolId.endsWith(`-${nodePoolId}`) ||
      poolSuffix === nodePoolId
    );

    const hostMatches = (
      !poolHost ||
      !nodeHost ||
      poolHost === nodeHost
    );

    return idMatches && hostMatches;
  }) || null;
}

function canvasClusterId(poolNode) {
  return `asic-cluster:${poolNode.id}`;
}

function canvasClusterMembers(poolNode, asicNodes) {
  return asicNodes.filter(asic => {
    const pool = canvasPoolForAsic(asic);
    return pool?.id === poolNode.id;
  });
}

function canvasBuildPoolCluster(poolNode, members) {
  const totalHashrate = members.reduce(
    (sum, member) =>
      sum + Number(liveHashrateForNode(member) || 0),
    0
  );

  const miningCount = members.filter(member =>
    liveHashrateForNode(member) > 0
  ).length;

  const offlineCount = members.filter(member => {
    const status = String(
      liveNodeStatus(member) || ""
    ).toLowerCase();

    return [
      "offline",
      "failed",
      "fault",
      "critical"
    ].includes(status);
  }).length;

  const warningCount = members.filter(member => {
    const status = String(
      liveNodeStatus(member) || ""
    ).toLowerCase();

    return [
      "warning",
      "degraded"
    ].includes(status);
  }).length;

  return {
    id: canvasClusterId(poolNode),
    type: "asic-cluster",
    label: `${members.length} ASICs`,
    status:
      offlineCount > 0
        ? "warning"
        : miningCount > 0
          ? "mining"
          : "idle",
    properties: {
      syntheticCluster: true,
      poolNodeId: poolNode.id,
      poolName: poolNode.label,
      memberIds: members.map(member => member.id),
      minerCount: members.length,
      miningCount,
      warningCount,
      offlineCount,
      totalHashrate,
      assetType: "asic-cluster",
      managed: true,
      lifecycleStatus: "managed"
    }
  };
}

function canvasBuildModel() {
  const allNodes = canvasManagedNodes();
  const mode = resolvedCanvasViewMode(allNodes);

  if (mode === "engineering") {
    return {
      mode,
      nodes: allNodes,
      edges: graph.edges.map(edge => ({ ...edge }))
    };
  }

  const asicNodes = canvasAsicNodes(allNodes);

  const visibleNodes = allNodes.filter(node =>
    inventoryCategory(node) !== "asic"
  );

  const syntheticEdges = [];

  visibleNodes
    .filter(node => inventoryCategory(node) === "pool")
    .forEach(poolNode => {
      const members = canvasClusterMembers(
        poolNode,
        asicNodes
      );

      if (!members.length) {
        return;
      }

      if (expandedPoolClusters.has(poolNode.id)) {
        visibleNodes.push(...members);

        members.forEach(member => {
          syntheticEdges.push({
            source: member.id,
            target: poolNode.id,
            type: "MINES_ON",
            label: "Mines On"
          });
        });

        return;
      }

      const cluster = canvasBuildPoolCluster(
        poolNode,
        members
      );

      visibleNodes.push(cluster);

      syntheticEdges.push({
        source: cluster.id,
        target: poolNode.id,
        type: "MINES_ON",
        label: "Mines On"
      });
    });

  /*
   * Preserve relationships between visible infrastructure objects,
   * but remove individual worker/miner edges hidden inside clusters.
   */
  const visibleIds = new Set(
    visibleNodes.map(node => node.id)
  );

  const retainedEdges = graph.edges.filter(edge =>
    String(edge.type || "").toUpperCase() !== "MINES_ON" &&
    visibleIds.has(edge.source) &&
    visibleIds.has(edge.target)
  );

  return {
    mode,
    nodes: visibleNodes,
    edges: [
      ...retainedEdges,
      ...syntheticEdges
    ]
  };
}

function canvasLayerForNode(node) {
  if (node.type === "asic-cluster") return 5;

  const category = inventoryCategory(node);

  if (category === "blockchain") return 1;
  if (category === "server") return 2;
  if (category === "pool") return 3;
  if (category === "asic") return 5;

  return 6;
}

function canvasDisplayName(node) {
  if (node.type === "asic-cluster") {
    const props = node.properties || {};
    return `${props.minerCount || 0} ASICs`;
  }

  return inventoryDisplayName(node);
}

function canvasDisplayType(node) {
  if (node.type === "asic-cluster") {
    return "MINER CLUSTER";
  }

  return inventoryTypeLabel(node);
}

function canvasDisplayMetric(node) {
  if (node.type === "asic-cluster") {
    const props = node.properties || {};
    const hashrate = Number(
      props.totalHashrate || 0
    );

    return hashrate > 0
      ? formatHashrate(hashrate)
      : `${props.minerCount || 0} MINERS`;
  }

  const hashrate = liveHashrateForNode(node);
  const status = liveNodeStatus(node);

  return hashrate > 0
    ? formatHashrate(hashrate)
    : String(status || "unknown").toUpperCase();
}

function renderCanvasModeControls() {
  const canvas = byId("graphCanvas");

  if (!canvas || byId("canvasModeControls")) {
    return;
  }

  const controls = document.createElement("div");
  controls.id = "canvasModeControls";
  controls.className = "canvas-mode-controls";

  controls.innerHTML = `
    <div class="canvas-mode-copy">
      <strong>Canvas Detail</strong>
      <span id="canvasModeStatus"></span>
    </div>

    <div class="canvas-mode-buttons">
      <button
        type="button"
        data-canvas-mode="auto"
      >
        Auto
      </button>

      <button
        type="button"
        data-canvas-mode="overview"
      >
        Overview
      </button>

      <button
        type="button"
        data-canvas-mode="engineering"
      >
        Engineering
      </button>
    </div>
  `;

  canvas.parentElement?.insertBefore(
    controls,
    canvas
  );

  controls
    .querySelectorAll("[data-canvas-mode]")
    .forEach(button => {
      button.addEventListener("click", () => {
        canvasViewMode =
          button.dataset.canvasMode || "auto";

        localStorage.setItem(
          "nexusCanvasViewMode",
          canvasViewMode
        );

        expandedPoolClusters = new Set();

        renderCanvas();
      });
    });
}

function updateCanvasModeControls(
  mode,
  nodes
) {
  renderCanvasModeControls();

  document
    .querySelectorAll("[data-canvas-mode]")
    .forEach(button => {
      button.classList.toggle(
        "active",
        button.dataset.canvasMode === canvasViewMode
      );
    });

  const status = byId("canvasModeStatus");

  if (!status) return;

  const asicCount = canvasAsicNodes(
    canvasManagedNodes()
  ).length;

  status.textContent = (
    mode === "overview"
      ? `${asicCount} miners grouped by pool`
      : `${asicCount} individual miners shown`
  );
}

function layoutNodes(inputNodes = null) {
  const nodes = (
    inputNodes ||
    canvasBuildModel().nodes
  ).map(node => ({ ...node }));

  const groups = {};

  nodes.forEach(node => {
    const layer = canvasLayerForNode(node);

    groups[layer] ||= [];
    groups[layer].push(node);
  });

  Object.entries(groups).forEach(([layer, items]) => {
    items
      .sort((a, b) =>
        String(a.label || "").localeCompare(
          String(b.label || "")
        )
      )
      .forEach((node, index) => {
        node.x =
          90 +
          (Number(layer) - 1) * 250;

        node.y =
          90 +
          index * 130;
      });
  });

  return nodes;
}

function canvasNodeCenter(node) {
  return {
    x: Number(node.x || 0) + 90,
    y: Number(node.y || 0) + 42
  };
}

function canvasNodeBoundaryPoint(fromNode, towardNode) {
  const from = canvasNodeCenter(fromNode);
  const toward = canvasNodeCenter(towardNode);

  const dx = toward.x - from.x;
  const dy = toward.y - from.y;

  if (!dx && !dy) {
    return from;
  }

  /*
   * Canvas cards are 180 x 84. Intersect the line with the card
   * boundary so relationship arrows do not disappear underneath it.
   */
  const halfWidth = 90;
  const halfHeight = 42;

  const scaleX = dx ? halfWidth / Math.abs(dx) : Infinity;
  const scaleY = dy ? halfHeight / Math.abs(dy) : Infinity;
  const scale = Math.min(scaleX, scaleY);

  return {
    x: from.x + dx * scale,
    y: from.y + dy * scale
  };
}

function canvasRelationshipGeometry(edge) {
  const start = canvasNodeBoundaryPoint(
    edge.sourceNode,
    edge.targetNode
  );

  const end = canvasNodeBoundaryPoint(
    edge.targetNode,
    edge.sourceNode
  );

  const dx = end.x - start.x;
  const dy = end.y - start.y;

  /*
   * A slight curve keeps parallel and crossing connections readable.
   */
  const distance = Math.sqrt(dx * dx + dy * dy);
  const curvature = Math.min(50, Math.max(16, distance * 0.09));

  const normalX = distance ? -dy / distance : 0;
  const normalY = distance ? dx / distance : 0;

  const controlX =
    (start.x + end.x) / 2 + normalX * curvature;

  const controlY =
    (start.y + end.y) / 2 + normalY * curvature;

  return {
    start,
    end,
    control: {
      x: controlX,
      y: controlY
    },
    midpoint: {
      x:
        0.25 * start.x +
        0.5 * controlX +
        0.25 * end.x,
      y:
        0.25 * start.y +
        0.5 * controlY +
        0.25 * end.y
    },
    path:
      `M ${start.x} ${start.y} ` +
      `Q ${controlX} ${controlY} ${end.x} ${end.y}`
  };
}

function canvasRelationshipType(edge) {
  return String(edge?.type || "")
    .trim()
    .toUpperCase();
}

function canvasMiningRelationship(edge) {
  return canvasRelationshipType(edge) === "MINES_ON";
}

function canvasRelationshipActive(edge) {
  if (canvasMiningRelationship(edge)) {
    return liveHashrateForNode(edge.sourceNode) > 0;
  }

  return highlightedEdgeKeys.has(edgeKey(edge));
}

function canvasRelationshipLabel(edge) {
  const type = canvasRelationshipType(edge);

  if (type === "MINES_ON") {
    return "MINES ON";
  }

  return String(
    edge.label ||
    type.replaceAll("_", " ")
  ).toUpperCase();
}


function canvasRelationshipTelemetryKind(edge) {
  const type = canvasRelationshipType(edge);

  if (
    type === "MINES_ON" ||
    type === "RUNS_WORKER"
  ) {
    return "shares";
  }

  if (
    type === "USES_RPC" ||
    type === "HOSTS" ||
    type === "HOSTED_ON"
  ) {
    return "rpc";
  }

  if (
    type === "HAS_NETWORK_IDENTITY" ||
    type.includes("HEALTH")
  ) {
    return "health";
  }

  return "relationship";
}

function canvasRelationshipFault(edge) {
  const sourceStatus = String(
    liveNodeStatus(edge.sourceNode) || ""
  ).toLowerCase();

  const targetStatus = String(
    liveNodeStatus(edge.targetNode) || ""
  ).toLowerCase();

  const badStates = new Set([
    "offline",
    "failed",
    "fault",
    "error",
    "critical",
    "warning"
  ]);

  return (
    badStates.has(sourceStatus) ||
    badStates.has(targetStatus)
  );
}

function canvasWorkerForRelationship(edge) {
  if (!canvasMiningRelationship(edge)) {
    return null;
  }

  const node = edge.sourceNode;
  const props = node?.properties || {};
  const ip = inventoryIp(node);

  return liveWorkers.find(worker => {
    const workerId = shortWorkerId(
      worker.workerName ||
      worker.name ||
      worker.workerId
    );

    const assetWorkerId = shortWorkerId(
      props.liveWorkerId ||
      props.workerId ||
      props.workerName
    );

    return (
      worker.assetName === node.label ||
      worker.displayName === node.label ||
      worker.assetIp === ip ||
      (
        workerId &&
        assetWorkerId &&
        workerId === assetWorkerId
      )
    );
  }) || null;
}

function canvasRelationshipActivity(edge) {
  const kind = canvasRelationshipTelemetryKind(edge);
  const fault = canvasRelationshipFault(edge);

  if (fault) {
    return {
      kind: "fault",
      active: true,
      rate: 1,
      duration: 1.25,
      particles: 1
    };
  }

  if (kind === "shares") {
    const worker = canvasWorkerForRelationship(edge);

    const sharesPerSecond = Number(
      worker?.sharesPerSecond ||
      edge.sourceNode?.properties?.liveSharesPerSecond ||
      0
    );

    const hashrate = liveHashrateForNode(edge.sourceNode);
    const active = hashrate > 0;

    /*
     * Faster share flow produces faster particles, but clamp it so
     * low-difficulty miners do not turn the browser into a laser show.
     */
    const normalizedRate = Math.max(
      0,
      Math.min(1, sharesPerSecond / 0.25)
    );

    return {
      kind,
      active,
      rate: sharesPerSecond,
      duration: active
        ? 2.8 - normalizedRate * 1.55
        : 0,
      particles: active && sharesPerSecond > 0.1 ? 2 : 1
    };
  }

  if (kind === "rpc") {
    const active =
      String(edge.sourceNode?.status || "").toLowerCase() !== "offline" &&
      String(edge.targetNode?.status || "").toLowerCase() !== "offline";

    return {
      kind,
      active,
      rate: active ? 1 : 0,
      duration: 3.2,
      particles: 1
    };
  }

  if (kind === "health") {
    return {
      kind,
      active: true,
      rate: 1,
      duration: 4.8,
      particles: 1
    };
  }

  return {
    kind,
    active: false,
    rate: 0,
    duration: 0,
    particles: 0
  };
}

function canvasAnimationPolicy(nodes, edges) {
  const assetCount = nodes.length;
  const relationshipCount = edges.length;

  /*
   * Engineering view:
   * Animate every useful relationship.
   */
  if (assetCount <= 75 && relationshipCount <= 120) {
    return {
      mode: "full",
      animateShares: true,
      animateRpc: true,
      animateHealth: true,
      showLabels: relationshipCount <= 24,
      maxAnimatedEdges: 120
    };
  }

  /*
   * Medium fleet:
   * Prioritize live mining and fault traffic.
   */
  if (assetCount <= 300 && relationshipCount <= 600) {
    return {
      mode: "reduced",
      animateShares: true,
      animateRpc: false,
      animateHealth: false,
      showLabels: false,
      maxAnimatedEdges: 160
    };
  }

  /*
   * Large fleet:
   * Animate only selected paths and faults. Clustering will become the
   * default view in the next scalability phase.
   */
  return {
    mode: "enterprise",
    animateShares: false,
    animateRpc: false,
    animateHealth: false,
    showLabels: false,
    maxAnimatedEdges: 40
  };
}

function canvasShouldAnimateRelationship(
  edge,
  activity,
  policy,
  index
) {
  if (document.hidden) {
    return false;
  }

  if (!activity.active) {
    return false;
  }

  const selectedPath =
    selectedNodeId &&
    (
      edge.source === selectedNodeId ||
      edge.target === selectedNodeId ||
      highlightedEdgeKeys.has(edgeKey(edge))
    );

  if (activity.kind === "fault") {
    return index < policy.maxAnimatedEdges;
  }

  if (policy.mode === "enterprise") {
    return Boolean(selectedPath);
  }

  if (
    activity.kind === "shares" &&
    policy.animateShares
  ) {
    return index < policy.maxAnimatedEdges;
  }

  if (
    activity.kind === "rpc" &&
    policy.animateRpc
  ) {
    return index < policy.maxAnimatedEdges;
  }

  if (
    activity.kind === "health" &&
    policy.animateHealth
  ) {
    return index < policy.maxAnimatedEdges;
  }

  return false;
}

function canvasPulseMarkup(
  geometry,
  activity,
  animationDelay = 0
) {
  const duration = Number(activity.duration || 2.2);

  return `
    <circle
      class="
        telemetry-particle
        telemetry-${activity.kind}
      "
      r="${activity.kind === "fault" ? 5 : 4}"
    >
      <animateMotion
        dur="${duration}s"
        begin="${animationDelay}s"
        repeatCount="indefinite"
        path="${geometry.path}"
      ></animateMotion>
    </circle>
  `;
}

function renderCanvas() {
  const canvasModel = canvasBuildModel();

  const nodes = layoutNodes(
    canvasModel.nodes
  ).map(node => {
    if (manualPositions[node.id]) {
      node.x = manualPositions[node.id].x;
      node.y = manualPositions[node.id].y;
    }

    return node;
  });

  updateCanvasModeControls(
    canvasModel.mode,
    nodes
  );

  const nodeMap = Object.fromEntries(
    nodes.map(node => [node.id, node])
  );

  const edges = canvasModel.edges
    .map(edge => ({
      ...edge,
      sourceNode: nodeMap[edge.source],
      targetNode: nodeMap[edge.target]
    }))
    .filter(edge =>
      edge.sourceNode &&
      edge.targetNode
    );

  const animationPolicy = canvasAnimationPolicy(
    nodes,
    edges
  );

  const maxX = Math.max(...nodes.map(n => n.x), 900) + 180;
  const maxY = Math.max(...nodes.map(n => n.y), 460) + 100;

  byId("graphCanvas").innerHTML = `
    <svg viewBox="0 0 ${maxX} ${maxY}" class="infra-svg" id="infraSvgCanvas">
      <defs>
        <filter
          id="miningLineGlow"
          x="-40%"
          y="-40%"
          width="180%"
          height="180%"
        >
          <feGaussianBlur stdDeviation="3.2" result="blur"></feGaussianBlur>
          <feMerge>
            <feMergeNode in="blur"></feMergeNode>
            <feMergeNode in="SourceGraphic"></feMergeNode>
          </feMerge>
        </filter>

        <marker
          id="arrowDefault"
          markerWidth="11"
          markerHeight="11"
          refX="9"
          refY="4"
          orient="auto"
          markerUnits="strokeWidth"
        >
          <path
            d="M0,0 L0,8 L10,4 z"
            fill="#60a5fa"
          ></path>
        </marker>

        <marker
          id="arrowMining"
          markerWidth="12"
          markerHeight="12"
          refX="10"
          refY="4"
          orient="auto"
          markerUnits="strokeWidth"
        >
          <path
            d="M0,0 L0,8 L10,4 z"
            fill="#34d399"
          ></path>
        </marker>

        <marker
          id="arrowMiningIdle"
          markerWidth="11"
          markerHeight="11"
          refX="9"
          refY="4"
          orient="auto"
          markerUnits="strokeWidth"
        >
          <path
            d="M0,0 L0,8 L10,4 z"
            fill="#64748b"
          ></path>
        </marker>

        <marker
          id="arrowHealth"
          markerWidth="11"
          markerHeight="11"
          refX="9"
          refY="4"
          orient="auto"
          markerUnits="strokeWidth"
        >
          <path
            d="M0,0 L0,8 L10,4 z"
            fill="#facc15"
          ></path>
        </marker>

        <marker
          id="arrowFault"
          markerWidth="12"
          markerHeight="12"
          refX="10"
          refY="4"
          orient="auto"
          markerUnits="strokeWidth"
        >
          <path
            d="M0,0 L0,8 L10,4 z"
            fill="#f43f5e"
          ></path>
        </marker>
      </defs>

      ${edges.map((edge, edgeIndex) => {
        const geometry = canvasRelationshipGeometry(edge);
        const mining = canvasMiningRelationship(edge);
        const activity = canvasRelationshipActivity(edge);

        const highlighted =
          highlightedEdgeKeys.has(edgeKey(edge));

        const faded =
          selectedNodeId &&
          !highlighted &&
          selectedNodeId !== edge.source &&
          selectedNodeId !== edge.target;

        const shouldAnimate =
          canvasShouldAnimateRelationship(
            edge,
            activity,
            animationPolicy,
            edgeIndex
          );

        const relationshipClass = [
          mining ? "mining" : "default-relationship",
          `telemetry-path-${activity.kind}`,
          activity.active ? "telemetry-active" : "telemetry-idle",
          highlighted ? "active" : "",
          faded ? "faded" : ""
        ].filter(Boolean).join(" ");

        const marker = activity.kind === "fault"
          ? "url(#arrowFault)"
          : activity.kind === "shares" && activity.active
            ? "url(#arrowMining)"
            : activity.kind === "shares"
              ? "url(#arrowMiningIdle)"
              : activity.kind === "health"
                ? "url(#arrowHealth)"
                : "url(#arrowDefault)";

        const showLabel =
          animationPolicy.showLabels &&
          (
            mining ||
            highlighted
          );

        const particleCount =
          shouldAnimate
            ? Math.max(
                1,
                Number(activity.particles || 1)
              )
            : 0;

        return `
          <g
            class="infra-relationship ${relationshipClass}"
            data-source="${edge.source}"
            data-target="${edge.target}"
            data-type="${canvasRelationshipType(edge)}"
          >
            <path
              class="infra-link-glow"
              d="${geometry.path}"
            ></path>

            <path
              class="infra-link"
              d="${geometry.path}"
              marker-end="${marker}"
            ></path>

            ${
              Array.from({
                length: particleCount
              }).map((_, particleIndex) =>
                canvasPulseMarkup(
                  geometry,
                  activity,
                  -(
                    particleIndex *
                    Number(activity.duration || 2.2) /
                    particleCount
                  )
                )
              ).join("")
            }

            ${
              showLabel
                ? `
                  <g
                    class="infra-edge-label"
                    transform="
                      translate(
                        ${geometry.midpoint.x},
                        ${geometry.midpoint.y}
                      )
                    "
                  >
                    <rect
                      x="-37"
                      y="-12"
                      width="74"
                      height="23"
                      rx="6"
                      ry="6"
                    ></rect>

                    <text
                      x="0"
                      y="4"
                      text-anchor="middle"
                    >
                      ${canvasRelationshipLabel(edge)}
                    </text>
                  </g>
                `
                : ""
            }
          </g>
        `;
      }).join("")}

      ${nodes.map(n => {
        const h = liveHashrateForNode(n);
        const liveStatus = liveNodeStatus(n);
        return `
        <g class="infra-node node-${n.type} status-${liveStatus} ${selectedNodeId === n.id ? "selected" : ""} ${highlightedNodeIds.has(n.id) ? "highlighted" : ""} ${selectedNodeId && !highlightedNodeIds.has(n.id) ? "faded" : ""}" data-id="${n.id}">
          <rect x="${n.x}" y="${n.y}" rx="16" ry="16" width="180" height="84"></rect>
          <circle cx="${n.x + 18}" cy="${n.y + 22}" r="6"></circle>
          <text
            x="${n.x + 34}"
            y="${n.y + 26}"
            class="infra-node-title"
          >
            ${shortLabel(canvasDisplayName(n), 20)}
          </text>

          <text
            x="${n.x + 16}"
            y="${n.y + 54}"
            class="infra-node-type"
          >
            ${canvasDisplayType(n)}
          </text>

          <text
            x="${n.x + 16}"
            y="${n.y + 73}"
            class="infra-node-metric"
          >
            ${canvasDisplayMetric(n)}
          </text>
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
    el.addEventListener("click", async event => {
      event.stopPropagation();

      const clickedId = el.dataset.id;
      const canvasNode = nodes.find(node =>
        node.id === clickedId
      );

      if (canvasNode?.properties?.syntheticCluster) {
        const poolNodeId =
          canvasNode.properties.poolNodeId;

        expandedPoolClusters.add(poolNodeId);
        renderCanvas();
        return;
      }

      /*
       * In Overview mode, clicking an expanded pool collapses its
       * individual miners back into the cluster.
       */
      if (
        canvasModel.mode === "overview" &&
        expandedPoolClusters.has(clickedId)
      ) {
        expandedPoolClusters.delete(clickedId);
        renderCanvas();
        return;
      }

      selectedNodeId = clickedId;

      await loadImpactHighlight(
        selectedNodeId
      );

      renderCanvas();
      renderNodes();
      renderRelationships();

      const node = nodeById(selectedNodeId);
      const impact = await fetchImpact(
        selectedNodeId
      );

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

      if (!node) {
        return;
      }

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

function inventoryIp(node) {
  const props = node?.properties || {};

  return (
    props.ip ||
    props.assetIp ||
    props.host ||
    props.poolHost ||
    ""
  );
}

function inventoryWorker(node) {
  if (inventoryCategory(node) !== "asic") {
    return null;
  }

  const props = node?.properties || {};
  const ip = inventoryIp(node);

  return liveWorkers.find(worker =>
    worker.assetName === node.label ||
    worker.assetIp === ip ||
    worker.workerId === props.workerId ||
    worker.workerName === props.workerName ||
    worker.name === props.workerName
  ) || null;
}

function scalarValue(value, preferredKeys = []) {
  if (value === undefined || value === null || value === "") return "";

  if (typeof value === "string" || typeof value === "number") {
    return String(value);
  }

  if (typeof value === "object") {
    for (const key of preferredKeys) {
      if (value[key] !== undefined && value[key] !== null) {
        return scalarValue(value[key], preferredKeys);
      }
    }

    for (const key of ["symbol", "name", "id", "label", "value"]) {
      if (value[key] !== undefined && value[key] !== null) {
        return scalarValue(value[key], preferredKeys);
      }
    }
  }

  return "";
}

function coinDisplay(value) {
  const raw = scalarValue(value, ["symbol", "ticker", "code", "name"])
    .trim();

  if (!raw) return "";

  const lower = raw.toLowerCase();

  if (lower === "bch" || lower.includes("bitcoin cash")) {
    return "Bitcoin Cash";
  }

  if (lower === "btc" || lower === "bitcoin") {
    return "Bitcoin";
  }

  return raw.toUpperCase();
}

function shortWorkerId(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";

  /*
   * MiningCore workers commonly arrive as wallet.001 or a long wallet
   * followed by .001. The operator-facing inventory only needs the suffix.
   */
  const dotParts = raw.split(".");
  const suffix = dotParts[dotParts.length - 1];

  if (/^[a-z0-9_-]{1,16}$/i.test(suffix)) {
    return suffix;
  }

  const trailingNumber = raw.match(/(?:worker[-_ ]?)?(\d{1,6})$/i);
  if (trailingNumber) {
    return trailingNumber[1].padStart(3, "0");
  }

  return raw.length > 16
    ? `${raw.slice(0, 8)}…`
    : raw;
}

function inventorySecondaryText(node) {
  const category = inventoryCategory(node);
  const props = node?.properties || {};
  const ip = inventoryIp(node);
  const worker = inventoryWorker(node);

  if (category === "asic") {
    const workerValue =
      worker?.workerId ||
      worker?.workerName ||
      worker?.name ||
      props.workerId ||
      props.workerName ||
      "";

    const workerId = shortWorkerId(workerValue);

    const pool = scalarValue(
      worker?.poolId ||
      worker?.pool ||
      props.poolGroup ||
      props.poolId ||
      "",
      ["id", "name"]
    );

    return [
      ip,
      workerId ? `Worker ${workerId}` : "",
      pool ? `Pool ${pool.toUpperCase()}` : ""
    ].filter(Boolean).join(" · ");
  }

  if (category === "pool") {
    const mode = scalarValue(
      props.mode ||
      props.visibility ||
      props.poolMode ||
      ""
    );

    const coin = coinDisplay(
      props.coin ||
      props.symbol ||
      props.coinSymbol ||
      props.id ||
      ""
    );

    return [
      coin,
      mode ? mode.toUpperCase() : "",
      ip
    ].filter(Boolean).join(" · ");
  }

  if (category === "blockchain") {
    const ports = inventoryOpenPorts(node);
    const chain = coinDisplay(
      props.chain ||
      props.coin ||
      props.symbol ||
      props.coinSymbol ||
      ""
    );

    const rpcPort =
      Number(props.rpcPort) ||
      (ports.includes(8332) ? 8332 : "");

    const p2pPort =
      Number(props.p2pPort) ||
      (ports.includes(8333) ? 8333 : "");

    const rpcConnected =
      props.rpcConnected === true ||
      String(props.rpcStatus || "").toLowerCase() === "connected" ||
      String(props.rpcStatus || "").toLowerCase() === "online";

    return [
      ip,
      chain || "Bitcoin",
      rpcPort ? `RPC ${rpcPort}` : "",
      p2pPort ? `P2P ${p2pPort}` : "",
      rpcConnected ? "RPC Connected" : ""
    ].filter(Boolean).join(" · ");
  }

  return [
    ip,
    scalarValue(props.hostname || props.hostName || "")
  ].filter(Boolean).join(" · ");
}

function inventoryMetric(node) {
  const category = inventoryCategory(node);
  const hashrate = liveHashrateForNode(node);

  if ((category === "asic" || category === "pool") && hashrate > 0) {
    return formatHashrate(hashrate);
  }

  return safe(liveNodeStatus(node), node.status || "unknown").toUpperCase();
}

function inventoryDisplayName(node) {
  const category = inventoryCategory(node);
  const label = String(node?.label || node?.id || "Unknown Asset");

  if (
    category === "blockchain" &&
    (
      label.toLowerCase().includes("unknown") ||
      label.toLowerCase().includes("system")
    )
  ) {
    return blockchainDisplayName(node);
  }

  return label;
}

function renderNodes() {
  const nodes = filteredNodes();
  const target = byId("graphNodes");

  if (!nodes.length) {
    target.innerHTML = `
      <div class="empty-state">
        <h3>No infrastructure assets match.</h3>
        <p>Try another filter or clear the graph search.</p>
      </div>
    `;
    return;
  }

  target.innerHTML = nodes.map(node => {
    const category = inventoryCategory(node);
    const secondary = inventorySecondaryText(node);

    return `
      <button
        class="graph-node inventory-node inventory-${category} ${selectedNodeId === node.id ? "active" : ""}"
        data-id="${node.id}"
      >
        <div class="inventory-node-main">
          <strong>${inventoryDisplayName(node)}</strong>
          <span>${secondary || node.id}</span>
        </div>

        <div class="inventory-node-status">
          <b>${inventoryTypeLabel(node)}</b>
          <small>${inventoryMetric(node)}</small>
        </div>
      </button>
    `;
  }).join("");

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
    const worker = liveWorkers.find(worker =>
      worker.assetName === node.label ||
      worker.displayName === node.label ||
      worker.assetIp === props.ip ||
      shortWorkerId(
        worker.workerName ||
        worker.name ||
        worker.workerId
      ) === shortWorkerId(
        props.workerId ||
        props.liveWorkerId
      )
    );

    return Number(
      worker?.hashrate ||
      worker?.hashRate ||
      props.liveHashrate ||
      0
    );
  }

  if (node.type === "pool") {
    const poolId = String(
      props.id ||
      props.poolId ||
      ""
    ).toLowerCase();

    const poolHost = String(
      props.host ||
      props.poolHost ||
      ""
    );

    return liveWorkers
      .filter(worker => {
        const workerPoolId = String(
          worker.poolId ||
          worker.pool ||
          ""
        ).toLowerCase();

        const workerPoolHost = String(
          worker.poolHost ||
          worker.host ||
          ""
        );

        const workerPoolSuffix =
          workerPoolId.split("-").pop();

        const idMatches = (
          workerPoolId === poolId ||
          workerPoolId.endsWith(`-${poolId}`) ||
          workerPoolSuffix === poolId
        );

        const hostMatches = (
          !poolHost ||
          workerPoolHost === poolHost
        );

        return idMatches && hostMatches;
      })
      .reduce(
        (sum, worker) =>
          sum + Number(
            worker.hashrate ||
            worker.hashRate ||
            0
          ),
        0
      );
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


function inspectorEdges(nodeId) {
  return graph.edges.filter(edge =>
    edge.source === nodeId || edge.target === nodeId
  );
}

function inspectorRelatedNodes(nodeId) {
  return inspectorEdges(nodeId).map(edge => {
    const otherId =
      edge.source === nodeId
        ? edge.target
        : edge.source;

    return {
      edge,
      node: nodeById(otherId),
      direction:
        edge.source === nodeId
          ? "outgoing"
          : "incoming"
    };
  });
}

function inspectorPortList(node) {
  const ports = inventoryOpenPorts(node);

  return ports.length
    ? ports.join(", ")
    : "Not reported";
}

function inspectorRpcState(node) {
  const props = node?.properties || {};
  const ports = inventoryOpenPorts(node);

  if (
    props.rpcConnected === true ||
    String(props.rpcStatus || "").toLowerCase() === "connected" ||
    String(props.rpcStatus || "").toLowerCase() === "online"
  ) {
    return "Connected";
  }

  if (
    ports.includes(8332) ||
    ports.includes(9002) ||
    ports.includes(9332)
  ) {
    return "Port detected";
  }

  return "Not verified";
}

function inspectorPoolWorkers(node) {
  if (inventoryCategory(node) !== "pool") {
    return [];
  }

  const props = node?.properties || {};
  const poolId = String(
    props.id ||
    props.poolId ||
    ""
  ).toLowerCase();

  const poolHost = String(
    props.host ||
    props.poolHost ||
    ""
  );

  return liveWorkers.filter(worker => {
    const workerPool = String(
      worker.poolId ||
      worker.pool ||
      ""
    ).toLowerCase();

    const workerHost = String(
      worker.poolHost ||
      worker.host ||
      ""
    );

    const poolMatches =
      !poolId ||
      workerPool === poolId ||
      workerPool.includes(poolId) ||
      poolId.includes(workerPool);

    const hostMatches =
      !poolHost ||
      !workerHost ||
      workerHost === poolHost;

    return poolMatches && hostMatches;
  });
}

function inspectorWorkerForAsic(node) {
  const props = node?.properties || {};
  const assetIp = inventoryIp(node);

  return liveWorkers.find(worker =>
    worker.assetName === node.label ||
    worker.assetIp === assetIp ||
    shortWorkerId(worker.workerName || worker.name) ===
      shortWorkerId(props.workerId || props.workerName)
  ) || null;
}

function inspectorCoin(node) {
  const props = node?.properties || {};

  return coinDisplay(
    props.coin ||
    props.symbol ||
    props.coinSymbol ||
    props.chain ||
    ""
  ) || "Unknown";
}

function inspectorStatusClass(status) {
  const normalized = String(status || "").toLowerCase();

  if (
    normalized === "online" ||
    normalized === "healthy" ||
    normalized === "mining" ||
    normalized === "connected"
  ) {
    return "good";
  }

  if (
    normalized === "warning" ||
    normalized === "degraded" ||
    normalized === "idle"
  ) {
    return "warning";
  }

  return "";
}

function inspectorIdentitySection(node) {
  const props = node?.properties || {};

  return `
    <section class="digital-twin-section">
      <div class="digital-twin-section-head">
        <h3>Identity</h3>
        <span>${inventoryTypeLabel(node)}</span>
      </div>

      <div class="digital-twin-grid">
        <div class="digital-twin-field">
          <label>Asset ID</label>
          <strong>${safe(node?.id)}</strong>
        </div>

        <div class="digital-twin-field">
          <label>IP Address</label>
          <strong>${safe(inventoryIp(node), "Not set")}</strong>
        </div>

        <div class="digital-twin-field">
          <label>Canonical Type</label>
          <strong>${safe(props.assetType || node?.type)}</strong>
        </div>

        <div class="digital-twin-field">
          <label>Lifecycle</label>
          <strong>${safe(props.lifecycleStatus, "Managed")}</strong>
        </div>

        <div class="digital-twin-field">
          <label>Coin</label>
          <strong>${inspectorCoin(node)}</strong>
        </div>

        <div class="digital-twin-field">
          <label>Open Ports</label>
          <strong>${inspectorPortList(node)}</strong>
        </div>
      </div>
    </section>
  `;
}

function inspectorAsicSection(node) {
  const props = node?.properties || {};
  const worker = inspectorWorkerForAsic(node);
  const hashrate = liveHashrateForNode(node);

  const workerName = shortWorkerId(
    worker?.workerName ||
    worker?.name ||
    props.workerId ||
    props.workerName
  );

  const pool = safe(
    worker?.poolId ||
    props.poolId ||
    props.poolGroup,
    "Not assigned"
  );

  const shares = Number(
    worker?.sharesPerSecond ||
    worker?.shares_per_second ||
    0
  );

  return `
    <section class="digital-twin-section">
      <div class="digital-twin-section-head">
        <h3>ASIC Telemetry</h3>
        <span class="${hashrate > 0 ? "good" : "warning"}">
          ${hashrate > 0 ? "MINING" : "IDLE"}
        </span>
      </div>

      <div class="digital-twin-grid">
        <div class="digital-twin-field metric-primary">
          <label>Hashrate</label>
          <strong>${formatHashrate(hashrate)}</strong>
        </div>

        <div class="digital-twin-field">
          <label>Worker</label>
          <strong>${workerName || "Not reported"}</strong>
        </div>

        <div class="digital-twin-field">
          <label>Pool</label>
          <strong>${pool}</strong>
        </div>

        <div class="digital-twin-field">
          <label>Shares / Second</label>
          <strong>${shares.toFixed(3)}</strong>
        </div>

        <div class="digital-twin-field">
          <label>Pool Host</label>
          <strong>${safe(
            worker?.poolHost ||
            props.poolHost,
            "Not reported"
          )}</strong>
        </div>

        <div class="digital-twin-field">
          <label>Live Worker</label>
          <strong class="${worker ? "good" : "warning"}">
            ${worker ? "Connected" : "Not matched"}
          </strong>
        </div>
      </div>
    </section>
  `;
}

function miningReadinessStatusLabel(status) {
  const labels = {
    ready: "READY TO MINE",
    "idle-ready": "READY · IDLE",
    degraded: "DEGRADED",
    blocked: "BLOCKED"
  };

  return labels[status] || "UNKNOWN";
}

function miningReadinessStatusClass(status) {
  if (status === "ready" || status === "idle-ready") {
    return "good";
  }

  if (status === "degraded") {
    return "warning";
  }

  return "risk-high";
}

function miningReadinessCheckIcon(status) {
  if (status === "healthy") return "✓";
  if (status === "warning") return "!";
  if (status === "failed") return "×";

  return "?";
}

function inspectorPoolSection(node) {
  const props = node?.properties || {};
  const readiness = props.miningReadiness || null;
  const workers = inspectorPoolWorkers(node);

  const workerHashrate = workers.reduce(
    (sum, worker) =>
      sum + Number(worker.hashrate || worker.hashRate || 0),
    0
  );

  const totalHashrate = Number(
    readiness?.hashrate ?? workerHashrate
  );

  const connectedMiners = Number(
    readiness?.connectedMiners ?? workers.length
  );

  const readinessStatus =
    readiness?.status ||
    (totalHashrate > 0 ? "ready" : "degraded");

  return `
    <section class="digital-twin-section">
      <div class="digital-twin-section-head">
        <h3>Mining Operations</h3>

        <span class="${miningReadinessStatusClass(readinessStatus)}">
          ${miningReadinessStatusLabel(readinessStatus)}
        </span>
      </div>

      <div class="digital-twin-grid">
        <div class="digital-twin-field metric-primary">
          <label>Pool Hashrate</label>
          <strong>${formatHashrate(totalHashrate)}</strong>
        </div>

        <div class="digital-twin-field metric-primary">
          <label>Readiness Score</label>
          <strong>
            ${
              readiness
                ? `${readiness.readinessScore}%`
                : "Checking"
            }
          </strong>
        </div>

        <div class="digital-twin-field">
          <label>Connected Miners</label>
          <strong>${connectedMiners}</strong>
        </div>

        <div class="digital-twin-field">
          <label>Share Flow</label>
          <strong>
            ${
              readiness
                ? `${Number(
                    readiness.sharesPerSecond || 0
                  ).toFixed(3)} / sec`
                : "Not reported"
            }
          </strong>
        </div>

        <div class="digital-twin-field">
          <label>Coin</label>
          <strong>
            ${safe(
              readiness?.coin ||
              inspectorCoin(node),
              "Unknown"
            )}
          </strong>
        </div>

        <div class="digital-twin-field">
          <label>Mode</label>
          <strong>
            ${safe(
              readiness?.mode ||
              props.mode ||
              props.visibility,
              "Unknown"
            ).toUpperCase()}
          </strong>
        </div>

        <div class="digital-twin-field">
          <label>Blockchain Node</label>
          <strong>
            ${safe(
              readiness?.blockchainName,
              "Not linked"
            )}
          </strong>
        </div>

        <div class="digital-twin-field">
          <label>Blockchain RPC</label>
          <strong class="${
            readiness?.blockchainRpcConnected
              ? "good"
              : "warning"
          }">
            ${
              readiness?.blockchainRpcConnected
                ? "Connected"
                : "Not connected"
            }
          </strong>
        </div>

        <div class="digital-twin-field">
          <label>Block Height</label>
          <strong>
            ${
              readiness?.blockHeight
                ? Number(
                    readiness.blockHeight
                  ).toLocaleString()
                : "Not reported"
            }
          </strong>
        </div>

        <div class="digital-twin-field">
          <label>Peers</label>
          <strong>
            ${readiness?.peerCount ?? "Not reported"}
          </strong>
        </div>

        <div class="digital-twin-field">
          <label>Stratum Ports</label>
          <strong>
            ${
              readiness?.stratumPorts?.length
                ? readiness.stratumPorts.join(", ")
                : "Not reported"
            }
          </strong>
        </div>

        <div class="digital-twin-field">
          <label>Active Mining</label>
          <strong class="${
            readiness?.activeMining
              ? "good"
              : "warning"
          }">
            ${readiness?.activeMining ? "Yes" : "No"}
          </strong>
        </div>
      </div>

      <div class="mining-readiness-checks">
        ${
          (readiness?.checks || []).map(check => `
            <div class="mining-readiness-check status-${check.status}">
              <span class="mining-readiness-icon">
                ${miningReadinessCheckIcon(check.status)}
              </span>

              <div>
                <strong>${check.label}</strong>
                <small>${check.detail}</small>
              </div>
            </div>
          `).join("") ||
          `
            <div class="mining-readiness-check status-unknown">
              <span class="mining-readiness-icon">…</span>
              <div>
                <strong>Readiness Engine</strong>
                <small>Waiting for operational readiness data.</small>
              </div>
            </div>
          `
        }
      </div>

      <div class="digital-twin-mini-list">
        ${
          workers.map((worker, index) => `
            <div>
              <span>
                ${safe(
                  worker.assetName ||
                  worker.displayName ||
                  `Miner ${index + 1}`
                )}
              </span>

              <b>
                ${formatHashrate(
                  Number(
                    worker.hashrate ||
                    worker.hashRate ||
                    0
                  )
                )}
              </b>
            </div>
          `).join("") ||
          "<p>No live miners matched to this pool.</p>"
        }
      </div>

      <div class="digital-twin-recommendation ${
        readiness?.readyToMine
          ? "digital-twin-healthy"
          : ""
      }">
        <strong>
          ${
            readiness?.readyToMine
              ? "Mining Readiness"
              : "Recommended Action"
          }
        </strong>

        <span>
          ${
            readiness?.recommendation ||
            "Readiness data is not available yet."
          }
        </span>
      </div>
    </section>
  `;
}

function digitalTwinFormatBytes(value) {
  const bytes = Number(value || 0);

  if (!bytes) return "Not reported";

  const units = ["B", "KB", "MB", "GB", "TB", "PB"];
  let amount = bytes;
  let index = 0;

  while (amount >= 1024 && index < units.length - 1) {
    amount /= 1024;
    index += 1;
  }

  return `${amount.toFixed(index >= 3 ? 2 : 1)} ${units[index]}`;
}

function digitalTwinFormatNumber(value, digits = 0) {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return "Not reported";
  }

  return number.toLocaleString(undefined, {
    maximumFractionDigits: digits
  });
}

function digitalTwinCoreVersion(props) {
  if (props.subversion) {
    return String(props.subversion)
      .replaceAll("/", "")
      .replace("Satoshi:", "");
  }

  const version = Number(props.version || 0);

  if (!version) return "Not reported";

  const major = Math.floor(version / 10000);
  const minor = Math.floor((version % 10000) / 100);
  const patch = version % 100;

  return `${major}.${minor}.${patch}`;
}

function digitalTwinCheckedAge(value) {
  const timestamp = Number(value || 0);

  if (!timestamp) return "Not reported";

  const seconds = Math.max(
    0,
    Math.floor((Date.now() - timestamp) / 1000)
  );

  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;

  return `${Math.floor(seconds / 3600)}h ago`;
}

function inspectorBlockchainSection(node) {
  const props = node?.properties || {};
  const rpcState = inspectorRpcState(node);

  const syncPercent = Number(
    props.syncPercent ||
    props.syncPercentage ||
    props.verificationProgress ||
    props.verificationprogress ||
    0
  );

  const normalizedSync =
    syncPercent > 0 && syncPercent <= 1
      ? syncPercent * 100
      : syncPercent;

  const isSynced =
    props.initialBlockDownload === false &&
    normalizedSync >= 99.99 &&
    Number(props.blocks || 0) === Number(props.headers || 0);

  const warningText = props.error
    ? props.error
    : rpcState !== "Connected"
      ? "Verify RPC credentials and connectivity to unlock live blockchain telemetry."
      : !isSynced
        ? "The node is reachable but has not finished synchronizing."
        : "";

  return `
    <section class="digital-twin-section">
      <div class="digital-twin-section-head">
        <h3>Blockchain Operations</h3>
        <span class="${
          rpcState === "Connected" && isSynced
            ? "good"
            : "warning"
        }">
          ${
            rpcState === "Connected"
              ? isSynced
                ? "RPC CONNECTED · SYNCED"
                : "RPC CONNECTED · SYNCING"
              : `RPC ${rpcState.toUpperCase()}`
          }
        </span>
      </div>

      <div class="digital-twin-grid">
        <div class="digital-twin-field metric-primary">
          <label>Sync</label>
          <strong>
            ${
              normalizedSync > 0
                ? `${normalizedSync.toFixed(6)}%`
                : "Awaiting RPC"
            }
          </strong>
        </div>

        <div class="digital-twin-field">
          <label>RPC</label>
          <strong class="${inspectorStatusClass(rpcState)}">
            ${rpcState}
          </strong>
        </div>

        <div class="digital-twin-field">
          <label>Block Height</label>
          <strong>
            ${digitalTwinFormatNumber(
              props.blocks ||
              props.blockHeight ||
              props.height
            )}
          </strong>
        </div>

        <div class="digital-twin-field">
          <label>Headers</label>
          <strong>
            ${digitalTwinFormatNumber(props.headers)}
          </strong>
        </div>

        <div class="digital-twin-field">
          <label>Peers</label>
          <strong>
            ${digitalTwinFormatNumber(
              props.connections ||
              props.peers ||
              props.peerCount
            )}
          </strong>
        </div>

        <div class="digital-twin-field">
          <label>Version</label>
          <strong>${digitalTwinCoreVersion(props)}</strong>
        </div>

        <div class="digital-twin-field">
          <label>Chain</label>
          <strong>
            ${safe(props.chain, inspectorCoin(node)).toUpperCase()}
          </strong>
        </div>

        <div class="digital-twin-field">
          <label>Network</label>
          <strong class="${props.networkActive === false ? "warning" : "good"}">
            ${props.networkActive === false ? "Inactive" : "Active"}
          </strong>
        </div>

        <div class="digital-twin-field">
          <label>Disk Used</label>
          <strong>
            ${digitalTwinFormatBytes(props.sizeOnDisk)}
          </strong>
        </div>

        <div class="digital-twin-field">
          <label>Pruned</label>
          <strong>${props.pruned === true ? "Yes" : "No"}</strong>
        </div>

        <div class="digital-twin-field">
          <label>Mempool Transactions</label>
          <strong>
            ${digitalTwinFormatNumber(props.mempoolSize)}
          </strong>
        </div>

        <div class="digital-twin-field">
          <label>Mempool Data</label>
          <strong>
            ${digitalTwinFormatBytes(props.mempoolBytes)}
          </strong>
        </div>

        <div class="digital-twin-field">
          <label>Difficulty</label>
          <strong>
            ${digitalTwinFormatNumber(props.difficulty, 2)}
          </strong>
        </div>

        <div class="digital-twin-field">
          <label>Initial Block Download</label>
          <strong class="${props.initialBlockDownload ? "warning" : "good"}">
            ${props.initialBlockDownload ? "Yes" : "No"}
          </strong>
        </div>

        <div class="digital-twin-field">
          <label>Protocol</label>
          <strong>
            ${digitalTwinFormatNumber(props.protocolVersion)}
          </strong>
        </div>

        <div class="digital-twin-field">
          <label>Telemetry Updated</label>
          <strong>
            ${digitalTwinCheckedAge(props.checkedAt)}
          </strong>
        </div>
      </div>

      ${
        warningText
          ? `
            <div class="digital-twin-recommendation">
              <strong>Recommended Action</strong>
              <span>${warningText}</span>
            </div>
          `
          : `
            <div class="digital-twin-recommendation digital-twin-healthy">
              <strong>Mining Ready</strong>
              <span>
                Bitcoin Core is connected, synchronized, network-active,
                and ready to provide RPC services to Seymour MiningCore.
              </span>
            </div>
          `
      }
    </section>
  `;
}

function inspectorServerSection(node) {
  const props = node?.properties || {};

  return `
    <section class="digital-twin-section">
      <div class="digital-twin-section-head">
        <h3>Server Operations</h3>
        <span class="${inspectorStatusClass(node?.status)}">
          ${safe(node?.status, "online").toUpperCase()}
        </span>
      </div>

      <div class="digital-twin-grid">
        <div class="digital-twin-field">
          <label>Hostname</label>
          <strong>${safe(
            props.hostname ||
            props.profile?.hostname,
            "Not resolved"
          )}</strong>
        </div>

        <div class="digital-twin-field">
          <label>Primary Role</label>
          <strong>${safe(
            props.primaryRole,
            "Infrastructure Server"
          )}</strong>
        </div>

        <div class="digital-twin-field">
          <label>Open Ports</label>
          <strong>${inspectorPortList(node)}</strong>
        </div>

        <div class="digital-twin-field">
          <label>Health</label>
          <strong>${safe(
            props.health?.label ||
            props.health?.level ||
            node?.status,
            "Unknown"
          )}</strong>
        </div>
      </div>
    </section>
  `;
}

function inspectorOperationalSection(node, impact) {
  const related = inspectorRelatedNodes(node.id);
  const affectedTypes = impact?.affectedByType || {};

  return `
    <section class="digital-twin-section">
      <div class="digital-twin-section-head">
        <h3>Operational Impact</h3>
        <span class="risk-${safe(impact?.risk, "unknown").toLowerCase()}">
          ${safe(impact?.risk, "Unknown").toUpperCase()}
        </span>
      </div>

      <div class="digital-twin-grid">
        <div class="digital-twin-field metric-primary">
          <label>Estimated Hashrate Impact</label>
          <strong>${formatHashrate(
            impact?.estimatedHashrateLoss || 0
          )}</strong>
        </div>

        <div class="digital-twin-field">
          <label>Affected Objects</label>
          <strong>${impact?.affectedCount ?? 0}</strong>
        </div>

        <div class="digital-twin-field">
          <label>Direct Relationships</label>
          <strong>${related.length}</strong>
        </div>

        <div class="digital-twin-field">
          <label>Affected Types</label>
          <strong>
            ${
              Object.entries(affectedTypes)
                .map(([type, count]) => `${type}: ${count}`)
                .join(", ") ||
              "None"
            }
          </strong>
        </div>
      </div>

      <div class="digital-twin-relationships">
        ${
          related.map(item => `
            <button
              type="button"
              class="digital-twin-related"
              data-related-node="${item.node?.id || ""}"
            >
              <span>
                ${safe(
                  item.edge.label ||
                  item.edge.type
                )}
              </span>

              <strong>
                ${safe(
                  item.node?.label,
                  item.node?.id || "Unknown"
                )}
              </strong>
            </button>
          `).join("") ||
          "<p>No direct relationships recorded.</p>"
        }
      </div>
    </section>
  `;
}

function bindInspectorRelationships() {
  document
    .querySelectorAll("[data-related-node]")
    .forEach(button => {
      button.addEventListener("click", async () => {
        const nodeId = button.dataset.relatedNode;
        const node = nodeById(nodeId);

        if (!node) return;

        selectedNodeId = nodeId;
        await loadImpactHighlight(nodeId);

        renderCanvas();
        renderNodes();
        renderRelationships();

        const impact = await fetchImpact(nodeId);
        openInspector(node, impact);
      });
    });
}

async function fetchSelectedMiningReadiness(node) {
  const nodeId = String(node?.id || "");
  const props = node?.properties || {};

  const poolId = String(
    props.id ||
    props.poolId ||
    ""
  ).toLowerCase();

  const host = String(
    props.host ||
    props.poolHost ||
    ""
  );

  try {
    const response = await fetch(
      "/api/operations/mining-readiness",
      {
        cache: "no-store"
      }
    );

    if (!response.ok) {
      throw new Error(
        `/api/operations/mining-readiness returned ${response.status}`
      );
    }

    const payload = await response.json();
    const items = Array.isArray(payload.items)
      ? payload.items
      : [];

    return items.find(item => {
      const itemPoolId = String(
        item.poolId || ""
      ).toLowerCase();

      const itemHost = String(item.host || "");

      if (item.poolNodeId === nodeId) {
        return true;
      }

      const poolMatches =
        poolId &&
        itemPoolId &&
        (
          itemPoolId === poolId ||
          itemPoolId.endsWith(poolId) ||
          poolId.endsWith(itemPoolId)
        );

      const hostMatches =
        !host ||
        !itemHost ||
        itemHost === host;

      return poolMatches && hostMatches;
    }) || null;
  } catch (error) {
    console.error(
      "Selected mining-readiness request failed:",
      error
    );

    return null;
  }
}

async function fetchSelectedBlockchainTelemetry(node) {
  const assetId = String(
    node?.properties?.managedAssetId ||
    node?.properties?.id ||
    node?.id ||
    ""
  );

  const ip = String(
    inventoryIp(node) ||
    node?.properties?.ip ||
    ""
  );

  try {
    const response = await fetch(
      "/api/blockchain/nodes",
      {
        cache: "no-store"
      }
    );

    if (!response.ok) {
      throw new Error(
        `/api/blockchain/nodes returned ${response.status}`
      );
    }

    const payload = await response.json();
    const items = Array.isArray(payload.items)
      ? payload.items
      : [];

    const telemetry = items.find(item => {
      const telemetryAssetId = String(item?.assetId || "");
      const telemetryHost = String(item?.host || "");

      return (
        (assetId && telemetryAssetId === assetId) ||
        (ip && telemetryHost === ip)
      );
    });

    if (!telemetry) {
      console.warn(
        "No blockchain telemetry matched selected asset",
        {
          assetId,
          ip,
          items
        }
      );

      return null;
    }

    return telemetry;
  } catch (error) {
    console.error(
      "Selected blockchain telemetry request failed:",
      error
    );

    return null;
  }
}


function infrastructureActionCatalog(node) {
  const category = inventoryCategory(node);
  const props = node?.properties || {};
  const rpcConnected =
    props.rpcConnected === true ||
    String(props.rpcStatus || "").toLowerCase() === "connected";

  if (category === "blockchain") {
    return [
      {
        id: "test-rpc",
        operationAction: "bitcoin.rpc.test",
        label: "Test RPC",
        icon: "↔",
        tone: rpcConnected ? "healthy" : "warning",
        description:
          "Verify credentials, network access, RPC response, chain, and sync state.",
        steps: [
          "Connect to the configured RPC endpoint",
          "Authenticate using the stored Nexus credential",
          "Run getblockchaininfo",
          "Run getnetworkinfo",
          "Verify block height and headers",
          "Report RPC and synchronization health"
        ]
      },
      {
        id: "repair-rpc",
        label: rpcConnected ? "Repair RPC" : "Enable RPC",
        icon: "⚙",
        tone: rpcConnected ? "default" : "warning",
        description:
          "Inspect and repair rpcbind, rpcallowip, credentials, and firewall access.",
        steps: [
          "Identify the Bitcoin Core installation method",
          "Locate the active bitcoin.conf",
          "Back up the current configuration",
          "Verify server, rpcbind, rpcallowip, and rpcport",
          "Verify Nexus RPC credentials",
          "Check the host firewall",
          "Restart bitcoind only when changes are required",
          "Retest RPC from Nexus"
        ]
      },
      {
        id: "restart-service",
        label: "Restart Bitcoin",
        icon: "↻",
        tone: "danger",
        description:
          "Restart the Bitcoin Core service and verify that it returns healthy.",
        steps: [
          "Confirm the active bitcoind service",
          "Capture current service status",
          "Restart Bitcoin Core",
          "Wait for RPC availability",
          "Verify chain, peers, and synchronization",
          "Record the action in Mission Timeline"
        ]
      },
      {
        id: "view-logs",
        label: "View Logs",
        icon: "≡",
        tone: "default",
        description:
          "Open recent Bitcoin Core and system service events.",
        steps: [
          "Read recent bitcoind service events",
          "Read Bitcoin Core debug log",
          "Highlight RPC, peer, disk, and chain warnings",
          "Show the newest events first"
        ]
      },
      {
        id: "backup-wallet",
        label: "Backup Wallet",
        icon: "⬇",
        tone: "default",
        description:
          "Create and verify a timestamped wallet backup.",
        steps: [
          "List loaded wallets",
          "Select the pool wallet",
          "Create an encrypted timestamped backup",
          "Verify the backup file",
          "Record its location and checksum"
        ]
      },
      {
        id: "open-config",
        label: "Open Config",
        icon: "{}",
        tone: "default",
        description:
          "Review the active Bitcoin Core configuration with secrets hidden.",
        steps: [
          "Locate the active bitcoin.conf",
          "Read the effective configuration",
          "Mask passwords and authentication secrets",
          "Highlight risky or conflicting values"
        ]
      }
    ];
  }

  if (category === "pool") {
    return [
      {
        id: "test-pool",
        operationAction: "miningcore.pool.readiness",
        label: "Run Readiness Test",
        icon: "✓",
        tone: "healthy",
        description:
          "Verify the complete mining path from blockchain node through stratum.",
        steps: [
          "Test MiningCore API",
          "Verify blockchain RPC",
          "Verify blockchain synchronization",
          "Check stratum listeners",
          "Check connected miners",
          "Confirm live hashrate and share flow",
          "Calculate mining readiness"
        ]
      },
      {
        id: "restart-pool",
        label: "Restart Pool",
        icon: "↻",
        tone: "danger",
        description:
          "Restart the selected MiningCore pool and validate recovery.",
        steps: [
          "Capture current pool health",
          "Confirm active miners",
          "Restart the MiningCore service or pool process",
          "Verify API recovery",
          "Verify stratum recovery",
          "Confirm miners reconnect"
        ]
      },
      {
        id: "view-pool-config",
        label: "Pool Config",
        icon: "{}",
        tone: "default",
        description:
          "Review coin, wallet, ports, payout, fee, and daemon settings.",
        steps: [
          "Load the active pool configuration",
          "Mask wallet and RPC secrets",
          "Validate the pool schema",
          "Highlight conflicting ports or missing values"
        ]
      },
      {
        id: "view-pool-logs",
        label: "View Logs",
        icon: "≡",
        tone: "default",
        description:
          "Show recent pool, daemon, share, payout, and stratum events.",
        steps: [
          "Read recent MiningCore logs",
          "Filter for the selected pool",
          "Highlight daemon and stratum errors",
          "Show rejected-share and payout warnings"
        ]
      },
      {
        id: "backup-pool",
        label: "Backup Pool",
        icon: "⬇",
        tone: "default",
        description:
          "Back up the pool configuration and operational metadata.",
        steps: [
          "Export the selected pool configuration",
          "Mask or encrypt secrets",
          "Include wallet and payout metadata",
          "Generate a timestamped archive",
          "Verify archive integrity"
        ]
      },
      {
        id: "repair-pool",
        label: "Repair Installation",
        icon: "⚙",
        tone: "warning",
        description:
          "Diagnose and repair common MiningCore installation problems.",
        steps: [
          "Verify service installation",
          "Verify runtime dependencies",
          "Verify PostgreSQL connectivity",
          "Validate pool configuration",
          "Verify firewall and listening ports",
          "Restart only failed components",
          "Run readiness verification"
        ]
      }
    ];
  }

  if (category === "asic") {
    return [
      {
        id: "test-miner",
        label: "Run Diagnostics",
        icon: "✓",
        tone: "healthy",
        description:
          "Check connectivity, hashrate, share flow, pool assignment, and health.",
        steps: [
          "Ping the miner",
          "Check the management interface",
          "Match the live MiningCore worker",
          "Verify pool assignment",
          "Compare actual and expected hashrate",
          "Check recent share flow"
        ]
      },
      {
        id: "reboot-miner",
        label: "Reboot Miner",
        icon: "↻",
        tone: "danger",
        description:
          "Safely reboot the ASIC and verify that it reconnects.",
        steps: [
          "Capture current hashrate and pool",
          "Request a controlled reboot",
          "Wait for network recovery",
          "Wait for worker reconnection",
          "Verify hashrate recovery",
          "Record downtime"
        ]
      },
      {
        id: "open-miner-ui",
        label: "Open Miner UI",
        icon: "↗",
        tone: "default",
        description:
          "Open the ASIC manufacturer management interface.",
        steps: [
          "Verify the management port",
          "Open the device interface",
          "Keep credentials outside the browser URL"
        ]
      },
      {
        id: "change-pool",
        label: "Change Pool",
        icon: "⇄",
        tone: "warning",
        description:
          "Move the miner to another configured pool.",
        steps: [
          "List compatible pools",
          "Validate coin and algorithm",
          "Save the current pool configuration",
          "Apply the new stratum endpoint",
          "Verify worker reconnection",
          "Confirm live hashrate"
        ]
      },
      {
        id: "firmware",
        label: "Firmware",
        icon: "⬆",
        tone: "default",
        description:
          "Inspect firmware and prepare a controlled upgrade.",
        steps: [
          "Detect manufacturer and model",
          "Read installed firmware",
          "Check compatibility",
          "Back up miner configuration",
          "Stage the upgrade",
          "Require confirmation before installation"
        ]
      },
      {
        id: "locate-miner",
        label: "Locate Miner",
        icon: "◉",
        tone: "default",
        description:
          "Identify this physical miner using its light, sound, or network identity.",
        steps: [
          "Check supported locate capabilities",
          "Blink the miner identification light when available",
          "Show IP, MAC address, site, rack, and position"
        ]
      }
    ];
  }

  return [
    {
      id: "test-connectivity",
      label: "Test Connectivity",
      icon: "↔",
      tone: "healthy",
      description:
        "Check reachability, ports, services, and host health.",
      steps: [
        "Ping the host",
        "Scan known management ports",
        "Verify expected services",
        "Report latency and connectivity"
      ]
    },
    {
      id: "open-terminal",
      label: "Open Terminal",
      icon: ">_",
      tone: "default",
      description:
        "Start a secure administrative terminal session.",
      steps: [
        "Verify SSH connectivity",
        "Confirm the managed host identity",
        "Start an audited terminal session"
      ]
    },
    {
      id: "view-server-logs",
      label: "View Logs",
      icon: "≡",
      tone: "default",
      description:
        "Show recent operating system and service events.",
      steps: [
        "Read system journal events",
        "Highlight failed services",
        "Highlight disk, memory, and network warnings"
      ]
    },
    {
      id: "restart-server",
      label: "Restart Server",
      icon: "↻",
      tone: "danger",
      description:
        "Restart the managed server after dependency and impact checks.",
      steps: [
        "Calculate blast radius",
        "Check dependent pools and services",
        "Require operator confirmation",
        "Restart the server",
        "Verify services recover"
      ]
    }
  ];
}

function infrastructureActionSection(node) {
  const actions = infrastructureActionCatalog(node);

  return `
    <section class="digital-twin-section">
      <div class="digital-twin-section-head">
        <h3>Management Actions</h3>
        <span>INFRASTRUCTURE EXPLORER</span>
      </div>

      <p class="infrastructure-action-intro">
        Configure, repair, test, and maintain this asset directly from Nexus.
      </p>

      <div class="infrastructure-action-grid">
        ${actions.map(action => `
          <button
            type="button"
            class="
              infrastructure-action
              action-tone-${action.tone || "default"}
            "
            data-infrastructure-action="${action.id}"
          >
            <span class="infrastructure-action-icon">
              ${action.icon}
            </span>

            <span class="infrastructure-action-copy">
              <strong>${action.label}</strong>
              <small>${action.description}</small>
            </span>

            <span class="infrastructure-action-arrow">›</span>
          </button>
        `).join("")}
      </div>

      <div class="infrastructure-action-note">
        <span>Preview mode</span>
        Actions show their execution plan but will not modify infrastructure yet.
      </div>
    </section>
  `;
}


function escapeOperationHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function operationTargetForNode(node) {
  const props = node?.properties || {};

  const assetId = String(
    props.assetId ||
    node?.assetId ||
    node?.id ||
    ""
  ).trim();

  const host = String(
    inventoryIp(node) ||
    props.host ||
    props.ip ||
    ""
  ).trim();

  const coin = String(
    props.coin ||
    props.symbol ||
    ""
  ).trim().toUpperCase();

  const poolId = String(
    props.poolId ||
    props.nativePoolId ||
    node?.poolId ||
    ""
  ).trim();

  const poolNodeId = String(
    props.poolNodeId ||
    node?.poolNodeId ||
    (
      inventoryCategory(node) === "pool"
        ? node?.id || ""
        : ""
    )
  ).trim();

  const target = {};

  if (assetId) target.assetId = assetId;
  if (host) target.host = host;
  if (coin) target.coin = coin;
  if (poolId) target.poolId = poolId;
  if (poolNodeId) target.poolNodeId = poolNodeId;

  return target;
}

function operationStatusClass(status) {
  switch (String(status || "").toLowerCase()) {
    case "pass":
      return "operation-status-pass";
    case "warn":
      return "operation-status-warn";
    case "fail":
    case "error":
      return "operation-status-fail";
    case "running":
      return "operation-status-running";
    default:
      return "operation-status-unknown";
  }
}

function operationStatusIcon(status) {
  switch (String(status || "").toLowerCase()) {
    case "pass":
      return "✓";
    case "warn":
      return "!";
    case "fail":
    case "error":
      return "×";
    case "running":
      return "…";
    default:
      return "?";
  }
}

function operationStatusLabel(status) {
  if (window.NexusOperations?.statusLabel) {
    return window.NexusOperations.statusLabel(status);
  }

  return String(status || "unknown");
}

function formatOperationTimestamp(value) {
  if (!value) return "Not available";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return date.toLocaleString();
}

function formatOperationDetails(details) {
  if (
    details === null ||
    details === undefined ||
    details === ""
  ) {
    return "";
  }

  if (typeof details === "string") {
    return escapeOperationHtml(details);
  }

  return escapeOperationHtml(
    JSON.stringify(details, null, 2)
  );
}

function renderOperationRunning(node, action) {
  const content = byId("infrastructureActionPreviewContent");

  if (!content) return;

  content.innerHTML = `
    <div class="action-preview-header">
      <span class="digital-twin-kicker">
        Nexus Operational Playbook
      </span>

      <h2>${escapeOperationHtml(action.label)}</h2>

      <p>
        ${escapeOperationHtml(inventoryDisplayName(node))}
        ·
        ${escapeOperationHtml(inventoryTypeLabel(node))}
        ·
        ${escapeOperationHtml(
          safe(inventoryIp(node), "No IP")
        )}
      </p>
    </div>

    <div class="
      action-preview-summary
      operation-run-summary
      operation-status-running
    ">
      <span class="operation-run-icon">…</span>

      <div>
        <strong>Running live playbook</strong>
        <small>
          Nexus is executing read-only checks against the selected asset.
        </small>
      </div>
    </div>

    <section class="operation-running-panel">
      <div class="operation-running-spinner"></div>

      <div>
        <strong>Testing RPC connectivity and health</strong>
        <small>
          Credentials remain server-side. No configuration will be changed.
        </small>
      </div>
    </section>

    <div class="action-preview-buttons">
      <button
        type="button"
        class="btn"
        data-close-action-preview
      >
        Close
      </button>

      <button
        type="button"
        class="btn btn-primary"
        disabled
      >
        Running…
      </button>
    </div>
  `;

  content
    .querySelectorAll("[data-close-action-preview]")
    .forEach(button => {
      button.addEventListener(
        "click",
        closeInfrastructureActionPreview
      );
    });
}

function renderOperationResult(node, action, result) {
  const content = byId("infrastructureActionPreviewContent");

  if (!content) return;

  const steps = Array.isArray(result?.steps)
    ? result.steps
    : [];

  const status = String(result?.status || "unknown");
  const statusClass = operationStatusClass(status);
  const statusIcon = operationStatusIcon(status);

  content.innerHTML = `
    <div class="action-preview-header">
      <span class="digital-twin-kicker">
        Nexus Operational Playbook
      </span>

      <h2>${escapeOperationHtml(
        result?.label || action.label
      )}</h2>

      <p>
        ${escapeOperationHtml(inventoryDisplayName(node))}
        ·
        ${escapeOperationHtml(inventoryTypeLabel(node))}
        ·
        ${escapeOperationHtml(
          safe(inventoryIp(node), "No IP")
        )}
      </p>
    </div>

    <div class="
      action-preview-summary
      operation-run-summary
      ${statusClass}
    ">
      <span class="operation-run-icon">
        ${statusIcon}
      </span>

      <div>
        <strong>
          ${escapeOperationHtml(
            operationStatusLabel(status)
          )}
        </strong>

        <small>
          ${escapeOperationHtml(
            result?.summary ||
            "The operational playbook completed."
          )}
        </small>
      </div>
    </div>

    <section class="operation-run-metadata">
      <div>
        <span>Started</span>
        <strong>
          ${escapeOperationHtml(
            formatOperationTimestamp(result?.startedAt)
          )}
        </strong>
      </div>

      <div>
        <span>Completed</span>
        <strong>
          ${escapeOperationHtml(
            formatOperationTimestamp(result?.completedAt)
          )}
        </strong>
      </div>

      <div>
        <span>Duration</span>
        <strong>
          ${escapeOperationHtml(
            `${result?.durationMs ?? 0} ms`
          )}
        </strong>
      </div>

      <div>
        <span>Mode</span>
        <strong>
          ${result?.readOnly === true
            ? "Read-only"
            : "Controlled action"}
        </strong>
      </div>
    </section>

    <section class="action-preview-plan operation-result-plan">
      <div class="operation-section-heading">
        <h3>Playbook Results</h3>

        <span>
          ${steps.length}
          ${steps.length === 1 ? "check" : "checks"}
        </span>
      </div>

      <ol class="operation-result-steps">
        ${steps.map((step, index) => {
          const stepStatus = String(
            step?.status || "unknown"
          );

          const stepClass =
            operationStatusClass(stepStatus);

          const details = formatOperationDetails(
            step?.details
          );

          return `
            <li class="operation-result-step ${stepClass}">
              <span class="operation-step-icon">
                ${operationStatusIcon(stepStatus)}
              </span>

              <div class="operation-step-copy">
                <div class="operation-step-title">
                  <strong>
                    ${escapeOperationHtml(
                      step?.name || `Check ${index + 1}`
                    )}
                  </strong>

                  <small>
                    ${escapeOperationHtml(
                      operationStatusLabel(stepStatus)
                    )}
                  </small>
                </div>

                ${
                  step?.summary
                    ? `
                      <p>
                        ${escapeOperationHtml(step.summary)}
                      </p>
                    `
                    : ""
                }

                ${
                  details
                    ? `
                      <details class="operation-step-details">
                        <summary>Technical details</summary>
                        <pre>${details}</pre>
                      </details>
                    `
                    : ""
                }
              </div>
            </li>
          `;
        }).join("")}
      </ol>
    </section>

    <section class="action-preview-safety">
      <h3>Execution Record</h3>

      <div>
        <span>✓</span>
        <p>
          Run ID:
          <code>${escapeOperationHtml(
            result?.runId || "Not available"
          )}</code>
        </p>
      </div>

      <div>
        <span>✓</span>
        <p>
          Credentials remained server-side and were never exposed
          to the browser.
        </p>
      </div>

      <div>
        <span>✓</span>
        <p>
          This playbook performed read-only checks and did not change
          node configuration.
        </p>
      </div>
    </section>

    <div class="action-preview-buttons">
      <button
        type="button"
        class="btn"
        data-close-action-preview
      >
        Close
      </button>

      <button
        type="button"
        class="btn btn-primary"
        data-operation-run-again
      >
        Run Again
      </button>
    </div>
  `;

  content
    .querySelectorAll("[data-close-action-preview]")
    .forEach(button => {
      button.addEventListener(
        "click",
        closeInfrastructureActionPreview
      );
    });

  content
    .querySelector("[data-operation-run-again]")
    ?.addEventListener("click", () => {
      executeInfrastructureOperation(node, action);
    });
}

function renderOperationFailure(node, action, error) {
  const content = byId("infrastructureActionPreviewContent");

  if (!content) return;

  content.innerHTML = `
    <div class="action-preview-header">
      <span class="digital-twin-kicker">
        Nexus Operational Playbook
      </span>

      <h2>${escapeOperationHtml(action.label)}</h2>

      <p>
        ${escapeOperationHtml(inventoryDisplayName(node))}
        ·
        ${escapeOperationHtml(inventoryTypeLabel(node))}
        ·
        ${escapeOperationHtml(
          safe(inventoryIp(node), "No IP")
        )}
      </p>
    </div>

    <div class="
      action-preview-summary
      operation-run-summary
      operation-status-fail
    ">
      <span class="operation-run-icon">×</span>

      <div>
        <strong>Playbook request failed</strong>
        <small>
          ${escapeOperationHtml(
            error?.message ||
            "Nexus could not execute this operation."
          )}
        </small>
      </div>
    </div>

    <section class="action-preview-safety">
      <h3>What Happened</h3>

      <div>
        <span>!</span>
        <p>
          The operation did not complete. No infrastructure changes
          were made.
        </p>
      </div>

      <div>
        <span>✓</span>
        <p>
          Verify that the Nexus API is online and that the selected
          asset still exists.
        </p>
      </div>
    </section>

    <div class="action-preview-buttons">
      <button
        type="button"
        class="btn"
        data-close-action-preview
      >
        Close
      </button>

      <button
        type="button"
        class="btn btn-primary"
        data-operation-retry
      >
        Retry
      </button>
    </div>
  `;

  content
    .querySelectorAll("[data-close-action-preview]")
    .forEach(button => {
      button.addEventListener(
        "click",
        closeInfrastructureActionPreview
      );
    });

  content
    .querySelector("[data-operation-retry]")
    ?.addEventListener("click", () => {
      executeInfrastructureOperation(node, action);
    });
}

async function executeInfrastructureOperation(node, action) {
  if (!window.NexusOperations) {
    renderOperationFailure(
      node,
      action,
      new Error(
        "The shared Nexus operations client is unavailable."
      )
    );
    return;
  }

  if (!action?.operationAction) {
    return;
  }

  renderOperationRunning(node, action);

  try {
    const result = await window.NexusOperations.run(
      action.operationAction,
      operationTargetForNode(node)
    );

    renderOperationResult(node, action, result);
  } catch (error) {
    console.error(
      "Infrastructure operation failed:",
      error
    );

    renderOperationFailure(node, action, error);
  }
}

function openInfrastructureActionPreview(node, actionId) {
  const action = infrastructureActionCatalog(node)
    .find(item => item.id === actionId);

  if (!action) return;

  const panel = byId("infrastructureActionPreview");
  const backdrop = byId("infrastructureActionBackdrop");
  const content = byId("infrastructureActionPreviewContent");

  if (!panel || !backdrop || !content) return;

  panel.classList.add("open");
  backdrop.classList.add("open");

  /*
   * Actions with a registered shared backend operation run live.
   * All actions without one remain safe preview-only playbooks.
   */
  if (action.operationAction) {
    executeInfrastructureOperation(node, action);
    return;
  }

  const plannedSteps = Array.isArray(action.steps)
    ? action.steps
    : [];

  content.innerHTML = `
    <div class="action-preview-header">
      <span class="digital-twin-kicker">
        Nexus Operational Playbook
      </span>

      <h2>${escapeOperationHtml(action.label)}</h2>

      <p>
        ${escapeOperationHtml(inventoryDisplayName(node))}
        ·
        ${escapeOperationHtml(inventoryTypeLabel(node))}
        ·
        ${escapeOperationHtml(
          safe(inventoryIp(node), "No IP")
        )}
      </p>
    </div>

    <div class="action-preview-summary">
      <span class="infrastructure-action-icon">
        ${escapeOperationHtml(action.icon)}
      </span>

      <div>
        <strong>
          ${escapeOperationHtml(action.description)}
        </strong>

        <small>
          Review the planned checks and changes before execution.
        </small>
      </div>
    </div>

    <section class="action-preview-plan">
      <h3>Execution Plan</h3>

      <ol>
        ${plannedSteps.map((step, index) => `
          <li>
            <span>${index + 1}</span>
            <strong>${escapeOperationHtml(step)}</strong>
          </li>
        `).join("")}
      </ol>
    </section>

    <section class="action-preview-safety">
      <h3>Safety Controls</h3>

      <div>
        <span>✓</span>
        <p>
          Secrets remain server-side and are never shown in browser URLs.
        </p>
      </div>

      <div>
        <span>✓</span>
        <p>
          Configuration changes require a backup before modification.
        </p>
      </div>

      <div>
        <span>✓</span>
        <p>
          Disruptive actions require impact analysis and confirmation.
        </p>
      </div>

      <div>
        <span>✓</span>
        <p>
          Every action will be recorded in Mission Timeline.
        </p>
      </div>
    </section>

    <div class="action-preview-buttons">
      <button
        type="button"
        class="btn"
        data-close-action-preview
      >
        Cancel
      </button>

      <button
        type="button"
        class="btn btn-primary"
        data-action-preview-demo
      >
        Preview Run
      </button>
    </div>
  `;

  content
    .querySelectorAll("[data-close-action-preview]")
    .forEach(button => {
      button.addEventListener(
        "click",
        closeInfrastructureActionPreview
      );
    });

  content
    .querySelector("[data-action-preview-demo]")
    ?.addEventListener("click", event => {
      const button = event.currentTarget;

      button.disabled = true;
      button.textContent = "Playbook Preview Complete";

      setTimeout(() => {
        button.disabled = false;
        button.textContent = "Preview Run";
      }, 1800);
    });
}

function closeInfrastructureActionPreview() {

  byId("infrastructureActionPreview")
    ?.classList.remove("open");

  byId("infrastructureActionBackdrop")
    ?.classList.remove("open");
}

function bindInfrastructureActions(node) {
  document
    .querySelectorAll("[data-infrastructure-action]")
    .forEach(button => {
      button.addEventListener("click", () => {
        openInfrastructureActionPreview(
          node,
          button.dataset.infrastructureAction
        );
      });
    });
}

async function openInspector(node, impact) {
  if (!node) return;

  /*
   * Always open the Digital Twin immediately.
   * Telemetry enriches it but can never block access.
   */
  byId("inspectorPanel")?.classList.add("open");
  byId("inspectorBackdrop")?.classList.add("open");

  const category = inventoryCategory(node);

  if (category === "blockchain") {
    const telemetry = await fetchSelectedBlockchainTelemetry(node);

    if (telemetry) {
      node.properties = {
        ...(node.properties || {}),
        ...telemetry
      };

      node.status = telemetry.rpcConnected === true
        ? "online"
        : "warning";

      const graphNode = graph.nodes.find(item =>
        item.id === node.id
      );

      if (graphNode) {
        graphNode.properties = {
          ...(graphNode.properties || {}),
          ...telemetry
        };

        graphNode.status = node.status;
      }
    }
  }

  if (category === "pool") {
    const readiness = await fetchSelectedMiningReadiness(node);

    if (readiness) {
      node.properties = {
        ...(node.properties || {}),
        miningReadiness: readiness
      };
    }
  }

  const liveStatus = liveNodeStatus(node);

  let operationalSection = "";

  if (category === "asic") {
    operationalSection = inspectorAsicSection(node);
  } else if (category === "pool") {
    operationalSection = inspectorPoolSection(node);
  } else if (category === "blockchain") {
    operationalSection = inspectorBlockchainSection(node);
  } else {
    operationalSection = inspectorServerSection(node);
  }

  byId("inspectorContent").innerHTML = `
    <div class="digital-twin-head">
      <div>
        <span class="digital-twin-kicker">Infrastructure Digital Twin</span>
        <h2>${inventoryDisplayName(node)}</h2>
        <p>
          ${inventoryTypeLabel(node)}
          ·
          ${safe(inventoryIp(node), "No IP")}
        </p>
      </div>

      <div class="digital-twin-state ${inspectorStatusClass(liveStatus)}">
        <span></span>
        ${safe(liveStatus).toUpperCase()}
      </div>
    </div>

    ${inspectorIdentitySection(node)}
    ${operationalSection}
    ${inspectorOperationalSection(node, impact)}
    ${infrastructureActionSection(node)}

    <section class="digital-twin-section">
      <details class="digital-twin-raw">
        <summary>Raw asset data</summary>
        <pre>${JSON.stringify(node.properties || {}, null, 2)}</pre>
      </details>
    </section>
  `;

  byId("inspectorPanel")?.classList.add("open");
  byId("inspectorBackdrop")?.classList.add("open");

  bindInspectorRelationships();
  bindInfrastructureActions(node);
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

async function runTargetScan(event) {
  event.preventDefault();

  const input = byId("scanTargetsInput");
  const result = byId("scanTargetsResult");
  const targets = input?.value || "";

  if (!targets.trim()) {
    result.textContent = "Enter at least one IP address.";
    return;
  }

  result.textContent = "Scanning...";

  try {
    const res = await fetch("/api/discovery/scan-targets", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({targets})
    });

    const payload = await res.json();

    if (!res.ok || payload.error) {
      result.textContent = payload.error || "Scan failed.";
      return;
    }

    const systems = payload.systems || [];
    result.innerHTML = `
      <strong>${systems.length} system(s) discovered.</strong>
      ${systems.map(s => `
        <div class="scan-result-row">
          <div class="scan-result-main">
            <b>${s.ip}</b>
            <span>${s.primaryRole || "Unknown System"}</span>
            <small>Ports: ${(s.openPorts || []).join(", ") || "none"}</small>
          </div>
          <button class="btn btn-setup-rpc" type="button" onclick='showRpcSetup(${JSON.stringify(s)})'>Setup RPC</button>
          <button class="btn btn-add-infra" type="button" onclick='addDiscoveredSystem(${JSON.stringify(s)})'>Add</button>
        </div>
      `).join("")}
    `;

    await loadGraph(true);
  } catch (e) {
    result.textContent = e.message;
  }
}

window.addEventListener("DOMContentLoaded", () => {
  byId("scanTargetsForm")?.addEventListener("submit", runTargetScan);
});

function classifyDiscoveredSystem(system) {
  const role = String(system?.primaryRole || "").toLowerCase();
  const ports = (system?.openPorts || [])
    .map(port => Number(port))
    .filter(Number.isFinite);

  if (
    role.includes("blockchain") ||
    role.includes("bitcoin core") ||
    role.includes("bitcoin node") ||
    role.includes("btc node") ||
    role.includes("bch node") ||
    ports.includes(8332) ||
    ports.includes(8333)
  ) {
    return "blockchain-node";
  }

  if (
    role.includes("asic") ||
    role.includes("miner")
  ) {
    return "asic";
  }

  if (
    role.includes("pool") ||
    role.includes("mining backend") ||
    role.includes("stratum")
  ) {
    return "pool";
  }

  if (
    ports.includes(22) ||
    role.includes("server") ||
    role.includes("host")
  ) {
    return "server";
  }

  return "unknown";
}

function defaultDiscoveredName(system, assetType) {
  const role = String(system?.primaryRole || "");

  if (assetType === "blockchain-node") {
    const lower = role.toLowerCase();

    if (
      lower.includes("bitcoin cash") ||
      lower.includes("bch")
    ) {
      return "Bitcoin Cash Node";
    }

    return "Bitcoin Core";
  }

  if (role && !role.toLowerCase().includes("unknown")) {
    return role;
  }

  return system?.ip || "Managed Infrastructure Asset";
}

async function addDiscoveredSystem(system) {
  const assetType = classifyDiscoveredSystem(system);
  const suggestedName = defaultDiscoveredName(system, assetType);

  const name = prompt(
    "Name this discovered system:",
    suggestedName
  );

  if (!name) return;

  const payload = {
    ...system,

    /*
     * Canonical backend identity.
     */
    assetType,
    canonicalType: assetType,

    /*
     * Lifecycle fields establish that the operator explicitly chose
     * to manage this discovery result.
     */
    managed: true,
    lifecycleStatus: "managed",
    addedAt: new Date().toISOString(),

    friendlyName: name,
    displayName: name
  };

  const res = await fetch("/api/discovery/add-system", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)
  });

  const data = await res.json();

  if (!res.ok || data.error) {
    alert(data.error || "Failed to add system.");
    return;
  }

  await loadGraph(true);
}


function showRpcSetup(system) {
  const ip = system?.ip || "SERVER_IP";
  alert(`Bitcoin RPC setup for ${ip}

SSH into the BTC node and edit:

~/.bitcoin/bitcoin.conf

Add:

server=1
rpcbind=0.0.0.0
rpcallowip=192.168.1.0/24
rpcuser=nexus
rpcpassword=CHANGE_ME_LONG_RANDOM_PASSWORD
txindex=1

Then restart Bitcoin Core:

sudo systemctl restart bitcoind

Then test from Nexus:

nc -vz ${ip} 8332

Later Nexus can use RPC to read sync percent from getblockchaininfo.verificationprogress.`);
}

/*
 * Keep the Canvas efficient when Nexus is left open on a background tab.
 * The next normal graph refresh restores activity after returning.
 */
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    renderCanvas();
  }
});

window.addEventListener("DOMContentLoaded", () => {
  byId("infrastructureActionBackdrop")
    ?.addEventListener(
      "click",
      closeInfrastructureActionPreview
    );
});
