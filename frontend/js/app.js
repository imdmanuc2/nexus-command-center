async function loadSummary() {
  const res = await fetch('/api/dashboard/summary');
  const data = await res.json();

  document.getElementById('status').textContent = data.status.toUpperCase();
  document.getElementById('status').className = 'status ' + data.status;

  document.getElementById('systems').textContent = data.systems;
  document.getElementById('nodes').textContent = data.blockchainNodes;
  document.getElementById('backends').textContent = data.miningBackends;
  document.getElementById('dashboards').textContent = data.dashboards;
  document.getElementById('stratum').textContent = data.stratumServers;
  document.getElementById('rpc').textContent = data.rpcEndpoints;
  document.getElementById('alerts').textContent = data.alerts;
}

loadSummary();
setInterval(loadSummary, 15000);
