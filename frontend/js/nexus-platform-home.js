(() => {
  "use strict";
  const nativeFetch = window.fetch.bind(window);

  async function fetchJson(url, options) {
    const response = await nativeFetch(url, options);
    if (!response.ok) throw new Error(`${url} returned HTTP ${response.status}`);
    return response.json();
  }

  const number = (value, fallback = 0) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  };

  const online = value =>
    ["online", "healthy", "running", "active", "connected"]
      .includes(String(value || "").trim().toLowerCase());

  function normalizeWorker(worker) {
    return {
      ...worker,
      id: worker.id || worker.workerId,
      workerId: worker.sourceWorkerId || worker.workerId,
      canonicalWorkerId: worker.workerId,
      name: worker.name || worker.displayName || worker.workerName || worker.workerId,
      displayName: worker.displayName || worker.name || worker.workerId,
      hashrate: number(worker.hashrate ?? worker.currentHashrate),
      currentHashrate: number(worker.currentHashrate ?? worker.hashrate),
      sharesPerSecond: number(worker.sharesPerSecond),
      poolId: worker.nativePoolId || worker.poolId || "",
      poolInstanceId: worker.poolInstanceId || "",
      online: online(worker.status),
      status: worker.status || "unknown"
    };
  }

  function normalizePool(pool) {
    const workers = Array.isArray(pool.workers)
      ? pool.workers.map(normalizeWorker)
      : [];
    return {
      ...pool,
      id: pool.id || pool.poolId,
      poolId: pool.nativePoolId || pool.poolId,
      poolInstanceId: pool.poolId,
      nativePoolId: pool.nativePoolId || "",
      name: pool.name || pool.nativePoolId || pool.poolId,
      online: online(pool.status),
      stats: {
        ...(pool.stats || {}),
        poolHashrate: number(pool.stats?.poolHashrate ?? pool.currentHashrate),
        connectedMiners: pool.workerCount ?? workers.length
      },
      workerCount: pool.workerCount ?? workers.length,
      workers
    };
  }

  async function getFleet() {
    return fetchJson("/api/platform/fleet");
  }

  async function getWorkers() {
    const payload = await fetchJson("/api/platform/workers");
    const workers = Array.isArray(payload.workers)
      ? payload.workers.map(normalizeWorker)
      : [];
    return { ...payload, workers, items: workers, count: workers.length };
  }

  async function getPools() {
    const payload = await fetchJson("/api/platform/pools");
    const pools = Array.isArray(payload.pools)
      ? payload.pools.map(normalizePool)
      : [];
    return { ...payload, pools, items: pools, count: pools.length };
  }

  async function getHome() {
    const [fleet, workerPayload, poolPayload] = await Promise.all([
      getFleet(), getWorkers(), getPools()
    ]);
    const workers = workerPayload.workers;
    const pools = poolPayload.pools;
    const onlineWorkers = workers.filter(worker => worker.online);
    const onlinePools = pools.filter(pool => pool.online);
    const coins = new Set(
      pools.map(pool => String(pool.coin || "").trim().toUpperCase()).filter(Boolean)
    );
    const blockchainNodes = number(fleet.assets?.byType?.["blockchain-node"]);
    return {
      status: "ok",
      source: "nexus-postgresql-platform-home-adapter",
      fleetHealth: number(fleet.fleetHealth, 100),
      fleetHashrate: number(fleet.fleetHashrate),
      totalHashrate: number(fleet.fleetHashrate),
      hashrateUnit: fleet.hashrateUnit || "H/s",
      sharesPerSecond: workers.reduce(
        (sum, worker) => sum + number(worker.sharesPerSecond), 0
      ),
      coinCount: coins.size,
      poolCount: pools.length,
      activePoolCount: onlinePools.length,
      minerCount: workers.length,
      workerCount: workers.length,
      onlineMinerCount: onlineWorkers.length,
      onlineWorkerCount: onlineWorkers.length,
      offlineMinerCount: workers.length - onlineWorkers.length,
      offlineWorkerCount: workers.length - onlineWorkers.length,
      nodeCount: blockchainNodes,
      onlineNodeCount: blockchainNodes,
      matchedWorkerCount: number(fleet.workers?.matched),
      unmatchedWorkerCount: number(fleet.workers?.unmatched),
      assets: fleet.assets || {},
      workers: fleet.workers || {},
      pools: fleet.pools || {},
      workloads: fleet.workloads || {},
      compute: fleet.compute || {},
      workerItems: workers,
      poolItems: pools,
      generatedAt: new Date().toISOString()
    };
  }

  function response(data) {
    return new Response(JSON.stringify(data), {
      status: 200,
      headers: {
        "Content-Type": "application/json",
        "X-Nexus-Data-Source": "platform-api"
      }
    });
  }

  const routes = new Map([
    ["/api/fleet/home", getHome],
    ["/api/mining/workers", getWorkers],
    ["/api/mining/pools", getPools]
  ]);

  window.NexusPlatform = Object.freeze({
    getFleet, getHome, getWorkers, getPools, normalizeWorker, normalizePool
  });

  window.fetch = async function(input, options) {
    const rawUrl = typeof input === "string" ? input : input?.url;
    if (!rawUrl) return nativeFetch(input, options);
    const parsed = new URL(rawUrl, window.location.origin);
    const handler = routes.get(parsed.pathname);
    if (!handler || (options?.method && options.method.toUpperCase() !== "GET")) {
      return nativeFetch(input, options);
    }
    try {
      return response(await handler());
    } catch (error) {
      console.error(`[Nexus Platform] ${parsed.pathname} adapter failed`, error);
      return nativeFetch(input, options);
    }
  };

  console.info("Nexus Home v2 is using PostgreSQL-backed Platform APIs.");
})();
