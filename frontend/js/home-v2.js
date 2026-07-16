"use strict";

const HOME_V2_REFRESH_MS = 10000;
const HOME_V2_MAX_HISTORY = 40;

const homeV2State = {
  fleet: null,
  smcHealth: null,
  operationsEvents: null,
  priorityExpanded: false,
  poolHistories: {},
  poolLabels: {},
  poolColors: {},
  refreshTimer: null,
  loading: false,
};

const HOME_V2_COLORS = [
  "#60a5fa",
  "#39ff88",
  "#f7931a",
  "#facc15",
  "#a78bfa",
  "#22d3ee",
  "#fb7185",
  "#34d399",
  "#f472b6",
  "#c084fc",
];


function byId(id) {
  return document.getElementById(id);
}


function numberValue(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}


function integerValue(value, fallback = 0) {
  return Math.round(numberValue(value, fallback));
}


function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}


function fmtHashrate(value) {
  const number = numberValue(value);

  if (number >= 1e18) {
    return `${(number / 1e18).toFixed(2)} EH/s`;
  }

  if (number >= 1e15) {
    return `${(number / 1e15).toFixed(2)} PH/s`;
  }

  if (number >= 1e12) {
    return `${(number / 1e12).toFixed(2)} TH/s`;
  }

  if (number >= 1e9) {
    return `${(number / 1e9).toFixed(2)} GH/s`;
  }

  if (number >= 1e6) {
    return `${(number / 1e6).toFixed(2)} MH/s`;
  }

  if (number >= 1e3) {
    return `${(number / 1e3).toFixed(2)} KH/s`;
  }

  return `${number.toFixed(2)} H/s`;
}


function fmtNumber(value) {
  return new Intl.NumberFormat().format(
    integerValue(value)
  );
}


function fmtPercent(value) {
  const number = numberValue(value);

  return `${number.toFixed(
    number % 1 === 0 ? 0 : 2
  )}%`;
}


function fmtBytes(value) {
  const number = numberValue(value);

  if (!number) {
    return "—";
  }

  const units = [
    "B",
    "KB",
    "MB",
    "GB",
    "TB",
    "PB",
  ];

  let current = number;
  let index = 0;

  while (
    current >= 1024
    && index < units.length - 1
  ) {
    current /= 1024;
    index += 1;
  }

  return `${current.toFixed(
    index >= 3 ? 1 : 2
  )} ${units[index]}`;
}


function fmtTime(dateValue) {
  const date = dateValue
    ? new Date(dateValue)
    : new Date();

  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }

  return date.toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  });
}


function relativeTime(dateValue) {
  const date = new Date(dateValue);
  const difference = Date.now() - date.getTime();

  if (Number.isNaN(difference)) {
    return "Updated recently";
  }

  const seconds = Math.max(
    0,
    Math.round(difference / 1000)
  );

  if (seconds < 5) {
    return "Updated just now";
  }

  if (seconds < 60) {
    return `Updated ${seconds}s ago`;
  }

  const minutes = Math.round(seconds / 60);

  return `Updated ${minutes}m ago`;
}


function statusLabel(status) {
  const normalized = String(
    status || "unknown"
  ).toLowerCase();

  const labels = {
    mining: "Mining",
    "node-online": "Node Online",
    online: "Online",
    active: "Active",
    warning: "Warning",
    critical: "Critical",
    offline: "Offline",
    idle: "Idle",
    partial: "Partial",
  };

  return labels[normalized]
    || normalized.replaceAll("-", " ");
}


function coinDisplayName(coin) {
  if (coin?.name && coin.name !== coin.symbol) {
    return coin.name;
  }

  const names = {
    BTC: "Bitcoin",
    BCH: "Bitcoin Cash",
    LTC: "Litecoin",
    DOGE: "Dogecoin",
    DGB: "DigiByte",
    ZEC: "Zcash",
    KAS: "Kaspa",
  };

  return names[coin?.symbol]
    || coin?.symbol
    || "Unknown Blockchain";
}


function poolCoinSymbol(pool) {
  if (
    pool?.coin
    && typeof pool.coin === "object"
  ) {
    return pool.coin.symbol
      || pool.coin.type
      || "POOL";
  }

  return pool?.coin || "POOL";
}


function stableColor(id, index = 0) {
  if (homeV2State.poolColors[id]) {
    return homeV2State.poolColors[id];
  }

  let hash = 0;

  for (const character of String(id)) {
    hash = (
      (hash << 5)
      - hash
      + character.charCodeAt(0)
    ) | 0;
  }

  const colorIndex = Math.abs(
    hash + index
  ) % HOME_V2_COLORS.length;

  const color = HOME_V2_COLORS[colorIndex];

  homeV2State.poolColors[id] = color;

  return color;
}


function setText(id, value) {
  const element = byId(id);

  if (element) {
    element.textContent = value;
  }
}


function renderStatus(fleet) {
  const summary = fleet.summary || {};
  const status = String(
    fleet.status || "offline"
  ).toLowerCase();

  const badge = byId("fleetStatusBadge");

  badge.textContent = statusLabel(status).toUpperCase();
  badge.className = "live-badge";

  if (status === "critical") {
    badge.classList.add("critical");
  } else if (
    status === "warning"
    || status === "partial"
  ) {
    badge.classList.add("warning");
  }

  setText(
    "lastUpdated",
    relativeTime(fleet.generatedAt)
  );

  const chips = [
    {
      label: "FLEET",
      state: status,
    },
    {
      label: `${integerValue(
        summary.activePoolCount
      )} POOLS`,
      state: integerValue(
        summary.activePoolCount
      ) > 0
        ? "online"
        : "warning",
    },
    {
      label: `${integerValue(
        summary.onlineMinerCount
      )} MINERS`,
      state: integerValue(
        summary.onlineMinerCount
      ) > 0
        ? "online"
        : "warning",
    },
    {
      label: `${integerValue(
        summary.onlineNodeCount
      )} NODES`,
      state: integerValue(
        summary.onlineNodeCount
      ) > 0
        ? "online"
        : "warning",
    },
    {
      label: "API",
      state: "online",
    },
  ];

  byId("fleetStatusStrip").innerHTML = chips
    .map((chip) => {
      const state = chip.state === "online"
        ? ""
        : escapeHtml(chip.state);

      return `
        <div class="status-chip ${state}">
          <span></span>
          ${escapeHtml(chip.label)}
        </div>
      `;
    })
    .join("");
}


function renderFleetSummary(fleet) {
  const summary = fleet.summary || {};
  const health = Math.max(
    0,
    Math.min(
      100,
      numberValue(summary.fleetHealth)
    )
  );

  setText(
    "fleetHashrate",
    fmtHashrate(summary.fleetHashrate)
  );

  setText(
    "fleetHashrateSubtitle",
    [
      `${fmtNumber(
        summary.onlineMinerCount
      )} online miners`,
      `${fmtNumber(
        summary.activePoolCount
      )} active pools`,
      `${fmtNumber(
        summary.coinCount
      )} blockchain operations`,
    ].join(" • ")
  );

  byId(
    "fleetHashrateBar"
  ).firstElementChild.style.width = `${health}%`;

  setText(
    "fleetHealth",
    fmtPercent(health)
  );

  setText(
    "fleetHealthRingText",
    fmtPercent(health)
  );

  let healthLabel = "Healthy";

  if (health < 60) {
    healthLabel = "Critical";
  } else if (health < 90) {
    healthLabel = "Degraded";
  }

  setText(
    "fleetHealthLabel",
    healthLabel
  );

  const ring = byId("fleetHealthRing");
  const circumference = 2 * Math.PI * 50;

  ring.style.strokeDasharray = `${circumference}`;
  ring.style.strokeDashoffset = `${
    circumference
    - (health / 100) * circumference
  }`;

  if (health < 60) {
    ring.style.stroke = "#fb7185";
  } else if (health < 90) {
    ring.style.stroke = "#facc15";
  } else {
    ring.style.stroke = "#39ff88";
  }

  setText(
    "metricCoins",
    fmtNumber(summary.coinCount)
  );

  setText(
    "metricPools",
    fmtNumber(summary.activePoolCount)
  );

  setText(
    "metricMiners",
    fmtNumber(summary.onlineMinerCount)
  );

  setText(
    "metricNodes",
    `${fmtNumber(
      summary.onlineNodeCount
    )}/${fmtNumber(summary.nodeCount)}`
  );

  setText(
    "metricWarnings",
    fmtNumber(summary.warningCount)
  );

  setText(
    "metricCritical",
    fmtNumber(summary.criticalCount)
  );

  const critical = byId("metricCritical");

  critical.classList.toggle(
    "green",
    integerValue(summary.criticalCount) === 0
  );

  critical.classList.toggle(
    "critical",
    integerValue(summary.criticalCount) > 0
  );
}


function renderCoins(coins) {
  const container = byId("coinOperations");

  setText(
    "coinOperationCount",
    `${coins.length} operation${
      coins.length === 1 ? "" : "s"
    }`
  );

  if (!coins.length) {
    container.innerHTML = `
      <div class="home-v2-empty">
        No blockchain operations discovered.
      </div>
    `;
    return;
  }

  container.innerHTML = coins
    .map((coin) => {
      const status = String(
        coin.status || "offline"
      ).toLowerCase();

      const hashrate = numberValue(
        coin.hashrate
      );

      const primaryValue = hashrate > 0
        ? fmtHashrate(hashrate)
        : (
          integerValue(coin.onlineNodeCount) > 0
            ? "Node Ready"
            : "No Telemetry"
        );

      const primaryLabel = hashrate > 0
        ? "Combined active pool hashrate"
        : (
          integerValue(coin.onlineNodeCount) > 0
            ? "Ready for mining pool"
            : "No active mining or node telemetry"
        );

      return `
        <article
          class="home-v2-coin-card ${escapeHtml(status)}"
          data-symbol="${escapeHtml(
            coin.symbol || "?"
          )}"
        >
          <div class="home-v2-coin-header">
            <div>
              <div class="home-v2-coin-symbol">
                ${escapeHtml(coin.symbol)}
              </div>

              <div class="home-v2-coin-name">
                ${escapeHtml(
                  coinDisplayName(coin)
                )}
              </div>
            </div>

            <span class="home-v2-state-badge ${escapeHtml(status)}">
              ${escapeHtml(
                statusLabel(status)
              )}
            </span>
          </div>

          <div class="home-v2-coin-hashrate">
            ${escapeHtml(primaryValue)}

            <small>
              ${escapeHtml(primaryLabel)}
            </small>
          </div>

          <div class="home-v2-coin-stats">
            <div class="home-v2-mini-stat">
              <strong>
                ${fmtNumber(
                  coin.activePoolCount
                )}
              </strong>
              <span>Active Pools</span>
            </div>

            <div class="home-v2-mini-stat">
              <strong>
                ${fmtNumber(
                  coin.workerCount
                )}
              </strong>
              <span>Miners</span>
            </div>

            <div class="home-v2-mini-stat">
              <strong>
                ${fmtNumber(
                  coin.onlineNodeCount
                )}/${fmtNumber(
                  coin.nodeCount
                )}
              </strong>
              <span>Nodes</span>
            </div>
          </div>
        </article>
      `;
    })
    .join("");
}


function renderPools(pools) {
  const container = byId("activePools");
  const maxHashrate = Math.max(
    ...pools.map(
      (pool) => numberValue(pool.hashrate)
    ),
    1
  );

  setText(
    "activePoolCount",
    `${pools.length} active`
  );

  if (!pools.length) {
    container.innerHTML = `
      <div class="home-v2-empty">
        No active mining pools.
      </div>
    `;
    return;
  }

  container.innerHTML = pools
    .map((pool) => {
      const hashrate = numberValue(
        pool.hashrate
      );

      const width = Math.max(
        4,
        (hashrate / maxHashrate) * 100
      );

      const symbol = poolCoinSymbol(pool);

      const stratumPorts = Array.isArray(
        pool.stratumPorts
      )
        ? pool.stratumPorts.join(", ")
        : "—";

      return `
        <article class="home-v2-pool-card">
          <div class="home-v2-pool-card-header">
            <div>
              <h3>
                ${escapeHtml(
                  pool.name
                  || `${symbol} Pool`
                )}
              </h3>

              <div class="home-v2-pool-endpoint">
                ${escapeHtml(
                  pool.host || "Unknown host"
                )}:${escapeHtml(
                  pool.apiPort || "—"
                )}
              </div>
            </div>

            <span class="home-v2-state-badge active">
              ${escapeHtml(
                statusLabel(
                  pool.status || "active"
                )
              )}
            </span>
          </div>

          <div class="home-v2-pool-hashrate">
            ${escapeHtml(
              fmtHashrate(hashrate)
            )}
          </div>

          <div class="home-v2-pool-stats">
            <div class="home-v2-mini-stat">
              <strong>
                ${fmtNumber(pool.workerCount)}
              </strong>
              <span>Miners</span>
            </div>

            <div class="home-v2-mini-stat">
              <strong>
                ${escapeHtml(
                  numberValue(
                    pool.sharesPerSecond
                  ).toFixed(3)
                )}
              </strong>
              <span>Shares/sec</span>
            </div>

            <div class="home-v2-mini-stat">
              <strong>
                ${escapeHtml(stratumPorts)}
              </strong>
              <span>Stratum</span>
            </div>
          </div>

          <div class="home-v2-pool-progress">
            <div style="width:${width}%"></div>
          </div>
        </article>
      `;
    })
    .join("");
}


function updatePoolHistories(pools) {
  const activeIds = new Set();

  pools.forEach((pool, index) => {
    const id = String(
      pool.id
      || `${pool.host}-${pool.nativePoolId}`
    );

    activeIds.add(id);

    if (!homeV2State.poolHistories[id]) {
      homeV2State.poolHistories[id] = [];
    }

    homeV2State.poolHistories[id].push(
      numberValue(pool.hashrate)
    );

    if (
      homeV2State.poolHistories[id].length
      > HOME_V2_MAX_HISTORY
    ) {
      homeV2State.poolHistories[id].shift();
    }

    homeV2State.poolLabels[id] = (
      pool.name
      || `${poolCoinSymbol(pool)} Pool`
    );

    stableColor(id, index);
  });

  Object.keys(
    homeV2State.poolHistories
  ).forEach((id) => {
    if (!activeIds.has(id)) {
      delete homeV2State.poolHistories[id];
      delete homeV2State.poolLabels[id];
      delete homeV2State.poolColors[id];
    }
  });
}


function renderChartLegend() {
  const legend = byId("poolChartLegend");

  legend.innerHTML = Object.keys(
    homeV2State.poolHistories
  )
    .map((id) => {
      const color = homeV2State.poolColors[id];
      const label = homeV2State.poolLabels[id];

      return `
        <span class="home-v2-chart-legend-item">
          <span
            class="home-v2-chart-legend-dot"
            style="
              background:${color};
              color:${color};
            "
          ></span>

          ${escapeHtml(label)}
        </span>
      `;
    })
    .join("");
}


function renderPoolChart() {
  const canvas = byId("poolHashrateChart");

  if (!canvas) {
    return;
  }

  const rect = canvas.getBoundingClientRect();

  if (!rect.width || !rect.height) {
    return;
  }

  const pixelRatio = window.devicePixelRatio || 1;

  canvas.width = Math.round(
    rect.width * pixelRatio
  );

  canvas.height = Math.round(
    rect.height * pixelRatio
  );

  const context = canvas.getContext("2d");

  context.setTransform(
    pixelRatio,
    0,
    0,
    pixelRatio,
    0,
    0
  );

  const width = rect.width;
  const height = rect.height;

  context.clearRect(0, 0, width, height);

  const series = Object.entries(
    homeV2State.poolHistories
  ).filter(([, values]) => values.length);

  if (!series.length) {
    context.fillStyle = "#8faac6";
    context.font = "14px Arial";
    context.fillText(
      "Waiting for active pool telemetry...",
      24,
      48
    );
    return;
  }

  const padding = {
    left: 82,
    right: 25,
    top: 28,
    bottom: 42,
  };

  const plotWidth = (
    width
    - padding.left
    - padding.right
  );

  const plotHeight = (
    height
    - padding.top
    - padding.bottom
  );

  const allValues = series.flatMap(
    ([, values]) => values
  );

  let maximum = Math.max(...allValues, 1);
  let minimum = Math.min(...allValues, 0);

  if (maximum === minimum) {
    minimum = Math.max(0, minimum * 0.9);
    maximum = maximum * 1.1 || 1;
  }

  const range = maximum - minimum;

  context.font = "11px Arial";
  context.lineWidth = 1;

  for (let index = 0; index <= 5; index += 1) {
    const y = (
      padding.top
      + (plotHeight / 5) * index
    );

    const value = (
      maximum
      - (range / 5) * index
    );

    context.strokeStyle = "rgba(147,197,253,.12)";
    context.beginPath();
    context.moveTo(padding.left, y);
    context.lineTo(
      width - padding.right,
      y
    );
    context.stroke();

    context.fillStyle = "#8faac6";
    context.fillText(
      fmtHashrate(value),
      8,
      y + 4
    );
  }

  for (let index = 0; index <= 8; index += 1) {
    const x = (
      padding.left
      + (plotWidth / 8) * index
    );

    context.strokeStyle = "rgba(147,197,253,.07)";
    context.beginPath();
    context.moveTo(x, padding.top);
    context.lineTo(
      x,
      height - padding.bottom
    );
    context.stroke();
  }

  series.forEach(([id, values]) => {
    const color = homeV2State.poolColors[id];
    const sampleCount = Math.max(
      ...series.map(
        ([, samples]) => samples.length
      ),
      2
    );

    const leftPadding = (
      sampleCount - values.length
    );

    const points = values.map(
      (value, index) => {
        const overallIndex = (
          leftPadding + index
        );

        const x = (
          padding.left
          + (
            overallIndex
            / (sampleCount - 1)
          ) * plotWidth
        );

        const y = (
          padding.top
          + (
            1
            - (
              (value - minimum)
              / range
            )
          ) * plotHeight
        );

        return { x, y };
      }
    );

    if (!points.length) {
      return;
    }

    context.beginPath();

    points.forEach((point, index) => {
      if (index === 0) {
        context.moveTo(point.x, point.y);
      } else {
        context.lineTo(point.x, point.y);
      }
    });

    context.strokeStyle = color;
    context.lineWidth = 3;
    context.shadowColor = color;
    context.shadowBlur = 9;
    context.stroke();
    context.shadowBlur = 0;

    points.forEach((point) => {
      context.beginPath();
      context.arc(
        point.x,
        point.y,
        3,
        0,
        Math.PI * 2
      );

      context.fillStyle = "#07101f";
      context.fill();

      context.strokeStyle = color;
      context.lineWidth = 2;
      context.stroke();
    });
  });
}


