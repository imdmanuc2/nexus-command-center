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

    if (["running", "online", "healthy"].includes(state)) {
      return "running";
    }

    if (["syncing", "warning"].includes(state)) {
      return "syncing";
    }

    if (["offline", "critical", "failed"].includes(state)) {
      return "offline";
    }

    return "unknown";
  }

  function managedCard(node) {
    const state = node.state || node.nodeStatus || "unknown";

    const hasProgress = (
      node.syncProgress !== null
      && node.syncProgress !== undefined
      && node.syncProgress !== ""
      && Number.isFinite(Number(node.syncProgress))
    );

    const progress = hasProgress
      ? Number(node.syncProgress)
      : null;

    const progressMarkup = hasProgress
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

    const manager = node.manager?.manager_name || "Independent / discovered";
    const ownership = node.manager
      ? "Seymour managed"
      : "Discovered";

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
            ${escapeHtml(state)}
          </span>
        </div>

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
            <dt>RPC</dt>
            <dd>${
              node.rpcHealthy === true
                ? "Healthy"
                : node.rpcReachable === false
                  ? "Unavailable"
                  : "Unknown"
            }</dd>
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

        ${progressMarkup}

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

    const isMonero = provider.coin === "XMR";

    return `
      <article class="blockchain-provider-card">
        <div class="blockchain-card-head">
          <div>
            <p class="blockchain-coin">
              ${escapeHtml(provider.coin)}
            </p>
            <h3>${escapeHtml(provider.name)}</h3>
          </div>

          <span class="blockchain-state-pill healthy">
            Available
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
            <dd>${escapeHtml(formatBytes(storage.minimumFreeBytes))}</dd>
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
            ${
              isMonero
                ? "Ready for validation"
                : "Deployment planning"
            }
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
    $("blockchainRunningCount").textContent =
      items.filter(
        (item) => ["running", "online"].includes(item.state)
      ).length;
    $("blockchainSyncingCount").textContent =
      items.filter((item) => item.state === "syncing").length;
    $("blockchainAttentionCount").textContent =
      items.filter(
        (item) =>
          !["running", "online", "syncing"].includes(item.state)
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
