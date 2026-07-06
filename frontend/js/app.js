function byId(id) {
  return document.getElementById(id);
}

let hashHistory = [];

function fmtHashrate(v) {
  if (!v || isNaN(v)) return "0 H/s";
  if (v >= 1e15) return (v / 1e15).toFixed(2) + " PH/s";
  if (v >= 1e12) return (v / 1e12).toFixed(2) + " TH/s";
  if (v >= 1e9) return (v / 1e9).toFixed(2) + " GH/s";
  if (v >= 1e6) return (v / 1e6).toFixed(2) + " MH/s";
  return v.toFixed(2) + " H/s";
}

function renderChart(values) {
  if (!values.length) values = [0];

  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);

  const points = values.map((v, i) => {
    const x = values.length === 1 ? 0 : (i / (values.length - 1)) * 100;
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

  return miners.map((m) => {
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
  const miningRes = await fetch("/api/mining/summary");
  const mining = await miningRes.json();

  const workers = (mining.workers || []).map((w, index) => ({
    name: w.displayName || ("ASIC " + w.name),
    fullName: w.fullName || w.name,
    hashrate: w.hashrate || 0,
    sps: w.sharesPerSecond || 0,
    rank: index + 1
  })).sort((a, b) => b.hashrate - a.hashrate);

  workers.forEach((m, i) => m.rank = i + 1);

  const totalHash = mining.totalHashrate || workers.reduce((sum, w) => sum + w.hashrate, 0);
  const maxHash = Math.max(...workers.map(w => w.hashrate), 1);
  const workerCount = mining.workerCount ?? workers.length;

  hashHistory.push(totalHash);
  if (hashHistory.length > 40) hashHistory.shift();

  byId("bchHashrate").textContent = fmtHashrate(totalHash);
  byId("bchWorkers").textContent = `${workerCount} workers • Solo mining active`;

  byId("poolHashrate").textContent = fmtHashrate(totalHash);
  byId("workers").textContent = workerCount;
  byId("fleetHealth").textContent = mining.status === "online" ? "100%" : "0%";
  byId("warnings").textContent = mining.status === "online" ? "0" : "1";
  byId("soloTime").textContent = totalHash ? (72 / (totalHash / 1e12)).toFixed(1) + " yrs" : "—";

  byId("topMiners").innerHTML = minerRows(workers.slice(0, 10), maxHash, false);
  const avgHash = workers.length
    ? workers.reduce((sum, w) => sum + w.hashrate, 0) / workers.length
    : 0;

  const underperforming = workers
    .filter(w => avgHash && w.hashrate < avgHash * 0.85)
    .sort((a, b) => a.hashrate - b.hashrate)
    .slice(0, 10);

  byId("bottomMiners").innerHTML = underperforming.length
    ? minerRows(underperforming, maxHash, true)
    : '<div class="all-clear-box">All miners performing within normal range.</div>';

  renderChart(hashHistory);

  const now = new Date().toLocaleTimeString();
  const best = workers[0];
  const weakest = workers[workers.length - 1];

  byId("activityFeed").innerHTML = `
    <div class="event green"><b>${now}</b><span>MiningCore connector online</span></div>
    <div class="event green"><b>${now}</b><span>${workerCount} workers connected</span></div>
    <div class="event blue"><b>${now}</b><span>Live pool hashrate ${fmtHashrate(totalHash)}</span></div>
    <div class="event blue"><b>${now}</b><span>Shares/sec ${Number(mining.sharesPerSecond || 0).toFixed(3)}</span></div>
    <div class="event green"><b>${now}</b><span>Top miner: ${best ? best.name + " at " + fmtHashrate(best.hashrate) : "—"}</span></div>
    <div class="event gold"><b>${now}</b><span>Weakest miner: ${weakest ? weakest.name + " at " + fmtHashrate(weakest.hashrate) : "—"}</span></div>
  `;
}

window.addEventListener("DOMContentLoaded", () => {
  loadCommandCenter();
  setInterval(loadCommandCenter, 10000);
});
