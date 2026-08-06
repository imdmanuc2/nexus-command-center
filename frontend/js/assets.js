
async function loadDependencyData(assetId){const r=await fetch(`/api/cmdb/relationships/asset?assetId=${encodeURIComponent(assetId)}`);if(!r.ok)throw new Error('Dependency data unavailable');return r.json();}
function dependencyRows(data,assetId){const rows=(data.relationships||[]).map(r=>{const outbound=r.source_id===assetId||r.sourceId===assetId;const other=outbound?(r.target_id||r.targetId):(r.source_id||r.sourceId);const rel=r.relationship_type||r.relationshipType;return `<li><span>${outbound?'→':'←'} ${safe(rel,'relationship').replaceAll('_',' ')}</span><b>${safe(other,'unknown')}</b><small>${safe(r.criticality,'normal')} · ${r.confidence??'—'}%</small></li>`});return rows.join('')||'<li>No dependency relationships mapped yet.</li>';}
function workloadRows(data){return (data.workloads||[]).map(w=>`<li><span>${safe(w.workload_category,'workload').replaceAll('-',' ')}</span><b>${safe(w.workload_name,'Unnamed')}</b><small>${safe(w.status,'assigned')}</small></li>`).join('')||'<li>No workloads assigned.</li>';}
let latestSystems = [];
let latestFound = [];
let latestRelationships = { relationships: [], pools: [], assets: [] };
let activeFilter = "all";
let searchQuery = "";
const OPERATIONAL_STATES = [
  ["active","Active — expected to operate normally"],
  ["maintenance","Maintenance — planned work; alerts suppressed"],
  ["disabled","Disabled — intentionally offline"],
  ["provisioning","Provisioning — being installed or configured"],
  ["decommissioning","Decommissioning — being removed from service"],
  ["retired","Retired — historical record only"]
];
const LIFECYCLE_STATES = [["managed","Managed"],["discovered","Discovered"],["imported","Imported"],["virtual","Virtual"],["decommissioning","Decommissioning"],["retired","Retired"]];
function options(items,current){return items.map(([v,l])=>`<option value="${v}" ${v===current?'selected':''}>${l}</option>`).join('');}
async function loadLifecycle(assetId){
 const [a,h]=await Promise.all([fetch(`/api/cmdb/lifecycle/asset?assetId=${encodeURIComponent(assetId)}`).then(r=>r.json()),fetch(`/api/cmdb/lifecycle/history?assetId=${encodeURIComponent(assetId)}`).then(r=>r.json())]);
 return {asset:a.asset,history:h.history||[]};
}
async function saveLifecycle(assetId){
 const body={assetId,operationalState:byId('cmdbOperationalState').value,lifecycleStatus:byId('cmdbLifecycleStatus').value,desiredOperationalState:byId('cmdbDesiredState').value,reason:byId('cmdbChangeReason').value,changedBy:'cmdb-user',source:'cmdb-asset-editor'};
 const r=await fetch('/api/cmdb/lifecycle/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}); const d=await r.json();
 if(!r.ok||d.status!=='ok') throw new Error(d.error||'Update failed');
 byId('cmdbSaveStatus').textContent='Saved and added to audit history.'; setTimeout(()=>openDrawer(latestSystems.find(x=>x.asset?.id===assetId)),600);
}
function historyHtml(rows){return rows.length?rows.map(r=>`<li><div><b>${safe(r.fieldName).replaceAll('_',' ')}</b><small>${safe(r.previousValue,'—')} → ${safe(r.newValue,'—')}</small></div><span>${new Date(r.changedAt).toLocaleString()}<br>${safe(r.changedBy,'nexus')}${r.reason?` · ${r.reason}`:''}</span></li>`).join(''):'<li>No lifecycle changes recorded yet.</li>';}


function byId(id) {
  return document.getElementById(id);
}

function safe(value, fallback = "Unknown") {
  return value === undefined || value === null || value === "" ? fallback : value;
}

function closeDrawer() {
  byId("drawer")?.classList.remove("open");
  byId("drawerBackdrop")?.classList.remove("open");
}

function assetLabel(asset, system) {
  return safe(asset?.friendlyName || asset?.name || system?.ip, "Unknown Asset");
}

function assetText(system) {
  const asset = system.asset || {};
  return [
    asset.friendlyName,
    asset.name,
    asset.ip,
    system.ip,
    asset.type,
    asset.purpose,
    asset.workerId,
    asset.poolId,
    asset.poolHost,
    asset.poolGroup,
    asset.manufacturer,
    asset.model,
    asset.serialNumber,
    asset.macAddress,
    asset.rack,
    asset.position,
    ...(asset.tags || [])
  ].join(" ").toLowerCase();
}

function matchesFilter(system) {
  const asset = system.asset || {};
  const type = asset.type || "";

  if (activeFilter === "all") return true;
  if (activeFilter === "favorite") return asset.favorite === true;
  if (activeFilter === "unassigned") return !asset.poolId && !asset.poolGroup && !asset.workerId;
  return type === activeFilter;
}

function filteredSystems() {
  return latestSystems.filter(system => {
    const q = searchQuery.trim().toLowerCase();
    const matchesSearch = !q || assetText(system).includes(q);
    return matchesSearch && matchesFilter(system);
  });
}

function renderSummary() {
  const counts = {
    total: latestSystems.length,
    asic: latestSystems.filter(s => s.asset?.type === "asic").length,
    pools: latestSystems.filter(s => s.asset?.type === "pool-host").length,
    nodes: latestSystems.filter(s => s.asset?.type === "blockchain-node").length,
    unassigned: latestSystems.filter(s => !s.asset?.poolId && !s.asset?.poolGroup && !s.asset?.workerId).length
  };

  byId("assetSummary").innerHTML = `
    <div class="asset-summary-card"><span>Total Assets</span><strong>${counts.total}</strong></div>
    <div class="asset-summary-card"><span>ASICs</span><strong>${counts.asic}</strong></div>
    <div class="asset-summary-card"><span>Pool Hosts</span><strong>${counts.pools}</strong></div>
    <div class="asset-summary-card"><span>Nodes</span><strong>${counts.nodes}</strong></div>
    <div class="asset-summary-card"><span>Unassigned</span><strong>${counts.unassigned}</strong></div>
  `;
}

function renderAssets() {
  const systems = filteredSystems();

  const html = systems.map(system => {
    const asset = system.asset || {};

    return `
      <div class="inventory-card asset-card" data-ip="${system.ip}">
        <div class="node-status"></div>

        <div class="asset-card-head">
          <h3>${assetLabel(asset, system)}</h3>
          <span>${safe(asset.type, "unknown")}</span>
        </div>

        <div class="asset-card-meta">
          <span>${safe(asset.ip || system.ip)}</span>
          <span>${safe(asset.poolGroup, "Unassigned")}</span>
          <span>Worker ${safe(asset.workerId, "—")}</span>
        </div>

        <div class="asset-card-detail">
          <b>${safe(asset.manufacturer || asset.model || asset.purpose, "No hardware details yet")}</b>
          <small>${safe(system.primaryRole, "No detected role")}</small>
        </div>
      </div>
    `;
  }).join("");

  byId("assetsList").innerHTML = html || `
    <div class="empty-state">
      <h2>No assets match.</h2>
      <p>Try clearing the search or changing the filter.</p>
    </div>
  `;

  document.querySelectorAll(".asset-card").forEach(card => {
    card.addEventListener("click", (event) => {
      const system = latestSystems.find(s => s.ip === card.dataset.ip);
      if (!system) return;
      const asset = system.asset || {};
      const objectId = asset.id || asset.assetId;
      if (event.altKey || !objectId) {
        openDrawer(system);
        return;
      }
      window.location.href = cmdbObjectHref("asset", objectId);
    });
  });
}

function section(title, html) {
  return `
    <div class="asset-drawer-section">
      <h3>${title}</h3>
      <div class="asset-detail-grid">
        ${html}
      </div>
    </div>
  `;
}

function field(label, value) {
  return `
    <div class="asset-detail-field">
      <label>${label}</label>
      <strong>${safe(value, "Not set")}</strong>
    </div>
  `;
}

function relationshipRows(asset) {
  const rels = latestRelationships.relationships || [];
  const pools = latestRelationships.pools || [];

  const rows = rels
    .filter(rel => rel.fromId === asset.id || rel.toId === asset.id || rel.fromId === asset.poolId || rel.toId === asset.poolId)
    .map(rel => {
      let targetLabel = rel.toId;

      if (rel.toType === "pool") {
        const pool = pools.find(p => p.id === rel.toId);
        targetLabel = pool?.name || rel.toId;
      }

      if (rel.toType === "host") {
        targetLabel = rel.toId;
      }

      return `
        <li>
          <span>${rel.relationship.replaceAll("_", " ")}</span>
          <b>${targetLabel}</b>
        </li>
      `;
    });

  return rows.join("") || "<li>No relationships mapped yet.</li>";
}

async function loadIntelligence(assetId){ const r=await fetch(`/api/intelligence/analyze?assetId=${encodeURIComponent(assetId)}`); if(!r.ok) throw new Error('Intelligence unavailable'); return r.json(); }
function intelligenceHtml(data){ if(!data) return '<p>Analysis unavailable.</p>'; const rc=data.rootCause||{}; const impact=data.impact||{}; const recs=data.recommendations||[]; return `<div class="intelligence-summary"><div><span>Probable Root Cause</span><b>${rc.rootCauseAssetId||'Unknown'}</b></div><div><span>Confidence</span><b>${rc.confidence||0}%</b></div><div><span>Blast Radius</span><b>${impact.blastRadius||0} asset(s)</b></div></div><h4>Evidence</h4><ul class="service-list">${(rc.evidence||[]).map(x=>`<li>${x}</li>`).join('')||'<li>No conclusive evidence yet.</li>'}</ul><h4>Suggested Resolution</h4><ol class="intelligence-actions">${recs.map(r=>`<li><b>${r.label||r.code}</b><span>${r.confidence||0}% confidence · ${r.why||''}</span></li>`).join('')||'<li>Collect more telemetry and run diagnostics.</li>'}</ol>`;}

async function openDrawer(system) {
  const asset=system.asset||{}; const services=latestFound.filter(item=>item.ip===system.ip);
  let lifecycle={asset:{operationalState:asset.operationalState||'active',lifecycleStatus:asset.lifecycleStatus||'managed',desiredOperationalState:'online'},history:[]};
  let dependencyData={relationships:[],workloads:[],capability:null};
  let intelligenceData=null;
  try { if(asset.id) lifecycle=await loadLifecycle(asset.id); } catch(e) {}
  try { if(asset.id) dependencyData=await loadDependencyData(asset.id); } catch(e) {}
  try { if(asset.id) intelligenceData=await loadIntelligence(asset.id); } catch(e) {}
  const lc=lifecycle.asset||{};
  byId("drawerContent").innerHTML = `
    <div class="asset-profile-head"><div><h2>${assetLabel(asset,system)}</h2><p class="drawer-subtitle">${safe(asset.type||system.profile?.assetType,"Asset")}</p></div><span class="asset-profile-status state-${safe(lc.operationalState,'active')}">${safe(lc.operationalState,'active').toUpperCase()}</span></div>
    ${section("Identity", `${field("Asset ID",asset.id)}${field("Friendly Name",asset.friendlyName||asset.name)}${field("IP Address",asset.ip||system.ip)}${field("Hostname",asset.hostname||system.profile?.hostname)}${field("Type",asset.type)}${field("Purpose",asset.purpose)}`)}
    <div class="asset-drawer-section"><h3>Lifecycle & Operational Intent</h3><div class="cmdb-form-grid">
      <label>Operational State<select id="cmdbOperationalState">${options(OPERATIONAL_STATES,lc.operationalState||'active')}</select></label>
      <label>Lifecycle Status<select id="cmdbLifecycleStatus">${options(LIFECYCLE_STATES,lc.lifecycleStatus||'managed')}</select></label>
      <label>Desired State<select id="cmdbDesiredState"><option value="online" ${lc.desiredOperationalState==='online'?'selected':''}>Online — expected to be available</option><option value="offline" ${lc.desiredOperationalState==='offline'?'selected':''}>Offline — intentionally unavailable</option></select></label>
      <label class="wide">Reason for change<input id="cmdbChangeReason" placeholder="Required context for the audit trail"></label>
    </div><button class="cmdb-save" id="cmdbSaveLifecycle">Save Lifecycle Change</button><p id="cmdbSaveStatus" class="cmdb-save-status"></p></div>
    ${section("Mining Relationship", `${field("Worker ID",asset.workerId)}${field("Pool ID",asset.poolId)}${field("Pool Host",asset.poolHost)}${field("Pool Group",asset.poolGroup)}`)}
    ${section("Hardware", `${field("Manufacturer",asset.manufacturer)}${field("Model",asset.model)}${field("Serial Number",asset.serialNumber)}${field("MAC Address",asset.macAddress)}`)}
    ${section("Location", `${field("Location",asset.location)}${field("Rack",asset.rack)}${field("Position",asset.position)}`)}
    <div class="asset-drawer-section"><h3>Lifecycle Timeline</h3><ul class="cmdb-timeline">${historyHtml(lifecycle.history||[])}</ul></div>
    <div class="asset-drawer-section"><h3>Operational Intelligence</h3><p class="dependency-help">Explains probable cause, downstream impact, evidence, and grounded recommendations.</p>${intelligenceHtml(intelligenceData)}</div>
    <div class="asset-drawer-section"><h3>Dependency Map</h3><p class="dependency-help">CMDB-authoritative dependencies, including mining, CPU/GPU workloads, AI services, and rental providers.</p><ul class="service-list dependency-list">${dependencyRows(dependencyData,asset.id)}</ul></div><div class="asset-drawer-section"><h3>Compute & Workloads</h3>${dependencyData.capability?`<div class="field-grid">${field("Compute Kind",dependencyData.capability.compute_kind)}${field("Devices",dependencyData.capability.device_count)}${field("Model",dependencyData.capability.model)}</div>`:"<p>No compute capability profile recorded.</p>"}<ul class="service-list">${workloadRows(dependencyData)}</ul></div>
    <div class="asset-drawer-section"><h3>Discovered Services</h3><ul class="service-list">${services.map(s=>`<li><span>${s.service}</span><b>:${s.port}</b></li>`).join("")||"<li>No services discovered.</li>"}</ul></div>
    <div class="asset-drawer-section"><h3>Notes</h3><p>${safe(asset.notes,"No notes yet.")}</p></div>`;
  byId('cmdbSaveLifecycle')?.addEventListener('click',async()=>{try{byId('cmdbSaveStatus').textContent='Saving…';await saveLifecycle(asset.id);}catch(e){byId('cmdbSaveStatus').textContent=e.message;}});
  byId("drawer")?.classList.add("open"); byId("drawerBackdrop")?.classList.add("open");
}

async function loadAssets() {
  try {
    const [scanRes, relRes] = await Promise.all([
      fetch("/api/discovery/scan"),
      fetch("/api/assets/relationships")
    ]);

    const data = await scanRes.json();
    latestRelationships = await relRes.json();

    const discovery = data.discovery || data;

    latestSystems = discovery.systems || [];
    latestFound = discovery.found || [];

    renderSummary();
    renderAssets();
  } catch (err) {
    byId("assetsList").innerHTML = `<div class="empty-state"><h2>Assets failed to load.</h2><p>${err.message}</p></div>`;
  }
}

window.addEventListener("DOMContentLoaded", () => {
  byId("drawerClose")?.addEventListener("click", closeDrawer);
  byId("drawerBackdrop")?.addEventListener("click", closeDrawer);

  byId("assetSearch")?.addEventListener("input", e => {
    searchQuery = e.target.value;
    renderAssets();
  });

  document.querySelectorAll(".asset-filter").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".asset-filter").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      activeFilter = btn.dataset.filter;
      renderAssets();
    });
  });

  loadAssets();
});