function renderMiners(miners) {
  const container = byId("topMiners");

  setText(
    "topMinerCount",
    `${miners.length} ranked`
  );

  if (!miners.length) {
    container.innerHTML = `
      <div class="home-v2-empty">
        No miners currently online.
      </div>
    `;
    return;
  }

  container.innerHTML = miners
    .slice(0, 10)
    .map((miner, index) => {
      const rank = integerValue(
        miner.rank,
        index + 1
      );

      return `
        <article class="home-v2-miner-row">
          <div class="home-v2-miner-rank">
            #${rank}
          </div>

          <div>
            <div class="home-v2-miner-name">
              ${escapeHtml(
                miner.name || "Unknown Miner"
              )}
            </div>

            <div class="home-v2-miner-pool">
              ${escapeHtml(
                miner.coin || "—"
              )}
              •
              ${escapeHtml(
                miner.poolName
                || miner.poolHost
                || "Unknown pool"
              )}
            </div>
          </div>

          <div class="home-v2-miner-values">
            <strong>
              ${escapeHtml(
                fmtHashrate(miner.hashrate)
              )}
            </strong>

            <span>
              ${numberValue(
                miner.sharesPerSecond
              ).toFixed(3)}
              shares/sec
            </span>
          </div>
        </article>
      `;
    })
    .join("");
}


function renderNodes(nodes) {
  const container = byId("nodeReadiness");

  setText(
    "nodeCount",
    `${nodes.length} node${
      nodes.length === 1 ? "" : "s"
    }`
  );

  if (!nodes.length) {
    container.innerHTML = `
      <div class="home-v2-empty">
        No blockchain nodes are currently exposed
        through the Fleet API.
      </div>
    `;
    return;
  }

  container.innerHTML = nodes
    .map((node) => {
      const online = Boolean(node.online);
      const status = online
        ? "online"
        : "offline";

      const sync = node.syncPercent == null
        ? "—"
        : fmtPercent(node.syncPercent);

      return `
        <article class="home-v2-node-row">
          <div class="home-v2-node-row-header">
            <div>
              <h3>
                ${escapeHtml(
                  node.name
                  || `${node.coin || ""} Node`
                )}
              </h3>

              <div class="home-v2-node-host">
                ${escapeHtml(
                  node.host || "Unknown host"
                )}
              </div>
            </div>

            <span class="home-v2-state-badge ${status}">
              ${online ? "Online" : "Offline"}
            </span>
          </div>

          <div class="home-v2-node-stats">
            <div class="home-v2-mini-stat">
              <strong>
                ${node.blockHeight == null
                  ? "—"
                  : fmtNumber(node.blockHeight)}
              </strong>
              <span>Block Height</span>
            </div>

            <div class="home-v2-mini-stat">
              <strong>
                ${node.peers == null
                  ? "—"
                  : fmtNumber(node.peers)}
              </strong>
              <span>Peers</span>
            </div>

            <div class="home-v2-mini-stat">
              <strong>
                ${escapeHtml(sync)}
              </strong>
              <span>Sync</span>
            </div>
          </div>
        </article>
      `;
    })
    .join("");
}


function renderAlerts(alerts) {
  const container = byId("operationsAlerts");

  setText(
    "alertCount",
    `${alerts.length} alert${
      alerts.length === 1 ? "" : "s"
    }`
  );

  if (!alerts.length) {
    container.innerHTML = `
      <div class="home-v2-all-clear">
        ✓ No active fleet alerts
      </div>
    `;
    return;
  }

  container.innerHTML = alerts
    .map((alert) => {
      const severity = String(
        alert.severity || "warning"
      ).toLowerCase();

      return `
        <article class="home-v2-alert-row ${escapeHtml(severity)}">
          <div class="home-v2-alert-row-header">
            <div>
              <h3>
                ${escapeHtml(
                  alert.title
                  || "Operations Alert"
                )}
              </h3>

              <div class="home-v2-alert-source">
                ${escapeHtml(
                  alert.source
                  || alert.type
                  || "Nexus"
                )}
              </div>
            </div>

            <span class="home-v2-state-badge ${escapeHtml(severity)}">
              ${escapeHtml(
                statusLabel(severity)
              )}
            </span>
          </div>

          <div class="home-v2-alert-message">
            ${escapeHtml(
              alert.message
              || "No additional information."
            )}
          </div>
        </article>
      `;
    })
    .join("");
}


function buildActivity(fleet) {
  const summary = fleet.summary || {};
  const pools = Array.isArray(
    fleet.activePools
  )
    ? fleet.activePools
    : [];

  const miners = Array.isArray(
    fleet.topMiners
  )
    ? fleet.topMiners
    : [];

  const nodes = Array.isArray(fleet.nodes)
    ? fleet.nodes
    : [];

  const events = [];

  events.push({
    level: "green",
    text: (
      `Fleet API online with `
      + `${fmtNumber(summary.coinCount)} `
      + `blockchain operations`
    ),
  });

  events.push({
    level: "blue",
    text: (
      `${fmtNumber(summary.activePoolCount)} `
      + `active pools producing `
      + `${fmtHashrate(summary.fleetHashrate)}`
    ),
  });

  pools.slice(0, 4).forEach((pool) => {
    events.push({
      level: "green",
      text: (
        `${pool.name} active at `
        + `${fmtHashrate(pool.hashrate)} `
        + `with ${fmtNumber(
          pool.workerCount
        )} miner${
          integerValue(pool.workerCount) === 1
            ? ""
            : "s"
        }`
      ),
    });
  });

  if (miners[0]) {
    events.push({
      level: "blue",
      text: (
        `Top miner ${miners[0].name} `
        + `is producing `
        + `${fmtHashrate(
          miners[0].hashrate
        )} on ${miners[0].poolName}`
      ),
    });
  }

  nodes
    .filter((node) => node.online)
    .slice(0, 3)
    .forEach((node) => {
      events.push({
        level: "green",
        text: (
          `${node.name} online`
          + (
            node.blockHeight != null
              ? ` at block ${fmtNumber(
                node.blockHeight
              )}`
              : ""
          )
        ),
      });
    });

  if (
    integerValue(summary.warningCount) === 0
    && integerValue(summary.criticalCount) === 0
  ) {
    events.push({
      level: "green",
      text: "No warning or critical conditions detected",
    });
  }

  return events.slice(0, 10);
}


function renderActivity(fleet) {
  const events = buildActivity(fleet);
  const time = fmtTime(fleet.generatedAt);

  setText(
    "activityTimestamp",
    time
  );

  byId("activityFeed").innerHTML = events
    .map((event) => `
      <div class="event ${escapeHtml(event.level)}">
        <b>${escapeHtml(time)}</b>
        <span>${escapeHtml(event.text)}</span>
      </div>
    `)
    .join("");
}


function renderFleet(fleet) {
  homeV2State.fleet = fleet;

  const coins = Array.isArray(fleet.coins)
    ? fleet.coins
    : [];

  const pools = Array.isArray(
    fleet.activePools
  )
    ? fleet.activePools
    : [];

  const miners = Array.isArray(
    fleet.topMiners
  )
    ? fleet.topMiners
    : [];

  const nodes = Array.isArray(fleet.nodes)
    ? fleet.nodes
    : [];

  const alerts = Array.isArray(fleet.alerts)
    ? fleet.alerts
    : [];

  renderStatus(fleet);
  renderFleetSummary(fleet);
  renderCoins(coins);
  renderPools(pools);
  renderMiners(miners);
  renderNodes(nodes);
  renderAlerts(alerts);
  renderActivity(fleet);
  renderAttentionPanel();
  renderPriorityQueue();
  renderFleetInsights();

  updatePoolHistories(pools);
  renderChartLegend();

  setText(
    "chartFleetTotal",
    fmtHashrate(
      fleet.summary?.fleetHashrate
    )
  );

  requestAnimationFrame(
    renderPoolChart
  );
}


function renderLoadError(error) {
  console.error(
    "Unable to load Fleet API:",
    error
  );

  const badge = byId("fleetStatusBadge");

  badge.textContent = "API ERROR";
  badge.className = "live-badge critical";

  setText(
    "lastUpdated",
    "Fleet telemetry unavailable"
  );

  [
    "coinOperations",
    "activePools",
    "topMiners",
    "nodeReadiness",
    "operationsAlerts",
    "activityFeed",
  ].forEach((id) => {
    const element = byId(id);

    if (element) {
      element.innerHTML = `
        <div class="home-v2-empty">
          Unable to load live fleet data.
          ${escapeHtml(error.message || error)}
        </div>
      `;
    }
  });
}


async function loadFleet() {
  if (homeV2State.loading) {
    return;
  }

  homeV2State.loading = true;

  try {
    const response = await fetch(
      "/api/platform/home",
      {
        cache: "no-store",
        headers: {
          Accept: "application/json",
        },
      }
    );

    if (!response.ok) {
      throw new Error(
        `Fleet API returned HTTP ${response.status}`
      );
    }

    const fleet = await response.json();

    const normalizedFleet = normalizePlatformHome(fleet);


    renderFleet(normalizedFleet);
    renderPlatformOperations(normalizedFleet);
  } catch (error) {
    renderLoadError(error);
  } finally {
    homeV2State.loading = false;
  }
}


function startFleetRefresh() {
  clearInterval(homeV2State.refreshTimer);

  homeV2State.refreshTimer = setInterval(
    loadFleet,
    HOME_V2_REFRESH_MS
  );
}


function setupTvMode() {
  byId("homeV2TvToggle")?.addEventListener(
    "click",
    () => {
      document.body.classList.add(
        "command-tv"
      );
    }
  );

  byId("homeV2TvExit")?.addEventListener(
    "click",
    () => {
      document.body.classList.remove(
        "command-tv"
      );
    }
  );
}


window.addEventListener(
  "resize",
  () => {
    window.clearTimeout(
      window.homeV2ResizeTimer
    );

    window.homeV2ResizeTimer = window.setTimeout(
      renderPoolChart,
      150
    );
  }
);


window.addEventListener(
  "DOMContentLoaded",
  () => {
    setupTvMode();
    setupAttentionPanel();
    setupPriorityQueue();
    setupFleetInsights();
    setupMetricTrends();
    setupNexusOperationsBrief();
    setupMissionTimeline();
    setupFleetForecast();
    loadFleetForecast();
    loadMissionTimeline();
    loadNexusOperationsBrief();
    loadFleet();
    loadMetricTrends();
    loadSmcHealth();
    loadOperationsEvents();
    startFleetRefresh();

    setInterval(
      loadSmcHealth,
      15000
    );

    setInterval(
      loadOperationsEvents,
      5000
    );

    setInterval(
      loadMetricTrends,
      60000
    );
  }
);

/* =========================================================
   Seymour MiningCore Workhorse
   ========================================================= */

function smcStatusClass(status) {
  const normalized = String(
    status || "offline"
  ).toLowerCase();

  if (normalized === "healthy") {
    return "healthy";
  }

  if (normalized === "warning") {
    return "warning";
  }

  if (normalized === "critical") {
    return "critical";
  }

  return "offline";
}


function renderSmcFleetSummary(summary) {
  const container = byId("smcFleetSummary");

  if (!container) {
    return;
  }

  const items = [
    {
      label: "Health",
      value: fmtPercent(
        summary.healthScore
      ),
    },
    {
      label: "Instances Online",
      value: (
        `${fmtNumber(
          summary.onlineInstanceCount
        )}/${fmtNumber(
          summary.instanceCount
        )}`
      ),
    },
    {
      label: "Active Pools",
      value: fmtNumber(
        summary.activePoolCount
      ),
    },
    {
      label: "Connected Miners",
      value: fmtNumber(
        summary.connectedMiners
      ),
    },
    {
      label: "SMC Hashrate",
      value: fmtHashrate(
        summary.totalHashrate
      ),
    },
    {
      label: "API Shares/sec",
      value: numberValue(
        summary.sharesPerSecond
      ).toFixed(3),
    },
  ];

  container.innerHTML = items
    .map((item) => `
      <div class="smc-summary-stat">
        <span>
          ${escapeHtml(item.label)}
        </span>

        <strong>
          ${escapeHtml(item.value)}
        </strong>
      </div>
    `)
    .join("");
}


function smcPoolPriority(pool) {
  const stratumHealthy = (
    !Array.isArray(pool.stratumChecks)
    || !pool.stratumChecks.length
    || pool.stratumChecks.every(
      (check) => check.open
    )
  );

  if (!pool.api?.ok || !stratumHealthy) {
    return 0;
  }

  if (pool.active) {
    return 1;
  }

  return 2;
}


function smcPoolStatus(pool) {
  const stratumHealthy = (
    !Array.isArray(pool.stratumChecks)
    || !pool.stratumChecks.length
    || pool.stratumChecks.every(
      (check) => check.open
    )
  );

  if (!pool.api?.ok || !stratumHealthy) {
    return "critical";
  }

  if (pool.active) {
    return "active";
  }

  return "idle";
}


function smcPoolBadges(pool) {
  const badges = [];

  const visibility = String(
    pool.visibility || "private"
  ).toLowerCase();

  const mode = String(
    pool.mode || "solo"
  ).toLowerCase();

  badges.push(`
    <span class="smc-pool-badge ${escapeHtml(visibility)}">
      ${escapeHtml(visibility)}
    </span>
  `);

  if (mode) {
    badges.push(`
      <span class="smc-pool-badge mode">
        ${escapeHtml(mode)}
      </span>
    `);
  }

  return badges.join("");
}


function smcPoolRow(pool) {
  const status = smcPoolStatus(pool);

  return `
    <div class="smc-pool-row ${escapeHtml(status)}">
      <div class="smc-pool-primary">
        <div class="smc-pool-name">
          ${escapeHtml(
            pool.name
            || pool.nativePoolId
            || "Mining Pool"
          )}
        </div>

        <div class="smc-pool-badges">
          ${smcPoolBadges(pool)}

          <span class="smc-pool-badge ${escapeHtml(status)}">
            ${escapeHtml(statusLabel(status))}
          </span>
        </div>
      </div>

      <div class="smc-pool-hashrate">
        ${escapeHtml(
          fmtHashrate(pool.hashrate)
        )}
      </div>

      <div class="smc-pool-miners">
        ${fmtNumber(
          pool.connectedMiners
        )}
        miner${
          integerValue(
            pool.connectedMiners
          ) === 1
            ? ""
            : "s"
        }
      </div>
    </div>
  `;
}


function renderSmcPoolRows(
  pools,
  instanceId
) {
  if (!Array.isArray(pools) || !pools.length) {
    return `
      <div class="home-v2-empty">
        No MiningCore pools configured.
      </div>
    `;
  }

  const sortedPools = [...pools].sort(
    (left, right) => {
      const priorityDifference = (
        smcPoolPriority(left)
        - smcPoolPriority(right)
      );

      if (priorityDifference !== 0) {
        return priorityDifference;
      }

      return (
        numberValue(right.hashrate)
        - numberValue(left.hashrate)
      );
    }
  );

  const visiblePools = sortedPools.slice(0, 3);
  const hiddenPools = sortedPools.slice(3);

  const safeInstanceId = escapeHtml(
    instanceId || "unknown"
  );

  return `
    <div class="smc-pool-list">
      <div class="smc-pool-list-heading">
        <span>
          Top Pools
        </span>

        <span>
          ${fmtNumber(pools.length)} total
        </span>
      </div>

      ${visiblePools
        .map(smcPoolRow)
        .join("")}

      ${
        hiddenPools.length
          ? `
            <div
              id="smcHiddenPools-${safeInstanceId}"
              class="smc-hidden-pools"
              hidden
            >
              ${hiddenPools
                .map(smcPoolRow)
                .join("")}
            </div>

            <button
              class="smc-view-pools-button"
              type="button"
              data-instance-id="${safeInstanceId}"
              data-hidden-count="${hiddenPools.length}"
            >
              View all ${fmtNumber(
                pools.length
              )} pools
            </button>
          `
          : ""
      }
    </div>
  `;
}

function renderSmcFindings(findings) {
  if (
    !Array.isArray(findings)
    || !findings.length
  ) {
    return "";
  }

  return `
    <div class="smc-findings">
      ${findings.slice(0, 3).map((finding) => `
        <div class="smc-finding ${escapeHtml(
          finding.severity || "warning"
        )}">
          ${escapeHtml(
            finding.message
            || "MiningCore health issue detected."
          )}
        </div>
      `).join("")}
    </div>
  `;
}


function renderSmcInstances(instances) {
  const container = byId("smcInstances");

  if (!container) {
    return;
  }

  if (!Array.isArray(instances) || !instances.length) {
    container.innerHTML = `
      <div class="home-v2-empty">
        No Seymour MiningCore instances discovered.
      </div>
    `;
    return;
  }

  container.innerHTML = instances
    .map((instance) => {
      const status = smcStatusClass(
        instance.status
      );

      const apiOnline = Boolean(
        instance.api?.online
      );

      const consoleOnline = Boolean(
        instance.console?.online
      );

      const stratumChecks = (
        instance.pools || []
      ).flatMap(
        (pool) => pool.stratumChecks || []
      );

      const stratumOnline = (
        stratumChecks.length > 0
        && stratumChecks.every(
          (check) => check.open
        )
      );

      const apiLatency = (
        instance.api?.latencyMs == null
          ? "—"
          : `${numberValue(
            instance.api.latencyMs
          ).toFixed(0)} ms`
      );

      return `
        <article class="smc-instance-card ${escapeHtml(status)}">
          <div class="smc-instance-header">
            <div>
              <h3 class="smc-instance-name">
                ${escapeHtml(
                  instance.name
                  || "Seymour MiningCore"
                )}
              </h3>

              <div class="smc-instance-host">
                ${escapeHtml(
                  instance.host
                  || "Unknown host"
                )}
              </div>
            </div>

            <div class="smc-instance-health">
              <span class="smc-health-score">
                ${fmtPercent(
                  instance.healthScore
                )}
              </span>

              <span class="home-v2-state-badge ${escapeHtml(status)}">
                ${escapeHtml(
                  statusLabel(status)
                )}
              </span>
            </div>
          </div>

          <div class="smc-instance-metrics">
            <div class="smc-instance-metric">
              <strong>
                ${escapeHtml(apiLatency)}
              </strong>
              <span>API Latency</span>
            </div>

            <div class="smc-instance-metric">
              <strong>
                ${fmtNumber(
                  instance.activePoolCount
                )}/${fmtNumber(
                  instance.poolCount
                )}
              </strong>
              <span>Active Pools</span>
            </div>

            <div class="smc-instance-metric">
              <strong>
                ${fmtNumber(
                  instance.connectedMiners
                )}
              </strong>
              <span>Miners</span>
            </div>

            <div class="smc-instance-metric">
              <strong>
                ${escapeHtml(
                  fmtHashrate(
                    instance.totalHashrate
                  )
                )}
              </strong>
              <span>Hashrate</span>
            </div>
          </div>

          <div class="smc-services">
            <span class="smc-service-pill ${
              apiOnline ? "" : "offline"
            }">
              API
            </span>

            <span class="smc-service-pill ${
              stratumOnline ? "" : "offline"
            }">
              Stratum
            </span>

            <span class="smc-service-pill ${
              consoleOnline ? "" : "offline"
            }">
              Console :${escapeHtml(
                instance.console?.port || 8559
              )}
            </span>
          </div>

          ${renderSmcPoolRows(
            instance.pools,
            instance.id
          )}

          ${renderSmcFindings(
            instance.findings
          )}
        </article>
      `;
    })
    .join("");
}


