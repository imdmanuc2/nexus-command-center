function renderNav(active) {
  const nav = document.getElementById("topNav");
  if (!nav) return;

  const items = [
    ["Command Center", "/"],
    ["Mining", "#"],
    ["Infrastructure", "/map.html"],
    ["Assets", "/assets.html"],
    ["Pools", "/pools.html"],
    ["Discovery", "/discovery.html"],
    ["AI Assistant", "#"],
    ["Reports", "#"],
    ["Settings", "#"]
  ];

  nav.innerHTML = items.map(([label, href]) => `
    <a class="${label === active ? "active" : ""}" href="${href}">${label}</a>
  `).join("");
}