/* Package 056: CMDB foundation and PostgreSQL platform consolidation. */
let cmdbPlatformData = {
  inventory: null,
  pools: null,
  workers: null,
  workloads: null,
  relationships: null,
  topology: null,
  audit: null,
  discovery: null
};

async function cmdbFetchJson(url) {
  try {
    const response = await fetch(url, { headers: { Accept: "application/json" } });
    if (!response.ok) return null;
    return await response.json();
  } catch (_) {
    return null;
  }
}

function cmdbArray(value, keys = []) {
  if (Array.isArray(value)) return value;
  for (const key of keys) {
    if (Array.isArray(value?.[key])) return value[key];
  }
  return [];
}

function cmdbAssetRecord(item) {
  const raw = item?.asset || item || {};
  const ip = raw.ip || raw.ipAddress || raw.host || item?.ip || "";
  return {
    ip,
    primaryRole: raw.primaryRole || raw.role || raw.purpose || raw.assetType || raw.type,
    profile: item?.profile || {},
    asset: {
      ...raw,
      id: raw.id || raw.assetId,
      friendlyName: raw.friendlyName || raw.displayName || raw.name || raw.hostname,
      name: raw.name || raw.displayName || raw.friendlyName,
      ip,
      type: raw.type || raw.assetType || raw.classification || "unknown",
      operationalState: raw.operationalState || raw.activityState || raw.status,
      lifecycleStatus: raw.lifecycleStatus || raw.managementState || raw.reconciliationStatus,
      poolId: raw.poolId || raw.poolInstanceId,
      poolGroup: raw.poolGroup || raw.poolName,
      workerId: raw.workerId,
      tags: Array.isArray(raw.tags) ? raw.tags : []
    }
  };
}

