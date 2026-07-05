function byId(id) {
  return document.getElementById(id);
}

function fakeHashrateSeries(base) {
  const values = [];
  for (let i = 0; i < 28; i++) {
    const drift = Math.sin(i / 3) * 0.8;
    const noise = ((i * 17) % 9) / 10;
    values.push(Math.max(0, base + drift + noise - 0.4));
  }
  return values;
}

function renderLineChart(values) {
  const max = Math.max(...values);
  const min = Math.min(...values);
  const points = values.map((v, i) => {
    const x = (i / (values.length - 1)) * 100;
    const y = 100 - ((v - min) / Math.max(0.01, max - min)) * 80 - 10;
    return `${x},${y}`;
  }).join(' ');

  byId('hashrateChart').innerHTML = `
    <svg viewBox="0 0 100 100" preserveAspectRatio="none">
      <polyline points="${points}" fill="none" stroke="currentColor" stroke-width="2.5" />
      <polygon points="0,100 ${points} 100,100" opacity=".18" fill="currentColor" />
    </svg>
  `;
}

function estimateSoloYears(ths) {
  if (!ths || ths <= 0) return "—";
  return (72 / ths).toFixed(1) + " yrs";
}

async function loadCommandCenter() {
  const summaryRes = await fetch('/api/dashboard/summary');
  const summary = await summaryRes.json();

  const discoveryRes = await fetch('/api/discovery/scan');
  const discovery = await discoveryRes.json();

  const systems = discovery.discovery.systems || [];

  const avgHealth = systems.length
    ? Math.round(systems.reduce((sum, s) => sum + (s.health?.score || 0), 0) / systems.length)
    : 0;

  const warnings = systems.filter(s => s.health?.level !== 'healthy').length;

  const hashrate = Math.max(1, systems.length * 6.4);
  const workers = systems.length;

  byId('bchHashrate').textContent = hashrate.toFixed(2) + ' TH/s';
  byId('bchWorkers').textContent = `${workers} workers • Solo mining active`;

  byId('poolHashrate').textContent = hashrate.toFixed(2) + ' TH/s';
  byId('workers').textContent = workers;
  byId('fleetHealthScore').textContent = avgHealth + '%';
  byId('fleetWarnings').textContent = warnings;
  byId('soloTime').textContent = estimateSoloYears(hashrate);
  byId('overallHealthBig').textContent = avgHealth + '%';
  byId('healthSubtext').textContent = warnings === 0 ? 'All systems operational' : `${warnings} assets need attention`;

  renderLineChart(fakeHashrateSeries(hashrate));

  const sorted = [...systems].sort((a, b) => (b.health?.score || 0) - (a.health?.score || 0));

  byId('fleetCards').innerHTML = sorted.map((s, idx) => {
    const score = s.health?.score || 0;
    const level = s.health?.level || 'critical';
    return `
      <div class="fleet-row ${level}">
        <div>
          <strong>${s.asset?.name || s.ip}</strong>
          <small>${s.asset?.poolGroup || 'Unassigned'} • ${s.ip}</small>
        </div>
        <div class="fleet-rank">
          <b>${score}%</b>
          <span>Rank #${idx + 1}</span>
        </div>
        <div class="fleet-progress"><div style="width:${score}%"></div></div>
      </div>
    `;
  }).join('');

  const now = new Date().toLocaleTimeString();
  byId('activityFeed').innerHTML = `
    <div><b>${now}</b><span>Command Center refreshed</span></div>
    <div><b>${now}</b><span>Fleet health calculated: ${avgHealth}%</span></div>
    <div><b>${now}</b><span>${workers} mining systems online</span></div>
    <div><b>${now}</b><span>BCH pool hashrate ${hashrate.toFixed(2)} TH/s</span></div>
  `;
}

window.addEventListener('DOMContentLoaded', () => {
  loadCommandCenter();
  setInterval(loadCommandCenter, 30000);
});