function renderSmcHealth(payload) {
  homeV2State.smcHealth = payload;

  const summary = payload?.summary || {};
  const status = smcStatusClass(
    payload?.status
  );

  const badge = byId("smcHealthBadge");

  if (badge) {
    badge.textContent = statusLabel(
      status
    ).toUpperCase();

    badge.className = (
      `home-v2-state-badge ${status}`
    );
  }

  setText(
    "smcInstanceCount",
    `${fmtNumber(
      summary.onlineInstanceCount
    )}/${fmtNumber(
      summary.instanceCount
    )} online`
  );

  renderSmcFleetSummary(summary);

  renderSmcInstances(
    payload?.instances || []
  );

  renderAttentionPanel();
  renderPriorityQueue();
  renderFleetInsights();
}


function renderSmcError(error) {
  const message = escapeHtml(
    error?.message || error
  );

  const badge = byId("smcHealthBadge");

  if (badge) {
    badge.textContent = "UNAVAILABLE";
    badge.className = (
      "home-v2-state-badge critical"
    );
  }

  const summary = byId("smcFleetSummary");
  const instances = byId("smcInstances");

  if (summary) {
    summary.innerHTML = `
      <div class="home-v2-empty">
        Seymour MiningCore health unavailable:
        ${message}
      </div>
    `;
  }

  if (instances) {
    instances.innerHTML = "";
  }
}


async function loadSmcHealth() {
  try {
    const response = await fetch(
      "/api/smc/health",
      {
        cache: "no-store",
        headers: {
          Accept: "application/json",
        },
      }
    );

    if (!response.ok) {
      throw new Error(
        `SMC Health API returned HTTP ${response.status}`
      );
    }

    const payload = await response.json();

    renderSmcHealth(payload);
  } catch (error) {
    console.error(
      "Unable to load SMC health:",
      error
    );

    renderSmcError(error);
  }
}

document.addEventListener(
  "click",
  (event) => {
    const button = event.target.closest(
      ".smc-view-pools-button"
    );

    if (!button) {
      return;
    }

    const instanceId = button.dataset.instanceId;
    const hidden = byId(
      `smcHiddenPools-${instanceId}`
    );

    if (!hidden) {
      return;
    }

    const isHidden = hidden.hasAttribute(
      "hidden"
    );

    if (isHidden) {
      hidden.removeAttribute("hidden");
      button.textContent = "Show fewer pools";
    } else {
      hidden.setAttribute("hidden", "");
      button.textContent = (
        `View all ${
          button.dataset.hiddenCount
            ? (
              Number(
                button.dataset.hiddenCount
              ) + 3
            )
            : ""
        } pools`
      );
    }
    setInterval(
      loadMissionTimeline,
      30000
    );

    setInterval(
      loadFleetForecast,
      60000
    );

  }
);

/* =========================================================
   Things That Need Attention
   ========================================================= */

function normalizeAttentionSeverity(value) {
  const severity = String(
    value || "warning"
  ).toLowerCase();

  if (
    severity === "critical"
    || severity === "error"
    || severity === "offline"
  ) {
    return "critical";
  }

  if (
    severity === "info"
    || severity === "notice"
  ) {
    return "info";
  }

  return "warning";
}


function collectFleetAttention(fleet) {
  const items = [];

  const alerts = Array.isArray(fleet?.alerts)
    ? fleet.alerts
    : [];

  alerts.forEach((alert) => {
    items.push({
      severity: normalizeAttentionSeverity(
        alert.severity
      ),
      title: (
        alert.title
        || "Fleet condition detected"
      ),
      message: (
        alert.message
        || "No additional details available."
      ),
      source: (
        alert.source
        || alert.type
        || "Fleet API"
      ),
    });
  });

  const nodes = Array.isArray(fleet?.nodes)
    ? fleet.nodes
    : [];

  nodes.forEach((node) => {
    if (!node.online) {
      items.push({
        severity: "critical",
        title: "Blockchain node offline",
        message: (
          `${node.name || "Blockchain node"} `
          + "is not reporting as online."
        ),
        source: (
          node.host
          || node.coin
          || "Blockchain"
        ),
      });
    }

    if (
      node.syncPercent != null
      && numberValue(node.syncPercent) < 99.9
    ) {
      items.push({
        severity: "warning",
        title: "Blockchain node still syncing",
        message: (
          `${node.name || "Blockchain node"} `
          + `is ${fmtPercent(
            node.syncPercent
          )} synchronized.`
        ),
        source: (
          node.host
          || node.coin
          || "Blockchain"
        ),
      });
    }

    if (
      node.peers != null
      && integerValue(node.peers) < 4
    ) {
      items.push({
        severity: "warning",
        title: "Low blockchain peer count",
        message: (
          `${node.name || "Blockchain node"} `
          + `has only ${fmtNumber(
            node.peers
          )} connected peers.`
        ),
        source: (
          node.host
          || node.coin
          || "Blockchain"
        ),
      });
    }
  });

  return items;
}


function collectSmcAttention(payload) {
  const items = [];

  const instances = Array.isArray(
    payload?.instances
  )
    ? payload.instances
    : [];

  instances.forEach((instance) => {
    const findings = Array.isArray(
      instance.findings
    )
      ? instance.findings
      : [];

    findings.forEach((finding) => {
      items.push({
        severity: normalizeAttentionSeverity(
          finding.severity
        ),
        title: (
          finding.component
            ? (
              `${instance.name}: `
              + String(
                finding.component
              ).replaceAll("-", " ")
            )
            : (
              `${instance.name} health issue`
            )
        ),
        message: (
          finding.message
          || "Seymour MiningCore health issue detected."
        ),
        source: (
          instance.host
          || instance.name
          || "Seymour MiningCore"
        ),
      });
    });

    if (!instance.api?.online) {
      items.push({
        severity: "critical",
        title: `${instance.name} API unavailable`,
        message: (
          "Nexus cannot retrieve MiningCore "
          + "pool or worker telemetry."
        ),
        source: (
          instance.host
          || instance.name
        ),
      });
    }

    if (!instance.console?.online) {
      items.push({
        severity: "warning",
        title: `${instance.name} console unavailable`,
        message: (
          `The Seymour local console on port ${
            instance.console?.port || 8559
          } is not reachable.`
        ),
        source: (
          instance.host
          || instance.name
        ),
      });
    }
  });

  return items;
}


function deduplicateAttention(items) {
  const seen = new Set();

  return items.filter((item) => {
    const key = [
      item.severity,
      item.title,
      item.message,
      item.source,
    ].join("|");

    if (seen.has(key)) {
      return false;
    }

    seen.add(key);
    return true;
  });
}


function attentionPriority(severity) {
  if (severity === "critical") {
    return 0;
  }

  if (severity === "warning") {
    return 1;
  }

  return 2;
}


function renderAttentionPanel() {
  const panel = byId("attentionPanel");

  if (!panel) {
    return;
  }

  const fleetItems = collectFleetAttention(
    homeV2State.fleet
  );

  const smcItems = collectSmcAttention(
    homeV2State.smcHealth
  );

  const items = deduplicateAttention([
    ...fleetItems,
    ...smcItems,
  ]).sort(
    (left, right) => (
      attentionPriority(left.severity)
      - attentionPriority(right.severity)
    )
  );

  const criticalCount = items.filter(
    (item) => item.severity === "critical"
  ).length;

  const warningCount = items.filter(
    (item) => item.severity === "warning"
  ).length;

  let state = "healthy";

  if (criticalCount > 0) {
    state = "critical";
  } else if (warningCount > 0) {
    state = "warning";
  }

  panel.className = (
    `nexus-card attention-panel ${state}`
  );

  const subtitle = byId("attentionSubtitle");
  const count = byId("attentionCount");
  const container = byId("attentionItems");
  const toggle = byId("attentionToggle");

  if (!items.length) {
    subtitle.textContent = (
      "No current fleet, node, pool, "
      + "or Seymour MiningCore problems detected."
    );

    count.textContent = "ALL CLEAR";

    container.innerHTML = `
      <div class="attention-all-clear">
        ✓ Everything currently looks healthy
      </div>
    `;

    container.setAttribute("hidden", "");

    toggle.textContent = "Details";
    toggle.setAttribute(
      "aria-expanded",
      "false"
    );

    return;
  }

  subtitle.textContent = [
    criticalCount
      ? `${criticalCount} critical`
      : null,
    warningCount
      ? `${warningCount} warning`
      : null,
  ].filter(Boolean).join(" • ");

  count.textContent = (
    `${items.length} item${
      items.length === 1 ? "" : "s"
    }`
  );

  container.innerHTML = items
    .slice(0, 12)
    .map((item) => `
      <article class="attention-item ${escapeHtml(
        item.severity
      )}">
        <div class="attention-item-title">
          ${escapeHtml(item.title)}
        </div>

        <div class="attention-item-message">
          ${escapeHtml(item.message)}
        </div>

        <div class="attention-item-source">
          ${escapeHtml(item.source)}
        </div>
      </article>
    `)
    .join("");

  container.removeAttribute("hidden");

  toggle.textContent = "Hide";
  toggle.setAttribute(
    "aria-expanded",
    "true"
  );
}


function setupAttentionPanel() {
  const toggle = byId("attentionToggle");
  const items = byId("attentionItems");

  if (!toggle || !items) {
    return;
  }

  toggle.addEventListener(
    "click",
    () => {
      const hidden = items.hasAttribute(
        "hidden"
      );

      if (hidden) {
        items.removeAttribute("hidden");
        toggle.textContent = "Hide";
        toggle.setAttribute(
          "aria-expanded",
          "true"
        );
      } else {
        items.setAttribute("hidden", "");
        toggle.textContent = "Details";
        toggle.setAttribute(
          "aria-expanded",
          "false"
        );
      }
    }
  );
}

/* =========================================================
   Persistent Real Operations Events
   ========================================================= */

function operationsEventClass(severity) {
  const value = String(
    severity || "info"
  ).toLowerCase();

  if (value === "critical") {
    return "critical";
  }

  if (value === "warning") {
    return "warning";
  }

  if (value === "recovery") {
    return "recovery";
  }

  return "info";
}


function operationsEventIcon(event) {
  const type = String(
    event?.type || ""
  ).toLowerCase();

  if (type.includes("miner")) {
    return "⛏";
  }

  if (
    type.includes("pool")
    || type.includes("stratum")
  ) {
    return "◈";
  }

  if (
    type.includes("node")
    || type.includes("block")
    || type.includes("peer")
  ) {
    return "⬡";
  }

  if (
    type.includes("smc")
    || type.includes("miningcore")
  ) {
    return "⚙";
  }

  if (type.includes("alert")) {
    return "!";
  }

  return "●";
}


function renderOperationsEvents(payload) {
  homeV2State.operationsEvents = payload;

  const events = Array.isArray(
    payload?.events
  )
    ? payload.events
    : [];

  const container = byId("activityFeed");

  if (!container) {
    return;
  }

  setText(
    "activityTimestamp",
    payload?.generatedAt
      ? fmtTime(payload.generatedAt)
      : "Live"
  );

  if (!events.length) {
    container.innerHTML = `
      <div class="home-v2-empty">
        No persistent operations events recorded yet.
      </div>
    `;
    return;
  }

  container.innerHTML = events
    .slice(0, 12)
    .map((event) => {
      const severity = operationsEventClass(
        event.severity
      );

      return `
        <article class="operations-event ${escapeHtml(severity)}">
          <div class="operations-event-icon">
            ${escapeHtml(
              operationsEventIcon(event)
            )}
          </div>

          <div class="operations-event-content">
            <div class="operations-event-header">
              <strong>
                ${escapeHtml(
                  event.title
                  || "Operations event"
                )}
              </strong>

              <time>
                ${escapeHtml(
                  fmtTime(event.timestamp)
                )}
              </time>
            </div>

            <div class="operations-event-message">
              ${escapeHtml(
                event.message
                || "No additional event details."
              )}
            </div>

            <div class="operations-event-meta">
              <span>
                ${escapeHtml(
                  event.source
                  || "Nexus"
                )}
              </span>

              <span>
                ${escapeHtml(
                  event.objectType
                  || event.type
                  || "system"
                )}
              </span>
            </div>
          </div>
        </article>
      `;
    })
    .join("");

  renderPriorityQueue();
}


async function loadOperationsEvents() {
  try {
    const response = await fetch(
      "/api/events/operations",
      {
        cache: "no-store",
        headers: {
          Accept: "application/json",
        },
      }
    );

    if (!response.ok) {
      throw new Error(
        `Operations events returned HTTP ${response.status}`
      );
    }

    const payload = await response.json();

    renderOperationsEvents(payload);
  } catch (error) {
    console.error(
      "Unable to load operations events:",
      error
    );
  }
}

/* =========================================================
   Fleet Priority Queue
   ========================================================= */

function prioritySeverity(value) {
  const severity = String(
    value || "info"
  ).toLowerCase();

  if (
    severity === "critical"
    || severity === "error"
    || severity === "offline"
  ) {
    return "critical";
  }

  if (severity === "warning") {
    return "warning";
  }

  if (
    severity === "recovery"
    || severity === "resolved"
  ) {
    return "recovery";
  }

  return "info";
}


function priorityScore(item) {
  const severityScores = {
    critical: 1000,
    warning: 700,
    recovery: 300,
    info: 100,
  };

  let score = severityScores[
    prioritySeverity(item.severity)
  ] || 0;

  const type = String(
    item.type || item.objectType || ""
  ).toLowerCase();

  if (
    type.includes("smc")
    || type.includes("miningcore")
  ) {
    score += 80;
  }

  if (type.includes("stratum")) {
    score += 75;
  }

  if (type.includes("node")) {
    score += 65;
  }

  if (type.includes("pool")) {
    score += 55;
  }

  if (type.includes("miner")) {
    score += 45;
  }

  if (item.timestamp) {
    const age = (
      Date.now()
      - new Date(item.timestamp).getTime()
    );

    if (
      Number.isFinite(age)
      && age < 15 * 60 * 1000
    ) {
      score += 25;
    }
  }

  return score;
}


function priorityAge(timestamp) {
  if (!timestamp) {
    return "Current";
  }

  const date = new Date(timestamp);

  if (Number.isNaN(date.getTime())) {
    return "Current";
  }

  const seconds = Math.max(
    0,
    Math.round(
      (Date.now() - date.getTime()) / 1000
    )
  );

  if (seconds < 60) {
    return `${seconds}s ago`;
  }

  const minutes = Math.round(seconds / 60);

  if (minutes < 60) {
    return `${minutes}m ago`;
  }

  const hours = Math.round(minutes / 60);

  if (hours < 24) {
    return `${hours}h ago`;
  }

  return `${Math.round(hours / 24)}d ago`;
}


function collectPriorityItems() {
  const items = [];

  collectFleetAttention(
    homeV2State.fleet
  ).forEach((item) => {
    items.push({
      ...item,
      type: "fleet-alert",
      timestamp: (
        homeV2State.fleet?.generatedAt
        || new Date().toISOString()
      ),
    });
  });

  collectSmcAttention(
    homeV2State.smcHealth
  ).forEach((item) => {
    items.push({
      ...item,
      type: "smc-health",
      timestamp: (
        homeV2State.smcHealth?.generatedAt
        || new Date().toISOString()
      ),
    });
  });

  const operations = Array.isArray(
    homeV2State.operationsEvents?.events
  )
    ? homeV2State.operationsEvents.events
    : [];

  operations
    .filter((event) => {
      const severity = prioritySeverity(
        event.severity
      );

      const type = String(
        event.type || ""
      ).toLowerCase();

      const metadata = event.metadata || {};

      /*
      * Hashrate variation is normal.
      * Keep it in the operations feed, not the priority queue.
      */
      if (type === "miner-hashrate-shift") {
        return false;
      }

      if (type === "pool-hashrate-shift") {
        const change = Number(
          metadata.changePercent || 0
        );

        return change <= -50;
      }

      const actionableTypes = [
        "miner-offline",
        "miner-missing",
        "pool-idle",
        "pool-missing",
        "node-offline",
        "node-missing",
        "stratum-offline",
        "smc-api-offline",
        "smc-console-offline",
        "smc-missing",
        "alert-opened",
        "alert-resolved",
        "node-online",
        "stratum-restored",
        "smc-api-restored",
        "smc-console-restored",
        "miner-online",
        "pool-active",
      ];

      return (
        actionableTypes.includes(type)
        || severity === "critical"
        || severity === "recovery"
      );
    })
    .slice(0, 20)
    .forEach((event) => {
      items.push({
        severity: prioritySeverity(
          event.severity
        ),
        title: (
          event.title
          || "Operations event"
        ),
        message: (
          event.message
          || "No additional details."
        ),
        source: (
          event.source
          || "Nexus"
        ),
        type: (
          event.type
          || event.objectType
          || "operations-event"
        ),
        timestamp: event.timestamp,
      });
    });

  return deduplicateAttention(items)
    .map((item) => ({
      ...item,
      severity: prioritySeverity(
        item.severity
      ),
    }))
    .sort((left, right) => {
      const scoreDifference = (
        priorityScore(right)
        - priorityScore(left)
      );

      if (scoreDifference !== 0) {
        return scoreDifference;
      }

      return (
        new Date(right.timestamp || 0).getTime()
        - new Date(left.timestamp || 0).getTime()
      );
    });
}


