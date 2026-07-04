let latestSystems = [];
let latestFound = [];

function byId(id) {
  return document.getElementById(id);
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

    <div class="drawer-section"><label>IP Address</label><strong>${system.ip}</strong></div>
    <div class="drawer-section"><label>Mining Group</label><strong>${system.asset?.poolGroup || 'Unassigned'}</strong></div>
    <div class="drawer-section"><label>Purpose</label><strong>${system.asset?.purpose || 'Unknown'}</strong></div>
    <div class="drawer-section"><label>Detected Roles</label><div class="role-pills">${roles}</div></div>
    <div class="drawer-section"><label>Confirmed Services</label><div class="fingerprints">${fingerprints || 'No confirmed services yet.'}</div></div>
    <div class="drawer-section"><label>Open Services</label><ul>${serviceRows}</ul></div>
  `;

  byId('drawer')?.classList.add('open');
  byId('drawerBackdrop')?.classList.add('open');
}

async function loadMap() {
  const res = await fetch('/api/discovery/scan');
  const data = await res.json();

  latestSystems = data.discovery.systems || [];
  latestFound = data.discovery.found || [];

  const groups = {};

  latestSystems.forEach(system => {
    const group = system.asset?.poolGroup || 'Unassigned';
    if (!groups[group]) groups[group] = [];
    groups[group].push(system);
  });

  const html = Object.entries(groups).map(([group, systems]) => {
    const nodes = systems.map((system, index) => `
      <div class="map-node" data-ip="${system.ip}">
        <div class="node-status"></div>
        <div class="node-icon">🖥️</div>
        <strong>${system.asset?.name || system.ip}</strong>
        <span>${system.primaryRole}</span>
        <small>${system.ip}</small>
      </div>
    `).join('');

    return `
      <div class="map-group">
        <div class="map-group-title">⛏ ${group}</div>
        <div class="map-connector"></div>
        <div class="map-nodes">${nodes}</div>
      </div>
    `;
  }).join('');

  byId('mapGroups').innerHTML = html || 'No infrastructure discovered.';

  document.querySelectorAll('.map-node').forEach(node => {
    node.addEventListener('click', () => {
      const system = latestSystems.find(s => s.ip === node.dataset.ip);
      if (system) openDrawer(system);
    });
  });
}

window.addEventListener('DOMContentLoaded', () => {
  byId('drawerClose')?.addEventListener('click', closeDrawer);
  byId('drawerBackdrop')?.addEventListener('click', closeDrawer);

  loadMap();
  setInterval(loadMap, 30000);
});
