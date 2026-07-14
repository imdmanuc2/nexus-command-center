let latestSystems = [];
let latestFound = [];
let activeFilter = "all";
let searchQuery = "";

function byId(id) {
  return document.getElementById(id);
}

function safe(value, fallback = "Unknown") {
  return value === undefined || value === null || value === ""
    ? fallback
    : value;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function closeDrawer() {
  byId("drawer")?.classList.remove("open");
  byId("drawerBackdrop")?.classList.remove("open");
}

function infrastructureAvailable() {
  return Boolean(window.NexusInfrastructure);
}

function isManaged(ip) {
  return infrastructureAvailable()
    ? window.NexusInfrastructure.isManaged(ip)
    : false;
}

function systemName(system) {
  return (
    system?.asset?.name ||
    system?.profile?.hostname ||
    system?.ip ||
    "Unknown Asset"
  );
}

function systemText(system) {
  return [
    system.ip,
    system.primaryRole,
    system.profile?.hostname,
    system.profile?.assetType,
    system.asset?.name,
    system.asset?.purpose,
    ...(system.roles || []).map(role => role.label),
    ...(system.fingerprints || []).map(
      fingerprint => `${fingerprint.label} ${fingerprint.endpoint}`
    ),
    ...latestFound
      .filter(found => found.ip === system.ip)
      .map(found => `${found.service} ${found.port}`)
  ]
    .join(" ")
    .toLowerCase();
}

function matchesFilter(system) {
  const text = systemText(system);

  if (activeFilter === "all") return true;

  if (activeFilter === "mining") {
    return (
      text.includes("mining") ||
      text.includes("stratum") ||
      text.includes("pool")
    );
  }

  if (activeFilter === "node") {
    return (
      text.includes("node") ||
      text.includes("blockchain") ||
      text.includes("bitcoin") ||
      text.includes("8333")
    );
  }

  if (activeFilter === "dashboard") {
    return (
      text.includes("dashboard") ||
      text.includes("web interface")
    );
  }

  if (activeFilter === "healthy") {
    return system.health?.level === "healthy";
  }

  return true;
}

function filteredSystems() {
  return latestSystems.filter(system => {
    const query = searchQuery.trim().toLowerCase();

    return (
      (!query || systemText(system).includes(query)) &&
      matchesFilter(system)
    );
  });
}

function renderSummary(discovery) {
  const summary = discovery.summary || {};
  const healthy = latestSystems.filter(
    system => system.health?.level === "healthy"
  ).length;

  const managed = latestSystems.filter(system =>
    isManaged(system.ip)
  ).length;

  byId("discoverySummary").innerHTML = `
    <div class="asset-summary-card">
      <span>Targets</span>
      <strong>${(discovery.targets || []).length}</strong>
    </div>

    <div class="asset-summary-card">
      <span>Systems</span>
      <strong>${latestSystems.length}</strong>
    </div>

    <div class="asset-summary-card">
      <span>Managed</span>
      <strong>${managed}</strong>
    </div>

    <div class="asset-summary-card">
      <span>Healthy</span>
      <strong>${healthy}</strong>
    </div>

    <div class="asset-summary-card">
      <span>Mining Backends</span>
      <strong>${summary.miningBackends || 0}</strong>
    </div>

    <div class="asset-summary-card">
      <span>Nodes</span>
      <strong>${summary.blockchainNodes || 0}</strong>
    </div>
  `;
}

function rolePills(system) {
  return (system.roles || [])
    .map(
      role => `
        <span class="discovery-pill">
          ${escapeHtml(role.label)} ${Number(role.confidence || 0)}%
        </span>
      `
    )
    .join("");
}

function servicesFor(system) {
  return latestFound.filter(found => found.ip === system.ip);
}

function addSystemToInfrastructure(system) {
  if (!infrastructureAvailable()) {
    console.error("Nexus infrastructure state is unavailable.");
    return;
  }

  try {
    window.NexusInfrastructure.addOrUpdateAsset(
      system,
      latestFound
    );

    renderSystems();

    const drawer = byId("drawer");

    if (drawer?.classList.contains("open")) {
      openDrawer(system);
    }
  } catch (error) {
    console.error("Unable to add infrastructure asset", error);
    alert(`Unable to add asset: ${error.message}`);
  }
}

function requestSystemAction(system, action) {
  if (!infrastructureAvailable()) return;

  window.NexusInfrastructure.requestAction(
    {
      name: systemName(system),
      ip: system.ip
    },
    action
  );
}

function renderSystems() {
  const systems = filteredSystems();

  byId("discoveryList").innerHTML =
    systems
      .map(system => {
        const services = servicesFor(system);
        const managed = isManaged(system.ip);

        return `
          <article class="discovery-card" data-ip="${escapeHtml(system.ip)}">
            <div class="discovery-card-head">
              <div>
                <h2>${escapeHtml(systemName(system))}</h2>
                <p>${escapeHtml(safe(system.primaryRole))}</p>
              </div>

              <span class="asset-profile-status ${managed ? "managed" : ""}">
                ${
                  managed
                    ? "Managed"
                    : escapeHtml(safe(system.health?.label, "Unknown"))
                }
              </span>
            </div>

            <div class="pool-stats">
              <div>
                <b>IP</b>
                <span>${escapeHtml(system.ip)}</span>
              </div>

              <div>
                <b>Services</b>
                <span>${services.length}</span>
              </div>

              <div>
                <b>Health</b>
                <span class="good">
                  ${Number(system.health?.score || 0)}%
                </span>
              </div>
            </div>

            <div class="discovery-pills">
              ${rolePills(system)}

              ${
                managed
                  ? '<span class="discovery-pill infrastructure-managed-pill">Infrastructure Managed</span>'
                  : ""
              }
            </div>

            <small>
              ${
                services
                  .map(
                    service =>
                      `${escapeHtml(service.service)}:${escapeHtml(service.port)}`
                  )
                  .join(" · ") || "No open services reported"
              }
            </small>

            <div class="discovery-card-actions">
              <button
                class="btn add-infrastructure-btn"
                type="button"
                data-action="add-infrastructure"
                data-ip="${escapeHtml(system.ip)}"
              >
                ${
                  managed
                    ? "Update Infrastructure"
                    : "Add to Infrastructure"
                }
              </button>
            </div>
          </article>
        `;
      })
      .join("") ||
    `
      <div class="empty-state">
        <h2>No discovery results match.</h2>
        <p>Try clearing search or changing the filter.</p>
      </div>
    `;

  document
    .querySelectorAll(".discovery-card")
    .forEach(card => {
      card.addEventListener("click", event => {
        if (event.target.closest("[data-action]")) {
          return;
        }

        const system = latestSystems.find(
          item => item.ip === card.dataset.ip
        );

        if (system) {
          openDrawer(system);
        }
      });
    });

  document
    .querySelectorAll("[data-action='add-infrastructure']")
    .forEach(button => {
      button.addEventListener("click", event => {
        event.stopPropagation();

        const system = latestSystems.find(
          item => item.ip === button.dataset.ip
        );

        if (system) {
          addSystemToInfrastructure(system);
        }
      });
    });
}

function eventLabel(event) {
  const type = event.type || "CHANGE";

  if (type === "NODE_ADDED") {
    return `New ${event.nodeType || "node"} discovered`;
  }

  if (type === "NODE_REMOVED") {
    return `${event.nodeType || "node"} removed`;
  }

  if (type === "NODE_STATUS_CHANGED") {
    return "Status changed";
  }

  if (type === "NODE_RENAMED") {
    return "Node renamed";
  }

  if (type === "EDGE_ADDED") {
    return "Relationship added";
  }

  if (type === "EDGE_REMOVED") {
    return "Relationship removed";
  }

  return type.replaceAll("_", " ");
}

function renderTimeline(payload) {
  const events = payload.events || [];

  byId("timelineStatus").textContent =
    payload.timestamp || "Latest snapshot";

  if (!events.length) {
    byId("timelinePanel").innerHTML = `
      <div class="timeline-empty">
        <strong>No changes detected</strong>
        <span>
          The latest graph snapshot matches the previous snapshot.
        </span>
      </div>
    `;
    return;
  }

  byId("timelinePanel").innerHTML = events
    .map(
      event => `
        <div class="timeline-event ${escapeHtml(event.severity || "info")}">
          <div class="timeline-dot"></div>

          <div>
            <strong>${escapeHtml(eventLabel(event))}</strong>

            <span>
              ${escapeHtml(
                event.label ||
                event.nodeId ||
                event.source ||
                "Infrastructure graph"
              )}
            </span>

            <small>
              ${
                event.from && event.to
                  ? `${escapeHtml(event.from)} → ${escapeHtml(event.to)}`
                  : escapeHtml(event.relationship || "")
              }
            </small>
          </div>
        </div>
      `
    )
    .join("");
}

function openDrawer(system) {
  const services = servicesFor(system);
  const managed = isManaged(system.ip);

  byId("drawerContent").innerHTML = `
    <div class="asset-profile-head">
      <div>
        <h2>${escapeHtml(systemName(system))}</h2>
        <p class="drawer-subtitle">
          ${escapeHtml(safe(system.primaryRole))}
        </p>
      </div>

      <span class="asset-profile-status ${managed ? "managed" : ""}">
        ${
          managed
            ? "Managed"
            : escapeHtml(safe(system.health?.label, "Unknown"))
        }
      </span>
    </div>

    <div class="asset-drawer-section">
      <h3>System</h3>

      <div class="asset-detail-grid">
        <div class="asset-detail-field">
          <label>IP Address</label>
          <strong>${escapeHtml(system.ip)}</strong>
        </div>

        <div class="asset-detail-field">
          <label>Hostname</label>
          <strong>
            ${escapeHtml(
              safe(system.profile?.hostname, "Not resolved")
            )}
          </strong>
        </div>

        <div class="asset-detail-field">
          <label>Asset Type</label>
          <strong>
            ${escapeHtml(safe(system.profile?.assetType))}
          </strong>
        </div>

        <div class="asset-detail-field">
          <label>Nexus Agent</label>
          <strong>
            ${escapeHtml(
              safe(system.profile?.agent, "Not installed")
            )}
          </strong>
        </div>
      </div>
    </div>

    <div class="asset-drawer-section">
      <h3>Health Checks</h3>

      <ul class="service-list">
        ${
          (system.health?.checks || [])
            .map(
              check => `
                <li>
                  <span>${escapeHtml(check.name)}</span>
                  <b>${escapeHtml(check.status)}</b>
                </li>
              `
            )
            .join("") ||
          "<li>No health checks.</li>"
        }
      </ul>
    </div>

    <div class="asset-drawer-section">
      <h3>Fingerprints</h3>

      <ul class="service-list">
        ${
          (system.fingerprints || [])
            .map(
              fingerprint => `
                <li>
                  <span>${escapeHtml(fingerprint.label)}</span>
                  <b>${Number(fingerprint.confidence || 0)}%</b>
                </li>
              `
            )
            .join("") ||
          "<li>No fingerprints.</li>"
        }
      </ul>
    </div>

    <div class="asset-drawer-section">
      <h3>Open Services</h3>

      <ul class="service-list">
        ${
          services
            .map(
              service => `
                <li>
                  <span>${escapeHtml(service.service)}</span>
                  <b>:${escapeHtml(service.port)}</b>
                </li>
              `
            )
            .join("") ||
          "<li>No services discovered.</li>"
        }
      </ul>
    </div>

    <div class="asset-drawer-section">
      <h3>Infrastructure Lifecycle</h3>

      <div class="asset-detail-grid">
        <div class="asset-detail-field">
          <label>Status</label>
          <strong>${managed ? "Managed" : "Discovered"}</strong>
        </div>

        <div class="asset-detail-field">
          <label>Next Step</label>
          <strong>
            ${
              managed
                ? "Install or configure software"
                : "Add to Infrastructure"
            }
          </strong>
        </div>
      </div>

      <div class="infrastructure-drawer-actions">
        <button
          id="drawerAddInfrastructure"
          class="btn add-infrastructure-btn"
          type="button"
        >
          ${
            managed
              ? "Update Infrastructure"
              : "Add to Infrastructure"
          }
        </button>

        <button
          id="drawerInstallBitcoin"
          class="btn"
          type="button"
          ${managed ? "" : "disabled"}
        >
          Install Bitcoin Core
        </button>

        <button
          id="drawerEnableRpc"
          class="btn"
          type="button"
          ${managed ? "" : "disabled"}
        >
          Enable Bitcoin RPC
        </button>

        <button
          id="drawerInstallMiningCore"
          class="btn"
          type="button"
          ${managed ? "" : "disabled"}
        >
          Install Seymour MiningCore
        </button>
      </div>

      ${
        managed
          ? ""
          : `
            <p class="drawer-action-help">
              Add this system to Infrastructure before requesting
              installation or configuration actions.
            </p>
          `
      }
    </div>
  `;

  byId("drawer")?.classList.add("open");
  byId("drawerBackdrop")?.classList.add("open");

  byId("drawerAddInfrastructure")?.addEventListener(
    "click",
    () => addSystemToInfrastructure(system)
  );

  byId("drawerInstallBitcoin")?.addEventListener(
    "click",
    () =>
      requestSystemAction(
        system,
        "Install Bitcoin Core"
      )
  );

  byId("drawerEnableRpc")?.addEventListener(
    "click",
    () =>
      requestSystemAction(
        system,
        "Enable Bitcoin RPC"
      )
  );

  byId("drawerInstallMiningCore")?.addEventListener(
    "click",
    () =>
      requestSystemAction(
        system,
        "Install Seymour MiningCore"
      )
  );
}

async function loadDiscovery() {
  byId("discoveryStatus").textContent = "Scanning";

  try {
    const [scanRes, timelineRes] = await Promise.all([
      fetch("/api/discovery/scan"),
      fetch("/api/timeline/latest")
    ]);

    if (!scanRes.ok) {
      throw new Error(
        `/api/discovery/scan returned ${scanRes.status}`
      );
    }

    const data = await scanRes.json();

    if (timelineRes.ok) {
      const timeline = await timelineRes.json();
      renderTimeline(timeline);
    }

    const discovery = data.discovery || data;

    latestSystems = discovery.systems || [];
    latestFound = discovery.found || [];

    renderSummary(discovery);
    renderSystems();

    byId("discoveryStatus").textContent = "Live";
  } catch (error) {
    byId("discoveryList").innerHTML = `
      <div class="empty-state">
        <h2>Discovery failed.</h2>
        <p>${escapeHtml(error.message)}</p>
      </div>
    `;

    byId("discoveryStatus").textContent = "Error";
  }
}

window.addEventListener("DOMContentLoaded", () => {
  byId("drawerClose")?.addEventListener(
    "click",
    closeDrawer
  );

  byId("drawerBackdrop")?.addEventListener(
    "click",
    closeDrawer
  );

  byId("runScan")?.addEventListener(
    "click",
    loadDiscovery
  );

  byId("discoverySearch")?.addEventListener(
    "input",
    event => {
      searchQuery = event.target.value;
      renderSystems();
    }
  );

  document
    .querySelectorAll(".asset-filter")
    .forEach(button => {
      button.addEventListener("click", () => {
        document
          .querySelectorAll(".asset-filter")
          .forEach(item =>
            item.classList.remove("active")
          );

        button.classList.add("active");
        activeFilter = button.dataset.filter;
        renderSystems();
      });
    });

  window.addEventListener(
    "nexus:infrastructure-assets-changed",
    () => renderSystems()
  );

  loadDiscovery();
});
