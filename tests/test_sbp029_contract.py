from pathlib import Path

repo = Path(__file__).resolve().parents[1]

for page in [
    repo / "frontend" / "assets.html",
    repo / "frontend" / "cmdb-object.html",
]:
    text = page.read_text()
    assert "/css/cmdb-runtime-state.css" in text
    assert "/js/cmdb-runtime-state.js" in text

js = (
    repo
    / "frontend"
    / "js"
    / "cmdb-runtime-state.js"
).read_text()

for marker in [
    "/api/cmdb/assets",
    "runtimeState",
    "runtimeRpcReachable",
    "runtimeRpcHealthy",
    "runtimeInitialBlockDownload",
    "runtimeVerificationProgress",
    "cmdb-runtime-card",
    "cmdb-runtime-inline-badge",
]:
    assert marker in js, marker

css = (
    repo
    / "frontend"
    / "css"
    / "cmdb-runtime-state.css"
).read_text()

assert '.cmdb-runtime-badge[data-state="syncing"]' in css
assert '.cmdb-runtime-badge[data-state="healthy"]' in css
assert '.cmdb-runtime-badge[data-state="degraded"]' in css

print("SBP-029 CMDB runtime-state UI contract verification: PASS")
