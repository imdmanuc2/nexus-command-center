let timelineFilter = "all";
let timelineEvents = [];

function byId(id) {
  return document.getElementById(id);
}

function fmtTimelineTime(value) {
  try {
    return new Date(value).toLocaleString("en-US", {
      month: "2-digit",
      day: "2-digit",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
      second: "2-digit",
      hour12: true
    });
  } catch {
    return value || "";
  }
}

function iconFor(e) {
  if (e.severity === "warning") return "⚠";
  if (e.severity === "critical") return "🚨";
  if (e.severity === "success") return "✓";
  return "ℹ";
}

function renderTimeline() {
  const list = byId("timelineList");

  const events = timelineEvents
    .slice()
    .reverse()
    .filter(e => timelineFilter === "all" || e.severity === timelineFilter);

  list.innerHTML = events.map(e => `
    <article class="timeline-event ${e.severity || "info"}">
      <div class="timeline-dot">${iconFor(e)}</div>
      <div>
        <h3>${e.message || "Event"}</h3>
        <p>${fmtTimelineTime(e.time)} • ${e.type || "event"}</p>
        <small>
          ${e.assetName ? `Miner: ${e.assetName}` : ""}
          ${e.workerId ? ` · Worker: ${e.workerId}` : ""}
          ${e.poolGroup || e.poolId ? ` · Pool: ${e.poolGroup || e.poolId}` : ""}
        </small>
      </div>
    </article>
  `).join("") || `<div class="empty-state">No timeline events.</div>`;
}

async function loadTimeline() {
  const res = await fetch("/api/events/live");
  if (!res.ok) return;

  timelineEvents = await res.json();
  renderTimeline();
}

window.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".timeline-filter").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".timeline-filter").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      timelineFilter = btn.dataset.filter;
      renderTimeline();
    });
  });

  byId("refreshTimeline")?.addEventListener("click", loadTimeline);
  loadTimeline();
  setInterval(loadTimeline, 3000);
});
