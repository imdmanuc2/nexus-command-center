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

  const grouped = {};
  discovery.discovery.found.forEach(item => {
    if (!grouped[item.ip]) grouped[item.ip] = [];
    grouped[item.ip].push(item);
  });

  const html = Object.entries(grouped).map(([ip, services]) => {
    const rows = services.map(s => `<li>${s.service} <b>:${s.port}</b></li>`).join('');
    return `
      <div class="system-row">
        <div>
          <strong>${ip}</strong>
          <small>${services.length} services detected</small>
        </div>
        <ul>${rows}</ul>
      </div>
    `;
  }).join('');

  document.getElementById('systemsList').innerHTML = html || 'No systems discovered.';
}

loadSummary();
setInterval(loadSummary, 30000);