function cmdbInventoryAssets(payload) {
  const rows = cmdbArray(payload, ["assets", "items", "inventory", "systems"]);
  return rows.map(cmdbAssetRecord).filter(row => row.asset.id || row.ip || row.asset.friendlyName);
}

function cmdbCount(payload, keys = []) {
  if (typeof payload?.count === "number") return payload.count;
  if (typeof payload?.total === "number") return payload.total;
  return cmdbArray(payload, keys).length;
}

function cmdbStatusClass(value) {
  const status = String(value || "unknown").toLowerCase();
  if (["online", "active", "healthy", "managed", "observed", "connected"].includes(status)) return "healthy";
  if (["warning", "partial", "idle", "standby", "unknown"].includes(status)) return "warning";
  if (["offline", "failed", "critical", "unmanaged"].includes(status)) return "critical";
  return "neutral";
}

function cmdbObjectHref(objectType, objectId) {
  if (!objectId) return "";
  return `/cmdb-object.html?type=${encodeURIComponent(objectType || "object")}&id=${encodeURIComponent(objectId)}`;
}

function cmdbObjectCard(title, type, status, details = [], href = "") {
  const body = `<div class="cmdb-object-head"><div><span>${safe(type, "Object")}</span><h3>${safe(title)}</h3></div><b class="cmdb-state-pill ${cmdbStatusClass(status)}">${safe(status, "Unknown")}</b></div>
    <dl>${details.filter(([, value]) => value !== undefined && value !== null && value !== "").map(([label, value]) => `<div><dt>${label}</dt><dd>${safe(value)}</dd></div>`).join("") || "<div><dt>Details</dt><dd>Awaiting reconciliation</dd></div>"}</dl>`;
  return href
    ? `<a class="cmdb-object-card cmdb-object-link" href="${href}">${body}<span class="cmdb-open-object">Open CMDB object →</span></a>`
    : `<article class="cmdb-object-card">${body}</article>`;
}

