(() => {
  "use strict";
  const nativeFetch = window.fetch.bind(window);
  const num = (v, f = 0) => Number.isFinite(Number(v)) ? Number(v) : f;
  const upperType = v => String(v || "").trim().replaceAll("-", "_").toUpperCase();

  function normalizeWorker(w) {
    const sourceWorkerId = w.sourceWorkerId || w.workerName || w.workerId || "";
    return {
      ...w,
      workerId: sourceWorkerId,
      canonicalWorkerId: w.workerId,
      workerName: w.workerName || sourceWorkerId,
      name: w.workerName || w.displayName || sourceWorkerId,
      displayName: w.displayName || w.workerName || sourceWorkerId,
      assetName: w.assetName || w.displayName || w.workerName || sourceWorkerId,
      assetIp: w.assetIp || w.identity?.ip || "",
      hashrate: num(w.hashrate ?? w.currentHashrate),
      hashRate: num(w.hashRate ?? w.currentHashrate ?? w.hashrate),
      sharesPerSecond: num(w.sharesPerSecond),
      poolId: w.nativePoolId || w.poolId || "",
      poolHost: w.poolHost || "",
      status: w.status || "unknown"
    };
  }

  function normalizeNode(node) {
    const properties = { ...(node.properties || {}) };
    let type = node.assetType || node.nodeType || "unknown";

    if (node.nodeType === "pool") {
      type = "pool";
      properties.assetType = "pool";
      properties.poolId = properties.nativePoolId || properties.poolId || node.id;
      properties.id = properties.nativePoolId || properties.poolId || node.id;
    } else if (node.nodeType === "worker") {
      type = "worker";
      properties.hashrate = num(properties.hashrate ?? properties.currentHashrate);
    } else if (node.nodeType === "workload") {
      type = "workload";
    }

    properties.assetType = properties.assetType || node.assetType || type;
    return {
      id: node.id,
      type,
      label: node.label || node.id,
      status: node.status || "unknown",
      properties
    };
  }

  function normalizeEdge(edge) {
    return {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: upperType(edge.type),
      label: String(edge.type || "").replaceAll("-", " ").replaceAll("_", " "),
      status: edge.status || "active",
      confidence: edge.confidence,
      properties: edge.properties || {}
    };
  }

  function buildLegacyGraph(topology) {
    const nodes = (topology.nodes || []).map(normalizeNode);
    const originalEdges = (topology.edges || []).map(normalizeEdge);
    const nodeMap = new Map(nodes.map(n => [n.id, n]));
    const workerToAsset = new Map();

    originalEdges.forEach(edge => {
      if (edge.type === "RUNS_ON") {
        const source = nodeMap.get(edge.source);
        if (source?.type === "worker") workerToAsset.set(edge.source, edge.target);
      }
    });

    const derivedEdges = [];
    originalEdges.forEach(edge => {
      if (edge.type !== "MINES_ON") return;
      const assetId = workerToAsset.get(edge.source);
      if (!assetId) return;

      const workerNode = nodeMap.get(edge.source);
      const assetNode = nodeMap.get(assetId);

      if (assetNode && workerNode) {
        assetNode.properties.liveWorkerId =
          workerNode.properties.sourceWorkerId ||
          workerNode.properties.workerId ||
          workerNode.id;
        assetNode.properties.liveHashrate = num(
          workerNode.properties.currentHashrate ??
          workerNode.properties.hashrate
        );
        assetNode.properties.liveSharesPerSecond = num(
          workerNode.properties.sharesPerSecond
        );
        assetNode.properties.livePoolId =
          workerNode.properties.nativePoolId ||
          workerNode.properties.poolId ||
          "";
        assetNode.properties.livePoolHost =
          workerNode.properties.poolHost || "";
      }

      derivedEdges.push({
        id: `derived:${assetId}:${edge.target}:MINES_ON`,
        source: assetId,
        target: edge.target,
        type: "MINES_ON",
        label: "Mines On",
        status: edge.status,
        confidence: edge.confidence,
        properties: {
          derivedFromWorker: edge.source,
          source: "nexus-platform-topology-adapter"
        }
      });
    });

    const seen = new Set();
    const edges = [];
    [...originalEdges, ...derivedEdges].forEach(edge => {
      const key = `${edge.source}->${edge.target}:${edge.type}`;
      if (!seen.has(key)) {
        seen.add(key);
        edges.push(edge);
      }
    });

    return {
      status: "ok",
      source: "nexus-postgresql-platform-explorer-adapter",
      counts: { ...(topology.counts || {}), nodes: nodes.length, edges: edges.length },
      nodes,
      edges
    };
  }

  async function getTopology() {
    const r = await nativeFetch("/api/platform/topology");
    if (!r.ok) throw new Error(`Topology HTTP ${r.status}`);
    return buildLegacyGraph(await r.json());
  }

  async function getWorkers() {
    const r = await nativeFetch("/api/platform/workers");
    if (!r.ok) throw new Error(`Workers HTTP ${r.status}`);
    const payload = await r.json();
    return {
      ...payload,
      workers: Array.isArray(payload.workers)
        ? payload.workers.map(normalizeWorker)
        : []
    };
  }

  const jsonResponse = payload => new Response(JSON.stringify(payload), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
      "X-Nexus-Data-Source": "nexus-postgresql-platform"
    }
  });

  window.NexusExplorerPlatform = Object.freeze({
    getTopology, getWorkers, buildLegacyGraph, normalizeNode, normalizeEdge
  });

  window.fetch = async function(input, options) {
    const rawUrl = typeof input === "string" ? input : input?.url;
    if (!rawUrl) return nativeFetch(input, options);

    const parsed = new URL(rawUrl, window.location.origin);
    const method = String(options?.method || "GET").toUpperCase();

    if (method === "GET" &&
        (parsed.pathname === "/api/graph/live" ||
         parsed.pathname === "/api/graph/rebuild")) {
      try {
        return jsonResponse(await getTopology());
      } catch (error) {
        console.error("Platform topology adapter failed.", error);
        return nativeFetch(input, options);
      }
    }

    if (method === "GET" && parsed.pathname === "/api/mining/workers") {
      try {
        return jsonResponse(await getWorkers());
      } catch (error) {
        console.error("Platform worker adapter failed.", error);
        return nativeFetch(input, options);
      }
    }

    return nativeFetch(input, options);
  };

  console.info(
    "Infrastructure Explorer is using PostgreSQL-backed Platform topology."
  );
})();
