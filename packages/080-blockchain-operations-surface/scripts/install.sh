#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

STAMP="$(date -u +%Y%m%d-%H%M%S)"
BACKUP="backups/pkg080-$STAMP"

mkdir -p "$BACKUP"

echo "===== PACKAGE 080 INSTALL ====="

cp backend/api/server.py "$BACKUP/server.py"
cp backend/modules/blockchain_management.py "$BACKUP/blockchain_management.py"
cp frontend/js/nav.js "$BACKUP/nav.js"

echo "Backup: $BACKUP"

python3 - <<'PATCHCHECK'
from pathlib import Path

server = Path("backend/api/server.py").read_text()

required = [
    '"/api/blockchain/nodes": blockchain.nodes,',
    '"/api/blockchain/catalog": blockchain_management.catalog,',
    "def json_response(",
    "def _send_json(",
]

missing = [item for item in required if item not in server]

if missing:
    raise SystemExit(
        "ERROR: expected Nexus API contract missing: "
        + ", ".join(missing)
    )

print("PASS: Nexus blockchain route contract")
print("PASS: Nexus JSON response contract")
PATCHCHECK

cat > backend/services/blockchain_operations_service.py <<'SERVICEPY'
from __future__ import annotations

from typing import Any

from backend.db.connection import get_connection


def _rows(cursor) -> list[dict[str, Any]]:
    return [dict(row) for row in cursor.fetchall()]


