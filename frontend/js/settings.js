"use strict";

const SETTINGS_API =
  "/api/platform/nexus-peer-settings";

const PEERS_API =
  "/api/platform/nexus-peers";

const DISCOVERY_CANDIDATES_API =
  "/api/platform/nexus-discovery-candidates";

function settingsById(id) {
  return document.getElementById(id);
}

function settingsEscape(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    character => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;"
    })[character]
  );
}

function setSettingsStatus(text, state = "") {
  const element = settingsById("settingsStatus");
  if (!element) return;

  element.textContent = text;
  element.className =
    "settings-source-state" +
    (state ? ` ${state}` : "");
}

function setSettingsMessage(text, state = "") {
  const element = settingsById("settingsMessage");
  if (!element) return;

  element.textContent = text;
  element.className =
    "settings-message" +
    (state ? ` ${state}` : "");
}

function setSwitchState(input, enabled) {
  input.checked = Boolean(enabled);

  const state = input
    .closest(".settings-switch")
    ?.querySelector(".settings-switch-state");

  if (state) {
    state.textContent = input.checked ? "On" : "Off";
  }
}

function capabilityPill(label, enabled) {
  return `
    <span class="settings-capability ${enabled ? "enabled" : ""}">
      ${settingsEscape(label)} · ${enabled ? "On" : "Off"}
    </span>
  `;
}

function renderAvailableSystems(payload) {
  const root = settingsById("availableSystems");

  const count =
    settingsById("availableSystemCount");

  const refresh =
    settingsById("refreshAvailableSystems");

  if (!root || !count) return;

  const enabled =
    payload?.enabled === true;

  const candidates =
    Array.isArray(payload?.candidates)
      ? payload.candidates
      : [];

  count.textContent =
    String(candidates.length);

  if (refresh) {
    refresh.disabled = !enabled;
  }

  if (!enabled) {
    root.innerHTML = `
      <div class="settings-empty">
        Turn on “Discover Nexus systems on this network”
        to look for available Nexus installations.
      </div>
    `;
    return;
  }

  if (!candidates.length) {
    root.innerHTML = `
      <div class="settings-empty">
        No unconnected Nexus systems discovered.
      </div>
    `;
    return;
  }

  root.innerHTML = candidates.map(candidate => {
    const machine =
      candidate.machineIdentity || {};

    const transport =
      candidate.transport || {};

    const addresses =
      Array.isArray(transport.addresses)
        ? transport.addresses
        : [];

    const identityText =
      machine.fingerprint ||
      "Verified machine identity";

    const addressText =
      addresses.length
        ? `${addresses.length} discovered address${
            addresses.length === 1 ? "" : "es"
          }`
        : "Network discovered";

    return `
      <article
        class="settings-peer-card settings-available-card"
      >
        <div class="settings-peer-header">
          <div>
            <div class="settings-peer-name">
              ${settingsEscape(
                candidate.name ||
                candidate.hostname ||
                candidate.instanceId ||
                "Nexus System"
              )}
            </div>

            <div class="settings-peer-host">
              ${settingsEscape(
                candidate.hostname ||
                "Discovered Nexus"
              )}
            </div>
          </div>

          <div
            class="settings-peer-status discovered"
          >
            Verified · Available
          </div>
        </div>

        <div class="settings-available-details">
          <div>
            <span>Identity</span>
            <strong>
              ${settingsEscape(identityText)}
            </strong>
          </div>

          <div>
            <span>Transport</span>
            <strong>
              ${settingsEscape(addressText)}
            </strong>
          </div>
        </div>

        <div class="settings-available-note">
          Discovery verifies Nexus identity but does not grant
          trust, management access, CMDB exchange, or authority.
        </div>

        <button
          class="settings-connect-planned"
          type="button"
          disabled
          title="Secure pairing will be wired in the next milestone."
        >
          Connect · Coming Next
        </button>
      </article>
    `;
  }).join("");
}

