"use strict";

const SETTINGS_API =
  "/api/platform/nexus-peer-settings";

const PEERS_API =
  "/api/platform/nexus-peers";

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

    loadSettings();
  }
);