def get_blockchain_operations() -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    n.node_id,
                    n.asset_id,
                    n.coin,
                    n.network,
                    n.implementation,
                    n.version,
                    n.status,
                    n.sync_status,
                    n.block_height,
                    n.header_height,
                    n.peer_count,
                    n.observed_state,
                    n.updated_at,
                    n.last_seen_at,
                    a.name,
                    n.ip_address,
                    a.lifecycle_status,
                    a.health_state AS health,
                    a.connectivity_state AS connectivity
                FROM nexus.blockchain_nodes n
                LEFT JOIN nexus.assets a
                  ON a.asset_id = n.asset_id
                ORDER BY n.coin, n.asset_id
                """
            )
            nodes = _rows(cur)

            asset_ids = [
                row["asset_id"]
                for row in nodes
                if row.get("asset_id")
            ]

            metrics_by_asset: dict[str, dict[str, dict[str, Any]]] = {}

            if asset_ids:
                cur.execute(
                    """
                    SELECT
                        subject_id,
                        metric_name,
                        metric_value,
                        metric_unit,
                        status,
                        observed_at
                    FROM nexus.current_metrics
                    WHERE subject_id = ANY(%s)
                    ORDER BY subject_id, metric_name
                    """,
                    (asset_ids,),
                )

                for row in _rows(cur):
                    metrics_by_asset.setdefault(
                        row["subject_id"],
                        {},
                    )[row["metric_name"]] = row

            manager_by_runtime: dict[str, dict[str, Any]] = {}

            if asset_ids:
                cur.execute(
                    """
                    SELECT
                        r.source_id AS manager_asset_id,
                        r.target_id AS runtime_asset_id,
                        r.status,
                        r.last_seen_at,
                        a.name AS manager_name
                    FROM nexus.relationships r
                    LEFT JOIN nexus.assets a
                      ON a.asset_id = r.source_id
                    WHERE r.relationship_type = 'manages'
                      AND r.target_id = ANY(%s)
                      AND r.status = 'active'
                    ORDER BY r.last_seen_at DESC NULLS LAST
                    """,
                    (asset_ids,),
                )

                for row in _rows(cur):
                    manager_by_runtime.setdefault(
                        row["runtime_asset_id"],
                        row,
                    )

    items: list[dict[str, Any]] = []

    for node in nodes:
        asset_id = node["asset_id"]
        metrics = metrics_by_asset.get(asset_id, {})

        def metric(name: str):
            value = metrics.get(name)
            return value.get("metric_value") if value else None

        sync_progress = metric("sync_progress")

        rpc_reachable = metric("runtime.rpc.reachable")
        if rpc_reachable is None:
            rpc_reachable = metric("rpc_reachable")

        rpc_healthy = metric("runtime.rpc.healthy")
        running = metric("running")
        ibd = metric("runtime.initial_block_download")

        if ibd is None:
            ibd = metric("initial_block_download")

        state = str(
            node.get("sync_status")
            or node.get("status")
            or "unknown"
        ).lower()

        # Canonical live-runtime precedence.
        if running == 0:
            state = "stopped"
        elif ibd == 1 and rpc_reachable == 1:
            state = "syncing"
        elif running == 1 and rpc_healthy == 1:
            state = "running"

        items.append(
            {
                "nodeId": node.get("node_id"),
                "assetId": asset_id,
                "name": (
                    node.get("name")
                    or node.get("implementation")
                    or asset_id
                ),
                "coin": node.get("coin"),
                "network": node.get("network"),
                "implementation": node.get("implementation"),
                "version": node.get("version"),
                "state": state,
                "nodeStatus": node.get("status"),
                "syncStatus": node.get("sync_status"),
                "syncProgress": sync_progress,
                "blockHeight": node.get("block_height"),
                "headerHeight": node.get("header_height"),
                "peerCount": node.get("peer_count"),
                "rpcReachable": (
                    None
                    if rpc_reachable is None
                    else bool(rpc_reachable)
                ),
                "rpcHealthy": (
                    None
                    if rpc_healthy is None
                    else bool(rpc_healthy)
                ),
                "running": (
                    None
                    if running is None
                    else bool(running)
                ),
                "initialBlockDownload": (
                    None
                    if ibd is None
                    else bool(ibd)
                ),
                "ipAddress": node.get("ip_address"),
                "lifecycleStatus": node.get("lifecycle_status"),
                "health": node.get("health"),
                "connectivity": node.get("connectivity"),
                "manager": manager_by_runtime.get(asset_id),
                "lastSeenAt": node.get("last_seen_at"),
                "updatedAt": node.get("updated_at"),
            }
        )

    return {
        "status": "ok",
        "source": "nexus-postgresql-platform",
        "count": len(items),
        "syncing": sum(
            1 for item in items
            if item["state"] == "syncing"
        ),
        "running": sum(
            1 for item in items
            if item["state"] == "running"
        ),
        "warning": sum(
            1 for item in items
            if item["state"] in {"warning", "degraded"}
        ),
        "offline": sum(
            1 for item in items
            if item["state"] in {
                "offline",
                "stopped",
                "error",
            }
        ),
        "items": items,
    }
SERVICEPY

echo "PASS: blockchain operations service installed"

python3 - <<'PATCHMODULE'
from pathlib import Path

path = Path("backend/modules/blockchain_management.py")
text = path.read_text()

import_line = (
    "from backend.services import "
    "blockchain_operations_service\n"
)

anchor = (
    "from backend.services import "
    "blockchain_management_service\n"
)

if import_line not in text:
    if anchor not in text:
        raise SystemExit(
            "ERROR: blockchain_management_service import not found"
        )

    text = text.replace(
        anchor,
        anchor + import_line,
        1,
    )

function = """
def operations(
    _query: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    return blockchain_operations_service.get_blockchain_operations()
"""

if "def operations(" not in text:
    text = text.rstrip() + "\n\n\n" + function.strip() + "\n"

path.write_text(text)

print("PASS: blockchain management operations adapter installed")
PATCHMODULE

python3 - <<'PATCHSERVER'
from pathlib import Path

path = Path("backend/api/server.py")
text = path.read_text()

api_entry = (
    '            "/api/blockchain/operations": '
    'blockchain_management.operations,\n'
)

api_anchor = (
    '            "/api/blockchain/catalog": '
    'blockchain_management.catalog,\n'
)

if api_entry not in text:
    if api_anchor not in text:
        raise SystemExit(
            "ERROR: blockchain catalog API route not found"
        )

    text = text.replace(
        api_anchor,
        api_anchor + api_entry,
        1,
    )

html_route = '''        if self.path == "/blockchain.html":
            return self._send_file(
                "frontend/blockchain.html",
                "text/html",
            )
'''

html_anchor = '''        if self.path == "/assets.html":
            return self._send_file("frontend/assets.html", "text/html")
'''

if html_route not in text:
    if html_anchor not in text:
        raise SystemExit(
            "ERROR: assets static route anchor not found"
        )

    text = text.replace(
        html_anchor,
        html_anchor + html_route,
        1,
    )

path.write_text(text)

print("PASS: blockchain API route installed")
print("PASS: blockchain page static route installed")
PATCHSERVER

python3 - <<'PATCHNAV'
from pathlib import Path

path = Path("frontend/js/nav.js")
text = path.read_text()

entry = (
    '  { label: "Blockchain", href: "/blockchain.html", '
    'routes: ["/blockchain.html"] },\n'
)

anchor = (
    '  { label: "CMDB", href: "/assets.html", '
    'routes: ["/assets.html", "/cmdb-object.html"] },\n'
)

if entry not in text:
    if anchor not in text:
        raise SystemExit(
            "ERROR: CMDB navigation anchor not found"
        )

    text = text.replace(
        anchor,
        anchor + entry,
        1,
    )

path.write_text(text)

print("PASS: Blockchain primary navigation entry installed")
PATCHNAV

cat > frontend/blockchain.html <<'HTML080'
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta
    name="viewport"
    content="width=device-width,initial-scale=1"
  >
  <title>Blockchain Operations · Nexus</title>

  <link rel="stylesheet" href="/css/style.css">
  <link rel="stylesheet" href="/css/blockchain.css">
</head>
<body>
  <header class="topbar">
    <div>
      <h1>Nexus Command Center</h1>
      <p>Blockchain Operations</p>
    </div>

    <nav id="topNav"></nav>
  </header>

  <main class="page-shell blockchain-page">
    <section class="blockchain-header">
      <div>
        <p class="cmdb-eyebrow">Blockchain Operations</p>
        <h1>Blockchain</h1>
        <p>
          Canonical runtime state, synchronization, RPC health,
          and management relationships across blockchain nodes.
        </p>
      </div>

      <div
        id="blockchainSourceState"
        class="cmdb-source-state"
      >
        Loading canonical state…
      </div>
    </section>

    <section
      id="blockchainSummary"
      class="blockchain-summary"
    ></section>

    <section class="blockchain-panel">
      <div class="blockchain-panel-heading">
        <div>
          <span>Managed runtimes</span>
          <h2>Blockchain Nodes</h2>
        </div>

        <button id="refreshBlockchain" type="button">
          Refresh
        </button>
      </div>

      <div
        id="blockchainNodes"
        class="blockchain-grid"
      >
        <div class="blockchain-empty">
          Loading blockchain runtimes…
        </div>
      </div>
    </section>
  </main>

  <script src="/js/nav.js"></script>
  <script src="/js/blockchain.js"></script>
</body>
</html>
HTML080

cat > frontend/css/blockchain.css <<'CSS080'
.blockchain-page{display:grid;gap:18px}
.blockchain-header,.blockchain-panel{border:1px solid rgba(96,165,250,.2);border-radius:18px;background:linear-gradient(145deg,rgba(9,28,53,.95),rgba(5,17,34,.96))}
.blockchain-header{display:flex;justify-content:space-between;align-items:flex-start;gap:24px;padding:24px}
.blockchain-header h1{margin:4px 0 8px}
.blockchain-header p:last-child{max-width:760px;color:#8fa9c4}
.blockchain-summary{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}
.blockchain-summary-card{padding:17px;border:1px solid rgba(96,165,250,.16);border-radius:15px;background:rgba(8,24,45,.92)}
.blockchain-summary-card span{display:block;color:#7899b8;font-size:.68rem;text-transform:uppercase;letter-spacing:.08em}
.blockchain-summary-card strong{display:block;margin-top:7px;font-size:1.7rem}
.blockchain-panel{padding:20px}
.blockchain-panel-heading{display:flex;justify-content:space-between;align-items:center;margin-bottom:17px}
.blockchain-panel-heading span{color:#65d7ef;font-size:.68rem;text-transform:uppercase;letter-spacing:.08em}
.blockchain-panel-heading h2{margin:4px 0 0}
.blockchain-panel-heading button{padding:9px 13px;border:1px solid rgba(96,165,250,.28);border-radius:10px;background:rgba(37,99,235,.12);color:#b9dcff;cursor:pointer}
.blockchain-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.blockchain-node{padding:18px;border:1px solid rgba(96,165,250,.16);border-radius:16px;background:rgba(3,14,29,.62)}
.blockchain-node-head{display:flex;justify-content:space-between;gap:14px}
.blockchain-node-head h3{margin:4px 0 0}
.blockchain-coin{color:#65d7ef;font-size:.68rem;font-weight:900;text-transform:uppercase;letter-spacing:.08em}
.blockchain-state{height:fit-content;padding:6px 9px;border-radius:999px;font-size:.68rem;font-weight:900;text-transform:uppercase}
.blockchain-state.running,.blockchain-state.synchronized{color:#86efac;background:rgba(34,197,94,.14)}
.blockchain-state.syncing{color:#7dd3fc;background:rgba(14,165,233,.14)}
.blockchain-state.warning,.blockchain-state.degraded,.blockchain-state.unknown{color:#fde68a;background:rgba(250,204,21,.14)}
.blockchain-state.offline,.blockchain-state.stopped,.blockchain-state.error{color:#fda4af;background:rgba(244,63,94,.14)}
.blockchain-progress{margin:17px 0}
.blockchain-progress-head{display:flex;justify-content:space-between;gap:12px;margin-bottom:7px;color:#8fa9c4;font-size:.74rem}
.blockchain-progress-track{height:8px;overflow:hidden;border-radius:999px;background:rgba(148,163,184,.13)}
.blockchain-progress-bar{height:100%;border-radius:inherit;background:#38bdf8}
.blockchain-facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}
.blockchain-fact{padding:11px;border:1px solid rgba(96,165,250,.1);border-radius:10px;background:rgba(2,10,22,.48)}
.blockchain-fact span{display:block;color:#6889a8;font-size:.64rem;text-transform:uppercase;letter-spacing:.06em}
.blockchain-fact strong{display:block;margin-top:5px;overflow-wrap:anywhere}
.blockchain-actions{display:flex;gap:9px;margin-top:15px}
.blockchain-actions a{padding:9px 11px;border:1px solid rgba(96,165,250,.2);border-radius:9px;color:#9fd0ff;text-decoration:none;font-size:.76rem;font-weight:800}
.blockchain-empty{grid-column:1/-1;padding:30px;text-align:center;color:#7899b8}
@media(max-width:980px){.blockchain-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.blockchain-grid{grid-template-columns:1fr}}
@media(max-width:650px){.blockchain-header{flex-direction:column}.blockchain-summary{grid-template-columns:1fr}.blockchain-facts{grid-template-columns:1fr}}
CSS080

cat > frontend/js/blockchain.js <<'JS080'
"use strict";

function blockchainEscape(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function blockchainValue(value, fallback = "—") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }

  return value;
}

function blockchainPercent(value) {
  const number = Number(value);

  if (!Number.isFinite(number)) {
    return null;
  }

  return Math.max(0, Math.min(100, number));
}

function renderBlockchainSummary(payload) {
  const root = document.getElementById("blockchainSummary");

  if (!root) return;

  const cards = [
    ["Nodes", payload.count ?? 0],
    ["Running", payload.running ?? 0],
    ["Syncing", payload.syncing ?? 0],
    ["Warning", payload.warning ?? 0],
    ["Offline", payload.offline ?? 0]
  ];

  root.innerHTML = cards.map(([label, value]) => `
    <article class="blockchain-summary-card">
      <span>${label}</span>
      <strong>${value}</strong>
    </article>
  `).join("");
}

function renderBlockchainNode(node) {
  const progress = blockchainPercent(node.syncProgress);
  const state = String(node.state || "unknown").toLowerCase();

  const progressMarkup = progress === null ? "" : `
    <div class="blockchain-progress">
      <div class="blockchain-progress-head">
        <span>Synchronization</span>
        <strong>${progress.toFixed(2)}%</strong>
      </div>
      <div class="blockchain-progress-track">
        <div
          class="blockchain-progress-bar"
          style="width:${progress}%"
        ></div>
      </div>
    </div>
  `;

  const rpc =
    node.rpcReachable === true
      ? (
          node.rpcHealthy === false
            ? "Reachable · degraded"
            : "Healthy"
        )
      : (
          node.rpcReachable === false
            ? "Unreachable"
            : "Unknown"
        );

  const manager =
    node.manager?.manager_name
    || node.manager?.managerName
    || "—";

  return `
    <article class="blockchain-node">
      <div class="blockchain-node-head">
        <div>
          <span class="blockchain-coin">
            ${blockchainEscape(node.coin || "Blockchain")}
            ·
            ${blockchainEscape(node.network || "unknown")}
          </span>
          <h3>${blockchainEscape(node.name)}</h3>
        </div>

        <span class="blockchain-state ${blockchainEscape(state)}">
          ${blockchainEscape(state)}
        </span>
      </div>

      ${progressMarkup}

      <div class="blockchain-facts">
        <div class="blockchain-fact">
          <span>Block Height</span>
          <strong>${blockchainValue(node.blockHeight)}</strong>
        </div>

        <div class="blockchain-fact">
          <span>Header Height</span>
          <strong>${blockchainValue(node.headerHeight)}</strong>
        </div>

        <div class="blockchain-fact">
          <span>Peers</span>
          <strong>${blockchainValue(node.peerCount)}</strong>
        </div>

        <div class="blockchain-fact">
          <span>RPC</span>
          <strong>${blockchainEscape(rpc)}</strong>
        </div>

        <div class="blockchain-fact">
          <span>Host</span>
          <strong>${blockchainEscape(
            blockchainValue(node.ipAddress)
          )}</strong>
        </div>

        <div class="blockchain-fact">
          <span>Managed By</span>
          <strong>${blockchainEscape(manager)}</strong>
        </div>
      </div>

      <div class="blockchain-actions">
        <a
          href="/cmdb-object.html?id=${encodeURIComponent(node.assetId)}"
        >
          Digital Twin
        </a>

        <a
          href="/operations-center.html?target=${encodeURIComponent(
            node.assetId
          )}"
        >
          Operations
        </a>
      </div>
    </article>
  `;
}

function renderBlockchainNodes(payload) {
  const root = document.getElementById("blockchainNodes");

  if (!root) return;

  const items = payload.items || [];

  if (!items.length) {
    root.innerHTML = `
      <div class="blockchain-empty">
        No canonical blockchain nodes found.
      </div>
    `;
    return;
  }

  root.innerHTML = items.map(renderBlockchainNode).join("");
}

async function loadBlockchainOperations() {
  const source =
    document.getElementById("blockchainSourceState");

  try {
    if (source) {
      source.textContent = "Refreshing canonical state…";
      source.classList.remove("warning");
    }

    const response = await fetch(
      "/api/blockchain/operations",
      { cache: "no-store" }
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();

    renderBlockchainSummary(payload);
    renderBlockchainNodes(payload);

    if (source) {
      source.textContent = "PostgreSQL CMDB · authoritative";
    }
  } catch (error) {
    if (source) {
      source.textContent = `Unable to load: ${error.message}`;
      source.classList.add("warning");
    }

    const root = document.getElementById("blockchainNodes");

    if (root) {
      root.innerHTML = `
        <div class="blockchain-empty">
          Blockchain operations data is unavailable.
        </div>
      `;
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  document
    .getElementById("refreshBlockchain")
    ?.addEventListener(
      "click",
      loadBlockchainOperations
    );

  loadBlockchainOperations();
});
JS080

python3 -m py_compile \
  backend/services/blockchain_operations_service.py \
  backend/modules/blockchain_management.py \
  backend/api/server.py

echo "PASS: Python syntax"
echo "PASS: Package 080 installed"
