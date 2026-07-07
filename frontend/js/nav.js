function renderNav(active) {
  const nav = document.getElementById("topNav");
  if (!nav) return;

  const items = [
    ["Command Center", "/"],
    ["Mining", "#"],
    ["Infrastructure", "/map.html"],
    ["ASIC Fleet", "/inventory.html"],
    ["Pools", "#"],
    ["Discovery", "#"],
    ["AI Assistant", "#"],
    ["Reports", "#"],
    ["Settings", "#"]
  ];

  nav.innerHTML = items.map(([label, href]) => `
    <a class="${label === active ? "active" : ""}" href="${href}">${label}</a>
  `).join("");
}
