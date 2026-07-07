let latestSystems = [];
let latestFound = [];

function byId(id) {
  return document.getElementById(id);
}

function safe(value, fallback = "Unknown") {
  return value === undefined || value === null || value === "" ? fallback : value;
}

function closeDrawer() {
  byId("drawer")?.classList.remove("open");
  byId("drawerBackdrop")?.classList.remove("open");
}

function assetLabel(asset, system) {
  return safe(asset?.friendlyName || asset?.name || system?.ip, "Unknown Asset");
}

function openDrawer(system) {
  const asset = system.asset || {};
  const services = latestFound.filter(item => item.ip === system.ip);

  byId("drawerContent").innerHTML = `
    <h2>${assetLabel(asset, system)}</h2>
    <p class="drawer-subtitle">${safe(asset.type || system.profile?.assetType, "Asset")}</p>

    <div class="drawer-section"><label>Asset ID</label><strong>${safe(asset.id)}</strong></div>
    <div class="drawer-section"><label>Friendly Name</label><strong>${safe(asset.friendlyName || asset.name)}</strong></div>
    <div class="drawer-section"><label>IP Address</label><strong>${safe(asset.ip || system.ip)}</strong></div>
    <div class="drawer-section"><label>Type</label><strong>${safe(asset.type)}</strong></div>
    <div class="drawer-section"><label>Purpose</label><strong>${safe(asset.purpose)}</strong></div>

    <div class="drawer-section"><label>Worker ID</label><strong>${safe(asset.workerId, "Unassigned")}</strong></div>
    <div class="drawer-section"><label>Pool ID</label><strong>${safe(asset.poolId, "Unassigned")}</strong></div>
    <div class="drawer-section"><label>Pool Host</label><strong>${safe(asset.poolHost, "Unassigned")}</strong></div>
    <div class="drawer-section"><label>Pool Group</label><strong>${safe(asset.poolGroup, "Unassigned")}</strong></div>

    <div class="drawer-section"><label>Manufacturer</label><strong>${safe(asset.manufacturer, "Not set")}</strong></div>
    <div class="drawer-section"><label>Model</label><strong>${safe(asset.model, "Not set")}</strong></div>
    <div class="drawer-section"><label>Serial Number</label><strong>${safe(asset.serialNumber, "Not set")}</strong></div>
    <div class="drawer-section"><label>MAC Address</label><strong>${safe(asset.macAddress, "Not set")}</strong></div>

    <div class="drawer-section"><label>Rack / Position</label><strong>${safe(asset.rack, "No rack")} ${safe(asset.position, "")}</strong></div>
    <div class="drawer-section"><label>Services</label><ul>${services.map(s => `<li>${s.service} <b>:${s.port}</b></li>`).join("") || "<li>No services discovered.</li>"}</ul></div>
  `;

  byId("drawer")?.classList.add("open");
  byId("drawerBackdrop")?.classList.add("open");
}

async function loadAssets() {
  try {
    const res = await fetch("/api/discovery/scan");
    const data = await res.json();

    const discovery = data.discovery || data;

    latestSystems = discovery.systems || [];
    latestFound = discovery.found || [];

    const html = latestSystems.map(system => {
      const asset = system.asset || {};

      return `
        <div class="inventory-card asset-card" data-ip="${system.ip}">
          <div class="node-status"></div>
          <h3>${assetLabel(asset, system)}</h3>
          <p>${safe(asset.type || system.profile?.assetType, "Unknown Asset")}</p>

          <div class="inventory-meta">
            <span>${safe(asset.ip || system.ip)}</span>
            <span>${safe(asset.poolGroup, "Unassigned")}</span>
            <span>Worker ${safe(asset.workerId, "—")}</span>
          </div>

          <small>${safe(asset.manufacturer || asset.model || asset.purpose, "No hardware details yet")}</small>
        </div>
      `;
    }).join("");

    byId("assetsList").innerHTML = html || "No assets discovered.";

    document.querySelectorAll(".asset-card").forEach(card => {
      card.addEventListener("click", () => {
        const system = latestSystems.find(s => s.ip === card.dataset.ip);
        if (system) openDrawer(system);
      });
    });
  } catch (err) {
    byId("assetsList").innerHTML = `<div class="empty-state"><h2>Assets failed to load.</h2><p>${err.message}</p></div>`;
  }
}

window.addEventListener("DOMContentLoaded", () => {
  byId("drawerClose")?.addEventListener("click", closeDrawer);
  byId("drawerBackdrop")?.addEventListener("click", closeDrawer);
  loadAssets();
});