function cmdbRenderOverview() {
  const assets = latestSystems;
  const pools = cmdbArray(cmdbPlatformData.pools, ["pools", "items"]);
  const workloads = cmdbArray(cmdbPlatformData.workloads, ["workloads", "items"]);
  const relationships = cmdbArray(cmdbPlatformData.relationships, ["relationships", "items"]);
  const nodes = assets.filter(row => String(row.asset?.type).toLowerCase() === "blockchain-node");
  const services = latestFound;
  const discovered = cmdbArray(cmdbPlatformData.discovery?.discovery || cmdbPlatformData.discovery, ["systems", "found", "items"]);
  const audit = cmdbArray(cmdbPlatformData.audit, ["audit", "events", "items", "changes"]);

  const cards = [
    ["Assets", assets.length, "Authoritative records", "assets"],
    ["Pools", pools.length, "Mining pool instances", "pools"],
    ["Blockchain Nodes", nodes.length, "Chain infrastructure", "nodes"],
    ["Services", services.length, "Observed endpoints", "services"],
    ["Workloads", workloads.length, "Assigned operations", "workloads"],
    ["Relationships", relationships.length, "Mapped dependencies", "relationships"],
    ["Discovery", discovered.length, "Observed candidates", "discovery"],
    ["Recent Changes", audit.length, "Audit records loaded", "audit"]
  ];
  byId("cmdbOverviewCards").innerHTML = cards.map(([label, count, text, sectionName]) => `
    <button class="cmdb-overview-card" data-open-section="${sectionName}"><span>${label}</span><strong>${count}</strong><small>${text}</small></button>
  `).join("");

  const byType = {};
  assets.forEach(row => { const type = safe(row.asset?.type, "unknown"); byType[type] = (byType[type] || 0) + 1; });
  byId("cmdbInventorySnapshot").innerHTML = Object.entries(byType).sort((a,b) => b[1]-a[1]).map(([type,count]) => `<div><span>${type.replaceAll("-", " ")}</span><b>${count}</b></div>`).join("") || "<p>No CMDB assets loaded.</p>";

  byId("cmdbRelationshipSnapshot").innerHTML = relationships.slice(0, 6).map(rel => `<div><span>${safe(rel.relationshipType || rel.relationship_type || rel.relationship, "relationship").replaceAll("_", " ")}</span><b><a href="${safe(rel.sourceHref || cmdbObjectHref(rel.sourceType, rel.sourceId))}">${safe(rel.sourceName || rel.sourceId || "?")}</a> → <a href="${safe(rel.targetHref || cmdbObjectHref(rel.targetType, rel.targetId))}">${safe(rel.targetName || rel.targetId || "?")}</a></b></div>`).join("") || "<p>No platform relationships loaded.</p>";

  document.querySelectorAll("[data-open-section]").forEach(button => button.onclick = () => cmdbOpenSection(button.dataset.openSection));
}

function cmdbRenderPools() {
  const rows = cmdbArray(cmdbPlatformData.pools, ["pools", "items"]);
  byId("cmdbPoolsList").innerHTML = rows.map(pool => cmdbObjectCard(
    pool.name || pool.displayName || pool.nativePoolId || pool.id,
    `${safe(pool.coin?.symbol || pool.coin, "Mining")} ${safe(pool.mode, "Pool")}`,
    pool.status || (pool.online ? "online" : "unknown"),
    [["Host", pool.host || pool.poolHost], ["Workers", pool.onlineWorkerCount ?? pool.workerCount ?? pool.connectedMiners], ["Hashrate", pool.hashrate ? `${Number(pool.hashrate).toLocaleString()} H/s` : null], ["Stratum", Array.isArray(pool.stratumPorts) ? pool.stratumPorts.join(", ") : pool.stratumPort]],
    cmdbObjectHref("pool", pool.poolInstanceId || pool.poolId || pool.id)
  )).join("") || '<div class="empty-state"><h2>No pool records loaded.</h2><p>Pool instances will appear after platform reconciliation.</p></div>';
}

