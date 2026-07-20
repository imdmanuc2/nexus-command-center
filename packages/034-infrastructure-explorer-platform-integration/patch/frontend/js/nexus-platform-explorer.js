(() => {
  "use strict";

  const REQUEST_TIMEOUT_MS = 8000;
  const num = (value, fallback = 0) =>
    Number.isFinite(Number(value)) ? Number(value) : fallback;
  const upperType = value =>
    String(value || "").trim().replaceAll("-", "_").toUpperCase();

  async function fetchJson(url, options = {}) {
    const controller = new AbortController();
    const timeout = window.setTimeout(
      () => controller.abort(),
      REQUEST_TIMEOUT_MS
    );

    try {
      const response = await window.fetch(url, {
        ...options,
        signal: options.signal || controller.signal,
        headers: {
          Accept: "application/json",
          ...(options.headers || {})
        }
      });

      if (!response.ok) {
        throw new Error(`${url} returned HTTP ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      if (error?.name === "AbortError") {
        throw new Error(`${url} timed out after 8 seconds`);
      }
      throw error;
    } finally {
      window.clearTimeout(timeout);
    }
  }

  function normalizeWorker(worker) {
    const sourceWorkerId =
      worker.sourceWorkerId ||
      worker.workerName ||
      worker.workerId ||
      "";

    return {
      ...worker,
      workerId: sourceWorkerId,
      canonicalWorkerId: worker.workerId,
      workerName: worker.workerName || sourceWorkerId,
      name: worker.workerName || worker.displayName || sourceWorkerId,
      displayName:
        worker.displayName || worker.workerName || sourceWorkerId,
      assetName:
        worker.assetName ||
        worker.displayName ||
        worker.workerName ||
        sourceWorkerId,
      assetIp: worker.assetIp || worker.identity?.ip || "",
      hashrate: num(worker.hashrate ?? worker.currentHashrate),
      hashRate: num(
        worker.hashRate ?? worker.currentHashrate ?? worker.hashrate
      ),
      currentHashrate: num(
        worker.currentHashrate ?? worker.hashrate ?? worker.hashRate
      ),
      sharesPerSecond: num(worker.sharesPerSecond),
      poolId: worker.nativePoolId || worker.poolId || "",
      poolInstanceId:
        worker.poolInstanceId || worker.observedState?.poolId || "",
      poolHost: worker.poolHost || "",
      status: worker.status || "unknown",
      observedState: worker.observedState || {}
    };
  }

  function normalizeNode(node) {
    const properties = { ...(node.properties || {}) };
    let type = node.nodeType || node.assetType || "unknown";

    if (node.nodeType === "pool") {
      type = "pool";
      properties.assetType = "pool";
      properties.poolId =
        properties.nativePoolId || properties.poolId || node.id;
      properties.id =
        properties.nativePoolId || properties.poolId || node.id;
    } else if (node.nodeType === "worker") {
      type = "worker";
      properties.hashrate = num(
        properties.hashrate ?? properties.currentHashrate
      );
    } else if (node.nodeType === "workload") {
      type = "workload";
    }

    properties.assetType = properties.assetType || node.assetType || type;

    return {
      id: node.id,
      nodeType: node.nodeType || type,
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
      label: String(edge.type || "")
        .replaceAll("-", " ")
        .replaceAll("_", " "),
      status: edge.status || "active",
      confidence: edge.confidence,
      properties: edge.properties || {}
    };
  }

  function buildExplorerGraph(topology) {
    const nodes = (topology.nodes || []).map(normalizeNode);
    const nodeIds = new Set(nodes.map(node => node.id));
    const seen = new Set();

    const edges = (topology.edges || [])
      .map(normalizeEdge)
      .filter(edge => {
        if (!nodeIds.has(edge.source) || !nodeIds.has(edge.target)) {
          return false;
        }

        const key = `${edge.source}->${edge.target}:${edge.type}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });

    return {
      status: topology.status || "ok",
      source: "nexus-postgresql-platform-topology",
      generatedAt:
        topology.generatedAt || topology.observedAt || new Date().toISOString(),
      counts: {
        ...(topology.counts || {}),
        nodes: nodes.length,
        edges: edges.length
      },
      nodes,
      edges
    };
  }

  async function getTopology() {
    return buildExplorerGraph(
      await fetchJson("/api/platform/topology")
    );
  }

  async function getWorkers() {
    const payload = await fetchJson("/api/platform/workers");
    return {
      ...payload,
      source: payload.source || "nexus-postgresql-platform-workers",
      workers: Array.isArray(payload.workers)
        ? payload.workers.map(normalizeWorker)
        : []
    };
  }

  window.NexusExplorerPlatform = Object.freeze({
    REQUEST_TIMEOUT_MS,
    fetchJson,
    getTopology,
    getWorkers,
    buildExplorerGraph,
    normalizeWorker,
    normalizeNode,
    normalizeEdge
  });

  console.info(
    "Infrastructure Explorer Platform client ready; no fetch interception enabled."
  );
})();
