"use strict";

const PEERS_API =
  "/api/platform/nexus-peers";

const DISCOVERY_API =
  "/api/platform/nexus-discovery-candidates";

const REQUESTS_API =
  "/api/platform/nexus-connection-requests";

const CONNECT_API =
  "/api/platform/nexus-connect";

const PAIRINGS_API =
  "/api/platform/nexus-pairings";

function byId(id) {
  return document.getElementById(id);
}

function escapeHtml(value) {
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

function status(text, state = "") {
  const element = byId("peersStatus");
  if (!element) return;

  element.textContent = text;
  element.className =
    "peers-source-state" +
    (state ? ` ${state}` : "");
}

function message(text, state = "") {
  const element = byId("peersMessage");
  if (!element) return;

  element.textContent = text;
  element.className =
    "peers-message" +
    (state ? ` ${state}` : "");
}

function formatDate(value) {
  if (!value) return "Unknown";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return date.toLocaleString();
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

function capability(label, enabled) {
  return `
    <span class="peer-capability ${enabled ? "enabled" : ""}">
      ${escapeHtml(label)} · ${enabled ? "On" : "Off"}
    </span>
  `;
}

function renderConnected(payload) {
  const root = byId("connectedPeers");

  const peers =
    Array.isArray(payload?.peers)
      ? payload.peers
      : [];

  byId("summaryConnected").textContent =
    String(peers.length);

  if (!peers.length) {
    root.innerHTML = `
      <div class="peers-empty">
        No connected Nexus systems.
      </div>
    `;
    return;
  }

  root.innerHTML = peers.map(peer => {
    const caps = peer.capabilities || {};

    return `
      <article class="peer-card">
        <div class="peer-card-header">
          <div>
            <h3>
              ${escapeHtml(
                peer.name ||
                peer.hostname ||
                peer.remoteInstanceId ||
                "Nexus System"
              )}
            </h3>

            <p>
              ${escapeHtml(
                peer.hostname || "Unknown host"
              )}
            </p>
          </div>

          <span class="peer-state connected">
            ${
              peer.status === "verified" && peer.enabled
                ? "Verified · Connected"
                : escapeHtml(peer.status || "Unknown")
            }
          </span>
        </div>

        <div class="peer-meta">
          <div>
            <span>Instance</span>
            <strong>
              ${escapeHtml(peer.remoteInstanceId || "Unknown")}
            </strong>
          </div>

          <div>
            <span>Fingerprint</span>
            <strong class="peer-fingerprint">
              ${escapeHtml(
                peer.publicKeyFingerprint || "Unavailable"
              )}
            </strong>
          </div>

          <div>
            <span>Protocol</span>
            <strong>
              ${escapeHtml(peer.protocol?.name || "Unknown")}
              ${escapeHtml(peer.protocol?.version || "")}
            </strong>
          </div>

          <div>
            <span>Last verified</span>
            <strong>
              ${escapeHtml(formatDate(peer.lastVerifiedAt))}
            </strong>
          </div>

          <div>
            <span>Last seen</span>
            <strong>
              ${escapeHtml(formatDate(peer.lastSeenAt))}
            </strong>
          </div>
        </div>

        <div class="peer-capabilities">
          ${capability("Peer awareness", caps.peerAwareness)}
          ${capability("Federation", caps.federation)}
          ${capability("CMDB sharing", caps.cmdbExchange)}
          ${capability(
            "Discovery sharing",
            caps.discoveryExchange
          )}
          ${capability(
            "Remote management",
            caps.management
          )}
          ${capability(
            "Authority delegation",
            caps.authorityDelegation
          )}
        </div>
      </article>
    `;
  }).join("");
}

function renderDiscovered(payload) {
  const root = byId("discoveredPeers");

  const enabled = payload?.enabled === true;

  const candidates =
    Array.isArray(payload?.candidates)
      ? payload.candidates
      : [];

  byId("summaryDiscovered").textContent =
    String(candidates.length);

  if (!enabled) {
    root.innerHTML = `
      <div class="peers-empty">
        Local Nexus discovery is disabled.
        Enable it from Settings to discover peers.
      </div>
    `;
    return;
  }

  if (!candidates.length) {
    root.innerHTML = `
      <div class="peers-empty">
        No unconnected Nexus systems discovered.
      </div>
    `;
    return;
  }

  root.innerHTML = candidates.map(candidate => {
    const machine = candidate.machineIdentity || {};
    const transport = candidate.transport || {};
    const addresses =
      Array.isArray(transport.addresses)
        ? transport.addresses
        : [];

    return `
      <article class="peer-card">
        <div class="peer-card-header">
          <div>
            <h3>
              ${escapeHtml(
                candidate.name ||
                candidate.hostname ||
                candidate.instanceId ||
                "Nexus System"
              )}
            </h3>

            <p>
              ${escapeHtml(
                candidate.hostname || "Discovered Nexus"
              )}
            </p>
          </div>

          <span class="peer-state discovered">
            Verified · Untrusted
          </span>
        </div>

        <div class="peer-meta">
          <div>
            <span>Instance</span>
            <strong>
              ${escapeHtml(candidate.instanceId || "Unknown")}
            </strong>
          </div>

          <div>
            <span>Fingerprint</span>
            <strong class="peer-fingerprint">
              ${escapeHtml(
                machine.fingerprint || "Unknown"
              )}
            </strong>
          </div>

          <div>
            <span>Discovery</span>
            <strong>
              ${escapeHtml(
                candidate.source || "Local network"
              )}
            </strong>
          </div>

          <div>
            <span>Transport</span>
            <strong>
              ${escapeHtml(
                addresses.length
                  ? `${addresses.length} address${
                      addresses.length === 1 ? "" : "es"
                    }`
                  : "Network discovered"
              )}
            </strong>
          </div>
        </div>

        <div class="peer-actions">
          <button
            class="peers-button primary"
            type="button"
            data-peer-action="connect"
            data-instance-id="${
              escapeHtml(candidate.instanceId || "")
            }"
          >
            Connect
          </button>
        </div>
      </article>
    `;
  }).join("");
}

function requestIdentity(request) {
  return (
    request.remoteName ||
    request.requestedRemoteName ||
    request.remoteHostname ||
    request.requestedRemoteHostname ||
    request.remoteInstanceId ||
    request.requestedRemoteInstanceId ||
    "Nexus System"
  );
}

function requestEnrollmentId(request) {
  return (
    request.enrollmentId ||
    request.id ||
    ""
  );
}

function renderInboundRequests(payload) {
  const requests =
    Array.isArray(payload?.requests)
      ? payload.requests
      : [];

  return requests.map(request => {
    const enrollmentId =
      requestEnrollmentId(request);

    return `
      <article class="peer-card">
        <div class="peer-card-header">
          <div>
            <h3>
              ${escapeHtml(requestIdentity(request))}
            </h3>
            <p>Incoming secure connection request</p>
          </div>

          <span class="peer-state pending">
            Pending Approval
          </span>
        </div>

        <div class="peer-meta">
          <div>
            <span>Enrollment</span>
            <strong>
              ${escapeHtml(enrollmentId || "Unknown")}
            </strong>
          </div>

          <div>
            <span>Expires</span>
            <strong>
              ${escapeHtml(
                formatDate(request.expiresAt)
              )}
            </strong>
          </div>
        </div>

        <div class="peer-actions">
          <button
            class="peers-button primary"
            type="button"
            data-peer-action="approve"
            data-enrollment-id="${escapeHtml(enrollmentId)}"
          >
            Approve
          </button>

          <button
            class="peers-button danger"
            type="button"
            data-peer-action="reject"
            data-enrollment-id="${escapeHtml(enrollmentId)}"
          >
            Reject
          </button>
        </div>
      </article>
    `;
  }).join("");
}

function renderOutboundPairings(payload) {
  const pairings =
    Array.isArray(payload?.pairings)
      ? payload.pairings
      : [];

  const active = pairings.filter(
    pairing => pairing.status !== "connected"
  );

  return active.map(pairing => {
    const state =
      String(pairing.status || "unknown");

    const canReconcile =
      ["pending", "requesting", "failed"].includes(state);

    const canComplete =
      ["approved", "completing", "failed"].includes(state);

    return `
      <article class="peer-card">
        <div class="peer-card-header">
          <div>
            <h3>
              ${escapeHtml(
                pairing.remoteName ||
                pairing.remoteHostname ||
                pairing.remoteInstanceId ||
                "Nexus System"
              )}
            </h3>

            <p>Outbound secure pairing</p>
          </div>

          <span class="peer-state pending">
            ${escapeHtml(state)}
          </span>
        </div>

        <div class="peer-meta">
          <div>
            <span>Instance</span>
            <strong>
              ${escapeHtml(
                pairing.remoteInstanceId || "Unknown"
              )}
            </strong>
          </div>

          <div>
            <span>Fingerprint</span>
            <strong class="peer-fingerprint">
              ${escapeHtml(
                pairing.remotePublicKeyFingerprint ||
                "Unknown"
              )}
            </strong>
          </div>

          <div>
            <span>Requested</span>
            <strong>
              ${escapeHtml(
                formatDate(pairing.requestedAt)
              )}
            </strong>
          </div>

          <div>
            <span>Last error</span>
            <strong>
              ${escapeHtml(
                pairing.lastError || "None"
              )}
            </strong>
          </div>
        </div>

        <div class="peer-actions">
          ${
            canReconcile
              ? `
                <button
                  class="peers-button secondary"
                  type="button"
                  data-peer-action="reconcile"
                  data-pairing-id="${
                    escapeHtml(pairing.pairingId)
                  }"
                >
                  Check Approval
                </button>
              `
              : ""
          }

          ${
            canComplete
              ? `
                <button
                  class="peers-button primary"
                  type="button"
                  data-peer-action="complete"
                  data-pairing-id="${
                    escapeHtml(pairing.pairingId)
                  }"
                >
                  Complete Connection
                </button>
              `
              : ""
          }
        </div>
      </article>
    `;
  }).join("");
}