function cmdbRenderNodes() {
  const rows = latestSystems.filter(row => String(row.asset?.type).toLowerCase() === "blockchain-node");
  byId("cmdbNodesList").innerHTML = rows.map(row => cmdbObjectCard(assetLabel(row.asset, row), "Blockchain Node", row.asset.operationalState || row.asset.status, [["IP", row.asset.ip || row.ip], ["Purpose", row.asset.purpose], ["Lifecycle", row.asset.lifecycleStatus]], cmdbObjectHref("asset", row.asset.id || row.asset.assetId))).join("") || '<div class="empty-state"><h2>No blockchain nodes loaded.</h2></div>';
}

function cmdbRenderServices() {
  byId("cmdbServicesList").innerHTML = latestFound.map(service => cmdbObjectCard(service.service || service.name, "Service", service.status || "observed", [["Host", service.ip || service.host], ["Port", service.port], ["Protocol", service.protocol]])).join("") || '<div class="empty-state"><h2>No discovered services loaded.</h2></div>';
}

function cmdbRenderWorkloads() {
  const rows = cmdbArray(cmdbPlatformData.workloads, ["workloads", "items"]);
  byId("cmdbWorkloadsList").innerHTML = rows.map(workload => cmdbObjectCard(workload.workloadName || workload.workload_name || workload.name || workload.id, workload.workloadCategory || workload.workload_category || workload.type || "Workload", workload.status || workload.activityState, [["Asset", workload.assetId || workload.asset_id], ["Pool", workload.poolInstanceId || workload.pool_instance_id], ["Coin", workload.coin]], cmdbObjectHref("workload", workload.workloadId || workload.workload_id || workload.id))).join("") || '<div class="empty-state"><h2>No workload records loaded.</h2></div>';
}

function cmdbRenderRelationships() {
  const rows = cmdbArray(cmdbPlatformData.relationships, ["relationships", "items"]);
  byId("cmdbRelationshipsList").innerHTML = rows.length ? `<div class="cmdb-rel-row cmdb-rel-head"><span>Source</span><span>Relationship</span><span>Target</span><span>State</span></div>${rows.map(rel => `<div class="cmdb-rel-row"><span><a href="${safe(rel.sourceHref || cmdbObjectHref(rel.sourceType, rel.sourceId || rel.source_id))}">${safe(rel.sourceName || rel.sourceId || rel.source_id || rel.fromId)}</a></span><b>${safe(rel.relationshipType || rel.relationship_type || rel.relationship).replaceAll("_", " ")}</b><span><a href="${safe(rel.targetHref || cmdbObjectHref(rel.targetType, rel.targetId || rel.target_id))}">${safe(rel.targetName || rel.targetId || rel.target_id || rel.toId)}</a></span><em>${safe(rel.status || rel.state || rel.reconciliationStatus, "mapped")}</em></div>`).join("")}` : '<div class="empty-state"><h2>No relationships loaded.</h2></div>';
}

function cmdbRenderDiscovery() {
  const discovery = cmdbPlatformData.discovery?.discovery || cmdbPlatformData.discovery || {};
  const systems = cmdbArray(discovery, ["systems", "items"]);
  const found = cmdbArray(discovery, ["found", "services"]);
  const rows = [...systems.map(system => ({ title: system.hostname || system.name || system.ip, type: "Discovered Device", status: system.status || "observed", details: [["IP", system.ip], ["Role", system.primaryRole]] })), ...found.map(service => ({ title: service.service || service.name, type: "Discovered Service", status: "observed", details: [["Host", service.ip], ["Port", service.port]] }))];
  byId("cmdbDiscoveryList").innerHTML = rows.map(row => cmdbObjectCard(row.title, row.type, row.status, row.details)).join("") || '<div class="empty-state"><h2>No discovery candidates loaded.</h2></div>';
}

function cmdbRenderAudit() {
  const rows = cmdbArray(cmdbPlatformData.audit, ["audit", "events", "items", "changes"]);
  byId("cmdbAuditList").innerHTML = rows.map(row => `<article><div><b>${safe(row.eventType || row.action || row.fieldName || row.type, "CMDB change")}</b><span>${safe(row.assetName || row.assetId || row.asset_id || row.entityId, "Platform")}</span></div><p>${safe(row.message || row.reason || row.summary, "Recorded platform change")}</p><time>${row.changedAt || row.createdAt || row.timestamp ? new Date(row.changedAt || row.createdAt || row.timestamp).toLocaleString() : "Time unavailable"}</time></article>`).join("") || '<div class="empty-state"><h2>No audit records loaded.</h2></div>';
}