function renderPriorityQueue() {
  const panel = byId("fleetPriorityQueue");
  const container = byId("priorityQueueItems");
  const count = byId("priorityQueueCount");
  const subtitle = byId("priorityQueueSubtitle");
  const toggle = byId("priorityQueueToggle");

  if (
    !panel
    || !container
    || !count
    || !subtitle
    || !toggle
  ) {
    return;
  }

  const items = collectPriorityItems();

  const criticalCount = items.filter(
    (item) => item.severity === "critical"
  ).length;

  const warningCount = items.filter(
    (item) => item.severity === "warning"
  ).length;

  let panelState = "healthy";

  if (criticalCount > 0) {
    panelState = "critical";
  } else if (warningCount > 0) {
    panelState = "warning";
  }

  panel.className = (
    `nexus-card priority-queue ${panelState}`
  );

  if (!items.length) {
    count.textContent = "NO ACTIONS";

    subtitle.textContent = (
      "No current operational priorities. "
      + "Fleet monitoring remains active."
    );

    toggle.hidden = true;

    container.innerHTML = `
      <div class="priority-all-clear">
        ✓ No priority actions required
      </div>
    `;

    return;
  }

  count.textContent = (
    `${items.length} priorit${
      items.length === 1 ? "y" : "ies"
    }`
  );

  subtitle.textContent = [
    criticalCount
      ? `${criticalCount} critical`
      : null,
    warningCount
      ? `${warningCount} warning`
      : null,
    (
      !criticalCount
      && !warningCount
      ? "Recent recoveries"
      : null
    ),
  ].filter(Boolean).join(" • ");

  const visibleLimit = (
    homeV2State.priorityExpanded
      ? items.length
      : 5
  );

  const visibleItems = items.slice(
    0,
    visibleLimit
  );

  container.innerHTML = visibleItems
    .map((item, index) => `
      <article class="priority-item ${escapeHtml(
        item.severity
      )}">
        <div class="priority-item-rank">
          ${index + 1}
        </div>

        <div class="priority-item-content">
          <div class="priority-item-header">
            <div class="priority-item-title">
              ${escapeHtml(
                item.title
                || "Fleet priority"
              )}
            </div>

            <span class="priority-item-severity ${escapeHtml(
              item.severity
            )}">
              ${escapeHtml(
                statusLabel(item.severity)
              )}
            </span>
          </div>

          <div class="priority-item-message">
            ${escapeHtml(
              item.message
              || "No additional information."
            )}
          </div>

          <div class="priority-item-footer">
            <span class="priority-item-source">
              ${escapeHtml(
                item.source
                || "Nexus"
              )}
            </span>

            <span class="priority-item-age">
              ${escapeHtml(
                priorityAge(item.timestamp)
              )}
            </span>
          </div>
        </div>
      </article>
    `)
    .join("");

  toggle.hidden = items.length <= 5;

  if (!toggle.hidden) {
    toggle.textContent = (
      homeV2State.priorityExpanded
        ? "Show top 5"
        : `View all ${items.length}`
    );
  }
}


function setupPriorityQueue() {
  const toggle = byId("priorityQueueToggle");

  if (!toggle) {
    return;
  }

  toggle.addEventListener(
    "click",
    () => {
      homeV2State.priorityExpanded = (
        !homeV2State.priorityExpanded
      );

      renderPriorityQueue();
    }
  );
}

/* =========================================================
   Fleet Insights
   ========================================================= */

function insightItem({
  type = "observation",
  title,
  message,
  source = "Nexus",
  value = "",
  symbol = "✦",
}) {
  return {
    type,
    title,
    message,
    source,
    value,
    symbol,
  };
}


function buildFleetInsights() {
  const fleet = homeV2State.fleet || {};
  const smc = homeV2State.smcHealth || {};

  const summary = fleet.summary || {};
  const smcSummary = smc.summary || {};

  const coins = Array.isArray(fleet.coins)
    ? fleet.coins
    : [];

  const pools = Array.isArray(
    fleet.activePools
  )
    ? fleet.activePools
    : [];

  const miners = Array.isArray(
    fleet.topMiners
  )
    ? fleet.topMiners
    : [];

  const nodes = Array.isArray(fleet.nodes)
    ? fleet.nodes
    : [];

  const instances = Array.isArray(
    smc.instances
  )
    ? smc.instances
    : [];

  const insights = [];

  const warningCount = integerValue(
    summary.warningCount
  );

  const criticalCount = integerValue(
    summary.criticalCount
  );

  if (
    warningCount === 0
    && criticalCount === 0
  ) {
    insights.push(
      insightItem({
        type: "positive",
        title: "Fleet operating without active alerts",
        message:
          "Nexus currently detects no warning or critical conditions across the monitored fleet.",
        source: "Fleet API",
        value: "All clear",
        symbol: "✓",
      })
    );
  }

  const healthiestSmc = instances.every(
    (instance) => (
      integerValue(instance.healthScore) >= 90
    )
  );

  if (instances.length && healthiestSmc) {
    insights.push(
      insightItem({
        type: "positive",
        title: "Seymour MiningCore fleet is healthy",
        message:
          `${instances.length} monitored MiningCore instance${
            instances.length === 1 ? " is" : "s are"
          } online with healthy API, Stratum, and service telemetry.`,
        source: "Seymour MiningCore",
        value: fmtPercent(
          smcSummary.healthScore
        ),
        symbol: "⚙",
      })
    );
  }

  if (pools.length) {
    const strongestPool = [...pools].sort(
      (left, right) => (
        numberValue(right.hashrate)
        - numberValue(left.hashrate)
      )
    )[0];

    insights.push(
      insightItem({
        type: "observation",
        title: "Highest-producing active pool",
        message:
          `${strongestPool.name} currently leads the fleet with ${
            fmtNumber(strongestPool.workerCount)
          } connected miner${
            integerValue(
              strongestPool.workerCount
            ) === 1 ? "" : "s"
          }.`,
        source:
          strongestPool.host
          || strongestPool.name,
        value: fmtHashrate(
          strongestPool.hashrate
        ),
        symbol: "◈",
      })
    );
  }

  if (miners.length) {
    const strongestMiner = [...miners].sort(
      (left, right) => (
        numberValue(right.hashrate)
        - numberValue(left.hashrate)
      )
    )[0];

    insights.push(
      insightItem({
        type: "observation",
        title: "Current top-performing miner",
        message:
          `${strongestMiner.name} is the fleet leader and is mining through ${strongestMiner.poolName || strongestMiner.poolHost || "its assigned pool"}.`,
        source:
          strongestMiner.assetIp
          || strongestMiner.poolHost
          || "Mining fleet",
        value: fmtHashrate(
          strongestMiner.hashrate
        ),
        symbol: "⛏",
      })
    );
  }

  const btcOperation = coins.find(
    (coin) => coin.symbol === "BTC"
  );

  if (
    btcOperation
    && integerValue(
      btcOperation.onlineNodeCount
    ) > 0
    && integerValue(
      btcOperation.activePoolCount
    ) === 0
  ) {
    insights.push(
      insightItem({
        type: "recommendation",
        title: "Bitcoin infrastructure is ready for a pool",
        message:
          "Bitcoin Core is online and synchronized, but Nexus does not currently see an active BTC mining pool.",
        source: "BTC operation",
        value: "Pool ready",
        symbol: "₿",
      })
    );
  }

  coins.forEach((coin) => {
    if (
      integerValue(coin.activePoolCount) > 0
      && integerValue(coin.nodeCount) === 0
    ) {
      insights.push(
        insightItem({
          type: "infrastructure",
          title: `${coin.symbol} node telemetry is not linked`,
          message:
            `${coin.symbol} mining is active, but no blockchain node is currently represented in the Fleet API for that coin.`,
          source: `${coin.symbol} operation`,
          value: `${fmtNumber(
            coin.activePoolCount
          )} pools`,
          symbol: "⬡",
        })
      );
    }
  });

  if (nodes.length === 1) {
    insights.push(
      insightItem({
        type: "recommendation",
        title: "Consider blockchain-node redundancy",
        message:
          "The current fleet has one monitored blockchain node. A second node can reduce dependency on a single RPC and storage host.",
        source:
          nodes[0].host
          || nodes[0].name
          || "Blockchain fleet",
        value: "1 node",
        symbol: "⛓",
      })
    );
  }

  nodes.forEach((node) => {
    if (
      node.online
      && node.peers != null
      && integerValue(node.peers) >= 8
    ) {
      insights.push(
        insightItem({
          type: "positive",
          title: `${node.name} has healthy peer connectivity`,
          message:
            `The node is online with ${fmtNumber(
              node.peers
            )} connected peers and is available to support dependent services.`,
          source:
            node.host
            || node.coin
            || "Blockchain node",
          value: `${fmtNumber(
            node.peers
          )} peers`,
          symbol: "⬡",
        })
      );
    }
  });

  const apiLatencies = instances
    .map((instance) => (
      numberValue(
        instance.api?.latencyMs,
        -1
      )
    ))
    .filter((value) => value >= 0);

  if (apiLatencies.length) {
    const averageLatency = (
      apiLatencies.reduce(
        (sum, value) => sum + value,
        0
      )
      / apiLatencies.length
    );

    insights.push(
      insightItem({
        type:
          averageLatency <= 100
            ? "positive"
            : "recommendation",
        title: "MiningCore API responsiveness",
        message:
          averageLatency <= 100
            ? "Average MiningCore API latency is currently within a healthy operating range."
            : "MiningCore API latency is elevated and may affect dashboard refresh and operational automation.",
        source: "SMC health telemetry",
        value: `${averageLatency.toFixed(0)} ms`,
        symbol: "↯",
      })
    );
  }

  const totalStratumPorts = instances.reduce(
    (total, instance) => (
      total
      + (instance.pools || []).reduce(
        (poolTotal, pool) => (
          poolTotal
          + (
            Array.isArray(pool.stratumPorts)
              ? pool.stratumPorts.length
              : 0
          )
        ),
        0
      )
    ),
    0
  );

  const tlsPorts = instances.reduce(
    (total, instance) => (
      total
      + (instance.pools || []).reduce(
        (poolTotal, pool) => (
          poolTotal
          + (
            Array.isArray(pool.tlsPorts)
              ? pool.tlsPorts.length
              : 0
          )
        ),
        0
      )
    ),
    0
  );

  if (
    totalStratumPorts > 0
    && tlsPorts === 0
  ) {
    insights.push(
      insightItem({
        type: "security",
        title: "Stratum connections are not using TLS",
        message:
          "All currently monitored Stratum ports appear to be unencrypted. TLS should be considered for remote or public-facing pool traffic.",
        source: "Seymour MiningCore",
        value: `${totalStratumPorts} ports`,
        symbol: "🔒",
      })
    );
  }

  if (
    integerValue(summary.onlineMinerCount) > 0
    && integerValue(summary.activePoolCount) > 0
  ) {
    const minersPerPool = (
      numberValue(
        summary.onlineMinerCount
      )
      / Math.max(
        1,
        numberValue(
          summary.activePoolCount
        )
      )
    );

    insights.push(
      insightItem({
        type: "capacity",
        title: "Current fleet distribution",
        message:
          `The fleet is averaging ${minersPerPool.toFixed(
            1
          )} online miners per active pool across ${fmtNumber(
            summary.coinCount
          )} blockchain operation${
            integerValue(summary.coinCount) === 1
              ? ""
              : "s"
          }.`,
        source: "Fleet topology",
        value: `${minersPerPool.toFixed(1)} / pool`,
        symbol: "▦",
      })
    );
  }

  return insights.slice(0, 8);
}


function renderFleetInsights() {
  const container = byId(
    "fleetInsightsGrid"
  );

  const count = byId(
    "fleetInsightsCount"
  );

  const subtitle = byId(
    "fleetInsightsSubtitle"
  );

  if (!container || !count || !subtitle) {
    return;
  }

  const insights = buildFleetInsights();

  count.textContent = (
    `${insights.length} insight${
      insights.length === 1 ? "" : "s"
    }`
  );

  subtitle.textContent = (
    "Live observations and recommendations "
    + "derived from current telemetry."
  );

  if (!insights.length) {
    container.innerHTML = `
      <div class="home-v2-empty">
        More telemetry is needed before Nexus can
        produce useful fleet insights.
      </div>
    `;
    return;
  }

  container.innerHTML = insights
    .map((insight) => `
      <article class="fleet-insight-card ${escapeHtml(
        insight.type
      )}">
        <div class="fleet-insight-top">
          <span class="fleet-insight-type">
            ${escapeHtml(
              insight.type
            )}
          </span>

          <span class="fleet-insight-symbol">
            ${escapeHtml(
              insight.symbol
            )}
          </span>
        </div>

        <div class="fleet-insight-title">
          ${escapeHtml(
            insight.title
          )}
        </div>

        <div class="fleet-insight-message">
          ${escapeHtml(
            insight.message
          )}
        </div>

        <div class="fleet-insight-footer">
          <span class="fleet-insight-source">
            ${escapeHtml(
              insight.source
            )}
          </span>

          <span class="fleet-insight-value">
            ${escapeHtml(
              insight.value
            )}
          </span>
        </div>
      </article>
    `)
    .join("");
}


function setupFleetInsights() {
  byId(
    "fleetInsightsRefresh"
  )?.addEventListener(
    "click",
    () => {
      renderFleetInsights();
    }
  );
}

/* =========================================================
   PostgreSQL Fleet Metric Trends
   ========================================================= */

function metricHistoryRows(payload) {
  return Array.isArray(payload?.metrics)
    ? payload.metrics
    : [];
}


function metricSeries(
  payload,
  entityType,
  entityId,
  metricName
) {
  return metricHistoryRows(payload)
    .filter((metric) => (
      String(metric.entityType) === entityType
      && String(metric.entityId) === entityId
      && String(metric.metricName) === metricName
      && Number.isFinite(
        Number(metric.metricValue)
      )
    ))
    .map((metric) => ({
      value: Number(metric.metricValue),
      observedAt: metric.observedAt,
      unit: metric.metricUnit || "",
    }))
    .sort((left, right) => (
      new Date(left.observedAt).getTime()
      - new Date(right.observedAt).getTime()
    ));
}


function metricSeriesDelta(series) {
  if (!Array.isArray(series) || series.length < 2) {
    return {
      value: null,
      type: "neutral",
      label: "Collecting",
    };
  }

  const first = Number(series[0].value);
  const latest = Number(
    series[series.length - 1].value
  );

  if (
    !Number.isFinite(first)
    || !Number.isFinite(latest)
  ) {
    return {
      value: null,
      type: "neutral",
      label: "Unavailable",
    };
  }

  if (first === 0) {
    const difference = latest - first;

    return {
      value: difference,
      type: difference > 0
        ? "positive"
        : difference < 0
          ? "negative"
          : "neutral",
      label: difference === 0
        ? "No change"
        : `${difference > 0 ? "+" : ""}${difference.toFixed(0)}`,
    };
  }

  const percent = (
    (latest - first)
    / Math.abs(first)
    * 100
  );

  return {
    value: percent,
    type: percent > 0.05
      ? "positive"
      : percent < -0.05
        ? "negative"
        : "neutral",
    label: (
      Math.abs(percent) < 0.05
        ? "Stable"
        : `${percent > 0 ? "+" : ""}${percent.toFixed(1)}%`
    ),
  };
}


function sparklineGeometry(series) {
  const width = 320;
  const height = 76;
  const paddingX = 3;
  const paddingY = 7;

  if (!Array.isArray(series) || series.length < 2) {
    return null;
  }

  const values = series.map(
    (point) => Number(point.value)
  );

  let minimum = Math.min(...values);
  let maximum = Math.max(...values);

  if (!Number.isFinite(minimum) || !Number.isFinite(maximum)) {
    return null;
  }

  if (minimum === maximum) {
    const padding = Math.max(
      Math.abs(minimum) * 0.03,
      1
    );

    minimum -= padding;
    maximum += padding;
  }

  const usableWidth = width - paddingX * 2;
  const usableHeight = height - paddingY * 2;

  const points = series.map((point, index) => {
    const x = (
      paddingX
      + (
        index
        / Math.max(1, series.length - 1)
      ) * usableWidth
    );

    const ratio = (
      (Number(point.value) - minimum)
      / (maximum - minimum)
    );

    const y = (
      height
      - paddingY
      - ratio * usableHeight
    );

    return {
      x,
      y,
      value: point.value,
    };
  });

  const linePath = points
    .map((point, index) => (
      `${index === 0 ? "M" : "L"}`
      + `${point.x.toFixed(2)},`
      + `${point.y.toFixed(2)}`
    ))
    .join(" ");

  const areaPath = [
    linePath,
    `L ${points[points.length - 1].x.toFixed(2)},${height}`,
    `L ${points[0].x.toFixed(2)},${height}`,
    "Z",
  ].join(" ");

  return {
    width,
    height,
    points,
    linePath,
    areaPath,
    minimum,
    maximum,
  };
}


function renderMetricSparkline(
  series,
  gradientId
) {
  const geometry = sparklineGeometry(series);

  if (!geometry) {
    return `
      <div class="metric-trend-empty">
        More historical samples are needed
      </div>
    `;
  }

  const latest = geometry.points[
    geometry.points.length - 1
  ];

  return `
    <svg
      class="metric-sparkline"
      viewBox="0 0 ${geometry.width} ${geometry.height}"
      preserveAspectRatio="none"
      role="img"
      aria-label="Historical metric trend"
    >
      <defs>
        <linearGradient
          id="${escapeHtml(gradientId)}"
          x1="0"
          y1="0"
          x2="0"
          y2="1"
        >
          <stop
            offset="0%"
            stop-color="currentColor"
            stop-opacity="0.34"
          ></stop>

          <stop
            offset="100%"
            stop-color="currentColor"
            stop-opacity="0"
          ></stop>
        </linearGradient>
      </defs>

      <line
        class="metric-sparkline-grid"
        x1="0"
        y1="25"
        x2="${geometry.width}"
        y2="25"
      ></line>

      <line
        class="metric-sparkline-grid"
        x1="0"
        y1="51"
        x2="${geometry.width}"
        y2="51"
      ></line>

      <path
        d="${geometry.areaPath}"
        fill="url(#${escapeHtml(gradientId)})"
        opacity="0.52"
      ></path>

      <path
        class="metric-sparkline-line"
        d="${geometry.linePath}"
      ></path>

      <circle
        class="metric-sparkline-point"
        cx="${latest.x.toFixed(2)}"
        cy="${latest.y.toFixed(2)}"
        r="4"
      ></circle>
    </svg>
  `;
}


function formatMetricTrendValue(type, value) {
  if (!Number.isFinite(Number(value))) {
    return "—";
  }

  if (type === "hashrate") {
    return fmtHashrate(value);
  }

  if (type === "health") {
    return fmtPercent(value);
  }

  return fmtNumber(value);
}


