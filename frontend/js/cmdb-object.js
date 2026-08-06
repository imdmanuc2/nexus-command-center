(function () {
  "use strict";
  const byId = (id) => document.getElementById(id);
  const safe = (value, fallback = "—") => (value === undefined || value === null || value === "") ? fallback : String(value);
  const esc = (value) => safe(value, "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
  const norm = (value) => safe(value, "unknown").trim().toLowerCase().replaceAll("_", "-");

  function label(value) {
    return safe(value, "Object").replaceAll("_", " ").replaceAll("-", " ").replace(/([a-z])([A-Z])/g, "$1 $2").replace(/\b\w/g, (c) => c.toUpperCase());
  }
  function statusClass(value) {
    const state = norm(value);
    if (["online","active","healthy","managed","observed","mining","accepting-shares","connected","synchronized","stable"].includes(state)) return "healthy";
    if (["warning","partial","idle","unknown","starting","syncing","stale"].includes(state)) return "warning";
    if (["offline","failed","critical","unmanaged","disconnected","fault"].includes(state)) return "critical";
    return "neutral";
  }
  function formatState(value) { return label(norm(value)); }
  function formatHashrate(value) {
    const h = Number(value || 0); if (!Number.isFinite(h) || h <= 0) return "—";
    const units = [[1e18,"EH/s"],[1e15,"PH/s"],[1e12,"TH/s"],[1e9,"GH/s"],[1e6,"MH/s"],[1e3,"kH/s"]];
    for (const [n,u] of units) if (h >= n) return `${(h/n).toFixed(h/n >= 100 ? 0 : 2)} ${u}`;
    return `${h.toFixed(0)} H/s`;
  }
  function formatNumber(value) { const n = Number(value); return Number.isFinite(n) ? new Intl.NumberFormat().format(n) : "—"; }
  function formatTime(value) {
    if (!value) return "—"; const d = new Date(value); if (Number.isNaN(d.getTime())) return safe(value);
    return d.toLocaleString();
  }
  function parseCoin(value) {
    if (!value) return {};
    if (typeof value === "object") return value;
    const text = String(value).trim();
    try { return JSON.parse(text.replaceAll("'", '"')); } catch (_) {}
    const symbol = (text.match(/symbol['"]?\s*:\s*['"]?([A-Za-z0-9]+)/i) || [])[1];
    const name = (text.match(/name['"]?\s*:\s*['"]([^'"}]+)/i) || [])[1];
    const algorithm = (text.match(/algorithm['"]?\s*:\s*['"]?([A-Za-z0-9-]+)/i) || [])[1];
    return {symbol, name, algorithm};
  }
  function metric(labelText, value, state = "") {
    return `<div class="cmdb-metric ${state ? statusClass(state) : ""}"><span>${esc(labelText)}</span><strong>${esc(value)}</strong></div>`;
  }
  function identityRows(object, raw) {
    const coin = parseCoin(raw.coin);
    const rows = [
      ["Object ID", object.objectId], ["Classification", raw.canonicalType || raw.assetType || raw.workerType || object.objectType],
      ["IP / Host", raw.ip || raw.host || raw.poolHost], ["Hostname", raw.hostname],
      ["Worker ID", raw.workerName || raw.workerId], ["Coin", coin.symbol ? `${coin.name || coin.symbol} (${coin.symbol})` : raw.coin],
      ["Algorithm", coin.algorithm], ["Management", raw.managementModel || (raw.managed ? "Nexus Managed" : "Observed")],
      ["Lifecycle", raw.lifecycleStage || raw.lifecycleStatus], ["Last Updated", formatTime(raw.updatedAt || raw.lastSeenAt)]
    ].filter(([,v]) => v !== undefined && v !== null && v !== "" && v !== "—");
    return rows.map(([k,v]) => `<div><dt>${esc(k)}</dt><dd>${esc(label(String(v)))}</dd></div>`).join("");
  }
  function liveMetrics(object, summary, raw) {
    const os = raw.observedState || {};
    const coin = parseCoin(summary.coin || raw.coin);
    const currentPool = summary.currentPoolId || raw.livePoolId || os.currentPool || raw.poolInstanceId;
    const state = summary.observedOperationalState || object.status;
    const metrics = [["Current State", formatState(state), state]];
    if (["asset","worker"].includes(object.objectType)) {
      metrics.push(["Live Hashrate", formatHashrate(summary.currentHashrate || raw.liveHashrate || raw.currentHashrate || os.hashrate)]);
      metrics.push(["Current Pool", currentPool || "Not assigned"]);
      metrics.push(["Accepted Shares", formatNumber(summary.acceptedShares)]);
      metrics.push(["Rejected Shares", formatNumber(summary.rejectedShares)]);
      metrics.push(["Last Share", formatTime(raw.lastShareAt || os.lastShareAt)]);
    } else if (object.objectType === "pool") {
      metrics.push(["Pool Hashrate", formatHashrate(summary.currentHashrate || os.hashrate)]);
      metrics.push(["Active Workers", formatNumber(os.activeWorkers ?? raw.workerCount)]);
      metrics.push(["Accepted Shares", formatNumber(summary.acceptedShares ?? os.acceptedShares)]);
      metrics.push(["Rejected Shares", formatNumber(summary.rejectedShares ?? os.rejectedShares)]);
      metrics.push(["Stratum", os.stratumReachable === true ? "Reachable" : os.stratumReachable === false ? "Unreachable" : "Unknown", os.stratumReachable === true ? "connected" : "unknown"]);
      metrics.push(["Coin", coin.symbol ? `${coin.name || coin.symbol} (${coin.symbol})` : "—"]);
    } else {
      metrics.push(["Host", summary.host || "—"]);
      metrics.push(["Last Observed", formatTime(summary.lastObservedAt)]);
      if (raw.syncPercent !== undefined) metrics.push(["Synchronization", `${Number(raw.syncPercent).toFixed(5)}%`]);
      if (raw.peers !== undefined) metrics.push(["Peers", formatNumber(raw.peers)]);
    }
    return metrics.map(([k,v,s]) => metric(k,v,s)).join("");
  }
  function healthMetrics(summary, raw) {
    const telemetry = raw.telemetryAvailable ?? raw.observedState?.apiReachable;
    const items = [
      ["Health", formatState(summary.health), summary.health], ["Connectivity", formatState(summary.connectivity), summary.connectivity],
      ["Telemetry", telemetry === true ? "Available" : telemetry === false ? "Unavailable" : "Unknown", telemetry === true ? "healthy" : telemetry === false ? "critical" : "unknown"],
      ["Last Observed", formatTime(summary.lastObservedAt)]
    ];
    return items.map(([k,v,s]) => metric(k,v,s)).join("");
  }
  function relationshipCard(rel, currentId) {
    const outgoing = rel.sourceId === currentId; const neighbor = outgoing ? rel.targetObject : rel.sourceObject;
    const href = neighbor?.href || (outgoing ? rel.targetHref : rel.sourceHref) || "#";
    const state = rel.status || rel.activityState || "mapped";
    return `<a class="cmdb-relationship-card" href="${esc(href)}"><span>${outgoing ? "Outgoing" : "Incoming"} · ${esc(label(rel.relationshipType || "related-to"))}</span><strong>${esc(neighbor?.displayName || (outgoing ? rel.targetName : rel.sourceName))}</strong><small>${esc(neighbor?.subtitle || label(neighbor?.objectType || "CMDB object"))}</small><em class="${statusClass(state)}">${esc(formatState(state))}</em></a>`;
  }
  function operationCatalog(object, raw, summary) {
    const q = `type=${encodeURIComponent(object.objectType)}&id=${encodeURIComponent(object.objectId)}`;
    const kind = norm(raw.assetType || raw.canonicalType || raw.workerType || object.objectType);
    const common = [
      ["Open in Explorer", `/graph.html?focus=${encodeURIComponent(object.objectId)}`, "Inspect topology and blast radius"],
      ["View Timeline", `/timeline.html?${q}`, "Review recent state changes and evidence"],
      ["Open Operations", `/operations-center.html?${q}`, "Open the full Operations Center"]
    ];
    if (object.objectType === "pool") {
      common.splice(1, 0,
        ["Pool Readiness", `/operations.html?action=pool-readiness&${q}`, "Test API, Stratum, workers, RPC, and share flow"],
        ["Worker Sessions", `/operations-center.html?view=sessions&${q}`, "Inspect active and historical pool sessions"],
        ["Share Statistics", `/operations-center.html?view=shares&${q}`, "Review accepted, rejected, and recent shares"]
      );
    } else if (kind.includes("blockchain") || kind.includes("bitcoin")) {
      common.splice(1, 0,
        ["Test RPC", `/operations.html?action=bitcoin-rpc-test&${q}`, "Verify RPC credentials, chain, peers, and synchronization"],
        ["Peer Health", `/operations-center.html?view=peers&${q}`, "Review peer count and network health"],
        ["View Logs", `/operations-center.html?view=logs&${q}`, "Inspect recent Bitcoin Core service events"]
      );
    } else if (["asset","worker"].includes(object.objectType)) {
      common.splice(1, 0,
        ["Run Diagnostics", `/operations.html?action=diagnostics&${q}`, "Check connectivity, hashrate, pool assignment, and shares"],
        ["Pool Connectivity", `/operations-center.html?view=pool-connectivity&${q}`, "Verify the current Stratum path"],
        ["Maintenance Mode", `/operations-center.html?view=maintenance&${q}`, "Prepare this object for controlled maintenance"]
      );
    }
    return common;
  }
  function operations(object, raw, summary) {
    return operationCatalog(object, raw, summary).map(([name,href,detail]) => `<a href="${esc(href)}"><strong>${esc(name)}</strong><small>${esc(detail)}</small><span>→</span></a>`).join("");
  }
  function recommendationMatches(rec, object) {
    const entityId = String(rec.entityId || rec.assetId || "");
    const entityType = norm(rec.entityType || "");
    const objectType = norm(object.objectType || "");
    if (entityId && entityId === object.objectId) return true;
    if (rec.evidence && Object.values(rec.evidence).some((value) => String(value) === object.objectId)) return true;
    return entityType === objectType && entityId === object.objectId;
  }
  function recommendationCard(rec, object) {
    const priority = norm(rec.priority || "normal");
    const q = `type=${encodeURIComponent(object.objectType)}&id=${encodeURIComponent(object.objectId)}`;
    return `<article class="cmdb-recommendation-card priority-${esc(priority)}">
      <div><span>${esc(label(priority))}</span><strong>${esc(rec.title || "Operational recommendation")}</strong></div>
      <p>${esc(rec.explanation || rec.recommendedAction || "Review this object's current state.")}</p>
      <small>${esc(rec.recommendedAction || "Open Operations Center for next steps.")}</small>
      <a href="/operations-center.html?recommendation=${encodeURIComponent(rec.recommendationId || "")}&${q}">Review recommendation <span>→</span></a>
    </article>`;
  }
  async function loadOperationsCenter(object, raw, summary) {
    const recommendationTarget = byId("objectRecommendations");
    const evidenceTarget = byId("operationsEvidence");
    const state = summary.observedOperationalState || object.status || "unknown";
    byId("operationsObjectState").textContent = formatState(state).toUpperCase();
    byId("operationsObjectState").className = `cmdb-ops-state ${statusClass(state)}`;
    try {
      const [recommendationsResponse, automationResponse] = await Promise.all([
        fetch("/api/platform/recommendations", {cache:"no-store"}),
        fetch("/api/platform/automation/summary", {cache:"no-store"})
      ]);
      const recommendationsPayload = recommendationsResponse.ok ? await recommendationsResponse.json() : {};
      const automation = automationResponse.ok ? await automationResponse.json() : {};
      const recommendations = (recommendationsPayload.recommendations || []).filter((rec) => recommendationMatches(rec, object) && norm(rec.status || "open") === "open");
      byId("recommendationCount").textContent = recommendations.length;
      recommendationTarget.innerHTML = recommendations.length
        ? recommendations.slice(0, 4).map((rec) => recommendationCard(rec, object)).join("")
        : '<div class="cmdb-ops-clear"><strong>No open recommendations</strong><span>This Digital Twin has no object-specific operational guidance right now.</span></div>';
      const running = Number(automation.running || 0);
      const queued = Number(automation.queued || 0);
      const failed = Number(automation.failed || 0);
      byId("automationState").textContent = running ? "RUNNING" : queued ? "QUEUED" : failed ? "ATTENTION" : "READY";
      evidenceTarget.innerHTML = `
        <div class="cmdb-evidence-grid">
          ${metric("Running", formatNumber(running), running ? "active" : "neutral")}
          ${metric("Queued", formatNumber(queued), queued ? "warning" : "neutral")}
          ${metric("Completed", formatNumber(automation.completed || 0), "healthy")}
          ${metric("Failed", formatNumber(failed), failed ? "critical" : "neutral")}
        </div>
        <div class="cmdb-evidence-links">
          <a href="/operations-center.html?type=${encodeURIComponent(object.objectType)}&id=${encodeURIComponent(object.objectId)}">Open Operations Center <span>→</span></a>
          <a href="/timeline.html?type=${encodeURIComponent(object.objectType)}&id=${encodeURIComponent(object.objectId)}">View execution timeline <span>→</span></a>
        </div>`;
    } catch (error) {
      recommendationTarget.innerHTML = `<div class="cmdb-object-empty">Recommendations unavailable: ${esc(error.message)}</div>`;
      evidenceTarget.innerHTML = '<div class="cmdb-object-empty">Operational evidence is temporarily unavailable.</div>';
    }
  }
  function timeline(summary, raw, relationships) {
    const rows = [];
    if (raw.lastShareAt || raw.observedState?.lastShareAt) rows.push(["Share activity observed", "Live mining telemetry", raw.lastShareAt || raw.observedState.lastShareAt]);
    if (summary.lastObservedAt) rows.push(["Object observed", formatState(summary.observedOperationalState), summary.lastObservedAt]);
    if (raw.updatedAt) rows.push(["CMDB record updated", "Authoritative object record", raw.updatedAt]);
    relationships.slice(0,2).forEach((r) => rows.push([`${label(r.relationshipType)} relationship`, r.status || "mapped", r.updatedAt || r.lastSeenAt]));
    if (!rows.length) return '<div class="cmdb-object-empty">No recent activity is available for this object.</div>';
    return rows.slice(0,5).map(([title,detail,time]) => `<div class="cmdb-timeline-item"><span></span><div><strong>${esc(title)}</strong><small>${esc(detail)}</small><time>${esc(formatTime(time))}</time></div></div>`).join("");
  }
  function setProfile(p) {
    byId("profileMission").value = p.mission || ""; byId("profileRole").value = p.role || "";
    byId("profileManagement").value = p.managementModel || "nexus-managed"; byId("profileLifecycle").value = p.lifecycleStage || "production";
    byId("profileDesired").value = p.desiredOperationalState || "automatic"; byId("profileObserved").value = p.observedOperationalState || "unknown";
    byId("profileHealth").value = p.health || "unknown"; byId("profileConnectivity").value = p.connectivity || "unknown";
  }
  async function loadProfile(assetId) {
    const form = byId("operationalProfileForm"); if (!assetId) { form.hidden = true; return; }
    const response = await fetch(`/api/cmdb/operational-profile?assetId=${encodeURIComponent(assetId)}`, {cache:"no-store"});
    if (!response.ok) { form.hidden = true; return; } const payload = await response.json(); setProfile(payload.profile || {});
    form.onsubmit = async (event) => {
      event.preventDefault(); const message = byId("profileMessage"); message.textContent = "Saving…";
      try {
        const update = await fetch("/api/cmdb/operational-profile/update", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({assetId,mission:byId("profileMission").value,role:byId("profileRole").value,managementModel:byId("profileManagement").value,lifecycleStage:byId("profileLifecycle").value,desiredOperationalState:byId("profileDesired").value,observedOperationalState:byId("profileObserved").value,health:byId("profileHealth").value,connectivity:byId("profileConnectivity").value,reason:byId("profileReason").value,changedBy:"cmdb-ui"})});
        const result = await update.json(); if (!update.ok) throw new Error(result.error || "Profile update failed"); setProfile(result.profile || {}); message.textContent = "Saved";
      } catch (e) { message.textContent = e.message; }
    };
  }
  async function load() {
    const params = new URLSearchParams(location.search); const objectType = params.get("type") || "object"; const objectId = params.get("id") || "";
    if (!objectId) { byId("objectError").hidden = false; byId("objectError").innerHTML = 'No CMDB object ID was provided. <a href="/assets.html">Choose an object from the CMDB.</a>'; return; }
    try {
      const response = await fetch(`/api/platform/objects/${encodeURIComponent(objectType)}/${encodeURIComponent(objectId)}`, {cache:"no-store"}); const payload = await response.json();
      if (!response.ok || payload.status !== "ok") throw new Error(payload.error || "CMDB object not found.");
      const object = payload.object || {}; const raw = object.raw || {}; const summary = payload.summary || {}; const relationships = payload.relationships || [];
      document.title = `${object.displayName || objectId} · Nexus CMDB`; byId("breadcrumbType").textContent = label(object.objectType || objectType); byId("breadcrumbName").textContent = object.displayName || objectId;
      byId("objectName").textContent = object.displayName || objectId; byId("objectSubtitle").textContent = object.subtitle || label(object.objectType || objectType);
      byId("objectStatus").textContent = formatState(summary.observedOperationalState || object.status).toUpperCase(); byId("objectStatus").className = `cmdb-state-pill ${statusClass(summary.observedOperationalState || object.status)}`;
      byId("headerFacts").innerHTML = [summary.host, raw.coin && (parseCoin(raw.coin).symbol || raw.coin), raw.role || raw.primaryRole].filter(Boolean).map((v) => `<span>${esc(label(String(v)))}</span>`).join("");
      byId("objectDetails").innerHTML = identityRows(object, raw) || '<div><dt>Record</dt><dd>No structured identity fields available.</dd></div>';
      byId("liveMetrics").innerHTML = liveMetrics(object, summary, raw); byId("healthMetrics").innerHTML = healthMetrics(summary, raw);
      byId("relationshipCount").textContent = relationships.length; byId("objectRelationships").innerHTML = relationships.length ? relationships.map((r) => relationshipCard(r, objectId)).join("") : '<div class="cmdb-object-empty">No CMDB relationships currently map to this object.</div>';
      byId("operationLinks").innerHTML = operations(object, raw, summary); await loadOperationsCenter(object, raw, summary); byId("timeline").innerHTML = timeline(summary, raw, relationships); byId("objectRaw").textContent = JSON.stringify(raw, null, 2);
      await loadProfile(object.objectType === "asset" ? objectId : ""); byId("objectContent").hidden = false; byId("rawSection").hidden = false;
    } catch (error) { byId("objectError").hidden = false; byId("objectError").textContent = error.message; }
  }
  addEventListener("DOMContentLoaded", load);
})();