function renderPeers(payload) {
  const root = settingsById("connectedPeers");
  const count = settingsById("connectedPeerCount");

  if (!root || !count) return;

  const peers = Array.isArray(payload?.peers)
    ? payload.peers
    : [];

  count.textContent = String(peers.length);

  if (!peers.length) {
    root.innerHTML = `
      <div class="settings-empty">
        No connected Nexus systems.
      </div>
    `;
    return;
  }

  root.innerHTML = peers.map(peer => {
    const capabilities = peer.capabilities || {};

    const statusText =
      peer.status === "verified" && peer.enabled
        ? "Verified · Connected"
        : peer.status || "Unknown";

    return `
      <article class="settings-peer-card">
        <div class="settings-peer-header">
          <div>
            <div class="settings-peer-name">
              ${settingsEscape(
                peer.name ||
                peer.hostname ||
                peer.remoteInstanceId ||
                "Nexus System"
              )}
            </div>

            <div class="settings-peer-host">
              ${settingsEscape(peer.hostname || "Unknown host")}
            </div>
          </div>

          <div class="settings-peer-status">
            ${settingsEscape(statusText)}
          </div>
        </div>

        <div class="settings-peer-meta">
          <div>
            <span>Instance</span>
            <strong>
              ${settingsEscape(peer.remoteInstanceId || "Unknown")}
            </strong>
          </div>

          <div>
            <span>Protocol</span>
            <strong>
              ${settingsEscape(
                peer.protocol?.name || "Unknown"
              )}
              ${settingsEscape(
                peer.protocol?.version || ""
              )}
            </strong>
          </div>

          <div>
            <span>Last verified</span>
            <strong>
              ${
                peer.lastVerifiedAt
                  ? settingsEscape(
                      new Date(
                        peer.lastVerifiedAt
                      ).toLocaleString()
                    )
                  : "Unknown"
              }
            </strong>
          </div>
        </div>

        <div class="settings-capabilities">
          ${capabilityPill(
            "Peer awareness",
            capabilities.peerAwareness
          )}
          ${capabilityPill(
            "Federation",
            capabilities.federation
          )}
          ${capabilityPill(
            "CMDB sharing",
            capabilities.cmdbExchange
          )}
          ${capabilityPill(
            "Discovery sharing",
            capabilities.discoveryExchange
          )}
          ${capabilityPill(
            "Remote management",
            capabilities.management
          )}
          ${capabilityPill(
            "Authority delegation",
            capabilities.authorityDelegation
          )}
        </div>
      </article>
    `;
  }).join("");
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    cache: "no-store",
    ...options
  });

  const payload = await response.json().catch(
    () => ({})
  );

  if (!response.ok || payload.status === "error") {
    throw new Error(
      payload.error ||
      `Request failed (${response.status})`
    );
  }

  return payload;
}

async function loadSettings() {
  const discovery =
    settingsById("localDiscoveryEnabled");

  const connections =
    settingsById("allowPeerConnections");

  discovery.disabled = true;
  connections.disabled = true;

  setSettingsStatus("Loading settings…");
  setSettingsMessage("");

  try {
    const [settingsPayload, peersPayload] =
      await Promise.all([
        requestJson(SETTINGS_API),
        requestJson(PEERS_API)
      ]);

    const settings =
      settingsPayload.settings || {};

    setSwitchState(
      discovery,
      settings.localDiscoveryEnabled
    );

    setSwitchState(
      connections,
      settings.allowPeerConnections
    );

    renderPeers(peersPayload);

    if (settings.localDiscoveryEnabled) {
      await loadAvailableSystems();
    } else {
      renderAvailableSystems({
        status: "ok",
        enabled: false,
        count: 0,
        candidates: []
      });
    }

    discovery.disabled = false;
    connections.disabled = false;

    setSettingsStatus(
      "Settings available",
      "healthy"
    );
  } catch (error) {
    setSettingsStatus(
      "Settings unavailable",
      "error"
    );

    setSettingsMessage(
      error.message,
      "error"
    );
  }
}

async function updateSetting(input, settingName) {
  const desired = input.checked;
  const previous = !desired;

  input.disabled = true;
  setSettingsMessage("Saving…");

  try {
    const payload = await requestJson(
      SETTINGS_API,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          [settingName]: desired
        })
      }
    );

    const settings = payload.settings || {};

    setSwitchState(
      input,
      settings[settingName]
    );

    setSettingsMessage(
      "Setting saved.",
      "success"
    );

    if (
      settingName === "localDiscoveryEnabled"
    ) {
      await loadAvailableSystems();
    }
  } catch (error) {
    setSwitchState(input, previous);

    setSettingsMessage(
      error.message,
      "error"
    );
  } finally {
    input.disabled = false;
  }
}

async function loadAvailableSystems() {
  const discovery =
    settingsById("localDiscoveryEnabled");

  const refresh =
    settingsById("refreshAvailableSystems");

  const root =
    settingsById("availableSystems");

  const count =
    settingsById("availableSystemCount");

  if (!discovery?.checked) {
    renderAvailableSystems({
      status: "ok",
      enabled: false,
      count: 0,
      candidates: []
    });
    return;
  }

  if (refresh) {
    refresh.disabled = true;
  }

  if (count) {
    count.textContent = "—";
  }

  if (root) {
    root.innerHTML = `
      <div class="settings-empty">
        Looking for Nexus systems…
      </div>
    `;
  }

  try {
    const payload = await requestJson(
      DISCOVERY_CANDIDATES_API
    );

    renderAvailableSystems(payload);
  } catch (error) {
    if (count) {
      count.textContent = "—";
    }

    if (root) {
      root.innerHTML = `
        <div
          class="settings-empty settings-empty-error"
        >
          ${settingsEscape(error.message)}
        </div>
      `;
    }
  } finally {
    if (refresh) {
      refresh.disabled =
        !discovery.checked;
    }
  }
}

document.addEventListener(
  "DOMContentLoaded",
  () => {
    const discovery =
      settingsById("localDiscoveryEnabled");

    const connections =
      settingsById("allowPeerConnections");

    discovery?.addEventListener(
      "change",
      () => updateSetting(
        discovery,
        "localDiscoveryEnabled"
      )
    );

    connections?.addEventListener(
      "change",
      () => updateSetting(
        connections,
        "allowPeerConnections"
      )
    );

    settingsById(
      "refreshAvailableSystems"
    )?.addEventListener(
      "click",
      loadAvailableSystems
    );

    loadSettings();
  }
);
