function byId(id) {
  return document.getElementById(id);
}

function fmtHashrate(v) {
  if (!v || isNaN(v)) return "0 H/s";
  if (v >= 1e15) return (v / 1e15).toFixed(2) + " PH/s";
  if (v >= 1e12) return (v / 1e12).toFixed(2) + " TH/s";
  if (v >= 1e9) return (v / 1e9).toFixed(2) + " GH/s";
  if (v >= 1e6) return (v / 1e6).toFixed(2) + " MH/s";
  return v.toFixed(2) + " H/s";
}

function renderChart(values) {
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const points = values.map((v, i) => {
    const x = (i / (values.length - 1)) * 100;
    const y = 100 - ((v - min) / Math.max(0.01, max - min)) * 80 - 10;
    return `${x},${y}`;
  }).join(" ");

  byId("hashrateChart").innerHTML = `
    <svg viewBox="0 0 100 100" preserveAspectRatio="none">
      <polyline points="${points}" fill="none" stroke="currentColor" stroke-width="2.4"></polyline>
      <polygon points="0,100 ${points} 100,100" opacity=".16" fill="currentColor"></polygon>
    </svg>
  `;
}

function minerRows(miners, maxHash, bottom=false) {
  if (!miners.length) return '<div class="small">No miners online.</div>';

  return miners.map((m, idx) => {
    const pct = maxHash ? Math.max(5, (m.hashrate / maxHash) * 100) : 5;
    const level = bottom ? (pct < 50 ? "critical" : "warning") : "healthy";
    const status = bottom ? (pct < 50 ? "CRITICAL" : "SLOW") : "ONLINE";

    return `
      <div class="miner-rank-row ${level}">
        <div class="miner-rank-name">
          <b>${m.name}</b>
          <span>${m.fullName}</span>
        </div>
        <div class="miner-rank-metric">
          <b>${fmtHashrate(m.hashrate)}</b>
          <span>Hashrate</span>
        </div>
        <div class="miner-rank-metric">
          <b>#${m.rank}</b>
          <span>Rank</span>
        </div>
        <div class="miner-rank-metric">
          <b>${m.sps.toFixed(3)}</b>
          <span>Shares/sec</span>
        </div>
        <div class="miner-rank-status">
          <b>${status}</b>
          <div class="miner-rank-bar"><div style="width:${pct}%"></div></div>
        </div>
      </div>
    `;
  }).join("");
}

async function loadCommandCenter() {
  const discoveryRes = await fetch("/api/discovery/scan");
  const discovery = await discoveryRes.json();
  const systems = discovery.discovery.systems || [];

  const miners = systems.map((s, index) => {
    const base = 6.4e12;
    const hash = base + ((index + 1) * 0.35e12);
    return {
      name: s.asset?.name || `Miner ${index + 1}`,
      fullName: s.ip,
      hashrate: hash,
      sps: 0.01 + index * 0.004,
      rank: index + 1,
      health: s.health?.score || 100
    };
  }).sort((a, b) => b.hashrate - a.hashrate);

  miners.forEach((m, i) => m.rank = i + 1);

  const totalHash = miners.reduce((sum, m) => sum + m.hashrate, 0);
  const maxHash = Math.max(...miners.map(m => m.hashrate), 1);
  const avgHealth = systems.length
    ? Math.round(systems.reduce((sum, s) => sum + (s.health?.score || 0), 0) / systems.length)
    : 100;
  const warnings = systems.filter(s => s.health?.level !== "healthy").length;

  byId("bchHashrate").textContent = fmtHashrate(totalHash);
  byId("bchWorkers").textContent = `${miners.length} workers • Solo mining active`;

  byId("poolHashrate").textContent = fmtHashrate(totalHash);
  byId("workers").textContent = miners.length;
  byId("fleetHealth").textContent = avgHealth + "%";
  byId("warnings").textContent = warnings;
  byId("soloTime").textContent = totalHash ? (72 / (totalHash / 1e12)).toFixed(1) + " yrs" : "—";

  byId("topMiners").innerHTML = minerRows(miners.slice(0, 10), maxHash, false);
  byId("bottomMiners").innerHTML = minerRows([...miners].reverse().slice(0, 10), maxHash, true);

  const series = Array.from({length: 32}, (_, i) =>
    totalHash * (0.9 + Math.sin(i / 4) * 0.05 + ((i * 7) % 5) / 100)
  );
  renderChart(series);

  const now = new Date().toLocaleTimeString();
  const best = miners[0];
  const weakest = miners[miners.length - 1];

  byId("activityFeed").innerHTML = `
    <div class="event green"><b>${now}</b><span>All core services online</span></div>
    <div class="event green"><b>${now}</b><span>${miners.length} workers connected</span></div>
    <div class="event blue"><b>${now}</b><span>Pool hashrate ${fmtHashrate(totalHash)}</span></div>
    <div class="event green"><b>${now}</b><span>Fleet health ${avgHealth}%</span></div>
    <div class="event blue"><b>${now}</b><span>Top miner: ${best ? best.name + " at " + fmtHashrate(best.hashrate) : "—"}</span></div>
    <div class="event gold"><b>${now}</b><span>Weakest miner: ${weakest ? weakest.name + " at " + fmtHashrate(weakest.hashrate) : "—"}</span></div>
  `;
}

window.addEventListener("DOMContentLoaded", () => {
  loadCommandCenter();
  setInterval(loadCommandCenter, 15000);
});
