(function () {
  "use strict";

  const ASSET_KEY = "nexus.infrastructure.assets.v1";
  const EVENT_KEY = "nexus.infrastructure.events.v1";

  function readList(key) {
    try {
      const value = JSON.parse(localStorage.getItem(key) || "[]");
      return Array.isArray(value) ? value : [];
    } catch (error) {
      console.warn(`Unable to read ${key}`, error);
      return [];
    }
  }

  function writeList(key, value) {
    localStorage.setItem(key, JSON.stringify(value));
  }

  function createId(prefix) {
    if (window.crypto?.randomUUID) {
      return `${prefix}-${window.crypto.randomUUID()}`;
    }

    return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function normalizeService(service) {
    return {
      service: service?.service || service?.name || "Unknown Service",
      port: Number(service?.port || 0),
      protocol: service?.protocol || "tcp",
      status: service?.status || "open"
    };
  }

  function getAssets() {
    return readList(ASSET_KEY);
  }

  function getEvents() {
    return readList(EVENT_KEY);
  }

  function findAssetByIp(ip) {
    return getAssets().find(asset => String(asset.ip) === String(ip)) || null;
  }

  function isManaged(ip) {
    return Boolean(findAssetByIp(ip));
  }

  function addEvent({
    type,
    message,
    severity = "info",
    assetName = "",
    assetIp = "",
    details = {}
  }) {
    const events = getEvents();

    const item = {
      id: createId("event"),
      time: new Date().toISOString(),
      type: type || "INFRASTRUCTURE_EVENT",
      message: message || "Infrastructure event",
      severity,
      assetName,
      assetIp,
      details
    };

    events.push(item);

    if (events.length > 500) {
      events.splice(0, events.length - 500);
    }

    writeList(EVENT_KEY, events);

    window.dispatchEvent(
      new CustomEvent("nexus:infrastructure-event", {
        detail: item
      })
    );

    return item;
  }

  function addOrUpdateAsset(system, foundServices = []) {
    if (!system?.ip) {
      throw new Error("Cannot add infrastructure asset without an IP address.");
    }

    const assets = getAssets();
    const existingIndex = assets.findIndex(
      asset => String(asset.ip) === String(system.ip)
    );

    const services = foundServices
      .filter(item => String(item.ip) === String(system.ip))
      .map(normalizeService);

    const now = new Date().toISOString();

    const existing = existingIndex >= 0 ? assets[existingIndex] : null;

    const asset = {
      id: existing?.id || createId("asset"),
      name:
        system.asset?.name ||
        system.profile?.hostname ||
        existing?.name ||
        system.ip,
      ip: system.ip,
      hostname:
        system.profile?.hostname ||
        existing?.hostname ||
        "",
      primaryRole:
        system.primaryRole ||
        existing?.primaryRole ||
        "Unknown",
      assetType:
        system.profile?.assetType ||
        existing?.assetType ||
        "server",
      purpose:
        system.asset?.purpose ||
        existing?.purpose ||
        "",
      status: "managed",
      health: system.health || existing?.health || {},
      roles: system.roles || existing?.roles || [],
      fingerprints:
        system.fingerprints ||
        existing?.fingerprints ||
        [],
      services,
      ports: services
        .map(service => service.port)
        .filter(port => Number.isFinite(port) && port > 0),
      addedAt: existing?.addedAt || now,
      updatedAt: now
    };

    if (existingIndex >= 0) {
      assets[existingIndex] = asset;
    } else {
      assets.push(asset);
    }

    writeList(ASSET_KEY, assets);

    addEvent({
      type:
        existingIndex >= 0
          ? "INFRASTRUCTURE_ASSET_UPDATED"
          : "INFRASTRUCTURE_ASSET_ADDED",
      message:
        existingIndex >= 0
          ? `${asset.name} was updated in Infrastructure Manager.`
          : `${asset.name} was added to Infrastructure Manager.`,
      severity: "success",
      assetName: asset.name,
      assetIp: asset.ip
    });

    window.dispatchEvent(
      new CustomEvent("nexus:infrastructure-assets-changed", {
        detail: {
          asset,
          action: existingIndex >= 0 ? "updated" : "added"
        }
      })
    );

    return asset;
  }

  function requestAction(assetOrSystem, action) {
    const name =
      assetOrSystem?.name ||
      assetOrSystem?.asset?.name ||
      assetOrSystem?.profile?.hostname ||
      assetOrSystem?.ip ||
      "Infrastructure asset";

    const ip = assetOrSystem?.ip || "";

    return addEvent({
      type: "INFRASTRUCTURE_ACTION_REQUESTED",
      message: `${action} requested for ${name}.`,
      severity: "info",
      assetName: name,
      assetIp: ip,
      details: {
        action
      }
    });
  }

  window.NexusInfrastructure = {
    getAssets,
    getEvents,
    findAssetByIp,
    isManaged,
    addEvent,
    addOrUpdateAsset,
    requestAction
  };
})();
