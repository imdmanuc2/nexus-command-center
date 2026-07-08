function missionFormatHashrate(value) {
  value = Number(value || 0);
  if (value >= 1e12) return `${(value / 1e12).toFixed(2)} TH/s`;
  if (value >= 1e9) return `${(value / 1e9).toFixed(2)} GH/s`;
  return `${value.toFixed(0)} H/s`;
}

function ensureMissionBar() {
  if (document.getElementById("missionBar")) return;

  const bar = document.createElement("section");
  bar.id = "missionBar";
  bar.className = "mission-bar";
  bar.innerHTML = "Loading mission status...";

  const nav = document.getElementById("topNav");
  if (nav && nav.parentNode) nav.insertAdjacentElement("afterend", bar);
  else document.body.prepend(bar);
}

async function loadMissionStatus() {
  ensureMissionBar();

  try {
    const res = await fetch("/api/mission/status");
    if (!res.ok) return;

    const s = await res.json();
    const critical = s.events?.critical || 0;
    const warnings = s.events?.warnings || 0;

    const bar = document.getElementById("missionBar");
    bar.classList.toggle("critical", critical > 0);
    bar.classList.toggle("warning", critical === 0 && warnings > 0);

    bar.innerHTML = `
      <a href="/analytics.html">🟢 ${missionFormatHashrate(s.miners?.hashrate)} Fleet</a>
      <a href="/graph.html">🟢 ${s.miners?.online}/${s.miners?.total} ASICs Online</a>
      <a href="/pools.html">🟢 MiningCore ${String(s.services?.miningcore || "unknown").toUpperCase()}</a>
      <a href="/discovery.html">🟢 ${s.infrastructure?.systems} Systems</a>
      <a href="/analytics.html">🟢 Stratum ${String(s.services?.stratum || "unknown").toUpperCase()}</a>
      <a href="/analytics.html">⚠ ${warnings} Warnings</a>
      <a href="/analytics.html">🚨 ${critical} Critical</a>
    `;
  } catch {}
}

window.addEventListener("DOMContentLoaded", () => {
  loadMissionStatus();
  setInterval(loadMissionStatus, 3000);
});
