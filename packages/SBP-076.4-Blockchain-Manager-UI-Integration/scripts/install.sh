#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

HTML="frontend/blockchain.html"
JS="frontend/js/blockchain.js"
CSS="frontend/css/blockchain.css"

BACKUP_DIR="packages/SBP-076.4-Blockchain-Manager-UI-Integration/backups"
mkdir -p "$BACKUP_DIR"

cp "$HTML" "$BACKUP_DIR/blockchain.html"
cp "$JS" "$BACKUP_DIR/blockchain.js"
cp "$CSS" "$BACKUP_DIR/blockchain.css"

python3 - <<'PY'
from pathlib import Path

html_path = Path("frontend/blockchain.html")
js_path = Path("frontend/js/blockchain.js")
css_path = Path("frontend/css/blockchain.css")

html = html_path.read_text()

html = html.replace(
    '<main class="container blockchain-page">',
    '<main class="container nexus-page-shell blockchain-page">'
)

html = html.replace(
    """<span>Managed Nodes</span>
        <strong id="blockchainManagedCount">—</strong>
        <small>Canonical CMDB runtimes</small>""",
    """<span>Blockchain Runtimes</span>
        <strong id="blockchainManagedCount">—</strong>
        <small>Canonical CMDB blockchain nodes</small>"""
)

html = html.replace(
    """<span>Running</span>
        <strong id="blockchainRunningCount">—</strong>
        <small>Operational runtimes</small>""",
    """<span>Operational</span>
        <strong id="blockchainRunningCount">—</strong>
        <small>Running or online nodes</small>"""
)

html = html.replace(
    "<h2>Managed Blockchains</h2>",
    "<h2>Blockchain Runtimes</h2>"
)

html = html.replace(
    "Canonical blockchain runtimes currently known to Nexus.",
    "Canonical blockchain nodes currently known to Nexus, including Seymour-managed and independently discovered runtimes."
)

start = html.index(
    '        <div\n'
    '          id="blockchainCatalogFilters"'
)

end_marker = """        </div>

        <input
          id="blockchainCatalogSearch\""""

end = html.index(end_marker, start)

replacement = """        <div
          id="blockchainCatalogFilters"
          class="blockchain-catalog-filters"
        >
          <button
            type="button"
            class="active"
            data-filter="all"
          >
            All
          </button>
        </div>

        <input
          id="blockchainCatalogSearch\""""

html = html[:start] + replacement + html[end + len(end_marker):]

html_path.write_text(html)


js = js_path.read_text()

js = js.replace(
    """    if (["running", "healthy"].includes(state)) {
      return "running";
    }""",
    """    if (["running", "online", "healthy"].includes(state)) {
      return "running";
    }"""
)

js = js.replace(
    """    const manager = node.manager?.manager_name || "—";""",
    """    const manager = node.manager?.manager_name || "Independent / discovered";
    const ownership = node.manager
      ? "Seymour managed"
      : "Discovered";"""
)

js = js.replace(
    """          <div>
            <dt>Managed by</dt>
            <dd>${escapeHtml(manager)}</dd>
          </div>""",
    """          <div>
            <dt>Ownership</dt>
            <dd>${escapeHtml(ownership)}</dd>
          </div>

          <div>
            <dt>Managed by</dt>
            <dd>${escapeHtml(manager)}</dd>
          </div>"""
)

catalog_anchor = """  function renderCatalog() {"""

catalog_helper = """  function renderCatalogFilters() {
    const container = $("blockchainCatalogFilters");

    if (!container) {
      return;
    }

    const providersByCoin = new Map();

    catalog.forEach((provider) => {
      const coin = String(provider.coin || "").trim();

      if (!coin || providersByCoin.has(coin)) {
        return;
      }

      providersByCoin.set(
        coin,
        provider.name || provider.implementation || coin
      );
    });

    const buttons = [
      `
        <button
          type="button"
          class="${activeFilter === "all" ? "active" : ""}"
          data-filter="all"
        >
          All
        </button>
      `,
      ...Array.from(providersByCoin.entries())
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([coin, name]) => `
          <button
            type="button"
            class="${activeFilter === coin ? "active" : ""}"
            data-filter="${escapeHtml(coin)}"
          >
            ${escapeHtml(name)}
          </button>
        `),
    ];

    container.innerHTML = buttons.join("");
  }


"""

if catalog_anchor not in js:
    raise RuntimeError("renderCatalog anchor not found")

js = js.replace(
    catalog_anchor,
    catalog_helper + catalog_anchor,
    1
)

js = js.replace(
    """    $("blockchainManagedCount").textContent = items.length;
    $("blockchainRunningCount").textContent =
      items.filter((item) => item.state === "running").length;""",
    """    $("blockchainManagedCount").textContent = items.length;
    $("blockchainRunningCount").textContent =
      items.filter(
        (item) => ["running", "online"].includes(item.state)
      ).length;"""
)

js = js.replace(
    """      items.filter(
        (item) => !["running", "syncing"].includes(item.state)
      ).length;""",
    """      items.filter(
        (item) =>
          !["running", "online", "syncing"].includes(item.state)
      ).length;"""
)

js = js.replace(
    """    $("blockchainSourceState").textContent =
      `CMDB canonical · ${items.length} managed`;""",
    """    const managedCount = items.filter(
      (item) => Boolean(item.manager)
    ).length;

    const discoveredCount = items.length - managedCount;

    $("blockchainSourceState").textContent =
      `CMDB canonical · ${managedCount} managed · ${discoveredCount} discovered`;"""
)

js = js.replace(
    """    catalog = Array.isArray(payload.providers)
      ? payload.providers
      : [];

    renderCatalog();""",
    """    catalog = Array.isArray(payload.providers)
      ? payload.providers
      : [];

    renderCatalogFilters();
    renderCatalog();"""
)

js_path.write_text(js)


css = css_path.read_text()

addition = """

/* SBP-076.4 — shared Nexus page framing */

.blockchain-page.nexus-page-shell {
  display: block;
  max-width: 1500px;
  margin: 24px auto 60px;
  padding: 24px;
  border: 1px solid rgba(144, 166, 190, .16);
  border-radius: 18px;
  background: rgba(8, 18, 29, .72);
  box-shadow: 0 18px 50px rgba(0, 0, 0, .18);
}

.blockchain-section {
  padding: 20px;
  border: 1px solid rgba(144, 166, 190, .14);
  border-radius: 16px;
  background: rgba(8, 18, 29, .42);
}

.blockchain-section + .blockchain-section {
  margin-top: 20px;
}

@media (max-width: 720px) {
  .blockchain-page.nexus-page-shell {
    margin-top: 12px;
    padding: 16px;
    border-radius: 14px;
  }

  .blockchain-section {
    padding: 14px;
  }
}
"""

if "SBP-076.4 — shared Nexus page framing" not in css:
    css += addition

css_path.write_text(css)

print("PASS: Blockchain UI patched")
PY

echo
echo "===== POST-INSTALL CONTRACT ====="

grep -q 'nexus-page-shell blockchain-page' "$HTML"
grep -q '>Blockchain Runtimes<' "$HTML"
grep -q 'function renderCatalogFilters()' "$JS"
grep -q '"online", "healthy"' "$JS"
grep -q 'Independent / discovered' "$JS"
grep -q 'managed ·' "$JS"
grep -q 'SBP-076.4 — shared Nexus page framing' "$CSS"

echo "PASS: SBP-076.4 install"
