
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
    card.addEventListener("click", () => {
      const system = latestSystems.find(s => s.ip === card.dataset.ip);
      if (system) openDrawer(system);
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

async function openDrawer(system) {
  const asset=system.asset||{}; const services=latestFound.filter(item=>item.ip===system.ip);
  let lifecycle={asset:{operationalState:asset.operationalState||'active',lifecycleStatus:asset.lifecycleStatus||'managed',desiredOperationalState:'online'},history:[]};
  let dependencyData={relationships:[],workloads:[],capability:null};
  try { if(asset.id) lifecycle=await loadLifecycle(asset.id); } catch(e) {}
  try { if(asset.id) dependencyData=await loadDependencyData(asset.id); } catch(e) {}
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