function metricTrendState(type, latestValue) {
  const value = Number(latestValue);

  if (!Number.isFinite(value)) {
    return "";
  }

  if (type === "health") {
    if (value >= 95) {
      return "healthy";
    }

    if (value >= 80) {
      return "warning";
    }

    return "critical";
  }

  return "";
}


function metricTrendCard({
  type,
  label,
  description,
  series,
}) {
  const latest = (
    series.length
      ? series[series.length - 1]
      : null
  );

  const delta = metricSeriesDelta(series);

  const latestValue = latest
    ? latest.value
    : null;

  const state = metricTrendState(
    type,
    latestValue
  );

  const gradientId = (
    `metric-gradient-${type}`
  );

  const firstAt = series[0]?.observedAt;
  const latestAt = latest?.observedAt;

  return `
    <article class="metric-trend-card ${escapeHtml(type)} ${escapeHtml(state)}">
      <div class="metric-trend-card-header">
        <div class="metric-trend-label">
          ${escapeHtml(label)}
        </div>

        <span class="metric-trend-delta ${escapeHtml(delta.type)}">
          ${escapeHtml(delta.label)}
        </span>
      </div>

      <div class="metric-trend-value">
        ${escapeHtml(
          formatMetricTrendValue(
            type,
            latestValue
          )
        )}
      </div>

      <div class="metric-trend-detail">
        ${escapeHtml(description)}
      </div>

      ${renderMetricSparkline(
        series,
        gradientId
      )}

      <div class="metric-trend-footer">
        <span>
          ${firstAt
            ? `From ${escapeHtml(fmtTime(firstAt))}`
            : "Awaiting baseline"}
        </span>

        <span>
          ${latestAt
            ? `Updated ${escapeHtml(priorityAge(latestAt))}`
            : "No samples"}
        </span>
      </div>
    </article>
  `;
}


function renderMetricTrends(payload) {
  const container = byId("metricTrendGrid");
  const age = byId("metricTrendsAge");

  if (!container || !age) {
    return;
  }

  const definitions = [
    {
      type: "hashrate",
      label: "Fleet Hashrate",
      description: "Total online worker hashrate",
      metricName: "fleet_hashrate",
    },
    {
      type: "health",
      label: "Fleet Health",
      description: "Combined worker and pool availability",
      metricName: "fleet_health",
    },
    {
      type: "workers",
      label: "Online Workers",
      description: "Workers currently reporting online",
      metricName: "worker_online",
    },
    {
      type: "pools",
      label: "Pool Inventory",
      description: "Managed pool instances",
      metricName: "pool_total",
    },
  ];

  const cards = definitions.map((definition) => ({
    ...definition,
    series: metricSeries(
      payload,
      "fleet",
      "primary",
      definition.metricName
    ),
  }));

  const allSamples = cards.flatMap(
    (card) => card.series
  );

  const latestTimestamp = allSamples
    .map((sample) => sample.observedAt)
    .filter(Boolean)
    .sort((left, right) => (
      new Date(right).getTime()
      - new Date(left).getTime()
    ))[0];

  age.textContent = latestTimestamp
    ? `Updated ${priorityAge(latestTimestamp)}`
    : "No historical samples";

  container.innerHTML = cards
    .map(metricTrendCard)
    .join("");
}


function renderMetricTrendError(error) {
  const container = byId("metricTrendGrid");
  const age = byId("metricTrendsAge");

  if (age) {
    age.textContent = "History unavailable";
  }

  if (container) {
    container.innerHTML = `
      <div class="home-v2-empty">
        Unable to load historical metrics:
        ${escapeHtml(
          error?.message || error
        )}
      </div>
    `;
  }
}


async function loadMetricTrends() {
  const button = byId("metricTrendsRefresh");

  if (button) {
    button.disabled = true;
    button.textContent = "Loading...";
  }

  try {
    const response = await fetch(
      "/api/platform/metrics/history",
      {
        cache: "no-store",
        headers: {
          Accept: "application/json",
        },
      }
    );

    if (!response.ok) {
      throw new Error(
        `Metrics history returned HTTP ${response.status}`
      );
    }

    const payload = await response.json();

    renderMetricTrends(payload);
  } catch (error) {
    console.error(
      "Unable to load fleet metric trends:",
      error
    );

    renderMetricTrendError(error);
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = "Refresh";
    }
  }
}


function setupMetricTrends() {
  byId(
    "metricTrendsRefresh"
  )?.addEventListener(
    "click",
    loadMetricTrends
  );
}

/* =========================================================
   PostgreSQL Platform Home Adapter
   ========================================================= */

function platformArray(value, key) {
  if (Array.isArray(value)) {
    return value;
  }

  if (
    value
    && typeof value === "object"
    && Array.isArray(value[key])
  ) {
    return value[key];
  }

  return [];
}


