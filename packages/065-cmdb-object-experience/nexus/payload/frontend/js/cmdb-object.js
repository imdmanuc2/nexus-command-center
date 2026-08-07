(function () {
  "use strict";
  const byId = (id) => document.getElementById(id);
  const safe = (value, fallback = "—") => value === undefined || value === null || value === "" ? fallback : String(value);
  const escapeHtml = (value) => safe(value, "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
  const number = (value) => Number(value || 0);

  function label(value) {
    return safe(value, "Object").replaceAll("_", " ").replaceAll("-", " ").replace(/\b\w/g, (char) => char.toUpperCase());
  }

  function statusClass(status) {
    const value = safe(status, "unknown").toLowerCase();
    if (["online", "active", "healthy", "managed", "observed", "mining", "connected", "synchronized", "accepting-shares"].includes(value)) return "healthy";
    if (["warning", "partial", "idle", "unknown", "starting", "commissioning", "maintenance"].includes(value)) return "warning";
    if (["offline", "failed", "critical", "unmanaged", "disconnected", "retired"].includes(value)) return "critical";
    return "neutral";
  }

  function formatHashrate(value) {
    const n = number(value);
    if (n >= 1e12) return `${(n / 1e12).toFixed(2)} TH/s`;
    if (n >= 1e9) return `${(n / 1e9).toFixed(2)} GH/s`;
    if (n >= 1e6) return `${(n / 1e6).toFixed(2)} MH/s`;
    if (n > 0) return `${n.toFixed(0)} H/s`;
    return "Not reported";
  }

  function formatDate(value) {
    if (!value) return "Not reported";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? safe(value) : date.toLocaleString();
  }

  function displayValue(value) {
    if (Array.isArray(value)) return value.join(", ") || "—";
    if (value && typeof value === "object") return JSON.stringify(value);
    return safe(value);
  }

  function importantFields(raw) {
    const preferred = ["assetId", "poolInstanceId", "workerId", "workloadId", "id", "assetType", "canonicalType", "workerType", "workloadType", "manufacturer", "model", "serialNumber", "ip", "host", "hostname", "macAddress", "operatingSystem", "architecture", "location", "rack", "position"];
    const rows = [];
    preferred.forEach((key) => {
      if (!(key in raw) || raw[key] === undefined || raw[key] === null || raw[key] === "") return;
      rows.push([label(key), displayValue(raw[key])]);
    });
    return rows.length ? rows : Object.entries(raw).filter(([, value]) => !value || typeof value !== "object").slice(0, 14).map(([key, value]) => [label(key), displayValue(value)]);
  }

  function metric(labelText, value, tone = "") {
    return `<div class="cmdb-metric ${tone}"><span>${escapeHtml(labelText)}</span><strong>${escapeHtml(value)}</strong></div>`;
  }

  function relationshipCard(rel, currentId) {
    const currentIsSource = rel.sourceId === currentId;
    const neighbor = currentIsSource ? rel.targetObject : rel.sourceObject;
    const direction = currentIsSource ? "Outgoing" : "Incoming";
    const relationship = label(rel.relationshipType || "related to");
    const href = neighbor?.href || "#";
    return `<a class="cmdb-relationship-card" href="${escapeHtml(href)}"><span>${direction} · ${escapeHtml(relationship)}</span><strong>${escapeHtml(neighbor?.displayName || (currentIsSource ? rel.targetName : rel.sourceName))}</strong><small>${escapeHtml(neighbor?.subtitle || neighbor?.objectType || "CMDB object")}</small><em class="${statusClass(rel.status)}">${escapeHtml(rel.status || "mapped")}</em></a>`;
  }

  function setProfile(profile) {
    byId("profileMission").value = profile.mission || "";
    byId("profileRole").value = profile.role || "";
    byId("profileManagement").value = profile.managementModel || "nexus-managed";
    byId("profileLifecycle").value = profile.lifecycleStage || "production";
    const desired = profile.desiredOperationalState || "automatic";
    const desiredSelect = byId("profileDesired");
    if (![...desiredSelect.options].some((option) => option.value === desired)) desiredSelect.add(new Option(label(desired), desired));
    desiredSelect.value = desired;
    byId("profileObserved").value = profile.observedOperationalState || "unknown";
    byId("profileHealth").value = profile.health || "unknown";
    byId("profileConnectivity").value = profile.connectivity || "unknown";
  }

  async function loadProfile(assetId) {
    const form = byId("operationalProfileForm");
    if (!assetId) { form.hidden = true; return; }
    const response = await fetch(`/api/cmdb/operational-profile?assetId=${encodeURIComponent(assetId)}`, {cache: "no-store"});
    if (!response.ok) { form.hidden = true; return; }
    const payload = await response.json();
    setProfile(payload.profile || {});
    form.onsubmit = async (event) => {
      event.preventDefault();
      const message = byId("profileMessage");
      message.textContent = "Saving…";
      try {
        const update = await fetch("/api/cmdb/operational-profile/update", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({assetId, mission: byId("profileMission").value, role: byId("profileRole").value, managementModel: byId("profileManagement").value, lifecycleStage: byId("profileLifecycle").value, desiredOperationalState: byId("profileDesired").value, observedOperationalState: byId("profileObserved").value, health: byId("profileHealth").value, connectivity: byId("profileConnectivity").value, reason: byId("profileReason").value, changedBy: "cmdb-ui"})});
        const result = await update.json();
        if (!update.ok) throw new Error(result.error || "Profile update failed");
        setProfile(result.profile || {});
        message.textContent = "Saved";
      } catch (error) { message.textContent = error.message; }
    };
  }

  function operationalState(object, raw) {
    return raw.observedOperationalState || raw.operationalState || raw.activityState || object.status || raw.status || "unknown";
  }

  function liveHashrate(raw) {
    return number(raw.currentHashrate || raw.liveHashrate || raw.hashrate || raw.observedState?.hashrate || raw.observedState?.telemetry?.hashrate5m);
  }

  function currentPoolName(raw, relationships) {
    const liveId = raw.livePoolId || raw.poolInstanceId || raw.observedState?.currentPool || raw.poolId;
    const poolRel = relationships.find((rel) => (rel.relationshipType || "").replaceAll("_", "-").toLowerCase() === "mines-on" && (rel.status || "active") !== "inactive");
    if (poolRel) return poolRel.targetObject?.displayName || poolRel.targetName || liveId || "Not assigned";
    return liveId || "Not assigned";
  }

  function renderLive(object, raw, relationships) {
    const type = object.objectType;
    const state = operationalState(object, raw);
    const observed = raw.observedState || {};
    const hashrate = liveHashrate(raw);
    const fields = [];
    fields.push(metric("Observed state", label(state), statusClass(state)));
    if (hashrate > 0 || ["asset", "worker", "pool"].includes(type)) fields.push(metric("Hashrate", formatHashrate(hashrate), hashrate > 0 ? "healthy" : ""));
    if (["asset", "worker"].includes(type)) {
      fields.push(metric("Current pool", currentPoolName(raw, relationships)));
      fields.push(metric("Worker", raw.workerName || raw.liveWorkerId || raw.sourceWorkerId || raw.workerId || "Not reported"));
      fields.push(metric("Accepted shares", safe(raw.acceptedShares ?? observed.acceptedShares, "Not reported")));
      fields.push(metric("Rejected shares", safe(raw.rejectedShares ?? observed.rejectedShares, "Not reported"), number(raw.rejectedShares ?? observed.rejectedShares) > 0 ? "warning" : "healthy"));
    } else if (type === "pool") {
      fields.push(metric("Active workers", safe(observed.activeWorkers ?? observed.connectedWorkers ?? raw.workerCount, "0"), number(observed.activeWorkers ?? raw.workerCount) > 0 ? "healthy" : ""));
      fields.push(metric("Accepted shares", safe(observed.acceptedShares, "Not reported")));
      fields.push(metric("Rejected shares", safe(observed.rejectedShares, "Not reported"), number(observed.rejectedShares) > 0 ? "warning" : "healthy"));
      fields.push(metric("Efficiency", observed.efficiency !== undefined ? `${(number(observed.efficiency) * 100).toFixed(2)}%` : "Not reported"));
    } else if (type === "service") {
      fields.push(metric("Implementation", raw.implementation || "Not reported"));
      fields.push(metric("Host", raw.host || "Not reported"));
      fields.push(metric("API port", safe(raw.apiPort, "Not reported")));
      fields.push(metric("Stratum ports", (raw.stratumPorts || []).join(", ") || "Not reported"));
    } else if (type === "workload") {
      fields.push(metric("Runtime", raw.runtime || "Not reported"));
      fields.push(metric("Software", raw.software || "Not reported"));
      fields.push(metric("Coin", raw.coin || "Not reported"));
      fields.push(metric("Pool", raw.poolInstanceId || raw.poolId || "Not assigned"));
    }
    byId("liveOperations").innerHTML = fields.join("");
    byId("liveStateBadge").textContent = label(state).toUpperCase();
    byId("liveStateBadge").className = statusClass(state);
  }

  function renderHealth(object, raw) {
    const health = raw.health || raw.healthState || (object.status === "online" ? "healthy" : "unknown");
    const connectivity = raw.connectivity || raw.connectivityState || (raw.connectionConfirmed ? "connected" : "unknown");
    const telemetry = raw.telemetryAvailable === true || raw.observedState?.apiReachable === true ? "available" : raw.telemetryAvailable === false ? "unavailable" : "unknown";
    const lastSeen = raw.lastSeenAt || raw.lastActivityAt || raw.lastShareAt || raw.updatedAt;
    byId("healthSummary").innerHTML = [metric("Health", label(health), statusClass(health)), metric("Connectivity", label(connectivity), statusClass(connectivity)), metric("Telemetry", label(telemetry), telemetry === "available" ? "healthy" : "warning"), metric("Last observed", formatDate(lastSeen))].join("");
    byId("objectHealth").textContent = `HEALTH ${label(health).toUpperCase()}`;
    byId("objectHealth").className = `cmdb-state-pill ${statusClass(health)}`;
  }

  function renderTimeline(raw, object, relationships) {
    const events = [];
    const add = (time, title, detail) => { if (time) events.push({time, title, detail}); };
    add(raw.createdAt || raw.firstSeenAt, "Object discovered", `${object.displayName} entered the CMDB.`);
    add(raw.lastConnectedAt || raw.observedState?.connectedAt, "Connection established", currentPoolName(raw, relationships));
    add(raw.lastShareAt || raw.observedState?.lastShareAt, "Latest mining share", `${formatHashrate(liveHashrate(raw))} observed.`);
    add(raw.lastSeenAt || raw.updatedAt, "CMDB observation updated", `State: ${label(operationalState(object, raw))}.`);
    events.sort((a, b) => new Date(b.time) - new Date(a.time));
    byId("objectTimeline").innerHTML = events.length ? events.slice(0, 6).map((event) => `<div class="cmdb-timeline-item"><span></span><div><strong>${escapeHtml(event.title)}</strong><small>${escapeHtml(event.detail)}</small><time>${escapeHtml(formatDate(event.time))}</time></div></div>`).join("") : '<div class="cmdb-object-empty">No timestamped activity is available for this object.</div>';
  }

  function renderOperations(object) {
    const encoded = encodeURIComponent(object.objectId);
    const actions = [
      ["Open in Explorer", `/graph.html?nodeId=${encoded}`],
      ["Operations Center", `/operations.html?target=${encoded}`],
      ["View Evidence", `/operations.html?target=${encoded}&tab=evidence`],
      ["Maintenance", `/operations.html?target=${encoded}&action=maintenance`]
    ];
    byId("objectOperations").innerHTML = actions.map(([name, href]) => `<a href="${href}">${escapeHtml(name)}<span>›</span></a>`).join("");
  }

  async function load() {
    const params = new URLSearchParams(window.location.search);
    const objectType = params.get("type") || "object";
    const objectId = params.get("id") || "";
    if (!objectId) { byId("objectError").hidden = false; byId("objectError").textContent = "No CMDB object ID was provided."; return; }
    try {
      const response = await fetch(`/api/platform/objects/${encodeURIComponent(objectType)}/${encodeURIComponent(objectId)}`, {cache: "no-store"});
      const payload = await response.json();
      if (!response.ok || payload.status !== "ok") throw new Error(payload.error || "CMDB object not found.");
      const object = payload.object || {};
      const raw = object.raw || {};
      const relationships = payload.relationships || [];
      const state = operationalState(object, raw);
      document.title = `${object.displayName || objectId} · Nexus CMDB`;
      byId("breadcrumbType").textContent = label(object.objectType || objectType);
      byId("breadcrumbName").textContent = object.displayName || objectId;
      byId("objectName").textContent = object.displayName || objectId;
      byId("objectSubtitle").textContent = object.subtitle || label(object.objectType || objectType);
      byId("objectStatus").textContent = label(state).toUpperCase();
      byId("objectStatus").className = `cmdb-state-pill ${statusClass(state)}`;
      byId("objectHeaderFacts").innerHTML = [object.objectType, raw.managementModel, raw.lifecycleStage, raw.mission || raw.purpose].filter(Boolean).map((fact) => `<span>${escapeHtml(label(fact))}</span>`).join("");
      byId("objectDetails").innerHTML = importantFields(raw).map(([key, value]) => `<div><dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value)}</dd></div>`).join("") || "<div><dt>Record</dt><dd>No structured identity fields available.</dd></div>";
      byId("relationshipCount").textContent = relationships.length;
      byId("objectRelationships").innerHTML = relationships.length ? relationships.map((rel) => relationshipCard(rel, objectId)).join("") : '<div class="cmdb-object-empty">No CMDB relationships currently map to this object.</div>';
      renderLive(object, raw, relationships);
      renderHealth(object, raw);
      renderTimeline(raw, object, relationships);
      renderOperations(object);
      byId("objectRaw").textContent = JSON.stringify(raw, null, 2);
      await loadProfile(object.objectType === "asset" ? objectId : "");
      byId("objectContent").hidden = false;
      byId("rawSection").hidden = false;
    } catch (error) { byId("objectError").hidden = false; byId("objectError").textContent = error.message; }
  }
  window.addEventListener("DOMContentLoaded", load);
})();
