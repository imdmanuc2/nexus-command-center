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

  const serviceRows = services.map(s =>
    `<li>${s.service} <b>:${s.port}</b></li>`
  ).join('');

  byId('drawerContent').innerHTML = `
    <h2>${system.asset?.name || system.ip}</h2>
    <p class="drawer-subtitle">${system.primaryRole}</p>

    <div class="drawer-section"><label>Asset Type</label><strong>${system.profile?.assetType || 'Unknown'}</strong></div>
    <div class="drawer-section"><label>Hostname</label><strong>${system.profile?.hostname || 'Not resolved'}</strong></div>
    <div class="drawer-section"><label>IP Address</label><strong>${system.ip}</strong></div>
    <div class="drawer-section"><label>Mining Group</label><strong>${system.asset?.poolGroup || 'Unassigned'}</strong></div>
    <div class="drawer-section"><label>Nexus Agent</label><strong>${system.profile?.agent || 'Not installed'}</strong></div>
    <div class="drawer-section"><label>Detected Roles</label><div class="role-pills">${roles}</div></div>
    <div class="drawer-section"><label>Infrastructure Services</label><ul>${serviceRows}</ul></div>
  `;

  byId('drawer')?.classList.add('open');
  byId('drawerBackdrop')?.classList.add('open');
}

async function loadInventory() {
  const res = await fetch('/api/discovery/scan');
  const data = await res.json();

  latestSystems = data.discovery.systems || [];
  latestFound = data.discovery.found || [];

  const html = latestSystems.map(system => `
    <div class="inventory-card" data-ip="${system.ip}">
      <div class="node-status"></div>
      <h3>${system.asset?.name || system.ip}</h3>
      <p>${system.primaryRole}</p>
      <div class="inventory-meta">
        <span>${system.profile?.assetType || 'Unknown Asset'}</span>
        <span>${system.asset?.poolGroup || 'Unassigned'}</span>
        <span>${system.serviceCount} services</span>
      </div>
      <small>${system.ip}</small>
    </div>
  `).join('');

  byId('inventoryList').innerHTML = html || 'No assets discovered.';

  document.querySelectorAll('.inventory-card').forEach(card => {
    card.addEventListener('click', () => {
      const system = latestSystems.find(s => s.ip === card.dataset.ip);
      if (system) openDrawer(system);
    });
  });
}

window.addEventListener('DOMContentLoaded', () => {
  byId('drawerClose')?.addEventListener('click', closeDrawer);
  byId('drawerBackdrop')?.addEventListener('click', closeDrawer);
  loadInventory();
});