function platformCoinSymbol(value) {
  if (value && typeof value === "object") {
    return String(
      value.symbol
      || value.type
      || value.coin
      || "UNKNOWN"
    ).toUpperCase();
  }

  const text = String(value || "").trim();

  if (!text) {
    return "UNKNOWN";
  }

  /*
   * Temporary normalization for previously imported records
   * whose coin dictionary was serialized as text.
   */
  const dictionaryMatch = text.match(
    /['"]SYMBOL['"]\s*:\s*['"]([^'"]+)['"]/i
  );

  if (dictionaryMatch) {
    return dictionaryMatch[1].toUpperCase();
  }

  return text.toUpperCase();
}


function platformPoolCoin(pool) {
  return platformCoinSymbol(
    pool?.observedState?.coin
    || pool?.coin
  );
}


function platformPoolHashrate(pool) {
  return numberValue(
    pool?.currentHashrate
    ?? pool?.observedState?.workerHashrate
    ?? pool?.observedState?.hashrate
    ?? 0
  );
}


function platformPoolWorkerCount(pool) {
  return integerValue(
    pool?.onlineWorkerCount
    ?? pool?.workerCount
    ?? pool?.observedState?.connectedMiners
    ?? pool?.observedState?.workerCount
    ?? 0
  );
}


function platformNodeList(payload) {
  return platformArray(
    payload?.nodes,
    "nodes"
  );
}


function normalizePlatformHome(payload) {
  const fleet = payload?.summary || {};

  const workers = platformArray(
    payload?.workers,
    "workers"
  );

  const pools = platformArray(
    payload?.pools,
    "pools"
  );

  const nodes = platformNodeList(payload);

  const alerts = platformArray(
    payload?.alerts,
    "alerts"
  );

  const events = platformArray(
    payload?.events,
    "events"
  );

  const miningCoreInstances = platformArray(
    payload?.miningCore,
    "instances"
  );

  const onlineWorkers = workers.filter(
    (worker) => (
      String(
        worker.status || ""
      ).toLowerCase() === "online"
    )
  );

  const activePools = pools
    .filter((pool) => (
      String(
        pool.status || ""
      ).toLowerCase() === "active"
      || platformPoolWorkerCount(pool) > 0
    ))
    .map((pool) => ({
      id: pool.poolId,
      poolId: pool.poolId,
      nativePoolId: pool.nativePoolId,
      name: pool.name,
      coin: platformPoolCoin(pool),
      host: pool.host,
      endpoint: pool.apiBase,
      apiPort: pool.apiPort,
      mode: pool.mode,
      visibility: pool.visibility,
      status: "active",
      workerCount: platformPoolWorkerCount(
        pool
      ),
      connectedMiners: platformPoolWorkerCount(
        pool
      ),
      hashrate: platformPoolHashrate(pool),
      sharesPerSecond: (
        pool?.observedState?.sharesPerSecond
        ?? pool?.workers?.reduce(
          (sum, worker) => (
            sum
            + numberValue(
              worker.sharesPerSecond
            )
          ),
          0
        )
        ?? 0
      ),
      stratumPorts: pool.stratumPorts || [],
      workers: pool.workers || [],
      observedState: pool.observedState || {},
    }));

  const topMiners = [...onlineWorkers]
    .sort((left, right) => (
      numberValue(right.currentHashrate)
      - numberValue(left.currentHashrate)
    ))
    .slice(0, 10)
    .map((worker, index) => {
      const matchingPool = pools.find(
        (pool) => (
          pool.poolId
          === worker.poolInstanceId
        )
      );

      return {
        rank: index + 1,
        workerId: worker.workerId,
        name: worker.displayName,
        displayName: worker.displayName,
        assetId: worker.assetId,
        assetIp: (
          worker.observedState?.assetIp
          || worker.poolHost
        ),
        coin: platformCoinSymbol(
          worker.coin
        ),
        poolId: worker.poolInstanceId,
        poolName: (
          matchingPool?.name
          || worker.observedState?.poolName
          || worker.poolHost
        ),
        poolHost: worker.poolHost,
        hashrate: numberValue(
          worker.currentHashrate
        ),
        currentHashrate: numberValue(
          worker.currentHashrate
        ),
        sharesPerSecond: numberValue(
          worker.sharesPerSecond
        ),
        status: worker.status,
      };
    });

  const coinMap = new Map();

  function ensureCoin(symbol) {
    const normalized = platformCoinSymbol(
      symbol
    );

    if (!coinMap.has(normalized)) {
      coinMap.set(normalized, {
        symbol: normalized,
        name: (
          normalized === "BCH"
            ? "Bitcoin Cash"
            : normalized === "BTC"
              ? "Bitcoin"
              : normalized
        ),
        status: "available",
        hashrate: 0,
        activePoolCount: 0,
        workerCount: 0,
        nodeCount: 0,
        onlineNodeCount: 0,
      });
    }

    return coinMap.get(normalized);
  }

  activePools.forEach((pool) => {
    const coin = ensureCoin(pool.coin);

    coin.activePoolCount += 1;
    coin.hashrate += numberValue(
      pool.hashrate
    );
  });

  onlineWorkers.forEach((worker) => {
    const coin = ensureCoin(worker.coin);

    coin.workerCount += 1;
  });

  nodes.forEach((node) => {
    const coin = ensureCoin(
      node.coin || node.network
    );

    coin.nodeCount += 1;

    if (
      node.online
      || String(node.status).toLowerCase()
        === "online"
    ) {
      coin.onlineNodeCount += 1;
    }
  });

  coinMap.forEach((coin) => {
    if (coin.activePoolCount > 0) {
      coin.status = "mining";
    } else if (coin.onlineNodeCount > 0) {
      coin.status = "node-online";
    }
  });

  const warningCount = alerts.filter(
    (alert) => (
      String(alert.severity).toLowerCase()
      === "warning"
      && !["resolved", "closed"].includes(
        String(alert.status).toLowerCase()
      )
    )
  ).length;

  const criticalCount = alerts.filter(
    (alert) => (
      String(alert.severity).toLowerCase()
      === "critical"
      && !["resolved", "closed"].includes(
        String(alert.status).toLowerCase()
      )
    )
  ).length;

  const onlineNodes = nodes.filter(
    (node) => (
      node.online
      || String(
        node.status || ""
      ).toLowerCase() === "online"
    )
  );

  return {
    status: payload?.status || "ok",
    source: payload?.source,
    generatedAt: payload?.generatedAt,

    summary: {
      fleetHashrate: numberValue(
        fleet.fleetHashrate
      ),
      sharesPerSecond: onlineWorkers.reduce(
        (sum, worker) => (
          sum
          + numberValue(
            worker.sharesPerSecond
          )
        ),
        0
      ),
      coinCount: coinMap.size,
      poolCount: pools.length,
      activePoolCount: activePools.length,
      minerCount: workers.length,
      onlineMinerCount: onlineWorkers.length,
      nodeCount: nodes.length,
      onlineNodeCount: onlineNodes.length,
      miningCoreInstanceCount:
        miningCoreInstances.length,
      onlineMiningCoreInstanceCount:
        miningCoreInstances.filter(
          (instance) => (
            instance.online
            || String(
              instance.status || ""
            ).toLowerCase() === "online"
          )
        ).length,
      fleetHealth: numberValue(
        fleet.fleetHealth,
        100
      ),
      warningCount,
      criticalCount,
    },

    coins: Array.from(
      coinMap.values()
    ).sort((left, right) => (
      numberValue(right.hashrate)
      - numberValue(left.hashrate)
    )),

    activePools,
    topMiners,
    nodes,
    alerts,
    events,

    miningCore: payload?.miningCore,
    metrics: payload?.metrics,
    platform: payload,
  };
}

/* =========================================================
   Platform Operations Matrix
   ========================================================= */

function platformDomainState({
  healthy = true,
  warning = false,
  critical = false,
} = {}) {
  if (critical) {
    return "critical";
  }

  if (warning) {
    return "warning";
  }

  if (healthy) {
    return "healthy";
  }

  return "unknown";
}


function platformDomainCard(domain) {
  return `
    <article class="platform-domain ${escapeHtml(
      domain.state
    )}">
      <div class="platform-domain-top">
        <div class="platform-domain-name">
          ${escapeHtml(domain.name)}
        </div>

        <span class="platform-domain-indicator"></span>
      </div>

      <div class="platform-domain-status">
        ${escapeHtml(domain.status)}
      </div>

      <div class="platform-domain-detail">
        ${escapeHtml(domain.detail)}
      </div>

      <div class="platform-domain-metric">
        ${escapeHtml(domain.metric)}
      </div>
    </article>
  `;
}


function buildPlatformDomains(fleet) {
  const summary = fleet?.summary || {};
  const platform = fleet?.platform || {};
  const platformSummary = platform?.summary || {};

  const miningCore = platform?.miningCore || {};
  const miningCoreSummary = miningCore?.summary || {};

  const metricsPayload = platform?.metrics || {};
  const metrics = Array.isArray(metricsPayload.metrics)
    ? metricsPayload.metrics
    : [];

  const workersTotal = integerValue(
    summary.minerCount
    ?? platformSummary?.workers?.total
  );

  const workersOnline = integerValue(
    summary.onlineMinerCount
    ?? platformSummary?.workers?.online
  );

  const poolsTotal = integerValue(
    summary.poolCount
    ?? platformSummary?.pools?.total
  );

  const poolsOnline = integerValue(
    summary.activePoolCount
    ?? platformSummary?.pools?.online
  );

  const nodesTotal = integerValue(
    summary.nodeCount
  );

  const nodesOnline = integerValue(
    summary.onlineNodeCount
  );

  const miningCoreTotal = integerValue(
    miningCore.count
    ?? miningCoreSummary.instanceCount
  );

  const miningCoreOnline = integerValue(
    miningCoreSummary.onlineInstanceCount
  );

  const assetTotal = integerValue(
    platformSummary?.assets?.total
  );

  const matchedWorkers = integerValue(
    platformSummary?.workers?.matched
  );

  const unmatchedWorkers = integerValue(
    platformSummary?.workers?.unmatched
  );

  const metricCount = integerValue(
    metricsPayload.count,
    metrics.length
  );

  const newestMetric = metrics
    .map((metric) => metric.observedAt)
    .filter(Boolean)
    .sort((left, right) => (
      new Date(right).getTime()
      - new Date(left).getTime()
    ))[0];

  const metricAgeMs = newestMetric
    ? Date.now() - new Date(newestMetric).getTime()
    : Infinity;

  const fleetCritical = integerValue(
    summary.criticalCount
  );

  const fleetWarnings = integerValue(
    summary.warningCount
  );

  const miningState = platformDomainState({
    critical: (
      workersTotal > 0
      && workersOnline === 0
    ),
    warning: (
      workersOnline < workersTotal
      || poolsOnline < poolsTotal
    ),
  });

  const blockchainState = platformDomainState({
    critical: (
      nodesTotal > 0
      && nodesOnline === 0
    ),
    warning: (
      nodesOnline < nodesTotal
    ),
  });

  const miningCoreState = platformDomainState({
    critical: (
      miningCoreTotal > 0
      && miningCoreOnline === 0
    ),
    warning: (
      miningCoreOnline < miningCoreTotal
    ),
  });

  const cmdbState = platformDomainState({
    warning: unmatchedWorkers > 0,
  });

  const telemetryState = platformDomainState({
    critical: metricCount === 0,
    warning: metricAgeMs > 180000,
  });

  const apiState = platformDomainState({
    critical: platform?.status !== "ok",
    warning: (
      fleetCritical > 0
      || fleetWarnings > 0
    ),
  });

  return [
    {
      name: "Mining",
      state: miningState,
      status:
        miningState === "healthy"
          ? "Healthy"
          : miningState === "critical"
            ? "Offline"
            : "Degraded",
      detail:
        `${workersOnline}/${workersTotal} workers online · `
        + `${poolsOnline}/${poolsTotal} active pools`,
      metric: fmtHashrate(
        summary.fleetHashrate
      ),
    },
    {
      name: "Blockchain",
      state: blockchainState,
      status:
        blockchainState === "healthy"
          ? "Healthy"
          : blockchainState === "critical"
            ? "Offline"
            : "Degraded",
      detail:
        `${nodesOnline}/${nodesTotal} nodes online`,
      metric:
        fleet?.nodes?.length
          ? fleet.nodes
              .map((node) => (
                `${platformCoinSymbol(
                  node.coin
                )} ${node.syncPercent != null
                  ? `${Number(node.syncPercent).toFixed(2)}%`
                  : node.status}`
              ))
              .join(" · ")
          : "No nodes registered",
    },
    {
      name: "MiningCore",
      state: miningCoreState,
      status:
        miningCoreState === "healthy"
          ? "Healthy"
          : miningCoreState === "critical"
            ? "Offline"
            : "Degraded",
      detail:
        `${miningCoreOnline}/${miningCoreTotal} instances online`,
      metric:
        `${integerValue(
          miningCoreSummary.activePoolCount
        )} pools · `
        + `${integerValue(
          miningCoreSummary.connectedMiners
        )} miners`,
    },
    {
      name: "CMDB",
      state: cmdbState,
      status:
        cmdbState === "healthy"
          ? "Healthy"
          : "Review Needed",
      detail:
        `${assetTotal} managed assets`,
      metric:
        unmatchedWorkers > 0
          ? `${unmatchedWorkers} workers unmatched`
          : `${matchedWorkers} workers matched`,
    },
    {
      name: "Telemetry",
      state: telemetryState,
      status:
        telemetryState === "healthy"
          ? "Collecting"
          : telemetryState === "critical"
            ? "Unavailable"
            : "Stale",
      detail:
        `${metricCount} current metrics`,
      metric:
        newestMetric
          ? `Updated ${priorityAge(newestMetric)}`
          : "No observations",
    },
    {
      name: "Platform API",
      state: apiState,
      status:
        apiState === "healthy"
          ? "Online"
          : apiState === "critical"
            ? "Offline"
            : "Attention",
      detail:
        "PostgreSQL Platform services",
      metric:
        fleetCritical || fleetWarnings
          ? `${fleetCritical} critical · ${fleetWarnings} warning`
          : "No active platform alerts",
    },
  ];
}


function renderPlatformOperations(fleet) {
  const container = byId(
    "platformOperationsGrid"
  );

  const overall = byId(
    "platformOperationsOverall"
  );

  const subtitle = byId(
    "platformOperationsSubtitle"
  );

  const updated = byId(
    "platformOperationsUpdated"
  );

  if (
    !container
    || !overall
    || !subtitle
    || !updated
  ) {
    return;
  }

  const domains = buildPlatformDomains(
    fleet
  );

  const criticalCount = domains.filter(
    (domain) => domain.state === "critical"
  ).length;

  const warningCount = domains.filter(
    (domain) => domain.state === "warning"
  ).length;

  let overallState = "healthy";
  let overallLabel = "ALL SYSTEMS OPERATIONAL";

  if (criticalCount > 0) {
    overallState = "critical";
    overallLabel = (
      `${criticalCount} CRITICAL`
    );
  } else if (warningCount > 0) {
    overallState = "warning";
    overallLabel = (
      `${warningCount} DEGRADED`
    );
  }

  overall.className = (
    `platform-overall-status ${overallState}`
  );

  overall.textContent = overallLabel;

  subtitle.textContent = (
    criticalCount === 0
    && warningCount === 0
      ? "All monitored operational domains are healthy."
      : `${criticalCount} critical and ${warningCount} degraded domain${
          criticalCount + warningCount === 1
            ? ""
            : "s"
        }.`
  );

  updated.textContent = fleet?.generatedAt
    ? `Updated ${priorityAge(
        fleet.generatedAt
      )}`
    : "Live";

  container.innerHTML = domains
    .map(platformDomainCard)
    .join("");
}

/* =========================================================
   Nexus Operations Brief
   ========================================================= */

function nexusContextHome(payload) {
  if (
    payload
    && typeof payload === "object"
    && payload.context
    && typeof payload.context === "object"
  ) {
    return payload.context;
  }

  return {};
}


function nexusContextCount(
  section,
  statusName
) {
  if (!section || typeof section !== "object") {
    return 0;
  }

  if (
    section.status
    && typeof section.status === "object"
    && statusName
  ) {
    return integerValue(
      section.status[statusName]
    );
  }

  return integerValue(
    section.total
  );
}


function nexusContextFleetHashrate(context) {
  return numberValue(
    context?.metricsByEntity
      ?.[
        "fleet:primary"
      ]
      ?.fleet_hashrate
      ?.metricValue
    ?? context?.workers?.top?.reduce(
      (sum, worker) => (
        sum
        + numberValue(
          worker.currentHashrate
        )
      ),
      0
    )
    ?? 0
  );
}


function nexusContextWorkerSummary(context) {
  const workers = context?.workers || {};

  return {
    total: integerValue(workers.total),
    online: nexusContextCount(
      workers,
      "online"
    ),
    items: Array.isArray(workers.top)
      ? workers.top
      : [],
  };
}


function nexusContextPoolSummary(context) {
  const pools = context?.pools || {};

  return {
    total: integerValue(pools.total),
    active: nexusContextCount(
      pools,
      "active"
    ),
    items: Array.isArray(pools.items)
      ? pools.items
      : [],
  };
}


function nexusContextNodeSummary(context) {
  const nodes = context?.nodes || {};

  return {
    total: integerValue(nodes.total),
    online: nexusContextCount(
      nodes,
      "online"
    ),
    items: Array.isArray(nodes.items)
      ? nodes.items
      : [],
  };
}


function nexusContextMiningCoreSummary(context) {
  const miningCore = context?.miningcore || {};

  return {
    total: integerValue(miningCore.total),
    connected: integerValue(
      miningCore.connected
    ),
    items: Array.isArray(miningCore.items)
      ? miningCore.items
      : [],
  };
}


function nexusMeaningfulObservations(context) {
  const observations = [];

  const workers = nexusContextWorkerSummary(
    context
  );

  const pools = nexusContextPoolSummary(
    context
  );

  const nodes = nexusContextNodeSummary(
    context
  );

  const miningCore =
    nexusContextMiningCoreSummary(
      context
    );

  const alerts = Array.isArray(
    context?.alerts
  )
    ? context.alerts
    : [];

  if (
    workers.total > 0
    && workers.online === workers.total
  ) {
    observations.push(
      `${workers.online} of ${workers.total} workers are online.`
    );
  } else if (workers.total > 0) {
    observations.push(
      `${workers.total - workers.online} worker${
        workers.total - workers.online === 1
          ? ""
          : "s"
      } require attention.`
    );
  }

  if (
    pools.total > 0
    && pools.active === pools.total
  ) {
    observations.push(
      `All ${pools.active} managed pools are active.`
    );
  }

  if (
    miningCore.total > 0
    && miningCore.connected
      === miningCore.total
  ) {
    observations.push(
      `All ${miningCore.connected} Seymour MiningCore instances are connected.`
    );
  }

  nodes.items.forEach((node) => {
    const coin = platformCoinSymbol(
      node.coin
    );

    const syncPercent = numberValue(
      node.syncPercent
    );

    const peers = integerValue(
      node.peers
    );

    observations.push(
      `${node.name || coin} is online${
        Number.isFinite(syncPercent)
          ? ` and ${syncPercent.toFixed(3)}% synchronized`
          : ""
      }${peers ? ` with ${peers} peers` : ""}.`
    );
  });

  if (!alerts.length) {
    observations.push(
      "No active alerts require operator attention."
    );
  } else {
    observations.push(
      `${alerts.length} active alert${
        alerts.length === 1 ? "" : "s"
      } require review.`
    );
  }

  return observations.slice(0, 6);
}


function nexusRecommendation(context) {
  const alerts = Array.isArray(
    context?.alerts
  )
    ? context.alerts
    : [];

  if (alerts.length) {
    const critical = alerts.find(
      (alert) => (
        String(alert.severity).toLowerCase()
        === "critical"
      )
    );

    const alert = critical || alerts[0];

    return (
      alert.recommendedAction
      || alert.message
      || "Review the active Platform alert queue."
    );
  }

  const pools = nexusContextPoolSummary(
    context
  );

  const publicPoolWithoutTls =
    pools.items.find((pool) => {
      const visibility = String(
        pool.visibility || ""
      ).toLowerCase();

      const ports = Array.isArray(
        pool.stratumPorts
      )
        ? pool.stratumPorts
        : [];

      const tlsConfigured = Boolean(
        pool.configuration?.tls
        || pool.observedState?.tls
      );

      return (
        visibility === "public"
        && ports.length > 0
        && !tlsConfigured
      );
    });

  if (publicPoolWithoutTls) {
    return (
      `Review TLS protection for ${publicPoolWithoutTls.name}.`
    );
  }

  const miningCore =
    nexusContextMiningCoreSummary(
      context
    );

  const unknownVersion =
    miningCore.items.some(
      (instance) => (
        !String(
          instance.softwareVersion
          || instance.version
          || ""
        ).trim()
      )
    );

  if (unknownVersion) {
    return (
      "Capture MiningCore software versions during synchronization "
      + "to strengthen upgrade and compliance reporting."
    );
  }

  return (
    "No immediate action is required. Continue normal monitoring."
  );
}


function nexusBriefState(context) {
  const alerts = Array.isArray(
    context?.alerts
  )
    ? context.alerts
    : [];

  const critical = alerts.some(
    (alert) => (
      String(alert.severity).toLowerCase()
      === "critical"
    )
  );

  if (critical) {
    return {
      state: "critical",
      label: "ACTION REQUIRED",
      headline:
        "Critical operational conditions require attention.",
    };
  }

  if (alerts.length) {
    return {
      state: "warning",
      label: "REVIEW NEEDED",
      headline:
        "The fleet is operating with conditions to review.",
    };
  }

  return {
    state: "healthy",
    label: "FLEET NORMAL",
    headline:
      "Fleet operating normally.",
  };
}


function nexusBriefFact(
  label,
  value
) {
  return `
    <div class="nexus-brief-fact">
      <div class="nexus-brief-fact-label">
        ${escapeHtml(label)}
      </div>

      <div class="nexus-brief-fact-value">
        ${escapeHtml(value)}
      </div>
    </div>
  `;
}


function renderNexusOperationsBrief(payload) {
  const body = byId("nexusBriefBody");
  const status = byId("nexusBriefStatus");
  const subtitle = byId("nexusBriefSubtitle");
  const source = byId("nexusBriefSource");
  const updated = byId("nexusBriefUpdated");

  if (
    !body
    || !status
    || !subtitle
    || !source
    || !updated
  ) {
    return;
  }

  const context = nexusContextHome(
    payload
  );

  const briefState = nexusBriefState(
    context
  );

  const workers = nexusContextWorkerSummary(
    context
  );

  const pools = nexusContextPoolSummary(
    context
  );

  const nodes = nexusContextNodeSummary(
    context
  );

  const miningCore =
    nexusContextMiningCoreSummary(
      context
    );

  const hashrate =
    nexusContextFleetHashrate(
      context
    );

  const health = numberValue(
    context.fleetHealth,
    0
  );

  const observations =
    nexusMeaningfulObservations(
      context
    );

  const recommendation =
    nexusRecommendation(context);

  status.className = (
    `nexus-brief-status ${briefState.state}`
  );

  status.textContent = briefState.label;

  subtitle.textContent = (
    "Derived from PostgreSQL Platform context, telemetry, "
    + "events, alerts, and infrastructure state."
  );

  source.textContent = (
    `${payload?.source || "nexus-postgresql-platform-context"}`
    + ` · ${payload?.contextVersion || "v1"}`
  );

  updated.textContent = payload?.generatedAt
    ? `Generated ${priorityAge(payload.generatedAt)}`
    : "Generated recently";

  const summary = (
    `${workers.online} workers are online across `
    + `${pools.active} active pool${
      pools.active === 1 ? "" : "s"
    }. `
    + `${nodes.online} blockchain node${
      nodes.online === 1 ? " is" : "s are"
    } online, and `
    + `${miningCore.connected} MiningCore instance${
      miningCore.connected === 1
        ? " is"
        : "s are"
    } connected.`
  );

  body.innerHTML = `
    <div class="nexus-brief-primary">
      <div class="nexus-brief-headline">
        ${escapeHtml(briefState.headline)}
      </div>

      <div class="nexus-brief-summary">
        ${escapeHtml(summary)}
      </div>

      <div class="nexus-brief-facts">
        ${nexusBriefFact(
          "Fleet Health",
          `${health.toFixed(1)}%`
        )}

        ${nexusBriefFact(
          "Fleet Hashrate",
          fmtHashrate(hashrate)
        )}

        ${nexusBriefFact(
          "Active Alerts",
          String(
            Array.isArray(context.alerts)
              ? context.alerts.length
              : 0
          )
        )}
      </div>

      <ul class="nexus-brief-observations">
        ${observations
          .map((observation) => `
            <li>
              ${escapeHtml(observation)}
            </li>
          `)
          .join("")}
      </ul>
    </div>

    <div class="nexus-brief-side">
      <div class="nexus-brief-side-card">
        <div class="nexus-brief-side-label">
          Platform Footprint
        </div>

        <div class="nexus-brief-side-value">
          ${workers.total} workers ·
          ${pools.total} pools ·
          ${nodes.total} nodes ·
          ${miningCore.total} MiningCore
        </div>
      </div>

      <div class="nexus-brief-side-card">
        <div class="nexus-brief-side-label">
          Telemetry State
        </div>

        <div class="nexus-brief-side-value">
          ${integerValue(
            context?.telemetry?.currentMetricCount
          )} current metrics ·
          ${integerValue(
            context?.telemetry?.sampleCount
          )} samples
        </div>
      </div>

      <div class="nexus-brief-side-card recommendation">
        <div class="nexus-brief-side-label">
          Recommended Next Step
        </div>

        <div class="nexus-brief-side-value">
          ${escapeHtml(recommendation)}
        </div>
      </div>
    </div>
  `;
}


function renderNexusBriefError(error) {
  const body = byId("nexusBriefBody");
  const status = byId("nexusBriefStatus");

  if (status) {
    status.className =
      "nexus-brief-status warning";

    status.textContent =
      "CONTEXT UNAVAILABLE";
  }

  if (body) {
    body.innerHTML = `
      <div class="home-v2-empty">
        Unable to build the Nexus Operations Brief:
        ${escapeHtml(
          error?.message || error
        )}
      </div>
    `;
  }
}


async function loadNexusOperationsBrief() {
  const button = byId(
    "nexusBriefRefresh"
  );

  if (button) {
    button.disabled = true;
    button.textContent = "Analyzing...";
  }

  try {
    const response = await fetch(
      "/api/platform/context/home",
      {
        cache: "no-store",
        headers: {
          Accept: "application/json",
        },
      }
    );

    if (!response.ok) {
      throw new Error(
        `Platform context returned HTTP ${response.status}`
      );
    }

    const payload = await response.json();

    homeV2State.platformContext = payload;

    renderNexusOperationsBrief(payload);
  } catch (error) {
    console.error(
      "Unable to load Nexus Operations Brief:",
      error
    );

    renderNexusBriefError(error);
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = "Refresh brief";
    }
  }
}


function setupNexusOperationsBrief() {
  byId(
    "nexusBriefRefresh"
  )?.addEventListener(
    "click",
    loadNexusOperationsBrief
  );
}

/* =========================================================
   Live Mission Timeline
   ========================================================= */

function missionEventList(payload) {
  if (Array.isArray(payload?.events)) {
    return payload.events;
  }

  if (Array.isArray(payload?.items)) {
    return payload.items;
  }

  return [];
}


function missionRecommendationList(payload) {
  return Array.isArray(payload?.recommendations)
    ? payload.recommendations
    : [];
}


function missionEventTime(event) {
  return (
    event.occurredAt
    || event.createdAt
    || event.generatedAt
    || null
  );
}


function missionChangedKeys(event) {
  const previous = (
    event?.previousState
    && typeof event.previousState === "object"
  )
    ? event.previousState
    : {};

  const current = (
    event?.currentState
    && typeof event.currentState === "object"
  )
    ? event.currentState
    : {};

  const keys = new Set([
    ...Object.keys(previous),
    ...Object.keys(current),
  ]);

  return [...keys].filter(
    (key) => (
      JSON.stringify(previous[key])
      !== JSON.stringify(current[key])
    )
  );
}


function missionIsMetricOnlyChange(event) {
  if (
    String(event?.eventType)
    !== "resource.state_changed"
  ) {
    return false;
  }

  const changed = missionChangedKeys(event);

  if (!changed.length) {
    return true;
  }

  const metricOnlyFields = new Set([
    "currentHashrate",
    "hashrate",
    "sharesPerSecond",
    "peers",
    "peerCount",
    "connections",
    "mempoolSize",
    "mempoolBytes",
    "mempoolUsage",
    "checkedAt",
    "lastSeenAt",
    "updatedAt",
  ]);

  return changed.every(
    (key) => metricOnlyFields.has(key)
  );
}


function missionMeaningfulEvents(events) {
  return events.filter((event) => {
    const type = String(
      event.eventType || ""
    );

    if (type === "resource.state_changed") {
      return !missionIsMetricOnlyChange(event);
    }

    return true;
  });
}


function missionPercentChange(
  previousValue,
  currentValue
) {
  const previous = Number(previousValue);
  const current = Number(currentValue);

  if (
    !Number.isFinite(previous)
    || !Number.isFinite(current)
    || previous === 0
  ) {
    return null;
  }

  return (
    (current - previous)
    / Math.abs(previous)
    * 100
  );
}


function missionWorkerPerformanceUpdate(events) {
  const workerEvents = events
    .filter((event) => (
      event.entityType === "worker"
      && event.eventType
        === "resource.state_changed"
      && event.previousState
      && event.currentState
      && Number.isFinite(
        Number(
          event.previousState.currentHashrate
        )
      )
      && Number.isFinite(
        Number(
          event.currentState.currentHashrate
        )
      )
    ))
    .slice(0, 20);

  if (!workerEvents.length) {
    return null;
  }

  const newestByWorker = new Map();

  workerEvents.forEach((event) => {
    if (!newestByWorker.has(event.entityId)) {
      newestByWorker.set(
        event.entityId,
        event
      );
    }
  });

  const changes = [
    ...newestByWorker.values(),
  ].map((event) => ({
    entityId: event.entityId,
    percent: missionPercentChange(
      event.previousState.currentHashrate,
      event.currentState.currentHashrate
    ),
    previous:
      event.previousState.currentHashrate,
    current:
      event.currentState.currentHashrate,
    occurredAt: event.occurredAt,
  })).filter(
    (item) => item.percent != null
  );

  if (!changes.length) {
    return null;
  }

  const average = (
    changes.reduce(
      (sum, item) => sum + item.percent,
      0
    )
    / changes.length
  );

  return {
    kind: "performance",
    state: (
      average > 2
        ? "success"
        : average < -8
          ? "warning"
          : "info"
    ),
    kicker: "Fleet Performance",
    title: "Worker output updated",
    message: (
      `${changes.length} worker${
        changes.length === 1 ? "" : "s"
      } reported recent production changes. `
      + `Average movement: ${
        average > 0 ? "+" : ""
      }${average.toFixed(1)}%.`
    ),
    meta: `${changes.length} workers summarized`,
    occurredAt: changes
      .map((item) => item.occurredAt)
      .filter(Boolean)
      .sort((a, b) => (
        new Date(b) - new Date(a)
      ))[0],
  };
}


function missionHumanEntity(event) {
  const type = String(
    event.entityType || "resource"
  );

  if (type === "blockchain-node") {
    return "Blockchain node";
  }

  if (type === "miningcore-instance") {
    return "Seymour MiningCore";
  }

  if (type === "worker") {
    return "Mining worker";
  }

  if (type === "pool") {
    return "Mining pool";
  }

  return type
    .replaceAll("-", " ")
    .replace(/\b\w/g, (char) => (
      char.toUpperCase()
    ));
}


function missionDescribeEvent(event) {
  const type = String(
    event.eventType || ""
  );

  const entity = missionHumanEntity(event);

  const current = event.currentState || {};
  const previous = event.previousState || {};

  if (type === "resource.discovered") {
    return {
      kind: "event",
      state: "success",
      kicker: "Resource Discovery",
      title: `${entity} joined the Platform`,
      message: (
        event.message
        || `${entity} entered the Nexus state model.`
      ),
      meta: event.entityId || entity,
      occurredAt: missionEventTime(event),
    };
  }

  if (
    type.includes("offline")
    || current.status === "offline"
    || current.connected === false
    || current.rpcConnected === false
  ) {
    return {
      kind: "event",
      state: "critical",
      kicker: "Operational State",
      title: `${entity} is offline`,
      message: (
        event.message
        || "The resource stopped responding to Platform monitoring."
      ),
      meta: event.entityId || entity,
      occurredAt: missionEventTime(event),
    };
  }

  if (
    type.includes("restored")
    || type.includes("recovered")
    || (
      previous.status === "offline"
      && current.status === "online"
    )
  ) {
    return {
      kind: "event",
      state: "success",
      kicker: "Recovery",
      title: `${entity} recovered`,
      message: (
        event.message
        || "The resource returned to normal operation."
      ),
      meta: event.entityId || entity,
      occurredAt: missionEventTime(event),
    };
  }

  if (
    event.entityType === "blockchain-node"
    && Number(current.blockHeight)
      > Number(previous.blockHeight)
  ) {
    return {
      kind: "event",
      state: "success",
      kicker: "Blockchain",
      title: "Blockchain node advanced",
      message:
        `Block height advanced from ${
          previous.blockHeight
        } to ${current.blockHeight}.`,
      meta: event.entityId || "Blockchain",
      occurredAt: missionEventTime(event),
    };
  }

  return {
    kind: "event",
    state: (
      event.severity === "critical"
        ? "critical"
        : event.severity === "warning"
          ? "warning"
          : "info"
    ),
    kicker: "Platform Event",
    title: (
      String(event.title || "Resource changed")
        .replaceAll("_", " ")
    ),
    message: (
      event.message
      || `${entity} reported a meaningful state change.`
    ),
    meta: event.entityId || entity,
    occurredAt: missionEventTime(event),
  };
}


function missionDescribeRecommendation(
  recommendation
) {
  const priority = String(
    recommendation.priority
    || recommendation.severity
    || "normal"
  ).toLowerCase();

  return {
    kind: "recommendation",
    state: "recommendation",
    kicker: (
      priority === "critical"
      || priority === "high"
        ? "High-Priority Recommendation"
        : "Recommendation"
    ),
    title: (
      recommendation.title
      || "Nexus recommends operator review"
    ),
    message: (
      recommendation.recommendedAction
      || recommendation.message
      || recommendation.description
      || "Review the recommendation details."
    ),
    meta: (
      recommendation.entityId
      || recommendation.assetId
      || recommendation.ruleId
      || "Nexus Intelligence"
    ),
    occurredAt: (
      recommendation.generatedAt
      || recommendation.createdAt
      || new Date().toISOString()
    ),
  };
}


function buildMissionNarrative(
  eventsPayload,
  recommendationsPayload
) {
  const allEvents = missionEventList(
    eventsPayload
  );

  const meaningful = missionMeaningfulEvents(
    allEvents
  );

  const narrative = meaningful
    .slice(0, 8)
    .map(missionDescribeEvent);

  const performance =
    missionWorkerPerformanceUpdate(
      allEvents
    );

  if (performance) {
    narrative.push(performance);
  }

  missionRecommendationList(
    recommendationsPayload
  )
    .slice(0, 3)
    .forEach((recommendation) => {
      narrative.push(
        missionDescribeRecommendation(
          recommendation
        )
      );
    });

  return narrative
    .sort((left, right) => (
      new Date(right.occurredAt || 0)
      - new Date(left.occurredAt || 0)
    ))
    .slice(0, 8);
}


function missionEntryHtml(entry) {
  return `
    <article class="mission-entry ${escapeHtml(
      entry.state
    )}">
      <div class="mission-entry-marker"></div>

      <div class="mission-entry-content">
        <div class="mission-entry-kicker">
          ${escapeHtml(entry.kicker)}
        </div>

        <div class="mission-entry-title">
          ${escapeHtml(entry.title)}
        </div>

        <div class="mission-entry-message">
          ${escapeHtml(entry.message)}
        </div>

        <div class="mission-entry-meta">
          <span>
            ${escapeHtml(entry.meta)}
          </span>
        </div>
      </div>

      <div class="mission-entry-time">
        ${entry.occurredAt
          ? escapeHtml(
              priorityAge(entry.occurredAt)
            )
          : "—"}
      </div>
    </article>
  `;
}


function renderMissionBrief(
  contextPayload,
  recommendationsPayload
) {
  const container = byId(
    "missionTimelineBrief"
  );

  if (!container) {
    return;
  }

  const context = nexusContextHome(
    contextPayload
  );

  const health = numberValue(
    context.fleetHealth
  );

  const workers =
    nexusContextWorkerSummary(context);

  const pools =
    nexusContextPoolSummary(context);

  const nodes =
    nexusContextNodeSummary(context);

  const recommendations =
    missionRecommendationList(
      recommendationsPayload
    );

  const nextAction = recommendations[0];

  container.innerHTML = `
    <div class="mission-brief-card primary">
      <div class="mission-brief-label">
        Current Mission State
      </div>

      <div class="mission-brief-value">
        ${health >= 95
          ? "Fleet operating normally"
          : health >= 80
            ? "Fleet operating with degradation"
            : "Operator attention required"}
      </div>

      <div class="mission-brief-detail">
        ${workers.online}/${workers.total} workers ·
        ${pools.active}/${pools.total} pools ·
        ${nodes.online}/${nodes.total} nodes
      </div>
    </div>

    <div class="mission-brief-card">
      <div class="mission-brief-label">
        Fleet Production
      </div>

      <div class="mission-brief-value">
        ${escapeHtml(
          fmtHashrate(
            nexusContextFleetHashrate(
              context
            )
          )
        )}
      </div>

      <div class="mission-brief-detail">
        Current aggregate worker output
      </div>
    </div>

    <div class="mission-brief-card recommendation">
      <div class="mission-brief-label">
        Recommended Action
      </div>

      <div class="mission-brief-value">
        ${escapeHtml(
          nextAction?.title
          || "No immediate intervention required"
        )}
      </div>

      <div class="mission-brief-detail">
        ${escapeHtml(
          nextAction?.recommendedAction
          || nextAction?.message
          || "Continue normal monitoring."
        )}
      </div>
    </div>
  `;
}


function renderMissionTimeline(
  eventsPayload,
  recommendationsPayload,
  contextPayload
) {
  const stream = byId(
    "missionTimelineStream"
  );

  const status = byId(
    "missionTimelineStatus"
  );

  const subtitle = byId(
    "missionTimelineSubtitle"
  );

  const source = byId(
    "missionTimelineSource"
  );

  const updated = byId(
    "missionTimelineUpdated"
  );

  if (
    !stream
    || !status
    || !subtitle
    || !source
    || !updated
  ) {
    return;
  }

  const narrative = buildMissionNarrative(
    eventsPayload,
    recommendationsPayload
  );

  const recommendations =
    missionRecommendationList(
      recommendationsPayload
    );

  status.className = (
    `mission-timeline-status ${
      recommendations.length
        ? "attention"
        : "live"
    }`
  );

  status.textContent = (
    recommendations.length
      ? `${recommendations.length} RECOMMENDATION${
          recommendations.length === 1
            ? ""
            : "S"
        }`
      : "LIVE"
  );

  subtitle.textContent = (
    "Meaningful discoveries, changes, recoveries, "
    + "performance summaries, and recommendations."
  );

  source.textContent = (
    `${eventsPayload?.source
      || "nexus-postgresql-platform-events"}`
    + " · "
    + `${recommendationsPayload?.source
      || "nexus-postgresql-platform-recommendations"}`
  );

  const latestTime = narrative
    .map((entry) => entry.occurredAt)
    .filter(Boolean)
    .sort((left, right) => (
      new Date(right) - new Date(left)
    ))[0];

  updated.textContent = latestTime
    ? `Latest ${priorityAge(latestTime)}`
    : "No recent activity";

  if (!narrative.length) {
    stream.innerHTML = `
      <div class="mission-timeline-empty">
        ✓ No meaningful operational changes detected
      </div>
    `;
  } else {
    stream.innerHTML = narrative
      .map(missionEntryHtml)
      .join("");
  }

  renderMissionBrief(
    contextPayload,
    recommendationsPayload
  );
}


function renderMissionTimelineError(error) {
  const stream = byId(
    "missionTimelineStream"
  );

  const status = byId(
    "missionTimelineStatus"
  );

  if (status) {
    status.className =
      "mission-timeline-status attention";

    status.textContent =
      "DATA UNAVAILABLE";
  }

  if (stream) {
    stream.innerHTML = `
      <div class="home-v2-empty">
        Unable to load the Mission Timeline:
        ${escapeHtml(
          error?.message || error
        )}
      </div>
    `;
  }
}


async function loadMissionTimeline() {
  const button = byId(
    "missionTimelineRefresh"
  );

  if (button) {
    button.disabled = true;
    button.textContent = "Loading...";
  }

  try {
    const [
      eventsResponse,
      recommendationsResponse,
      contextResponse,
    ] = await Promise.all([
      fetch(
        "/api/platform/events",
        { cache: "no-store" }
      ),
      fetch(
        "/api/platform/recommendations/high-priority",
        { cache: "no-store" }
      ),
      fetch(
        "/api/platform/context/home",
        { cache: "no-store" }
      ),
    ]);

    if (!eventsResponse.ok) {
      throw new Error(
        `Events returned HTTP ${eventsResponse.status}`
      );
    }

    if (!recommendationsResponse.ok) {
      throw new Error(
        `Recommendations returned HTTP ${recommendationsResponse.status}`
      );
    }

    if (!contextResponse.ok) {
      throw new Error(
        `Context returned HTTP ${contextResponse.status}`
      );
    }

    const [
      eventsPayload,
      recommendationsPayload,
      contextPayload,
    ] = await Promise.all([
      eventsResponse.json(),
      recommendationsResponse.json(),
      contextResponse.json(),
    ]);

    renderMissionTimeline(
      eventsPayload,
      recommendationsPayload,
      contextPayload
    );
  } catch (error) {
    console.error(
      "Unable to load Mission Timeline:",
      error
    );

    renderMissionTimelineError(error);
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = "Refresh";
    }
  }
}