async function loadPeerState() {
  status("Loading peer state…");
  message("");

  try {
    const [
      peers,
      discovery,
      requests,
      pairings
    ] = await Promise.all([
      requestJson(PEERS_API),
      requestJson(DISCOVERY_API),
      requestJson(REQUESTS_API),
      requestJson(PAIRINGS_API)
    ]);

    renderConnected(peers);
    renderDiscovered(discovery);

    const inbound =
      Array.isArray(requests?.requests)
        ? requests.requests
        : [];

    const outbound =
      Array.isArray(pairings?.pairings)
        ? pairings.pairings.filter(
            item => item.status !== "connected"
          )
        : [];

    byId("summaryPending").textContent =
      String(inbound.length + outbound.length);

    const pendingRoot = byId("pendingPeers");

    const pendingHtml =
      renderInboundRequests(requests) +
      renderOutboundPairings(pairings);

    pendingRoot.innerHTML =
      pendingHtml ||
      `
        <div class="peers-empty">
          No pending Nexus connection activity.
        </div>
      `;

    status("Peer state healthy", "healthy");
  } catch (error) {
    status("Peer state unavailable", "error");
    message(error.message, "error");
  }
}

async function postEmpty(url) {
  return requestJson(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: "{}"
  });
}

async function performAction(button) {
  const action =
    button.dataset.peerAction || "";

  button.disabled = true;
  message("");

  try {
    if (action === "connect") {
      const instanceId =
        button.dataset.instanceId || "";

      await requestJson(CONNECT_API, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          instanceId
        })
      });

      message(
        "Secure connection request created.",
        "success"
      );
    }

    if (action === "approve" || action === "reject") {
      const enrollmentId =
        button.dataset.enrollmentId || "";

      await postEmpty(
        `${REQUESTS_API}/${encodeURIComponent(
          enrollmentId
        )}/${action}`
      );

      message(
        action === "approve"
          ? "Connection request approved."
          : "Connection request rejected.",
        "success"
      );
    }

    if (action === "reconcile" || action === "complete") {
      const pairingId =
        button.dataset.pairingId || "";

      await postEmpty(
        `${PAIRINGS_API}/${encodeURIComponent(
          pairingId
        )}/${action}`
      );

      message(
        action === "reconcile"
          ? "Remote approval state checked."
          : "Secure peer connection completed.",
        "success"
      );
    }

    await loadPeerState();
  } catch (error) {
    message(error.message, "error");
    button.disabled = false;
  }
}

document.addEventListener("click", event => {
  const button =
    event.target.closest("[data-peer-action]");

  if (!button) return;

  performAction(button);
});

document.addEventListener("DOMContentLoaded", () => {
  byId("refreshPeers")?.addEventListener(
    "click",
    loadPeerState
  );

  loadPeerState();
});
