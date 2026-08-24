from __future__ import annotations

import json
from pathlib import Path


ROOT = Path.cwd()

REG = ROOT / "backend/db/repositories/seymour_registration_repository.py"
TEL = ROOT / "backend/db/repositories/seymour_telemetry_repository.py"
CATALOG = ROOT / "backend/data/config/blockchain_provider_catalog.json"
TEST = ROOT / "tests/test_sbp075_7_provider_neutral_projection.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"{label}: expected exactly one match, found {count}"
        )
    return text.replace(old, new, 1)


catalog = json.loads(CATALOG.read_text())
providers = catalog.get("providers")
if not isinstance(providers, list) or not providers:
    raise RuntimeError("provider catalog contains no providers")

implementation_map = {}
for provider in providers:
    if not isinstance(provider, dict):
        continue
    provider_id = str(provider.get("providerId") or "").strip()
    implementation = str(provider.get("implementation") or "").strip()
    if provider_id and implementation:
        implementation_map[provider_id] = implementation

for required in (
    "bitcoin-mainnet",
    "bitcoin-cash-mainnet",
    "monero-mainnet",
):
    if required not in implementation_map:
        raise RuntimeError(f"missing canonical provider: {required}")


reg = REG.read_text()

anchor = '''def _sync_value(sync: dict[str, Any], *names: str):
    for n in names:
        if sync.get(n) is not None: return sync.get(n)
    snap=sync.get("snapshot")
    if isinstance(snap,dict):
        for n in names:
            if snap.get(n) is not None: return snap.get(n)
    return None


'''

helpers = '''def _sync_value(sync: dict[str, Any], *names: str):
    for n in names:
        if sync.get(n) is not None: return sync.get(n)
    snap=sync.get("snapshot")
    if isinstance(snap,dict):
        for n in names:
            if snap.get(n) is not None: return snap.get(n)
    return None


def _provider_implementation(asset: dict[str, Any]) -> str:
    telemetry = asset.get("telemetry") if isinstance(asset.get("telemetry"), dict) else {}
    explicit = str(telemetry.get("implementation") or "").strip()
    if explicit:
        return explicit

    provider_id = str(asset.get("providerId") or "").strip()
    implementations = {
        "bitcoin-mainnet": "Bitcoin Core",
        "bitcoin-cash-mainnet": "Bitcoin Cash Node",
        "monero-mainnet": "Monero",
    }
    if provider_id in implementations:
        return implementations[provider_id]

    return str(asset.get("coin") or "Blockchain") + " Node"


def _operational_status(asset: dict[str, Any]) -> str:
    telemetry = asset.get("telemetry") if isinstance(asset.get("telemetry"), dict) else {}

    for value in (
        asset.get("status"),
        telemetry.get("lifecycleStatus"),
        telemetry.get("runtimeState"),
    ):
        if value is not None and str(value).strip():
            status = str(value).strip().lower()
            if status in {"running", "online", "active", "healthy", "ready"}:
                return "running"
            if status in {"stopped", "offline", "inactive"}:
                return "stopped"
            return status

    running = telemetry.get("running")
    if isinstance(running, bool):
        return "running" if running else "stopped"

    installed = telemetry.get("installed")
    if installed is False:
        return "not-installed"

    return "unknown"


'''

reg = replace_once(
    reg,
    anchor,
    helpers,
    "registration helper insertion",
)

reg = replace_once(
    reg,
    '''    status=str(asset.get("status") or tel.get("lifecycleStatus") or "unknown").lower()
''',
    '''    status=_operational_status(asset)
''',
    "registration status projection",
)

reg = replace_once(
    reg,
    'str(tel.get("implementation") or "Bitcoin Cash Node")',
    '_provider_implementation(asset)',
    "registration implementation projection",
)

REG.write_text(reg)


tel = TEL.read_text()

tel_anchor = (
    "def metric_candidates("
    "asset: dict[str, Any]"
    ") -> list[dict[str, Any]]:"
)