function cmdbOpenSection(name) {
  document.querySelectorAll(".cmdb-section-tab").forEach(tab => tab.classList.toggle("active", tab.dataset.section === name));
  document.querySelectorAll(".cmdb-section-panel").forEach(panel => panel.classList.toggle("active", panel.dataset.panel === name));
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function cmdbRenderAll() {
  renderSummary();
  renderAssets();
  cmdbRenderOverview();
  cmdbRenderPools();
  cmdbRenderNodes();
  cmdbRenderServices();
  cmdbRenderWorkloads();
  cmdbRenderRelationships();
  cmdbRenderDiscovery();
  cmdbRenderAudit();
}

async function loadAssets() {
  const [inventory, pools, workers, workloads, relationships, topology, audit, discovery] = await Promise.all([
    cmdbFetchJson("/api/platform/inventory"),
    cmdbFetchJson("/api/platform/pools"),
    cmdbFetchJson("/api/platform/workers"),
    cmdbFetchJson("/api/platform/workloads"),
    cmdbFetchJson("/api/platform/relationships"),
    cmdbFetchJson("/api/platform/topology"),
    cmdbFetchJson("/api/cmdb/audit"),
    cmdbFetchJson("/api/discovery/scan")
  ]);

  cmdbPlatformData = { inventory, pools, workers, workloads, relationships, topology, audit, discovery };
  const platformAssets = cmdbInventoryAssets(inventory);
  const discoveryPayload = discovery?.discovery || discovery || {};
  const discoveryAssets = cmdbArray(discoveryPayload, ["systems"]).map(cmdbAssetRecord);
  latestSystems = platformAssets.length ? platformAssets : discoveryAssets;
  latestFound = cmdbArray(discoveryPayload, ["found", "services"]);
  latestRelationships = relationships || { relationships: [], pools: cmdbArray(pools, ["pools", "items"]), assets: latestSystems.map(row => row.asset) };

  const sourceState = byId("cmdbSourceState");
  if (sourceState) {
    sourceState.textContent = platformAssets.length ? "PostgreSQL CMDB · authoritative" : "Discovery fallback · platform inventory unavailable";
    sourceState.classList.toggle("warning", !platformAssets.length);
  }
  cmdbRenderAll();
}

window.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".cmdb-section-tab").forEach(tab => tab.addEventListener("click", () => cmdbOpenSection(tab.dataset.section)));
});

/* Package 068: Fleet Operations Center. */
let fleetView = "overview";
let fleetQuickFilter = "all";
let fleetSearchQuery = "";
const fleetExpandedGroups = new Set(
  JSON.parse(localStorage.getItem("nexusFleetExpandedGroups") || "[]")
);
const fleetVisibleLimit = new Map();

function fleetNormalizeState(value) {
  return String(value || "unknown").trim().toLowerCase().replaceAll("_", "-");
}

function fleetFormatHashrate(value) {
  const number = Number(value || 0);
  if (number >= 1e15) return `${(number / 1e15).toFixed(2)} PH/s`;
  if (number >= 1e12) return `${(number / 1e12).toFixed(2)} TH/s`;
  if (number >= 1e9) return `${(number / 1e9).toFixed(2)} GH/s`;
  if (number >= 1e6) return `${(number / 1e6).toFixed(2)} MH/s`;
  if (number > 0) return `${number.toFixed(0)} H/s`;
  return "—";
}