function setupMissionTimeline() {
  byId(
    "missionTimelineRefresh"
  )?.addEventListener(
    "click",
    loadMissionTimeline
  );
}

/* =========================================================
   Mission Timeline Grouping and Noise Suppression
   ========================================================= */

function missionIsWorkerHashrateEvent(event) {
  if (
    event?.entityType !== "worker"
    || event?.eventType !== "resource.state_changed"
  ) {
    return false;
  }

  const changed = missionChangedKeys(event);

  if (!changed.length) {
    return false;
  }

  const workerMetricFields = new Set([
    "currentHashrate",
    "hashrate",
    "sharesPerSecond",
    "acceptedShares",
    "rejectedShares",
    "lastShareAt",
    "lastSeenAt",
    "updatedAt",
  ]);

  return changed.every(
    (key) => workerMetricFields.has(key)
  );
}


function missionIsBlockchainAdvance(event) {
  if (
    event?.entityType !== "blockchain-node"
    || event?.eventType !== "resource.state_changed"
  ) {
    return false;
  }

  const previousHeight = Number(
    event?.previousState?.blockHeight
  );

  const currentHeight = Number(
    event?.currentState?.blockHeight
  );

  return (
    Number.isFinite(previousHeight)
    && Number.isFinite(currentHeight)
    && currentHeight > previousHeight
  );
}


function missionIsRoutineBlockchainTelemetry(
  event
) {
  if (
    event?.entityType !== "blockchain-node"
    || event?.eventType !== "resource.state_changed"
  ) {
    return false;
  }

  if (missionIsBlockchainAdvance(event)) {
    return false;
  }

  const changed = missionChangedKeys(event);

  if (!changed.length) {
    return true;
  }

  const routineFields = new Set([
    "peers",
    "peerCount",
    "connections",
    "mempoolSize",
    "mempoolBytes",
    "mempoolUsage",
    "bestBlockHash",
    "chainWork",
    "difficulty",
    "checkedAt",
    "lastSeenAt",
    "updatedAt",
  ]);

  return changed.every(
    (key) => routineFields.has(key)
  );
}


function missionBlockchainAdvanceGroups(events) {
  const grouped = new Map();

  events
    .filter(missionIsBlockchainAdvance)
    .forEach((event) => {
      const entityId = (
        event.entityId
        || "blockchain-node"
      );

      if (!grouped.has(entityId)) {
        grouped.set(entityId, []);
      }

      grouped.get(entityId).push(event);
    });

  return [...grouped.entries()]
    .map(([entityId, nodeEvents]) => {
      const ordered = [...nodeEvents].sort(
        (left, right) => (
          new Date(
            missionEventTime(left) || 0
          ).getTime()
          - new Date(
            missionEventTime(right) || 0
          ).getTime()
        )
      );

      const first = ordered[0];
      const latest = ordered[
        ordered.length - 1
      ];

      const startingHeight = Number(
        first?.previousState?.blockHeight
      );

      const endingHeight = Number(
        latest?.currentState?.blockHeight
      );

      const blockIncrease = (
        Number.isFinite(startingHeight)
        && Number.isFinite(endingHeight)
      )
        ? endingHeight - startingHeight
        : ordered.length;

      const peers = Number(
        latest?.currentState?.peers
        ?? latest?.currentState?.peerCount
        ?? latest?.currentState?.connections
      );

      const rpcConnected = (
        latest?.currentState?.rpcConnected
      );

      const status = String(
        latest?.currentState?.status || ""
      ).toLowerCase();

      const healthy = (
        rpcConnected !== false
        && status !== "offline"
      );

      let message = (
        `Block height advanced from `
        + `${Number.isFinite(startingHeight)
          ? startingHeight.toLocaleString()
          : "the previous observation"}`
        + ` to `
        + `${Number.isFinite(endingHeight)
          ? endingHeight.toLocaleString()
          : "the latest observation"}`
        + ` across ${ordered.length} observation${
          ordered.length === 1 ? "" : "s"
        }.`
      );

      if (
        Number.isFinite(peers)
        && peers > 0
      ) {
        message += ` Peer connectivity remains healthy at ${peers}.`;
      }

      return {
        kind: "blockchain-summary",
        state: healthy
          ? "success"
          : "warning",
        kicker: "Blockchain",
        title: healthy
          ? "Blockchain node advancing normally"
          : "Blockchain progress requires review",
        message,
        meta: (
          `${entityId} · +${Math.max(
            0,
            blockIncrease
          )} block${
            blockIncrease === 1 ? "" : "s"
          }`
        ),
        occurredAt: missionEventTime(
          latest
        ),
      };
    });
}


function missionOperationalEventKey(event) {
  const type = String(
    event?.eventType || "event"
  );

  const entityType = String(
    event?.entityType || "resource"
  );

  const entityId = String(
    event?.entityId || "unknown"
  );

  const currentStatus = String(
    event?.currentState?.status
    ?? event?.currentState?.connected
    ?? event?.currentState?.rpcConnected
    ?? ""
  );

  return [
    type,
    entityType,
    entityId,
    currentStatus,
  ].join("|");
}


function missionDeduplicateEvents(events) {
  const seen = new Set();

  return events.filter((event) => {
    const key = missionOperationalEventKey(
      event
    );

    if (seen.has(key)) {
      return false;
    }

    seen.add(key);
    return true;
  });
}


function missionOperationalEvents(events) {
  const filtered = events.filter(
    (event) => {
      if (!event || typeof event !== "object") {
        return false;
      }

      if (missionIsWorkerHashrateEvent(event)) {
        return false;
      }

      if (missionIsBlockchainAdvance(event)) {
        return false;
      }

      if (
        missionIsRoutineBlockchainTelemetry(
          event
        )
      ) {
        return false;
      }

      if (missionIsMetricOnlyChange(event)) {
        return false;
      }

      return true;
    }
  );

  return missionDeduplicateEvents(filtered);
}


function missionWorkerPerformanceSummary(
  events
) {
  const recentWorkerEvents = events
    .filter(missionIsWorkerHashrateEvent)
    .sort((left, right) => (
      new Date(
        missionEventTime(right) || 0
      ).getTime()
      - new Date(
        missionEventTime(left) || 0
      ).getTime()
    ));

  if (!recentWorkerEvents.length) {
    return null;
  }

  const newestByWorker = new Map();

  recentWorkerEvents.forEach((event) => {
    const entityId = (
      event.entityId || "worker"
    );

    if (!newestByWorker.has(entityId)) {
      newestByWorker.set(
        entityId,
        event
      );
    }
  });

  const changes = [
    ...newestByWorker.values(),
  ]
    .map((event) => {
      const previousHashrate = Number(
        event?.previousState
          ?.currentHashrate
        ?? event?.previousState?.hashrate
      );

      const currentHashrate = Number(
        event?.currentState
          ?.currentHashrate
        ?? event?.currentState?.hashrate
      );

      const percent = missionPercentChange(
        previousHashrate,
        currentHashrate
      );

      return {
        event,
        previousHashrate,
        currentHashrate,
        percent,
      };
    })
    .filter((change) => (
      change.percent != null
    ));

  if (!changes.length) {
    return null;
  }

  const previousTotal = changes.reduce(
    (sum, change) => (
      sum + change.previousHashrate
    ),
    0
  );

  const currentTotal = changes.reduce(
    (sum, change) => (
      sum + change.currentHashrate
    ),
    0
  );

  const aggregateChange =
    missionPercentChange(
      previousTotal,
      currentTotal
    );

  const latestEvent = changes
    .map((change) => change.event)
    .sort((left, right) => (
      new Date(
        missionEventTime(right) || 0
      ).getTime()
      - new Date(
        missionEventTime(left) || 0
      ).getTime()
    ))[0];

  const significantDecline = (
    aggregateChange != null
    && aggregateChange <= -15
  );

  const significantIncrease = (
    aggregateChange != null
    && aggregateChange >= 10
  );

  let state = "info";
  let title = "Worker output updated";

  if (significantDecline) {
    state = "warning";
    title = "Fleet output decreased";
  } else if (significantIncrease) {
    state = "success";
    title = "Fleet output increased";
  }

  const movementText = (
    aggregateChange == null
      ? "changed"
      : (
          `${aggregateChange > 0 ? "+" : ""}`
          + `${aggregateChange.toFixed(1)}%`
        )
  );

  return {
    kind: "performance-summary",
    state,
    kicker: "Fleet Performance",
    title,
    message:
      `${changes.length} worker${
        changes.length === 1 ? "" : "s"
      } reported recent production changes. `
      + `Combined output ${movementText}.`,
    meta:
      `${changes.length} worker${
        changes.length === 1 ? "" : "s"
      } summarized · ${fmtHashrate(
        currentTotal
      )}`,
    occurredAt: missionEventTime(
      latestEvent
    ),
  };
}


