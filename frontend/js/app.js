let latestSystems = [];
let latestFound = [];

function byId(id) {
  return document.getElementById(id);
}

async function assignPool(system) {
  const current = system.asset?.poolGroup || "";
  const poolGroup = prompt("Enter mining group name:", current);

  if (poolGroup === null) return;

  await fetch("/api/assets/update", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      ip: system.ip,
      updates: {poolGroup: poolGroup.trim()}
    })
  });

  closeDrawer();
  await loadSummary();
}

async function renameAsset(system) {
  const current = system.asset?.name || system.ip;
  const name = prompt("Enter friendly name:", current);

  if (!name || name.trim() === "") return;

  await fetch("/api/assets/update", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      ip: system.ip,
      updates: {name: name.trim()}
    })
  });

  closeDrawer();
  await loadSummary();
}

function closeDrawer() {
  byId('drawer')?.classList.remove('open');
  byId('drawerBackdrop')?.classList.remove('open');
}

function openDrawer(system) {
  const services = latestFound.filter(item => item.ip === system.ip);

  const roles = system.roles.map(role =>
    `<span class="role-pill">${role.label} ${role.confidence}%</span>`
  ).join('');

  const fingerprints = (system.fingerprints || []).map(fp =>
    `<div class="fingerprint ${fp.status}">
      <span>${fp.label}</span>
      <b>${fp.status.toUpperCase()}</b>
    </div>`
  ).join('');

  const serviceRows = services.map(s =>
    `<li>${s.service} <b>:${s.port}</b></li>`
  ).join('');

  byId('drawerContent').innerHTML = `
    <h2>${system.asset?.name || system.ip}</h2>
    <p class="drawer-subtitle">${system.primaryRole}</p>

    <div class="drawer-section"><label>Asset Type</label><strong>${system.profile?.assetType || 'Unknown'}</strong></div>
    <div class="drawer-section"><label>Hostname</label><strong>${system.profile?.hostname || 'Not resolved'}</strong></div>
    <div class="drawer-section"><label>IP Address</label><strong>${system.ip}</strong></div>
    <div class="drawer-section"><label>Nexus Agent</label><strong>${system.profile?.agent || 'Not installed'}</strong></div>
    <div class="drawer-section"><label>Purpose</label><strong>${system.asset?.purpose || 'Unknown'}</strong></div>
    <div class="drawer-section"><label>Mining Group</label><strong>${system.asset?.poolGroup || 'Not assigned'}</strong></div>
    <div class="drawer-section"><label>Detected Roles</label><div class="role-pills">${roles}</div></div>
    <div class="drawer-section"><label>Confirmed Services</label><div class="fingerprints">${fingerprints || 'No confirmed services yet.'}</div></div>
    <div class="drawer-section"><label>Open Services</label><ul>${serviceRows}</ul></div>

    <div class="drawer-actions">
      <button onclick="renameAsset(latestSystems.find(s => s.ip === '${system.ip}'))">Rename</button>
      <button onclick="assignPool(latestSystems.find(s => s.ip === '${system.ip}'))">Assign Mining Group</button>
      <button>View Logs</button>
    </div>
  `;

  byId('drawer')?.classList.add('open');
  byId('drawerBackdrop')?.classList.add('open');
}


function renderTopology() {
  const groups = {};

  latestSystems.forEach(system => {
    const group = system.asset?.poolGroup || "Unassigned";
    if (!groups[group]) groups[group] = [];
    groups[group].push(system);
  });

  const html = Object.entries(groups).map(([group, systems]) => {
    const nodes = systems.map(system => `
      <div class="topology-node" onclick="openDrawer(latestSystems.find(s => s.ip === '${system.ip}'))">
        <div class="node-status"></div>
        <strong>${system.asset?.name || system.ip}</strong>
        <span>${system.primaryRole}</span>
        <small>${system.ip}</small>
      </div>
    `).join('');

    return `
      <div class="topology-group">
        <div class="topology-title">⛏ ${group}</div>
        <div class="topology-line"></div>
        <div class="topology-nodes">${nodes}</div>
      </div>
    `;
  }).join('');

  const el = byId('topologyView');
  if (el) el.innerHTML = html || 'No topology available.';
}


async function loadSummary() {
  const summaryRes = await fetch('/api/dashboard/summary');
  const data = await summaryRes.json();

  byId('overall').textContent = data.status.toUpperCase();
  byId('systems').textContent = data.systems;
  byId('nodes').textContent = data.blockchainNodes;
  byId('backends').textContent = data.miningBackends;
  byId('stratum').textContent = data.stratumServers;
  byId('rpc').textContent = data.rpcEndpoints;
  byId('alerts').textContent = data.alerts;

  const discoveryRes = await fetch('/api/discovery/scan');
  const discovery = await discoveryRes.json();

  latestSystems = discovery.discovery.systems || [];
  latestFound = discovery.discovery.found || [];

  const html = latestSystems.map((system, index) => {
    const services = latestFound.filter(item => item.ip === system.ip);

    const rolePills = system.roles.map(role =>
      `<span class="role-pill">${role.label} ${role.confidence}%</span>`
    ).join('');

    const fingerprints = (system.fingerprints || []).map(fp =>
      `<div class="fingerprint ${fp.status}">
        <span>${fp.label}</span>
        <b>${fp.status.toUpperCase()}</b>
      </div>`
    ).join('');

    const rows = services.map(s =>
      `<li><span>${s.service}</span><b>:${s.port}</b></li>`
    ).join('');

    return `
      <div class="system-row clickable" data-system-index="${index}">
        <div>
          <strong>${system.asset?.name || system.ip}</strong>
          <div class="system-ip">${system.ip}</div>
          <div class="primary-role">${system.primaryRole}</div>
          <small>${system.serviceCount} services detected</small>
          <div class="asset-meta">${system.asset?.poolGroup ? 'Mining Group: ' + system.asset.poolGroup : 'No mining group assigned'}</div>
          <div class="role-pills">${rolePills}</div>
          <div class="fingerprints">${fingerprints}</div>
        </div>
        <ul>${rows}</ul>
      </div>
    `;
  }).join('');

  byId('systemsList').innerHTML = html || 'No systems discovered.';

  document.querySelectorAll('.system-row.clickable').forEach(row => {
    row.addEventListener('click', () => {
      openDrawer(latestSystems[Number(row.dataset.systemIndex)]);
    });
  });
}

window.addEventListener('DOMContentLoaded', () => {
  byId('drawerClose')?.addEventListener('click', closeDrawer);
  byId('drawerBackdrop')?.addEventListener('click', closeDrawer);

  loadSummary();
  setInterval(loadSummary, 30000);
});