function fleetRelativeTime(value) {
  if (!value) return "Not observed";
  const timestamp = Date.parse(value);
  if (!Number.isFinite(timestamp)) return "Not observed";
  const seconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

function fleetWorkers() {
  const payload = cmdbPlatformData.workers || {};
  return cmdbArray(payload, ["activeWorkers", "workers", "items"]);
}

function fleetTopologyNodes() {
  return cmdbArray(cmdbPlatformData.topology, ["nodes", "items"]);
}

function fleetWorkerForAsset(assetId, label = "") {
  const candidates = fleetWorkers().filter(worker => {
    const state = fleetNormalizeState(worker.activityState || worker.status);
    return worker.assetId === assetId && !["stale", "retired", "offline", "disconnected"].includes(state);
  });
  if (candidates.length) {
    return candidates.sort((a, b) => Date.parse(b.lastSeenAt || b.updatedAt || 0) - Date.parse(a.lastSeenAt || a.updatedAt || 0))[0];
  }
  return fleetWorkers().find(worker => String(worker.displayName || "").toLowerCase() === String(label || "").toLowerCase()) || null;
}

function fleetCategory(node) {
  const props = node?.properties || {};
  const type = fleetNormalizeState(node?.assetType || node?.nodeType || props.assetType || props.type || node?.type);
  const role = String(props.primaryRole || props.role || "").toLowerCase();
  if (node?.nodeType === "pool" || type === "pool") return "pools";
  if (type.includes("blockchain") || role.includes("blockchain") || role.includes("bitcoin core")) return "blockchain";
  if (type === "asic" || role.includes("asic")) return "asic";
  if (type.includes("virtual-machine") && (role.includes("mining") || (props.capabilities || []).includes("crypto-mining"))) return "cpu";
  if (node?.nodeType === "service" || type.includes("service")) return "services";
  return "infrastructure";
}

function fleetStatusForNode(node, worker) {
  const props = node?.properties || {};
  const category = fleetCategory(node);
  if (category === "pools") {
    const state = fleetNormalizeState(props.operationalState || props.observedOperationalState || node.status || props.status);
    const activeWorkers = fleetWorkers().filter(item => item.currentSession === true && item.poolInstanceId === node.id).length;
    if (activeWorkers > 0) return "accepting-shares";
    return state;
  }
  if (worker?.currentSession === true) {
    const hashrate = Number(worker.currentHashrate || worker.hashrate || 0);
    return hashrate > 0 ? "mining" : fleetNormalizeState(worker.activityState || worker.status || "connected");
  }
  return fleetNormalizeState(props.observedOperationalState || props.activityState || node.status || props.status);
}

function fleetPoolName(worker) {
  if (!worker) return "Not assigned";
  const id = worker.poolInstanceId || worker.poolId;
  const pool = fleetTopologyNodes().find(node => node.id === id);
  return pool?.label || pool?.properties?.name || worker.poolName || id || "Not assigned";
}

function fleetRecordFromNode(node) {
  const props = node.properties || {};
  const category = fleetCategory(node);
  const objectType = node.nodeType || (category === "pools" ? "pool" : "asset");
  const worker = ["asic", "cpu"].includes(category) ? fleetWorkerForAsset(node.id, node.label) : null;
  const status = fleetStatusForNode(node, worker);
  const lifecycle = fleetNormalizeState(props.lifecycleStage || props.lifecycleStatus || "production");
  const management = fleetNormalizeState(props.managementModel || props.lifecycleStatus || (props.managed === false ? "observed" : "nexus-managed"));
  const coin = String(worker?.coin || props.coin?.symbol || props.coin || props.observedState?.coin?.symbol || "").toUpperCase();
  const activePoolWorkers = category === "pools" ? fleetWorkers().filter(item => item.currentSession === true && item.poolInstanceId === node.id) : [];
  const hashrate = category === "pools"
    ? activePoolWorkers.reduce((sum, item) => sum + Number(item.currentHashrate || item.hashrate || 0), 0) || Number(props.observedState?.hashrate || props.hashrate || 0)
    : Number(worker?.currentHashrate || worker?.hashrate || props.liveHashrate || 0);
  const health = fleetNormalizeState(props.health || (status === "offline" ? "offline" : "healthy"));
  const lastSeen = worker?.lastSeenAt || node.lastSeenAt || props.lastSeenAt || props.updatedAt || node.updatedAt;
  return {
    id: node.id,
    objectType,
    label: node.label || props.displayName || props.name || node.id,
    category,
    status,
    health,
    lifecycle,
    management,
    coin,
    hashrate,
    poolName: fleetPoolName(worker),
    workerCount: category === "pools" ? activePoolWorkers.length : null,
    ip: props.ip || props.host || props.poolHost || "",
    lastSeen,
    href: cmdbObjectHref(objectType, node.id),
    searchText: [node.id, node.label, category, status, health, lifecycle, management, coin, props.ip, props.host, fleetPoolName(worker), JSON.stringify(props.tags || [])].join(" ").toLowerCase()
  };
}

function fleetRecords() {
  return fleetTopologyNodes()
    .filter(node => ["asset", "pool", "service"].includes(String(node.nodeType || "").toLowerCase()))
    .map(fleetRecordFromNode);
}

function fleetIsAttention(record) {
  return ["offline", "failed", "fault", "critical", "warning", "degraded", "unknown"].includes(record.status) ||
    ["offline", "critical", "warning", "degraded"].includes(record.health);
}

function fleetMatchesView(record) {
  if (fleetView === "overview") return true;
  if (fleetView === "mining") return ["asic", "cpu"].includes(record.category);
  if (fleetView === "pools") return record.category === "pools";
  if (fleetView === "blockchain") return record.category === "blockchain";
  if (fleetView === "infrastructure") return ["infrastructure", "services"].includes(record.category);
  if (fleetView === "attention") return fleetIsAttention(record);
  if (fleetView === "maintenance") return record.lifecycle === "maintenance" || record.status === "maintenance";
  return true;
}

function fleetMatchesQuickFilter(record) {
  if (fleetQuickFilter === "all") return true;
  if (fleetQuickFilter === "mining") return record.status === "mining";
  if (fleetQuickFilter === "idle") return ["idle", "online", "standby"].includes(record.status);
  if (fleetQuickFilter === "offline") return record.status === "offline";
  if (fleetQuickFilter === "maintenance") return record.status === "maintenance" || record.lifecycle === "maintenance";
  if (fleetQuickFilter === "btc" || fleetQuickFilter === "bch") return record.coin.toLowerCase() === fleetQuickFilter;
  if (fleetQuickFilter === "managed") return record.management.includes("managed");
  if (fleetQuickFilter === "observed") return record.management.includes("observed");
  return true;
}

function fleetFilteredRecords() {
  const query = fleetSearchQuery.trim().toLowerCase();
  return fleetRecords().filter(record => fleetMatchesView(record) && fleetMatchesQuickFilter(record) && (!query || record.searchText.includes(query)));
}

function fleetStateLabel(status) {
  const labels = {
    "accepting-shares": "Accepting Shares",
    mining: "Mining",
    synchronized: "Synchronized",
    online: "Online",
    active: "Active",
    idle: "Idle",
    standby: "Standby",
    maintenance: "Maintenance",
    degraded: "Degraded",
    warning: "Warning",
    offline: "Offline",
    unknown: "Unknown"
  };
  return labels[status] || status.replaceAll("-", " ").replace(/\b\w/g, character => character.toUpperCase());
}

function fleetStatusTone(record) {
  if (["mining", "accepting-shares", "synchronized", "online", "active", "healthy"].includes(record.status)) return "healthy";
  if (["warning", "degraded", "maintenance", "idle", "standby", "unknown"].includes(record.status)) return "warning";
  if (["offline", "failed", "fault", "critical"].includes(record.status)) return "critical";
  return "neutral";
}

function fleetCard(record) {
  const metric = record.hashrate > 0 ? fleetFormatHashrate(record.hashrate) : record.category === "pools" ? `${record.workerCount || 0} active worker${record.workerCount === 1 ? "" : "s"}` : record.ip || fleetRelativeTime(record.lastSeen);
  const context = ["asic", "cpu"].includes(record.category) ? record.poolName : record.category === "pools" ? [record.coin, record.ip].filter(Boolean).join(" · ") : [record.ip, record.coin].filter(Boolean).join(" · ");
  return `<a class="fleet-object-card tone-${fleetStatusTone(record)}" href="${record.href}">
    <div class="fleet-card-head">
      <span class="fleet-card-state-dot" aria-hidden="true"></span>
      <div><small>${record.category.replaceAll("-", " ")}</small><h3>${safe(record.label)}</h3></div>
      <span class="fleet-card-status">${fleetStateLabel(record.status)}</span>
    </div>
    <strong class="fleet-card-metric">${metric}</strong>
    <p>${safe(context, "No current assignment")}</p>
    <footer><span>${record.lifecycle}</span><span>${record.management.replaceAll("-", " ")}</span><span>${fleetRelativeTime(record.lastSeen)}</span></footer>
  </a>`;
}

function fleetGroupLabel(category) {
  return ({ pools: "Mining Pools", asic: "ASIC Miners", cpu: "CPU Miners", blockchain: "Blockchain Nodes", services: "Managed Services", infrastructure: "Infrastructure" })[category] || category;
}

function fleetRenderSummary(records) {
  const all = fleetRecords();
  const activeMiners = all.filter(record => ["asic", "cpu"].includes(record.category) && record.status === "mining");
  const pools = all.filter(record => record.category === "pools");
  const blockchain = all.filter(record => record.category === "blockchain");
  const attention = all.filter(fleetIsAttention);
  const hashrate = activeMiners.reduce((sum, record) => sum + record.hashrate, 0);
  const cards = [
    ["Fleet Hashrate", fleetFormatHashrate(hashrate), `${activeMiners.length} active miner${activeMiners.length === 1 ? "" : "s"}`, "hashrate"],
    ["CMDB Objects", all.length, `${records.length} in current view`, "objects"],
    ["Pools", pools.length, `${pools.filter(record => record.status === "accepting-shares").length} accepting shares`, "pools"],
    ["Blockchain", blockchain.length, `${blockchain.filter(record => ["online", "synchronized", "active"].includes(record.status)).length} healthy`, "blockchain"],
    ["Needs Attention", attention.length, attention.length ? "Review recommended" : "Fleet healthy", attention.length ? "attention" : "healthy"],
    ["Last Sync", fleetRelativeTime(cmdbPlatformData.topology?.generatedAt || cmdbPlatformData.topology?.updatedAt || new Date().toISOString()), "PostgreSQL platform", "sync"]
  ];
  byId("fleetSummaryCards").innerHTML = cards.map(([label, value, detail, kind]) => `<article class="fleet-summary-card kind-${kind}"><span>${label}</span><strong>${value}</strong><small>${detail}</small></article>`).join("");
}

function fleetRenderQuickFilters(records) {
  const filters = [["all", "All"], ["mining", "Mining"], ["idle", "Idle"], ["offline", "Offline"], ["maintenance", "Maintenance"], ["btc", "BTC"], ["bch", "BCH"], ["managed", "Managed"], ["observed", "Observed"]];
  byId("fleetQuickFilters").innerHTML = filters.map(([value, label]) => `<button type="button" class="fleet-quick-filter ${fleetQuickFilter === value ? "active" : ""}" data-fleet-filter="${value}">${label}</button>`).join("");
  byId("fleetQuickFilters").querySelectorAll("[data-fleet-filter]").forEach(button => button.addEventListener("click", () => {
    fleetQuickFilter = button.dataset.fleetFilter;
    fleetRender();
  }));
}

function fleetRenderGroups(records) {
  const order = ["pools", "asic", "cpu", "blockchain", "services", "infrastructure"];
  const grouped = Object.groupBy ? Object.groupBy(records, record => record.category) : records.reduce((result, record) => ((result[record.category] ||= []).push(record), result), {});
  const sections = order.filter(category => grouped[category]?.length).map(category => {
    const rows = grouped[category];
    const collapsed = !fleetExpandedGroups.has(category) && records.length > 12;
    const limit = fleetVisibleLimit.get(category) || 24;
    const visible = collapsed ? [] : rows.slice(0, limit);
    return `<section class="fleet-group ${collapsed ? "collapsed" : ""}" data-fleet-group="${category}">
      <button type="button" class="fleet-group-heading" data-toggle-fleet-group="${category}" aria-expanded="${!collapsed}">
        <span><b>${fleetGroupLabel(category)}</b><small>${rows.length} object${rows.length === 1 ? "" : "s"}</small></span>
        <span class="fleet-group-summary">${rows.filter(record => ["mining", "accepting-shares", "online", "synchronized", "active"].includes(record.status)).length} active <i>⌄</i></span>
      </button>
      ${collapsed ? "" : `<div class="fleet-object-grid">${visible.map(fleetCard).join("")}</div>${rows.length > visible.length ? `<button type="button" class="fleet-show-more" data-fleet-more="${category}">Show ${Math.min(24, rows.length - visible.length)} more</button>` : ""}`}
    </section>`;
  }).join("");
  byId("fleetGroups").innerHTML = sections || `<div class="fleet-empty"><h3>No fleet objects match.</h3><p>Clear a filter or try a broader search.</p></div>`;
  byId("fleetGroups").querySelectorAll("[data-toggle-fleet-group]").forEach(button => button.addEventListener("click", () => {
    const category = button.dataset.toggleFleetGroup;
    if (fleetExpandedGroups.has(category)) fleetExpandedGroups.delete(category); else fleetExpandedGroups.add(category);
    localStorage.setItem("nexusFleetExpandedGroups", JSON.stringify([...fleetExpandedGroups]));
    fleetRender();
  }));
  byId("fleetGroups").querySelectorAll("[data-fleet-more]").forEach(button => button.addEventListener("click", () => {
    const category = button.dataset.fleetMore;
    fleetVisibleLimit.set(category, (fleetVisibleLimit.get(category) || 24) + 24);
    fleetExpandedGroups.add(category);
    fleetRender();
  }));
}

function fleetRender() {
  const records = fleetFilteredRecords();
  fleetRenderSummary(records);
  fleetRenderQuickFilters(records);
  fleetRenderGroups(records);
  const summary = byId("fleetResultSummary");
  if (summary) summary.textContent = `${records.length} object${records.length === 1 ? "" : "s"} shown · ${fleetView.replaceAll("-", " ")} view`;
  document.querySelectorAll("[data-fleet-view]").forEach(button => button.classList.toggle("active", button.dataset.fleetView === fleetView));
}

const cmdbRenderOverviewBase = cmdbRenderOverview;
cmdbRenderOverview = function cmdbRenderFleetOverview() {
  cmdbRenderOverviewBase();
  fleetRender();
};

window.addEventListener("DOMContentLoaded", () => {
  byId("fleetSearch")?.addEventListener("input", event => {
    fleetSearchQuery = event.target.value;
    fleetRender();
  });
  document.querySelectorAll("[data-fleet-view]").forEach(button => button.addEventListener("click", () => {
    fleetView = button.dataset.fleetView || "overview";
    fleetQuickFilter = "all";
    fleetRender();
  }));
});
