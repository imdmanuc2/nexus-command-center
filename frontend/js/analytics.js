let poolHistory = [];
let minerHistory = {};
let difficultyHistory = [];
let maxPoints = 45;

function byId(id) { return document.getElementById(id); }

function fmtHashrate(n) {
  n = Number(n || 0);
  if (n >= 1e12) return `${(n / 1e12).toFixed(2)} TH/s`;
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)} GH/s`;
  return `${n.toFixed(0)} H/s`;
}

function fmtCompact(n, unit = "") {
  n = Number(n || 0);

  if (unit === "hashrate") {
    if (n >= 1e12) return `${(n / 1e12).toFixed(1)}`;
    if (n >= 1e9) return `${(n / 1e9).toFixed(1)}`;
    return `${n.toFixed(0)}`;
  }

  if (n >= 1e12) return `${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(2)}K`;
  return `${n.toFixed(0)}`;
}

function drawLineChart(canvas, series, yLabel = "", unit = "") {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const width = canvas.offsetWidth;
  const height = canvas.offsetHeight;

  canvas.width = width * dpr;
  canvas.height = height * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);

  const pad = 48;
  const allValues = series.flatMap(s => s.values);
  const max = Math.max(...allValues, 1);
  const min = Math.min(...allValues, 0);

  ctx.strokeStyle = "rgba(96,165,250,.16)";
  ctx.fillStyle = "#93c5fd";
  ctx.font = "11px system-ui";

  for (let i = 0; i < 6; i++) {
    const y = pad + i * ((height - pad * 2) / 5);
    const value = max - ((max - min) * i / 5);

    ctx.beginPath();
    ctx.moveTo(pad, y);
    ctx.lineTo(width - pad, y);
    ctx.stroke();
    ctx.fillText(fmtCompact(value, unit), 8, y + 4);
  }

  if (yLabel) {
    ctx.fillStyle = "#93c5fd";
    ctx.font = "900 11px system-ui";
    ctx.fillText(yLabel, pad, 34);
  }

  series.forEach((s, index) => {
    const color = index === 0 ? "#60a5fa" : "#39ff88";
    ctx.lineWidth = 3;
    ctx.strokeStyle = color;
    ctx.shadowBlur = 14;
    ctx.shadowColor = color;
    ctx.beginPath();

    s.values.forEach((v, i) => {
      const x = pad + i * ((width - pad * 2) / Math.max(1, s.values.length - 1));
      const y = height - pad - ((v - min) / Math.max(1, max - min)) * (height - pad * 2);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });

    ctx.stroke();
    ctx.shadowBlur = 0;

    ctx.fillStyle = color;
    ctx.fillText(s.label, pad + 70 + index * 150, 24);
  });
}

function drawBarChart(canvas, items, yLabel = "") {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const width = canvas.offsetWidth;
  const height = canvas.offsetHeight;

  canvas.width = width * dpr;
  canvas.height = height * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);

  const pad = 46;
  const max = Math.max(...items.map(i => i.value), 1);

  ctx.fillStyle = "#93c5fd";
  ctx.font = "11px system-ui";
  ctx.fillText(yLabel, 6, 16);

  items.forEach((item, i) => {
    const slot = (width - pad * 2) / items.length;
    const barW = Math.max(28, slot - 24);
    const x = pad + i * slot + 12;
    const barH = (item.value / max) * (height - pad * 2);
    const y = height - pad - barH;

    ctx.fillStyle = "#39ff88";
    ctx.shadowBlur = 18;
    ctx.shadowColor = "#39ff88";
    ctx.fillRect(x, y, barW, barH);

    ctx.shadowBlur = 0;
    ctx.fillStyle = "#93c5fd";
    ctx.textAlign = "center";
    ctx.fillText(item.label, x + barW / 2, height - 14);
    ctx.fillText(item.display || String(item.value), x + barW / 2, y - 8);
  });

  ctx.textAlign = "left";
}

function drawDonut(canvas, items) {
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const width = canvas.offsetWidth;
  const height = canvas.offsetHeight;

  canvas.width = width * dpr;
  canvas.height = height * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);

  const cx = width / 2;
  const cy = height / 2;
  const r = Math.min(width, height) / 3;
  const total = items.reduce((s, i) => s + i.value, 0) || 1;
  const colors = ["#39ff88", "#60a5fa", "#a78bfa", "#facc15"];
  let start = -Math.PI / 2;

  items.forEach((item, idx) => {
    const slice = (item.value / total) * Math.PI * 2;
    ctx.beginPath();
    ctx.strokeStyle = colors[idx % colors.length];
    ctx.lineWidth = 30;
    ctx.shadowBlur = 18;
    ctx.shadowColor = ctx.strokeStyle;
    ctx.arc(cx, cy, r, start, start + slice);
    ctx.stroke();
    start += slice;
  });

  ctx.shadowBlur = 0;
  ctx.fillStyle = "#e5f3ff";
  ctx.font = "900 22px system-ui";
  ctx.textAlign = "center";
  ctx.fillText(fmtHashrate(total), cx, cy + 6);
  ctx.textAlign = "left";
}

function expectedYears(poolHashrate, networkHashrate) {
  if (!poolHashrate || !networkHashrate) return null;
  return (10 / (poolHashrate / networkHashrate)) / 60 / 24 / 365;
}

function fmtYears(y) {
  if (!y) return "—";
  if (y < 1) return `${(y * 365).toFixed(1)} days`;
  return `${y.toFixed(1)} yrs`;
}

async function loadAnalytics() {
  const [summaryRes, workersRes] = await Promise.all([
    fetch("/api/mining/summary"),
    fetch("/api/mining/workers")
  ]);

  const summary = await summaryRes.json();
  const workersPayload = await workersRes.json();
  const workers = workersPayload.workers || [];
  const totalHashrate = workers.reduce((s, w) => s + Number(w.hashrate || 0), 0);

  const poolObj = summary.pool?.pool || summary.pool || {};
  const networkStats = poolObj.networkStats || summary.pool?.networkStats || {};
  const networkHashrate = Number(networkStats.networkHashrate || 0);
  const networkDifficulty = Number(networkStats.networkDifficulty || 0);

  poolHistory.push(totalHashrate);
  poolHistory = poolHistory.slice(-maxPoints);

  difficultyHistory.push(networkDifficulty);
  difficultyHistory = difficultyHistory.slice(-maxPoints);

  workers.forEach(w => {
    const name = w.displayName || w.assetName || w.workerName || w.name;
    minerHistory[name] ||= [];
    minerHistory[name].push(Number(w.hashrate || 0));
    minerHistory[name] = minerHistory[name].slice(-maxPoints);
  });

  drawLineChart(byId("poolHashrateChart"), [{ label: "BCH pool", values: poolHistory }], "TH/s", "hashrate");
  drawLineChart(byId("minerHashrateChart"), Object.entries(minerHistory).map(([label, values]) => ({ label, values })), "TH/s", "hashrate");
  drawDonut(byId("hashrateSplitChart"), workers.map(w => ({ label: w.displayName || w.workerName, value: Number(w.hashrate || 0) })));
  drawBarChart(byId("shareRateChart"), workers.map(w => ({
    label: w.workerName || w.name,
    value: Number(w.sharesPerSecond || 0),
    display: Number(w.sharesPerSecond || 0).toFixed(3)
  })), "Shares/sec");
  drawLineChart(byId("networkDifficultyChart"), [{ label: "BCH difficulty", values: difficultyHistory }], "Difficulty");
  drawBarChart(byId("coinHashrateChart"), [
    { label: "BCH", value: totalHashrate, display: fmtHashrate(totalHashrate) },
    { label: "BTC", value: 0, display: "Soon" },
    { label: "DOGE", value: 0, display: "Later" },
    { label: "DGB", value: 0, display: "Later" }
  ], "Hashrate");

  const years = expectedYears(totalHashrate, networkHashrate);
  byId("fleetPulse").innerHTML = `
    <div class="pulse-big">${fmtHashrate(totalHashrate)}</div>
    <div class="pulse-sub">${workers.length} live miner(s)</div>
    <div class="pulse-meter"><span style="width:${Math.min(100, workers.length * 45)}%"></span></div>
  `;

  byId("soloOdds").innerHTML = `
    <div class="pulse-big">Active</div>
    <div class="pulse-sub">Solo mining status</div>
    <div class="odds-grid">
      <span>Pool</span><b>${summary.poolId || "bch"}</b>
      <span>Workers</span><b>${workers.length}</b>
      <span>Hashrate</span><b>${fmtHashrate(totalHashrate)}</b>
      <span>Expected time</span><b>${fmtYears(years)}</b>
    </div>
  `;

  byId("lotteryMeter").innerHTML = `
    <div class="lottery-coin">
      <h3>BCH Solo Odds <b>Live</b></h3>
      <div class="lottery-big">${fmtHashrate(totalHashrate)}</div>
      <p>Expected time: <strong class="lottery-warn">${fmtYears(years)}</strong></p>
      <p>You are rolling the BCH block lottery right now.</p>
    </div>
    <div class="lottery-coin">
      <h3>BTC Solo Odds <b>Coming Soon</b></h3>
      <div class="lottery-big">—</div>
      <p>BTC odds activate when the BTC pool is configured.</p>
    </div>
    <div class="lottery-coin">
      <h3>DOGE / DGB Odds <b>Later</b></h3>
      <div class="lottery-big">—</div>
      <p>More coins will appear here automatically.</p>
    </div>
  `;

  const onlineWorkers = workers.filter(w => Number(w.hashrate || 0) > 0).length;
  const avgHashrate = workers.length ? totalHashrate / workers.length : 0;
  const best = workers.slice().sort((a,b) => Number(b.hashrate||0)-Number(a.hashrate||0))[0];
  const weakest = workers.slice().sort((a,b) => Number(a.hashrate||0)-Number(b.hashrate||0))[0];
  const health = workers.length ? Math.round((onlineWorkers / workers.length) * 100) : 0;

  byId("fleetHealthScore").innerHTML = `
    <div class="health-row">
      <div class="health-stat"><span>Fleet Health</span><strong>${health}%</strong></div>
      <div class="health-stat"><span>Online Workers</span><strong>${onlineWorkers}/${workers.length}</strong></div>
      <div class="health-stat"><span>Best Miner</span><strong>${best?.displayName || best?.workerName || "—"}</strong></div>
      <div class="health-stat"><span>Weakest Miner</span><strong>${weakest?.displayName || weakest?.workerName || "—"}</strong></div>
      <div class="health-stat"><span>Avg Hashrate</span><strong>${fmtHashrate(avgHashrate)}</strong></div>
      <div class="health-stat"><span>Shares/sec</span><strong>${workers.reduce((s,w)=>s+Number(w.sharesPerSecond||0),0).toFixed(3)}</strong></div>
    </div>
    <div class="health-bar"><span style="width:${health}%"></span></div>
  `;
}

function toggleTvMode() {
  document.body.classList.toggle("analytics-tv");
}

window.addEventListener("DOMContentLoaded", () => {
  renderNav("Analytics");
  byId("analyticsTvMode")?.addEventListener("click", toggleTvMode);
  byId("analyticsTvExit")?.addEventListener("click", toggleTvMode);
  byId("refreshAnalytics")?.addEventListener("click", loadAnalytics);
  loadAnalytics();
  setInterval(loadAnalytics, 2500);
});



function widgetTitle(card) {
  return card?.querySelector(".widget-toggle")?.textContent?.trim() || card?.dataset.widget || "Widget";
}

function refreshWidgetDock() {
  const dock = byId("widgetDock");
  if (!dock) return;

  const cards = [...document.querySelectorAll(".analytics-card.widget")];

  dock.innerHTML = cards.map(card => `
    <button class="dock-pill ${card.classList.contains("hidden-widget") ? "" : "active"}"
      data-widget="${card.dataset.widget}">
      ${widgetTitle(card)}
    </button>
  `).join("");

  dock.querySelectorAll(".dock-pill").forEach(btn => {
    btn.addEventListener("click", () => {
      const card = document.querySelector(`.analytics-card.widget[data-widget="${btn.dataset.widget}"]`);
      card?.classList.toggle("hidden-widget");
      saveWidgetLayout();
      refreshWidgetDock();
    });
  });
}

function saveWidgetLayout() {
  const cards = [...document.querySelectorAll(".analytics-card.widget")];
  const layout = cards.map(card => ({
    id: card.dataset.widget,
    hidden: card.classList.contains("hidden-widget")
  }));

  localStorage.setItem("nexus.analytics.widgets", JSON.stringify(layout));
}

function loadWidgetLayout() {
  try {
    const layout = JSON.parse(localStorage.getItem("nexus.analytics.widgets") || "[]");
    const grid = document.querySelector(".analytics-grid");
    if (!grid || !layout.length) return;

    layout.forEach(item => {
      const card = document.querySelector(`.analytics-card.widget[data-widget="${item.id}"]`);
      if (!card) return;

      if (item.hidden) card.classList.add("hidden-widget");
      else card.classList.remove("hidden-widget");

      grid.appendChild(card);
    });
  } catch {}
}

function setupWidgets() {
  loadWidgetLayout();

  document.querySelectorAll(".analytics-card.widget").forEach(card => {
    card.setAttribute("draggable", "true");

    const btn = card.querySelector(".widget-toggle");
    if (btn) {
      btn.addEventListener("click", () => {
        card.classList.toggle("hidden-widget");
        saveWidgetLayout();
        refreshWidgetDock();
      });
    }

    if (!card.querySelector(".analytics-info-dot")) {
      const dot = document.createElement("span");
      dot.className = "analytics-info-dot";
      dot.textContent = "i";
      dot.setAttribute("data-tip", card.dataset.tip || "Analytics widget.");
      card.appendChild(dot);
    }
  });

  let dragged = null;

  document.querySelectorAll(".analytics-card.widget").forEach(card => {
    card.addEventListener("dragstart", e => {
      dragged = card;
      card.classList.add("dragging-widget");
      e.dataTransfer.effectAllowed = "move";
    });

    card.addEventListener("dragend", () => {
      dragged = null;
      card.classList.remove("dragging-widget");
      saveWidgetLayout();
    });

    card.addEventListener("dragover", e => {
      e.preventDefault();
      if (!dragged || dragged === card) return;

      const grid = document.querySelector(".analytics-grid");
      const cards = [...grid.querySelectorAll(".analytics-card.widget:not(.hidden-widget)")];
      const draggedIndex = cards.indexOf(dragged);
      const targetIndex = cards.indexOf(card);

      if (draggedIndex < targetIndex) {
        card.after(dragged);
      } else {
        card.before(dragged);
      }
    });
  });

  byId("showAllWidgets")?.addEventListener("click", () => {
    document.querySelectorAll(".analytics-card.widget").forEach(card => {
      card.classList.remove("hidden-widget");
    });
    saveWidgetLayout();
    refreshWidgetDock();
  });

  refreshWidgetDock();
}

window.addEventListener("DOMContentLoaded", setupWidgets);
