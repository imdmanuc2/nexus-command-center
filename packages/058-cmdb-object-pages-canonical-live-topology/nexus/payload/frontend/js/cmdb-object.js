(function () {
  "use strict";

  const byId = (id) => document.getElementById(id);
  const safe = (value, fallback = "—") => {
    if (value === undefined || value === null || value === "") return fallback;
    return String(value);
  };
  const escapeHtml = (value) => safe(value, "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

  function statusClass(status) {
    const value = safe(status, "unknown").toLowerCase();
    if (["online", "active", "healthy", "managed", "observed"].includes(value)) return "healthy";
    if (["warning", "partial", "idle", "unknown"].includes(value)) return "warning";
    if (["offline", "failed", "critical", "unmanaged"].includes(value)) return "critical";
    return "neutral";
  }

  function label(value) {
    return safe(value, "Object")
      .replaceAll("_", " ")
      .replaceAll("-", " ")
      .replace(/\b\w/g, (char) => char.toUpperCase());
  }

  function displayValue(value) {
    if (Array.isArray(value)) return value.join(", ") || "—";
    if (value && typeof value === "object") return JSON.stringify(value);
    return safe(value);
  }

  function importantFields(raw) {
    const preferred = [
      "assetId", "poolInstanceId", "workerId", "workloadId", "id",
      "assetType", "canonicalType", "workerType", "workloadType",
      "coin", "host", "ip", "poolHost", "apiBaseUrl", "rpcPort",
      "stratumPorts", "currentHashrate", "hashrateUnit", "activityState",
      "status", "operationalState", "lifecycleStatus", "managed",
      "manufacturer", "model", "operatingSystem", "purpose",
      "lastSeenAt", "lastShareAt", "updatedAt"
    ];
    const rows = [];
    preferred.forEach((key) => {
      if (!(key in raw)) return;
      const value = raw[key];
      if (value === undefined || value === null || value === "") return;
      rows.push([label(key), displayValue(value)]);
    });
    if (!rows.length) {
      Object.entries(raw).slice(0, 18).forEach(([key, value]) => {
        if (value && typeof value === "object") return;
        rows.push([label(key), displayValue(value)]);
      });
    }
    return rows;
  }

  function relationshipCard(rel, currentId) {
    const currentIsSource = rel.sourceId === currentId;
    const neighbor = currentIsSource ? rel.targetObject : rel.sourceObject;
    const direction = currentIsSource ? "Outgoing" : "Incoming";
    const relationship = label(rel.relationshipType || "related to");
    const href = neighbor?.href || "#";
    return `<a class="cmdb-relationship-card" href="${escapeHtml(href)}">
      <span>${direction} · ${escapeHtml(relationship)}</span>
      <strong>${escapeHtml(neighbor?.displayName || (currentIsSource ? rel.targetName : rel.sourceName))}</strong>
      <small>${escapeHtml(neighbor?.subtitle || neighbor?.objectType || "CMDB object")}</small>
      <em>${escapeHtml(rel.status || "mapped")}</em>
    </a>`;
  }

  async function load() {
    const params = new URLSearchParams(window.location.search);
    const objectType = params.get("type") || "object";
    const objectId = params.get("id") || "";

    if (!objectId) {
      byId("objectError").hidden = false;
      byId("objectError").textContent = "No CMDB object ID was provided.";
      return;
    }

    try {
      const response = await fetch(`/api/platform/objects/${encodeURIComponent(objectType)}/${encodeURIComponent(objectId)}`, { cache: "no-store" });
      const payload = await response.json();
      if (!response.ok || payload.status !== "ok") throw new Error(payload.error || "CMDB object not found.");

      const object = payload.object || {};
      const raw = object.raw || {};
      document.title = `${object.displayName || objectId} · Nexus CMDB`;
      byId("breadcrumbType").textContent = label(object.objectType || objectType);
      byId("breadcrumbName").textContent = object.displayName || objectId;
      byId("objectName").textContent = object.displayName || objectId;
      byId("objectSubtitle").textContent = object.subtitle || label(object.objectType || objectType);
      byId("objectStatus").textContent = safe(object.status, "unknown").toUpperCase();
      byId("objectStatus").className = `cmdb-state-pill ${statusClass(object.status)}`;
      byId("objectDetails").innerHTML = importantFields(raw)
        .map(([key, value]) => `<div><dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value)}</dd></div>`)
        .join("") || "<div><dt>Record</dt><dd>No structured fields available.</dd></div>";

      const relationships = payload.relationships || [];
      byId("relationshipCount").textContent = relationships.length;
      byId("objectRelationships").innerHTML = relationships.length
        ? relationships.map((rel) => relationshipCard(rel, objectId)).join("")
        : '<div class="cmdb-object-empty">No CMDB relationships currently map to this object.</div>';
      byId("objectRaw").textContent = JSON.stringify(raw, null, 2);
      byId("objectContent").hidden = false;
      byId("rawSection").hidden = false;
    } catch (error) {
      byId("objectError").hidden = false;
      byId("objectError").textContent = error.message;
    }
  }

  window.addEventListener("DOMContentLoaded", load);
})();