tel_helper = (
    "def _operational_status(asset: dict[str, Any]) -> str:\n"
    "    telemetry = _dict(asset.get(\"telemetry\"))\n"
    "\n"
    "    for value in (\n"
    "        asset.get(\"status\"),\n"
    "        telemetry.get(\"lifecycleStatus\"),\n"
    "        telemetry.get(\"runtimeState\"),\n"
    "    ):\n"
    "        if value is not None and str(value).strip():\n"
    "            status = str(value).strip().lower()\n"
    "            if status in {\"running\", \"online\", \"active\", \"healthy\", \"ready\"}:\n"
    "                return \"running\"\n"
    "            if status in {\"stopped\", \"offline\", \"inactive\"}:\n"
    "                return \"stopped\"\n"
    "            return status\n"
    "\n"
    "    running = telemetry.get(\"running\")\n"
    "    if isinstance(running, bool):\n"
    "        return \"running\" if running else \"stopped\"\n"
    "\n"
    "    installed = telemetry.get(\"installed\")\n"
    "    if installed is False:\n"
    "        return \"not-installed\"\n"
    "\n"
    "    return \"unknown\"\n"
    "\n"
    "\n"
)

tel = replace_once(
    tel,
    tel_anchor,
    tel_helper + tel_anchor,
    "telemetry helper insertion",
)

tel = replace_once(
    tel,
    '    status = str(asset.get("status") or telemetry.get("lifecycleStatus") or "unknown").strip().lower()\n',
    '    status = _operational_status(asset)\n',
    "telemetry status projection",
)

TEL.write_text(tel)

TEST.write_text(
    '''from backend.db.repositories.seymour_registration_repository import (
    _operational_status,
    _provider_implementation,
)


def test_bitcoin_provider_uses_bitcoin_core():
    asset = {
        "assetType": "blockchain-node",
        "providerId": "bitcoin-mainnet",
        "coin": "BTC",
        "telemetry": {},
    }
    assert _provider_implementation(asset) == "Bitcoin Core"


def test_bitcoin_cash_provider_uses_bchn():
    asset = {
        "assetType": "blockchain-node",
        "providerId": "bitcoin-cash-mainnet",
        "coin": "BCH",
        "telemetry": {},
    }
    assert _provider_implementation(asset) == "Bitcoin Cash Node"


def test_monero_provider_uses_monero():
    asset = {
        "assetType": "blockchain-node",
        "providerId": "monero-mainnet",
        "coin": "XMR",
        "telemetry": {},
    }
    assert _provider_implementation(asset) == "Monero"


def test_explicit_telemetry_implementation_wins():
    asset = {
        "providerId": "bitcoin-mainnet",
        "coin": "BTC",
        "telemetry": {"implementation": "Custom Bitcoin Runtime"},
    }
    assert _provider_implementation(asset) == "Custom Bitcoin Runtime"


def test_unknown_provider_never_defaults_to_bitcoin_cash():
    asset = {
        "providerId": "future-chain-mainnet",
        "coin": "FUT",
        "telemetry": {},
    }
    implementation = _provider_implementation(asset)
    assert implementation == "FUT Node"
    assert implementation != "Bitcoin Cash Node"


def test_runtime_state_running_projects_running():
    asset = {
        "telemetry": {
            "runtimeState": "running",
            "running": True,
        }
    }
    assert _operational_status(asset) == "running"


def test_running_boolean_projects_running():
    asset = {"telemetry": {"running": True}}
    assert _operational_status(asset) == "running"


def test_running_false_projects_stopped():
    asset = {"telemetry": {"running": False}}
    assert _operational_status(asset) == "stopped"


def test_explicit_offline_projects_stopped():
    asset = {
        "status": "offline",
        "telemetry": {"running": True},
    }
    assert _operational_status(asset) == "stopped"


def test_missing_state_is_unknown():
    assert _operational_status({"telemetry": {}}) == "unknown"
'''
)

print("SBP-075.7 patch prepared successfully.")
