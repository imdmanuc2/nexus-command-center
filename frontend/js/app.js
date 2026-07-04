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

  const systems = discovery.discovery.systems || [];
  const found = discovery.discovery.found || [];

  const html = systems.map(system => {
    const services = found.filter(item => item.ip === system.ip);

    const rolePills = system.roles.map(role => `
      <span class="role-pill">${role.label} ${role.confidence}%</span>
    `).join('');

    const rows = services.map(s => `
      <li>
        <span>${s.service}</span>
        <b>:${s.port}</b>
      </li>
    `).join('');

    return `
      <div class="system-row">
        <div>
          <strong>${system.ip}</strong>
          <div class="primary-role">${system.primaryRole}</div>
          <small>${system.serviceCount} services detected</small>
          <div class="role-pills">${rolePills}</div>
        </div>
        <ul>${rows}</ul>
      </div>
    `;
  }).join('');

  document.getElementById('systemsList').innerHTML = html || 'No systems discovered.';
}

loadSummary();
setInterval(loadSummary, 30000);
