function byId(id) {
  return document.getElementById(id);
}

let poolHistories = { bch: [] };

function fmtHashrate(v) {
  if (!v || isNaN(v)) return "0 H/s";
  if (v >= 1e15) return (v / 1e15).toFixed(2) + " PH/s";
  if (v >= 1e12) return (v / 1e12).toFixed(2) + " TH/s";
  if (v >= 1e9) return (v / 1e9).toFixed(2) + " GH/s";
  if (v >= 1e6) return (v / 1e6).toFixed(2) + " MH/s";
  return v.toFixed(2) + " H/s";
}

function renderChart(seriesMap) {
  const canvas = byId("hashrateChart");
  const ctx = canvas.getContext("2d");

  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * devicePixelRatio;
  canvas.height = rect.height * devicePixelRatio;
  ctx.scale(devicePixelRatio, devicePixelRatio);

  const width = rect.width;
  const height = rect.height;

  ctx.clearRect(0, 0, width, height);

  const padding = { left: 78, right: 26, top: 38, bottom: 58 };
  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;

  const allValues = Object.values(seriesMap).flat();
  if (!allValues.length) return;

  const max = Math.max(...allValues);
  const min = Math.min(...allValues);
  const range = Math.max(1, max - min);

  ctx.font = "12px Arial";
  ctx.strokeStyle = "rgba(147,197,253,.14)";
  ctx.fillStyle = "#93c5fd";
  ctx.lineWidth = 1;

  for (let i = 0; i <= 5; i++) {
    const y = padding.top + (plotH / 5) * i;
    const value = max - (range / 5) * i;

    ctx.beginPath();
    ctx.moveTo(padding.left, y);
    ctx.lineTo(width - padding.right, y);
    ctx.stroke();

    ctx.fillText(fmtHashrate(value), 12, y + 4);
  }

  for (let i = 0; i <= 10; i++) {
    const x = padding.left + (plotW / 10) * i;
    ctx.beginPath();
    ctx.moveTo(x, padding.top);
    ctx.lineTo(x, height - padding.bottom);
    ctx.stroke();
  }

  const colors = {
    bch: "#60a5fa",
    btc: "#f7931a",
    doge: "#ffd166",
    dgb: "#39ff88"
  };

  Object.entries(seriesMap).forEach(([pool, values]) => {
    if (!values.length) return;

    const color = colors[pool] || "#60a5fa";

    const points = values.map((v, i) => {
      const x = padding.left + (values.length === 1 ? 0 : (i / (values.length - 1)) * plotW);
      const y = padding.top + (1 - ((v - min) / range)) * plotH;
      return { x, y };
    });

    const grad = ctx.createLinearGradient(0, padding.top, 0, height - padding.bottom);
    grad.addColorStop(0, color + "55");
    grad.addColorStop(1, color + "05");

    ctx.beginPath();
    ctx.moveTo(points[0].x, height - padding.bottom);
    points.forEach(p => ctx.lineTo(p.x, p.y));
    ctx.lineTo(points[points.length - 1].x, height - padding.bottom);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    ctx.beginPath();
    points.forEach((p, i) => i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y));
    ctx.strokeStyle = color;
    ctx.lineWidth = 4;
    ctx.shadowColor = color;
    ctx.shadowBlur = 12;
    ctx.stroke();
    ctx.shadowBlur = 0;

    points.forEach(p => {
      ctx.beginPath();
      ctx.arc(p.x, p.y, 3, 0, Math.PI * 2);
      ctx.fillStyle = "#0b1427";
      ctx.fill();
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.stroke();
    });

    ctx.fillStyle = color;
    ctx.font = "bold 13px Arial";
    ctx.fillText(pool.toUpperCase() + " Pool Hashrate", padding.left, 22);
  });

  const latest = allValues[allValues.length - 1];

  ctx.fillStyle = "#e5f3ff";
  ctx.font = "bold 18px Arial";
  ctx.fillText("Live Pool Hashrate", padding.left, height - 24);

  ctx.fillStyle = "#60a5fa";
  ctx.font = "bold 22px Arial";
  ctx.fillText(fmtHashrate(latest), padding.left + 190, height - 24);
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

  poolHistories.bch.push(totalHash);
  if (poolHistories.bch.length > 40) poolHistories.bch.shift();

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

  renderChart(poolHistories);

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
