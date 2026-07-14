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
      "/api/fleet/home",
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

    renderFleet(fleet);
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
    loadFleet();
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

      return (
        severity === "critical"
        || severity === "warning"
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
