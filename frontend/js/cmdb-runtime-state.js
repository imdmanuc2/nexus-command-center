(() => {
  "use strict";

  const API_URL = "/api/cmdb/assets";
  const VALID_STATES = new Set([
    "not-installed",
    "stopped",
    "starting",
    "syncing",
    "healthy",
    "degraded",
  ]);

  function asObject(value) {
    return value && typeof value === "object" && !Array.isArray(value)
      ? value
      : {};
  }

  function text(value, fallback = "—") {
    if (value === undefined || value === null || value === "") return fallback;
    return String(value);
  }

  function boolLabel(value) {
    if (value === true || value === 1 || value === "1") return "Yes";
    if (value === false || value === 0 || value === "0") return "No";
    return "—";
  }

  function normalizeAssets(payload) {
    if (Array.isArray(payload)) return payload;
    if (Array.isArray(payload?.assets)) return payload.assets;
    if (Array.isArray(payload?.items)) return payload.items;
    if (Array.isArray(payload?.data)) return payload.data;
    return [];
  }

  function assetId(asset) {
    return String(
      asset?.assetId ??
      asset?.asset_id ??
      asset?.id ??
      ""
    );
  }

  function assetType(asset) {
    return String(
      asset?.assetType ??
      asset?.asset_type ??
      asset?.type ??
      ""
    ).toLowerCase();
  }

  function observedState(asset) {
    return asObject(
      asset?.observedState ??
      asset?.observed_state
    );
  }

  function runtimeState(asset) {
    const observed = observedState(asset);
    const nestedTelemetry = asObject(observed.telemetry);

    const state = String(
      observed.runtimeState ??
      nestedTelemetry.runtimeState ??
      asset?.runtimeState ??
      ""
    ).trim().toLowerCase();

    return VALID_STATES.has(state) ? state : "";
  }

  function runtimeInfo(asset) {
    const observed = observedState(asset);
    const nestedTelemetry = asObject(observed.telemetry);
    const sync = asObject(observed.sync);
    const telemetrySync = asObject(nestedTelemetry.sync);
    const state = runtimeState(asset);

    const verificationProgress =
      observed.runtimeVerificationProgress ??
      nestedTelemetry.runtimeVerificationProgress ??
      asObject(nestedTelemetry.operationalState).verificationProgress ??
      null;

    let progressPercent =
      sync?.snapshot?.progress_percent ??
      sync?.progressPercent ??
      telemetrySync?.progressPercent ??
      null;

    if (
      (progressPercent === null || progressPercent === undefined) &&
      verificationProgress !== null &&
      verificationProgress !== undefined
    ) {
      const numeric = Number(verificationProgress);
      if (Number.isFinite(numeric)) progressPercent = numeric * 100;
    }

    const rpcReachable =
      observed.runtimeRpcReachable ??
      nestedTelemetry.runtimeRpcReachable ??
      asObject(nestedTelemetry.operationalState).rpcReachable ??
      null;

    const rpcHealthy =
      observed.runtimeRpcHealthy ??
      nestedTelemetry.runtimeRpcHealthy ??
      asObject(nestedTelemetry.operationalState).rpcHealthy ??
      null;

    const initialBlockDownload =
      observed.runtimeInitialBlockDownload ??
      nestedTelemetry.runtimeInitialBlockDownload ??
      telemetrySync.initialBlockDownload ??
      asObject(nestedTelemetry.operationalState).initialBlockDownload ??
      null;

    const reason =
      observed.runtimeStateReason ??
      nestedTelemetry.runtimeStateReason ??
      asObject(nestedTelemetry.operationalState).reason ??
      "";

    return {
      state,
      reason,
      rpcReachable,
      rpcHealthy,
      initialBlockDownload,
      progressPercent,
      height:
        sync?.snapshot?.height ??
        telemetrySync.height ??
        asObject(asObject(nestedTelemetry.rpc).probe).height ??
        null,
      headers:
        sync?.snapshot?.headers ??
        telemetrySync.headers ??
        asObject(asObject(nestedTelemetry.rpc).probe).headers ??
        null,
      peers:
        sync?.snapshot?.peers ??
        nestedTelemetry.peers ??
        asObject(asObject(nestedTelemetry.rpc).probe).peers ??
        null,
    };
  }

  function stateLabel(state) {
    const labels = {
      "not-installed": "Not Installed",
      stopped: "Stopped",
      starting: "Starting",
      syncing: "Syncing",
      healthy: "Healthy",
      degraded: "Degraded",
    };
    return labels[state] || "Unknown";
  }

  function clampPercent(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return null;
    return Math.max(0, Math.min(100, n));
  }

  function currentAssetId() {
    const params = new URLSearchParams(window.location.search);
    return (
      params.get("id") ||
      params.get("assetId") ||
      params.get("asset_id") ||
      ""
    );
  }

  function detailCard(asset) {
    const info = runtimeInfo(asset);
    if (!info.state) return null;

    const card = document.createElement("section");
    card.className = "cmdb-runtime-card";
    card.dataset.runtimeState = info.state;

    const pct = clampPercent(info.progressPercent);
    const progressText = pct === null ? "Telemetry pending" : `${pct.toFixed(2)}%`;

    card.innerHTML = `
      <div class="cmdb-runtime-card__head">
        <div>
          <div class="cmdb-runtime-eyebrow">Blockchain Runtime</div>
          <h2>Operational State</h2>
        </div>
        <span class="cmdb-runtime-badge" data-state="${info.state}">
          ${stateLabel(info.state)}
        </span>
      </div>

      <div class="cmdb-runtime-grid">
        <div class="cmdb-runtime-stat">
          <span>RPC Reachable</span>
          <strong>${boolLabel(info.rpcReachable)}</strong>
        </div>
        <div class="cmdb-runtime-stat">
          <span>RPC Healthy</span>
          <strong>${boolLabel(info.rpcHealthy)}</strong>
        </div>
        <div class="cmdb-runtime-stat">
          <span>Initial Block Download</span>
          <strong>${boolLabel(info.initialBlockDownload)}</strong>
        </div>
        <div class="cmdb-runtime-stat">
          <span>Peers</span>
          <strong>${text(info.peers)}</strong>
        </div>
        <div class="cmdb-runtime-stat">
          <span>Block Height</span>
          <strong>${text(info.height)}</strong>
        </div>
        <div class="cmdb-runtime-stat">
          <span>Headers</span>
          <strong>${text(info.headers)}</strong>
        </div>
      </div>

      <div class="cmdb-runtime-progress">
        <div class="cmdb-runtime-progress__top">
          <span>Chain Synchronization</span>
          <strong>${progressText}</strong>
        </div>
        <div class="cmdb-runtime-progress__track" aria-label="Blockchain synchronization progress">
          <span style="width:${pct === null ? 0 : pct}%"></span>
        </div>
      </div>

      ${info.reason ? `
        <div class="cmdb-runtime-reason">
          <span>State reason</span>
          <p>${text(info.reason)}</p>
        </div>
      ` : ""}
    `;

    return card;
  }

  function injectDetail(asset) {
    if (document.querySelector(".cmdb-runtime-card")) return;

    const card = detailCard(asset);
    if (!card) return;

    const candidates = [
      document.querySelector(".cmdb-object-main"),
      document.querySelector(".cmdb-object-page"),
      document.querySelector("main .nexus-panel"),
      document.querySelector("main"),
    ].filter(Boolean);

    const host = candidates[0];
    if (!host) return;

    const firstSection = host.querySelector("section");
    if (firstSection && firstSection.parentNode === host) {
      firstSection.insertAdjacentElement("afterend", card);
    } else {
      host.appendChild(card);
    }
  }

  function decorateAssetLinks(assets) {
    const byId = new Map(
      assets
        .filter((asset) => assetType(asset) === "blockchain-node" && runtimeState(asset))
        .map((asset) => [assetId(asset), asset])
    );

    if (!byId.size) return;

    document.querySelectorAll("a[href*='cmdb-object']").forEach((link) => {
      if (link.querySelector(".cmdb-runtime-inline-badge")) return;

      let id = "";
      try {
        const url = new URL(link.href, window.location.origin);
        id = url.searchParams.get("id") ||
             url.searchParams.get("assetId") ||
             url.searchParams.get("asset_id") ||
             "";
      } catch (_) {
        return;
      }

      const asset = byId.get(String(id));
      if (!asset) return;

      const state = runtimeState(asset);
      const badge = document.createElement("span");
      badge.className = "cmdb-runtime-inline-badge";
      badge.dataset.state = state;
      badge.textContent = stateLabel(state);
      link.appendChild(badge);
    });
  }

  async function load() {
    let response;
    try {
      response = await fetch(API_URL, {
        cache: "no-store",
        headers: { Accept: "application/json" },
      });
    } catch (error) {
      console.warn("CMDB runtime state fetch failed", error);
      return;
    }

    if (!response.ok) {
      console.warn("CMDB runtime state API returned", response.status);
      return;
    }

    let payload;
    try {
      payload = await response.json();
    } catch (error) {
      console.warn("CMDB runtime state JSON parse failed", error);
      return;
    }

    const assets = normalizeAssets(payload);
    const id = currentAssetId();

    if (id) {
      const asset = assets.find((item) => assetId(item) === String(id));
      if (asset && assetType(asset) === "blockchain-node") {
        injectDetail(asset);
      }
    }

    decorateAssetLinks(assets);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", load, { once: true });
  } else {
    load();
  }

  // Assets may render after API calls from assets.js. Re-run decoration
  // without touching the existing CMDB rendering lifecycle.
  const observer = new MutationObserver(() => {
    window.clearTimeout(observer._timer);
    observer._timer = window.setTimeout(load, 150);
  });

  window.addEventListener("load", () => {
    observer.observe(document.body, {
      childList: true,
      subtree: true,
    });
  }, { once: true });
})();