/*
 * Replacement for the original timeline builder.
 *
 * Routine measurements stay in telemetry. The Mission Timeline
 * receives grouped operational meaning.
 */
function buildMissionNarrative(
  eventsPayload,
  recommendationsPayload
) {
  const allEvents = missionEventList(
    eventsPayload
  );

  const operationalEntries =
    missionOperationalEvents(allEvents)
      .slice(0, 8)
      .map(missionDescribeEvent);

  const blockchainEntries =
    missionBlockchainAdvanceGroups(
      allEvents
    );

  const performanceEntry =
    missionWorkerPerformanceSummary(
      allEvents
    );

  const recommendationEntries =
    missionRecommendationList(
      recommendationsPayload
    )
      .slice(0, 3)
      .map(
        missionDescribeRecommendation
      );

  const narrative = [
    ...operationalEntries,
    ...blockchainEntries,
    ...(performanceEntry
      ? [performanceEntry]
      : []),
    ...recommendationEntries,
  ];

  return narrative
    .filter(Boolean)
    .sort((left, right) => (
      new Date(
        right.occurredAt || 0
      ).getTime()
      - new Date(
        left.occurredAt || 0
      ).getTime()
    ))
    .slice(0, 8);
}

/* =========================================================
   PostgreSQL Fleet Forecast
   ========================================================= */

function fleetForecastRollups(payload) {
  return Array.isArray(payload?.metrics)
    ? payload.metrics
    : [];
}


function fleetForecastSeries(
  payload,
  metricName
) {
  return fleetForecastRollups(payload)
    .filter((metric) => (
      String(metric.entityType) === "fleet"
      && String(metric.entityId) === "primary"
      && String(metric.metricName) === metricName
      && Number.isFinite(
        Number(
          metric.lastValue
          ?? metric.averageValue
        )
      )
    ))
    .map((metric) => ({
      timestamp: metric.bucketStart,
      value: Number(
        metric.lastValue
        ?? metric.averageValue
      ),
      minimum: Number(
        metric.minimumValue
        ?? metric.lastValue
      ),
      maximum: Number(
        metric.maximumValue
        ?? metric.lastValue
      ),
      samples: integerValue(
        metric.sampleCount
      ),
    }))
    .filter((point) => point.timestamp)
    .sort((left, right) => (
      new Date(left.timestamp).getTime()
      - new Date(right.timestamp).getTime()
    ));
}


function fleetForecastRegression(series) {
  if (!Array.isArray(series) || series.length < 3) {
    return null;
  }

  const points = series.map(
    (point, index) => ({
      x: index,
      y: Number(point.value),
    })
  );

  const count = points.length;

  const meanX = points.reduce(
    (sum, point) => sum + point.x,
    0
  ) / count;

  const meanY = points.reduce(
    (sum, point) => sum + point.y,
    0
  ) / count;

  let numerator = 0;
  let denominator = 0;

  points.forEach((point) => {
    numerator += (
      (point.x - meanX)
      * (point.y - meanY)
    );

    denominator += (
      (point.x - meanX) ** 2
    );
  });

  const slope = denominator
    ? numerator / denominator
    : 0;

  const intercept = meanY - slope * meanX;

  const predicted = points.map(
    (point) => (
      intercept + slope * point.x
    )
  );

  const residuals = points.map(
    (point, index) => (
      point.y - predicted[index]
    )
  );

  const residualVariance = (
    residuals.reduce(
      (sum, residual) => (
        sum + residual ** 2
      ),
      0
    )
    / Math.max(1, count - 2)
  );

  const residualDeviation = Math.sqrt(
    residualVariance
  );

  const totalVariation = points.reduce(
    (sum, point) => (
      sum + (point.y - meanY) ** 2
    ),
    0
  );

  const unexplainedVariation =
    residuals.reduce(
      (sum, residual) => (
        sum + residual ** 2
      ),
      0
    );

  const rSquared = totalVariation > 0
    ? Math.max(
        0,
        Math.min(
          1,
          1 - (
            unexplainedVariation
            / totalVariation
          )
        )
      )
    : 1;

  const nextX = count;
  const forecast = (
    intercept + slope * nextX
  );

  return {
    count,
    slope,
    intercept,
    forecast,
    residualDeviation,
    rSquared,
    latest: points[count - 1].y,
    average: meanY,
  };
}


function fleetForecastConfidence(
  regression
) {
  if (!regression) {
    return {
      level: "low",
      label: "LOW CONFIDENCE",
      score: 0,
    };
  }

  const sampleFactor = Math.min(
    1,
    regression.count / 24
  );

  const fitFactor = Math.max(
    0.15,
    regression.rSquared
  );

  const score = Math.round(
    sampleFactor
    * fitFactor
    * 100
  );

  if (score >= 70) {
    return {
      level: "high",
      label: "HIGH CONFIDENCE",
      score,
    };
  }

  if (score >= 40) {
    return {
      level: "medium",
      label: "MEDIUM CONFIDENCE",
      score,
    };
  }

  return {
    level: "low",
    label: "LOW CONFIDENCE",
    score,
  };
}


function fleetForecastDirection(
  regression
) {
  if (!regression || regression.latest === 0) {
    return {
      state: "stable",
      label: "Stable",
      percent: 0,
    };
  }

  const percent = (
    regression.slope
    / Math.abs(regression.latest)
    * 100
  );

  if (percent >= 2) {
    return {
      state: "rising",
      label: "Rising",
      percent,
    };
  }

  if (percent <= -2) {
    return {
      state: "falling",
      label: "Falling",
      percent,
    };
  }

  return {
    state: "stable",
    label: "Stable",
    percent,
  };
}


function fleetForecastStability(
  series
) {
  if (!Array.isArray(series) || series.length < 2) {
    return {
      label: "Collecting",
      variation: null,
      state: "warning",
    };
  }

  const values = series.map(
    (point) => Number(point.value)
  );

  const average = values.reduce(
    (sum, value) => sum + value,
    0
  ) / values.length;

  const variance = values.reduce(
    (sum, value) => (
      sum + (value - average) ** 2
    ),
    0
  ) / values.length;

  const deviation = Math.sqrt(variance);

  const coefficient = average
    ? deviation / Math.abs(average) * 100
    : 0;

  if (coefficient <= 8) {
    return {
      label: "Highly stable",
      variation: coefficient,
      state: "healthy",
    };
  }

  if (coefficient <= 20) {
    return {
      label: "Normal variation",
      variation: coefficient,
      state: "healthy",
    };
  }

  return {
    label: "Volatile",
    variation: coefficient,
    state: "warning",
  };
}


function fleetForecastGeometry(
  series,
  regression
) {
  if (
    !Array.isArray(series)
    || series.length < 2
    || !regression
  ) {
    return null;
  }

  const width = 640;
  const height = 120;
  const paddingX = 6;
  const paddingY = 10;

  const historyValues = series.map(
    (point) => Number(point.value)
  );

  const rangePadding = (
    regression.residualDeviation * 1.96
  );

  const lowForecast = Math.max(
    0,
    regression.forecast - rangePadding
  );

  const highForecast = (
    regression.forecast + rangePadding
  );

  const allValues = [
    ...historyValues,
    lowForecast,
    highForecast,
  ];

  let minimum = Math.min(...allValues);
  let maximum = Math.max(...allValues);

  if (minimum === maximum) {
    minimum -= 1;
    maximum += 1;
  }

  const usableWidth = width - paddingX * 2;
  const usableHeight = height - paddingY * 2;

  const totalPoints = series.length + 1;

  function coordinates(index, value) {
    const x = (
      paddingX
      + (
        index
        / Math.max(1, totalPoints - 1)
      ) * usableWidth
    );

    const ratio = (
      (value - minimum)
      / (maximum - minimum)
    );

    const y = (
      height
      - paddingY
      - ratio * usableHeight
    );

    return { x, y };
  }

  const historyPoints = historyValues.map(
    (value, index) => (
      coordinates(index, value)
    )
  );

  const latestPoint = historyPoints[
    historyPoints.length - 1
  ];

  const forecastPoint = coordinates(
    series.length,
    regression.forecast
  );

  const lowPoint = coordinates(
    series.length,
    lowForecast
  );

  const highPoint = coordinates(
    series.length,
    highForecast
  );

  const historyPath = historyPoints
    .map((point, index) => (
      `${index === 0 ? "M" : "L"}`
      + `${point.x.toFixed(2)},`
      + `${point.y.toFixed(2)}`
    ))
    .join(" ");

  const projectionPath = (
    `M${latestPoint.x.toFixed(2)},`
    + `${latestPoint.y.toFixed(2)} `
    + `L${forecastPoint.x.toFixed(2)},`
    + `${forecastPoint.y.toFixed(2)}`
  );

  const bandPath = [
    `M${latestPoint.x.toFixed(2)},${latestPoint.y.toFixed(2)}`,
    `L${highPoint.x.toFixed(2)},${highPoint.y.toFixed(2)}`,
    `L${lowPoint.x.toFixed(2)},${lowPoint.y.toFixed(2)}`,
    "Z",
  ].join(" ");

  return {
    width,
    height,
    historyPath,
    projectionPath,
    bandPath,
    forecastPoint,
    lowForecast,
    highForecast,
  };
}


function fleetForecastChart(
  series,
  regression
) {
  const geometry = fleetForecastGeometry(
    series,
    regression
  );

  if (!geometry) {
    return `
      <div class="metric-trend-empty">
        Additional rollup samples are required
      </div>
    `;
  }

  return `
    <svg
      class="fleet-forecast-chart"
      viewBox="0 0 ${geometry.width} ${geometry.height}"
      preserveAspectRatio="none"
      role="img"
      aria-label="Fleet hashrate forecast"
    >
      <line
        class="fleet-forecast-chart-grid"
        x1="0"
        y1="40"
        x2="${geometry.width}"
        y2="40"
      ></line>

      <line
        class="fleet-forecast-chart-grid"
        x1="0"
        y1="80"
        x2="${geometry.width}"
        y2="80"
      ></line>

      <path
        class="fleet-forecast-chart-band"
        d="${geometry.bandPath}"
      ></path>

      <path
        class="fleet-forecast-chart-history"
        d="${geometry.historyPath}"
      ></path>

      <path
        class="fleet-forecast-chart-projection"
        d="${geometry.projectionPath}"
      ></path>

      <circle
        class="fleet-forecast-chart-point"
        cx="${geometry.forecastPoint.x.toFixed(2)}"
        cy="${geometry.forecastPoint.y.toFixed(2)}"
        r="4"
      ></circle>
    </svg>
  `;
}


function fleetForecastHealthOutlook(
  payload
) {
  const series = fleetForecastSeries(
    payload,
    "fleet_health"
  );

  const latest = series.length
    ? series[series.length - 1].value
    : null;

  const minimum = series.length
    ? Math.min(
        ...series.map((point) => point.value)
      )
    : null;

  if (latest == null) {
    return {
      state: "warning",
      title: "Health history collecting",
      detail:
        "More fleet-health rollups are required.",
    };
  }

  if (latest >= 95 && minimum >= 90) {
    return {
      state: "healthy",
      title: "Healthy outlook",
      detail:
        `Fleet health is ${latest.toFixed(1)}% `
        + `with a ${minimum.toFixed(1)}% window minimum.`,
    };
  }

  return {
    state: "warning",
    title: "Health variability detected",
    detail:
      `Fleet health is ${latest.toFixed(1)}% `
      + `with a ${minimum.toFixed(1)}% window minimum.`,
  };
}


function renderFleetForecast(payload) {
  const body = byId("fleetForecastBody");
  const confidenceBadge = byId(
    "fleetForecastConfidence"
  );
  const subtitle = byId(
    "fleetForecastSubtitle"
  );
  const source = byId(
    "fleetForecastSource"
  );
  const updated = byId(
    "fleetForecastUpdated"
  );

  if (
    !body
    || !confidenceBadge
    || !subtitle
    || !source
    || !updated
  ) {
    return;
  }

  const hashrateSeries = fleetForecastSeries(
    payload,
    "fleet_hashrate"
  ).slice(-24);

  const regression = fleetForecastRegression(
    hashrateSeries
  );

  const confidence =
    fleetForecastConfidence(
      regression
    );

  confidenceBadge.className = (
    `fleet-forecast-confidence ${confidence.level}`
  );

  confidenceBadge.textContent = (
    `${confidence.label} · ${confidence.score}%`
  );

  source.textContent = (
    payload?.source
    || "nexus-postgresql-telemetry"
  );

  const latestTimestamp = hashrateSeries[
    hashrateSeries.length - 1
  ]?.timestamp;

  updated.textContent = latestTimestamp
    ? `Latest rollup ${priorityAge(latestTimestamp)}`
    : "No rollups available";

  if (!regression) {
    subtitle.textContent = (
      "Waiting for enough PostgreSQL rollups "
      + "to calculate a reliable forecast."
    );

    body.innerHTML = `
      <div class="home-v2-empty">
        At least three fleet-hashrate rollups are required.
      </div>
    `;

    return;
  }

  const direction = fleetForecastDirection(
    regression
  );

  const stability = fleetForecastStability(
    hashrateSeries
  );

  const healthOutlook =
    fleetForecastHealthOutlook(
      payload
    );

  const rangePadding = (
    regression.residualDeviation * 1.96
  );

  const lowForecast = Math.max(
    0,
    regression.forecast - rangePadding
  );

  const highForecast = (
    regression.forecast + rangePadding
  );

  subtitle.textContent = (
    "Statistical next-hour outlook derived from "
    + `${hashrateSeries.length} PostgreSQL rollups.`
  );

  body.innerHTML = `
    <div class="fleet-forecast-primary">
      <div class="fleet-forecast-primary-top">
        <div>
          <div class="fleet-forecast-label">
            Expected Next-Hour Hashrate
          </div>

          <div class="fleet-forecast-value">
            ${escapeHtml(
              fmtHashrate(
                Math.max(
                  0,
                  regression.forecast
                )
              )
            )}
          </div>

          <div class="fleet-forecast-range">
            Expected range:
            ${escapeHtml(
              fmtHashrate(lowForecast)
            )}
            –
            ${escapeHtml(
              fmtHashrate(highForecast)
            )}
          </div>
        </div>

        <span class="fleet-forecast-direction ${escapeHtml(
          direction.state
        )}">
          ${direction.state === "rising"
            ? "↑"
            : direction.state === "falling"
              ? "↓"
              : "→"}
          ${escapeHtml(direction.label)}
        </span>
      </div>

      ${fleetForecastChart(
        hashrateSeries,
        regression
      )}

      <div class="fleet-forecast-stats">
        <div class="fleet-forecast-stat">
          <div class="fleet-forecast-stat-label">
            Current
          </div>

          <div class="fleet-forecast-stat-value">
            ${escapeHtml(
              fmtHashrate(
                regression.latest
              )
            )}
          </div>
        </div>

        <div class="fleet-forecast-stat">
          <div class="fleet-forecast-stat-label">
            Window Average
          </div>

          <div class="fleet-forecast-stat-value">
            ${escapeHtml(
              fmtHashrate(
                regression.average
              )
            )}
          </div>
        </div>

        <div class="fleet-forecast-stat">
          <div class="fleet-forecast-stat-label">
            Per-Bucket Trend
          </div>

          <div class="fleet-forecast-stat-value">
            ${direction.percent > 0 ? "+" : ""}
            ${direction.percent.toFixed(2)}%
          </div>
        </div>
      </div>
    </div>

    <div class="fleet-forecast-side">
      <div class="fleet-forecast-card ${escapeHtml(
        stability.state
      )}">
        <div class="fleet-forecast-card-label">
          Production Stability
        </div>

        <div class="fleet-forecast-card-value">
          ${escapeHtml(stability.label)}
        </div>

        <div class="fleet-forecast-card-detail">
          ${stability.variation == null
            ? "More samples are required."
            : `${stability.variation.toFixed(1)}% variation across the forecast window.`}
        </div>
      </div>

      <div class="fleet-forecast-card ${escapeHtml(
        healthOutlook.state
      )}">
        <div class="fleet-forecast-card-label">
          Health Outlook
        </div>

        <div class="fleet-forecast-card-value">
          ${escapeHtml(
            healthOutlook.title
          )}
        </div>

        <div class="fleet-forecast-card-detail">
          ${escapeHtml(
            healthOutlook.detail
          )}
        </div>
      </div>

      <div class="fleet-forecast-card">
        <div class="fleet-forecast-card-label">
          Forecast Quality
        </div>

        <div class="fleet-forecast-card-value">
          ${confidence.score}% confidence
        </div>

        <div class="fleet-forecast-card-detail">
          ${hashrateSeries.length} rollups analyzed ·
          ${(regression.rSquared * 100).toFixed(1)}%
          trend fit.
        </div>
      </div>
    </div>
  `;
}


function renderFleetForecastError(error) {
  const body = byId("fleetForecastBody");
  const confidence = byId(
    "fleetForecastConfidence"
  );

  if (confidence) {
    confidence.className =
      "fleet-forecast-confidence low";

    confidence.textContent =
      "FORECAST UNAVAILABLE";
  }

  if (body) {
    body.innerHTML = `
      <div class="home-v2-empty">
        Unable to build fleet forecast:
        ${escapeHtml(
          error?.message || error
        )}
      </div>
    `;
  }
}


async function loadFleetForecast() {
  const button = byId(
    "fleetForecastRefresh"
  );

  if (button) {
    button.disabled = true;
    button.textContent = "Calculating...";
  }

  try {
    const response = await fetch(
      "/api/platform/metrics/rollups",
      {
        cache: "no-store",
        headers: {
          Accept: "application/json",
        },
      }
    );

    if (!response.ok) {
      throw new Error(
        `Metric rollups returned HTTP ${response.status}`
      );
    }

    const payload = await response.json();

    homeV2State.fleetForecast = payload;

    renderFleetForecast(payload);
  } catch (error) {
    console.error(
      "Unable to load Fleet Forecast:",
      error
    );

    renderFleetForecastError(error);
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = "Refresh";
    }
  }
}


function setupFleetForecast() {
  byId(
    "fleetForecastRefresh"
  )?.addEventListener(
    "click",
    loadFleetForecast
  );
}
