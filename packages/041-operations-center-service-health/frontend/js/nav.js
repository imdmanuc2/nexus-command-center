function renderNav(active) {
  const nav = document.getElementById("topNav");
  if (!nav) return;

  const items = [
    ["Command Center", "/"],
    ["Operations Center", "/service-operations.html"],
        ["Assets", "/assets.html"],
    ["Pools", "/pools.html"],
    ["Discovery", "/discovery.html"],
    ["Infrastructure Explorer", "/graph.html"],
    ["Service Topology", "/service-topology.html"],
    ["Analytics", "/analytics.html"],
    ["AI Assistant", "#"],
    ["Alerts", "/alerts.html"],
    ["Timeline", "/timeline.html"],
    ["Reports", "#"],
    ["Settings", "#"]
  ];

  nav.innerHTML = items.map(([label, href]) => `
    <a class="${label === active ? "active" : ""}" href="${href}">${label}</a>
  `).join("");
}
