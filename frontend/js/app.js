let latestSystems = [];
let latestFound = [];

function openDrawer(system) {
  const services = latestFound.filter(item => item.ip === system.ip);

  const roles = system.roles.map(role => `
    <span class="role-pill">${role.label} ${role.confidence}%</span>
  `).join('');

  const fingerprints = (system.fingerprints || []).map(fp => `
    <div class="fingerprint ${fp.status}">
      <span>${fp.label}</span>
      <b>${fp.status.toUpperCase()}</b>
    </div>
  `).join('');

  const serviceRows = services.map(s => `
    <li>${s.service} <b>:${s.port}</b></li>
  `).join('');

  document.getElementById('drawerContent').innerHTML = `
    <h2>${system.asset?.name || system.ip}</h2>
    <p class="drawer-subtitle">${system.primaryRole}</p>

    <div class="drawer-section">
      <label>IP Address</label>
      <strong>${system.ip}</strong>
    </div>

    <div class="drawer-section">
      <label>Purpose</label>
      <strong>${system.asset?.purpose || 'Unknown'}</strong>
    </div>

    <div class="drawer-section">
      <label>Detected Roles</label>
      <div class="role-pills">${roles}</div>
    </div>

    <div class="drawer-section">
      <label>Confirmed Services</label>
      <div class="fingerprints">${fingerprints || 'No confirmed services yet.'}</div>
    </div>

    <div class="drawer-section">
      <label>Open Services</label>
      <ul>${serviceRows}</ul>
    </div>

    <div class="drawer-actions">
      <button>Rename</button>
      <button>Assign Pool</button>
      <button>View Logs</button>
    </div>
  `;

  document.getElementById('drawer').classList.add('open');
  document.getElementById('drawerBackdrop').classList.add('open');
}

function closeDrawer() {
  document.getElementById('drawer').classList.remove('open');
  document.getElementById('drawerBackdrop').classList.remove('open');
}

async function loadSummary() {
  const summaryRes = await fetch('/api/dashboard/summary');
  const data = await summaryRes.json();

  document.getElementById('overall').textContent = data.status.toUpperCase();
  document.getElementById('systems').textContent = data.systems;
  document.getElementById('nodes').textContent = data.blockchainNodes;
  document.getElementById('backends').textContent = data.miningBackends;
  document.getElementById('stratum').textContent = data.stratumServers;
  document.getElementById('rpc').textContent = data.rpcEndpoints;
  document.getElementById('alerts').textContent = data.alerts;

  const discoveryRes = await fetch('/api/discovery/scan');
  const discovery = await discoveryRes.json();

  latestSystems = discovery.discovery.systems || [];
  latestFound = discovery.discovery.found || [];

  const html = latestSystems.map((system, index) => {
    const services = latestFound.filter(item => item.ip === system.ip);

    const rolePills = system.roles.map(role => `
      <span class="role-pill">${role.label} ${role.confidence}%</span>
    `).join('');

    const fingerprints = (system.fingerprints || []).map(fp => `
      <div class="fingerprint ${fp.status}">
        <span>${fp.label}</span>
        <b>${fp.status.toUpperCase()}</b>
      </div>
    `).join('');

    const rows = services.map(s => `
      <li>
        <span>${s.service}</span>
        <b>:${s.port}</b>
      </li>
    `).join('');

    return `
      <div class="system-row clickable" data-system-index="${index}">
        <div>
          <strong>${system.asset?.name || system.ip}</strong>
          <div class="system-ip">${system.ip}</div>
          <div class="primary-role">${system.primaryRole}</div>
          <small>${system.serviceCount} services detected</small>
          <div class="role-pills">${rolePills}</div>
          <div class="fingerprints">${fingerprints}</div>
        </div>
        <ul>${rows}</ul>
      </div>
    `;
  }).join('');

  document.getElementById('systemsList').innerHTML = html || 'No systems discovered.';

  document.querySelectorAll('.system-row.clickable').forEach(row => {
    row.addEventListener('click', () => {
      const index = Number(row.dataset.systemIndex);
      openDrawer(latestSystems[index]);
    });
  });
}

document.getElementById('drawerClose').addEventListener('click', closeDrawer);
document.getElementById('drawerBackdrop').addEventListener('click', closeDrawer);

loadSummary();
setInterval(loadSummary, 30000);
