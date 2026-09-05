(() => {
  let catalog = [];
  let activeFilter = "all";

  const $ = (id) => document.getElementById(id);

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function formatNumber(value) {
    if (
      value === null
      || value === undefined
      || value === ""
    ) {
      return "—";
    }

    const number = Number(value);

    if (!Number.isFinite(number)) {
      return "—";
    }

    return new Intl.NumberFormat().format(number);
  }

  function formatPercent(value) {
    if (
      value === null
      || value === undefined
      || value === ""
    ) {
      return "—";
    }

    const number = Number(value);

    if (!Number.isFinite(number)) {
      return "—";
    }

    return `${number.toFixed(2)}%`;
  }

  function formatBytes(value) {
    const bytes = Number(value);

    if (!Number.isFinite(bytes) || bytes <= 0) {
      return "—";
    }

    const units = ["B", "KB", "MB", "GB", "TB"];
    let current = bytes;
    let unit = 0;

    while (current >= 1000 && unit < units.length - 1) {
      current /= 1000;
      unit += 1;
    }

    return `${current.toFixed(current >= 100 ? 0 : 1)} ${units[unit]}`;
  }

  function stateClass(value) {
    const state = String(value || "unknown").toLowerCase();

    if ([
      "ready",
      "running",
      "online",
      "healthy",
      "synced",
    ].includes(state)) {
      return "running";
    }

    if ([
      "syncing",
      "starting",
      "warning",
    ].includes(state)) {
      return "syncing";
    }

    if ([
      "degraded",
      "stalled",
    ].includes(state)) {
      return "warning";
    }

    if ([
      "offline",
      "stopped",
      "critical",
      "failed",
      "error",
    ].includes(state)) {
      return "offline";
    }

    return "unknown";
  }

  function stateLabel(value) {
    const state = String(value || "unknown")
      .trim()
      .toLowerCase();

    const labels = {
      "not-ready": "Not ready",
      "not-installed": "Not installed",
      ready: "Ready",
      running: "Running",
      starting: "Starting",
      syncing: "Syncing",
      synced: "Synced",
      online: "Online",
      healthy: "Healthy",
      degraded: "Degraded",
      stalled: "Stalled",
      offline: "Offline",
      stopped: "Stopped",
      unreachable: "Unreachable",
      unknown: "Unknown",
    };

    return labels[state]
      || state
        .split("-")
        .map(
          (part) =>
            part
              ? part[0].toUpperCase() + part.slice(1)
              : part
        )
        .join(" ");
  }

  function dimensionMarkup(label, value) {
    const normalized = value || "unknown";

    return `
      <div class="blockchain-health-dimension">
        <dt>${escapeHtml(label)}</dt>
        <dd>
          <span
            class="blockchain-dimension-pill ${stateClass(normalized)}"
          >
            ${escapeHtml(stateLabel(normalized))}
          </span>
        </dd>
      </div>
    `;
  }

  function managedCard(node) {
    const state = (
      node.overallState
      || node.state
      || node.nodeStatus
      || "unknown"
    );

    const hasProgress = (
      node.syncProgress !== null
      && node.syncProgress !== undefined
      && node.syncProgress !== ""
      && Number.isFinite(Number(node.syncProgress))
    );

    const progress = hasProgress
      ? Number(node.syncProgress)
      : null;

    const showProgress = (
      hasProgress
      && (
        node.syncState === "syncing"
        || state === "syncing"
      )
    );

    const progressMarkup = showProgress
      ? `
        <div class="blockchain-progress">
          <div class="blockchain-progress-head">
            <span>Sync progress</span>
            <strong>${escapeHtml(formatPercent(progress))}</strong>
          </div>
          <div class="blockchain-progress-track">
            <div
              class="blockchain-progress-bar"
              style="width:${Math.max(0, Math.min(100, progress))}%"
            ></div>
          </div>
        </div>
      `
      : "";

    const manager = (
      node.manager?.manager_name
      || "Independent / discovered"
    );

    const ownership = node.manager
      ? "Seymour managed"
      : "Discovered";

    const reasonMarkup = node.stateReason
      ? `
        <p class="blockchain-state-reason">
          ${escapeHtml(node.stateReason)}
        </p>
      `
      : "";

    return `
      <article class="blockchain-node-card">
        <div class="blockchain-card-head">
          <div>
            <p class="blockchain-coin">
              ${escapeHtml(node.coin || "CHAIN")}
            </p>
            <h3>${escapeHtml(node.name || node.assetId)}</h3>
          </div>

          <span
            class="blockchain-state-pill ${stateClass(state)}"
          >
            ${escapeHtml(stateLabel(state))}
          </span>
        </div>

        ${reasonMarkup}

        <dl class="blockchain-health-grid">
          ${dimensionMarkup(
            "Runtime",
            node.runtimeState,
          )}
          ${dimensionMarkup(
            "Connectivity",
            node.connectivityState,
          )}
          ${dimensionMarkup(
            "Sync",
            node.syncState,
          )}
          ${dimensionMarkup(
            "RPC",
            node.rpcState,
          )}
          ${dimensionMarkup(
            "Mining",
            node.miningReadiness,
          )}
        </dl>

        ${progressMarkup}

        <dl class="blockchain-details">
          <div>
            <dt>Network</dt>
            <dd>${escapeHtml(node.network || "—")}</dd>
          </div>

          <div>
            <dt>Implementation</dt>
            <dd>${escapeHtml(node.implementation || "—")}</dd>
          </div>

          <div>
            <dt>Block height</dt>
            <dd>${escapeHtml(formatNumber(node.blockHeight))}</dd>
          </div>

          <div>
            <dt>Header height</dt>
            <dd>${escapeHtml(formatNumber(node.headerHeight))}</dd>
          </div>

          <div>
            <dt>Peers</dt>
            <dd>${escapeHtml(formatNumber(node.peerCount))}</dd>
          </div>

          <div>
            <dt>Ownership</dt>
            <dd>${escapeHtml(ownership)}</dd>
          </div>

          <div>
            <dt>Managed by</dt>
            <dd>${escapeHtml(manager)}</dd>
          </div>
        </dl>

        <div class="blockchain-card-actions">
          <a href="/cmdb-object.html?id=${encodeURIComponent(node.assetId)}">
            CMDB
          </a>

          <a href="/operations-center.html">
            Operations
          </a>
        </div>
      </article>
    `;
  }

  function providerCard(provider) {
    const storage = provider.storage || {};
    const architectures = Array.isArray(provider.architectures)
      ? provider.architectures.join(" + ")
      : "—";

    const availability = String(
      provider.availability || "planned"
    ).toLowerCase();

    const selectable = Boolean(provider.selectable);

    const stateLabel = availability === "live"
      ? "Available"
      : availability === "coming-soon"
        ? "Coming Soon"
        : "Planned";

    const stateClass = availability === "live"
      ? "healthy"
      : availability === "coming-soon"
        ? "warning"
        : "offline";

    const actionLabel = availability === "live" && selectable
      ? "Deployment planning"
      : stateLabel;

    const minimumStorage =
      Number.isFinite(Number(storage.minimumFreeBytes))
      && Number(storage.minimumFreeBytes) > 0
        ? formatBytes(storage.minimumFreeBytes)
        : "To be defined";

    return `
      <article class="blockchain-provider-card">
        <div class="blockchain-card-head">
          <div>
            <p class="blockchain-coin">
              ${escapeHtml(provider.coin)}
            </p>
            <h3>${escapeHtml(provider.name)}</h3>
          </div>

          <span class="blockchain-state-pill ${stateClass}">
            ${escapeHtml(stateLabel)}
          </span>
        </div>

        <p class="provider-meta">
          ${escapeHtml(provider.implementation)}
          · ${escapeHtml(provider.network)}
        </p>

        <dl class="blockchain-details">
          <div>
            <dt>Architecture</dt>
            <dd>${escapeHtml(architectures)}</dd>
          </div>

          <div>
            <dt>Minimum storage</dt>
            <dd>${escapeHtml(minimumStorage)}</dd>
          </div>

          <div>
            <dt>P2P port</dt>
            <dd>${escapeHtml(provider.defaultPorts?.p2p || "—")}</dd>
          </div>

          <div>
            <dt>RPC port</dt>
            <dd>${escapeHtml(provider.defaultPorts?.rpc || "—")}</dd>
          </div>
        </dl>

        <div class="blockchain-card-actions">
          <button
            class="blockchain-provider-action"
            type="button"
            disabled
          >
            ${escapeHtml(actionLabel)}
          </button>
        </div>
      </article>
    `;
  }

  function renderCatalogFilters() {
    const container = $("blockchainCatalogFilters");

    if (!container) {
      return;
    }

    const providersByCoin = new Map();

    catalog.forEach((provider) => {
      const coin = String(provider.coin || "").trim();

      if (!coin || providersByCoin.has(coin)) {
        return;
      }

      providersByCoin.set(
        coin,
        provider.name || provider.implementation || coin
      );
    });

    const buttons = [
      `
        <button
          type="button"
          class="${activeFilter === "all" ? "active" : ""}"
          data-filter="all"
        >
          All
        </button>
      `,
      ...Array.from(providersByCoin.entries())
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([coin, name]) => `
          <button
            type="button"
            class="${activeFilter === coin ? "active" : ""}"
            data-filter="${escapeHtml(coin)}"
          >
            ${escapeHtml(name)}
          </button>
        `),
    ];

    container.innerHTML = buttons.join("");
  }


  function renderCatalog() {
    const search = String(
      $("blockchainCatalogSearch")?.value || ""
    )
      .trim()
      .toLowerCase();

    const filtered = catalog.filter((provider) => {
      if (
        activeFilter !== "all"
        && provider.coin !== activeFilter
      ) {
        return false;
      }

      if (!search) {
        return true;
      }

      const haystack = [
        provider.coin,
        provider.name,
        provider.implementation,
        provider.network,
        provider.providerId,
      ]
        .join(" ")
        .toLowerCase();

      return haystack.includes(search);
    });

    $("blockchainCatalogCount").textContent =
      `${filtered.length} provider${filtered.length === 1 ? "" : "s"}`;

    $("availableBlockchainGrid").innerHTML =
      filtered.length
        ? filtered.map(providerCard).join("")
        : `
          <article class="blockchain-empty-card">
            No blockchain providers match this filter.
          </article>
        `;
  }

  async function loadOperations() {
    const response = await fetch(
      "/api/blockchain/operations",
      { cache: "no-store" }
    );

    if (!response.ok) {
      throw new Error(
        `Blockchain operations request failed: ${response.status}`
      );
    }

    const payload = await response.json();
    const items = Array.isArray(payload.items)
      ? payload.items
      : [];

    $("blockchainManagedCount").textContent = items.length;

    $("blockchainReadyCount").textContent =
      items.filter(
        (item) => item.overallState === "ready"
      ).length;

    $("blockchainSyncingCount").textContent =
      items.filter(
        (item) => item.overallState === "syncing"
      ).length;

    $("blockchainAttentionCount").textContent =
      items.filter(
        (item) => ![
          "ready",
          "running",
          "syncing",
        ].includes(item.overallState)
      ).length;

    $("managedBlockchainGrid").innerHTML =
      items.length
        ? items.map(managedCard).join("")
        : `
          <article class="blockchain-empty-card">
            No canonical blockchain runtimes are currently
            registered in Nexus.
          </article>
        `;

    const managedCount = items.filter(
      (item) => Boolean(item.manager)
    ).length;

    const discoveredCount = items.length - managedCount;

    $("blockchainSourceState").textContent =
      `CMDB canonical · ${managedCount} managed · ${discoveredCount} discovered`;

    $("blockchainSourceState").classList.remove("warning");
  }

  async function loadCatalog() {
    const response = await fetch(
      "/api/blockchain/catalog",
      { cache: "no-store" }
    );

    if (!response.ok) {
      throw new Error(
        `Blockchain catalog request failed: ${response.status}`
      );
    }

    const payload = await response.json();

    catalog = Array.isArray(payload.providers)
      ? payload.providers
      : [];

    renderCatalogFilters();
    renderCatalog();
  }

  async function load() {
    try {
      await Promise.all([
        loadOperations(),
        loadCatalog(),
      ]);
    } catch (error) {
      console.error(error);

      $("blockchainSourceState").textContent =
        "Platform data unavailable";

      $("blockchainSourceState").classList.add("warning");
    }
  }

  $("refreshBlockchainButton")
    ?.addEventListener("click", load);

  $("blockchainCatalogSearch")
    ?.addEventListener("input", renderCatalog);

  $("blockchainCatalogFilters")
    ?.addEventListener("click", (event) => {
      const button = event.target.closest("button[data-filter]");

      if (!button) {
        return;
      }

      activeFilter = button.dataset.filter || "all";

      document
        .querySelectorAll(
          "#blockchainCatalogFilters button[data-filter]"
        )
        .forEach((candidate) => {
          candidate.classList.toggle(
            "active",
            candidate === button
          );
        });

      renderCatalog();
    });

  load();
})();
