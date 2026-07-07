import socket
import json
from urllib.request import urlopen, Request
from concurrent.futures import ThreadPoolExecutor, as_completed
from backend.core.assets import discover_asset


COMMON_PORTS = {
    4000: "MiningCore API",
    5007: "BCH Node App Proxy",
    6001: "Stratum",
    7002: "MiningCore API Alt",
    8332: "BTC/BCH RPC Common",
    8333: "BTC P2P",
    8334: "BCH P2P",
    8559: "Mining Dashboard",
    8560: "MiningCore Web/API",
    9002: "BCH Node RPC",
    80: "Web Interface",
    443: "Secure Web Interface",
}


ROLE_RULES = {
    "blockchain_node": {
        "label": "Blockchain Node",
        "ports": [8334, 9002, 8332],
    },
    "mining_backend": {
        "label": "Mining Backend",
        "ports": [4000, 7002, 8560],
    },
    "dashboard": {
        "label": "Dashboard",
        "ports": [8559, 80, 443],
    },
    "stratum": {
        "label": "Stratum Server",
        "ports": [6001],
    },
}


def check_port(ip, port, timeout=0.5):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return {
                "ip": ip,
                "port": port,
                "service": COMMON_PORTS.get(port, "Unknown"),
                "status": "open"
            }
    except Exception:
        return None



def probe_http_json(url, timeout=1.5):
    try:
        req = Request(url, headers={"User-Agent": "Nexus-Discovery/0.1"})
        with urlopen(req, timeout=timeout) as r:
            body = r.read(750000).decode("utf-8", errors="ignore")
            return json.loads(body)
    except Exception:
        return None


def fingerprint_host(ip, services):
    fingerprints = []

    open_ports = [item["port"] for item in services]

    if 4000 in open_ports:
        data = probe_http_json(f"http://{ip}:4000/api/pools/bch")
        if data:
            fingerprints.append({
                "type": "miningcore",
                "label": "MiningCore API",
                "status": "confirmed",
                "endpoint": f"http://{ip}:4000/api/pools/bch",
                "confidence": 100
            })

    if 8560 in open_ports:
        data = probe_http_json(f"http://{ip}:8560/api/pools/bch")
        if data:
            fingerprints.append({
                "type": "miningcore",
                "label": "MiningCore API",
                "status": "confirmed",
                "endpoint": f"http://{ip}:8560/api/pools/bch",
                "confidence": 100
            })

    if 5007 in open_ports:
        fingerprints.append({
            "type": "bch-node-app",
            "label": "Bitcoin Cash Node App Proxy",
            "status": "detected",
            "endpoint": f"http://{ip}:5007",
            "confidence": 80
        })

    return fingerprints

def classify_host(ip, services):
    open_ports = sorted([item["port"] for item in services])
    roles = []

    for role_id, rule in ROLE_RULES.items():
        matched_ports = [p for p in open_ports if p in rule["ports"]]
        if matched_ports:
            roles.append({
                "id": role_id,
                "label": rule["label"],
                "ports": matched_ports,
                "confidence": min(100, 55 + (len(matched_ports) * 15))
            })

    primary_role = "Mining System" if roles else "Unknown System"

    if any(r["id"] == "mining_backend" for r in roles) and any(r["id"] == "blockchain_node" for r in roles):
        primary_role = "Full Mining Stack"
    elif any(r["id"] == "mining_backend" for r in roles):
        primary_role = "Mining Backend Host"
    elif any(r["id"] == "blockchain_node" for r in roles):
        primary_role = "Blockchain Node Host"

    profile_stub = {
        "hostname": resolve_hostname(ip),
        "assetType": None,
        "os": "Unknown",
        "agent": "Not installed"
    }

    result = {
        "ip": ip,
        "primaryRole": primary_role,
        "openPorts": open_ports,
        "roles": roles,
        "fingerprints": fingerprint_host(ip, services),
        "serviceCount": len(services),
        "profile": profile_stub
    }

    result["profile"]["assetType"] = infer_asset_type(result)
    result["health"] = calculate_health(result)

    return result


def summarize_results(found):
    summary = {
        "miningSystems": len(set(item["ip"] for item in found)),
        "blockchainNodes": 0,
        "miningBackends": 0,
        "dashboards": 0,
        "stratumServers": 0,
        "rpcEndpoints": 0
    }

    for item in found:
        port = item["port"]

        if port in [8334]:
            summary["blockchainNodes"] += 1
        elif port in [4000, 7002, 8560]:
            summary["miningBackends"] += 1
        elif port in [8559]:
            summary["dashboards"] += 1
        elif port in [6001]:
            summary["stratumServers"] += 1
        elif port in [8332, 9002]:
            summary["rpcEndpoints"] += 1

    return summary



def resolve_hostname(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return None


def infer_asset_type(system):
    role = system.get("primaryRole", "")

    if "Full Mining Stack" in role:
        return "Infrastructure Host"
    if "Blockchain" in role:
        return "Blockchain Node"
    if "Mining Backend" in role:
        return "Mining Backend"
    return "Unknown Asset"


def calculate_health(system):
    score = 100
    checks = []

    open_ports = system.get("openPorts", [])
    fingerprints = system.get("fingerprints", [])

    def add_check(name, ok, penalty):
        nonlocal score
        checks.append({
            "name": name,
            "status": "healthy" if ok else "critical",
            "penalty": 0 if ok else penalty
        })
        if not ok:
            score -= penalty

    add_check("Host reachable", len(open_ports) > 0, 40)
    add_check("Mining backend detected", any(r["id"] == "mining_backend" for r in system.get("roles", [])), 20)
    add_check("Blockchain node detected", any(r["id"] == "blockchain_node" for r in system.get("roles", [])), 15)
    add_check("Confirmed MiningCore API", any(fp["type"] == "miningcore" and fp["status"] == "confirmed" for fp in fingerprints), 15)
    add_check("Management dashboard reachable", any(p in open_ports for p in [80, 8559]), 10)

    score = max(0, min(100, score))

    if score >= 90:
        level = "healthy"
        label = "Healthy"
    elif score >= 75:
        level = "warning"
        label = "Warning"
    else:
        level = "critical"
        label = "Critical"

    return {
        "score": score,
        "level": level,
        "label": label,
        "checks": checks
    }

def scan_targets(ips):
    targets = []

    for ip in ips:
        for port in COMMON_PORTS:
            targets.append((ip, port))

    found = []

    with ThreadPoolExecutor(max_workers=64) as executor:
        futures = [executor.submit(check_port, ip, port) for ip, port in targets]

        for future in as_completed(futures):
            result = future.result()
            if result:
                found.append(result)

    found.sort(key=lambda x: (x["ip"], x["port"]))

    grouped = {}
    for item in found:
        grouped.setdefault(item["ip"], []).append(item)

        systems = []

    for ip, services in sorted(grouped.items()):

        s = classify_host(ip, services)
        s["asset"] = discover_asset(s)

        systems.append(s)

    return {
        "targets": ips,
        "summary": summarize_results(found),
        "systems": systems,
        "found": found,
        "count": len(found)
    }


def scan_network():
    return scan_targets(["192.168.1.154", "192.168.1.156"])


# -----------------------------
# Discovery V2 - Service Model
# -----------------------------

def classify_pool_mode(pool):
    payout = (
        pool.get("paymentProcessing", {})
            .get("payoutScheme", "")
            .lower()
    )

    if "solo" in payout:
        return "solo"

    if payout:
        return "public"

    return "unknown"


def normalize_pool(host_ip, api_port, pool):
    coin = pool.get("coin", {}) or {}
    stats = pool.get("poolStats", {}) or {}
    payment = pool.get("paymentProcessing", {}) or {}

    pool_id = pool.get("id") or coin.get("symbol", "unknown").lower()
    mode = classify_pool_mode(pool)

    return {
        "id": pool_id,
        "name": f"{coin.get('symbol', pool_id).upper()} {'Solo' if mode == 'solo' else 'Public'} Pool",
        "type": "pool",
        "mode": mode,
        "visibility": "private" if mode == "solo" else "public",
        "coin": {
            "symbol": coin.get("symbol") or coin.get("type") or pool_id.upper(),
            "name": coin.get("name", ""),
            "family": coin.get("family", ""),
            "algorithm": coin.get("algorithm", "")
        },
        "host": host_ip,
        "apiPort": api_port,
        "apiBase": f"http://{host_ip}:{api_port}",
        "endpoint": f"http://{host_ip}:{api_port}/api/pools/{pool_id}",
        "stratumPorts": list((pool.get("ports") or {}).keys()),
        "payoutScheme": payment.get("payoutScheme"),
        "poolFeePercent": pool.get("poolFeePercent"),
        "address": pool.get("address"),
        "stats": {
            "connectedMiners": stats.get("connectedMiners", 0),
            "poolHashrate": stats.get("poolHashrate", 0),
            "sharesPerSecond": stats.get("sharesPerSecond", 0),
            "totalBlocks": pool.get("totalBlocks", 0),
            "totalPaid": pool.get("totalPaid", 0),
            "poolEffort": pool.get("poolEffort", 0)
        },
        "network": pool.get("networkStats", {}),
        "raw": pool
    }


def discover_miningcore_pools(host_ip, api_port):
    pools = []

    data = probe_http_json(f"http://{host_ip}:{api_port}/api/pools")
    if data and isinstance(data.get("pools"), list):
        for pool in data["pools"]:
            pools.append(normalize_pool(host_ip, api_port, pool))
        return pools

    # Fallback for older/simple installs
    for pool_id in ["bch", "btc", "ltc", "doge"]:
        data = probe_http_json(f"http://{host_ip}:{api_port}/api/pools/{pool_id}")
        if data and data.get("pool"):
            pools.append(normalize_pool(host_ip, api_port, data["pool"]))

    return pools


def discovery_v2_from_scan():
    base = scan_network()

    if "discovery" in base:
        discovery = base.get("discovery", {})
    else:
        discovery = base

    systems = discovery.get("systems", [])
    found = discovery.get("found", [])

    pools = []
    blockchain_nodes = []
    infrastructure = []

    for system in systems:
        ip = system["ip"]
        open_ports = system.get("openPorts", [])

        for port in [4000, 8560, 7002]:
            if port in open_ports:
                pools.extend(discover_miningcore_pools(ip, port))

        if any(p in open_ports for p in [8332, 8333, 8334, 9002]):
            blockchain_nodes.append({
                "type": "blockchain-node",
                "host": ip,
                "name": "Bitcoin Cash Node" if 8334 in open_ports or 9002 in open_ports else "Blockchain Node",
                "coin": "BCH" if 8334 in open_ports or 9002 in open_ports else "Unknown",
                "ports": [p for p in open_ports if p in [8332, 8333, 8334, 9002]],
                "status": "detected"
            })

        infrastructure.append({
            "type": "host",
            "host": ip,
            "name": system.get("asset", {}).get("name") or ip,
            "primaryRole": system.get("primaryRole"),
            "assetType": system.get("profile", {}).get("assetType"),
            "openPorts": open_ports,
            "health": system.get("health", {}),
            "services": [item for item in found if item["ip"] == ip],
            "asset": system.get("asset", {})
        })

    return {
        "timestamp": base.get("timestamp"),
        "discovery": discovery,
        "topology": {
            "privatePools": [p for p in pools if p["visibility"] == "private"],
            "publicPools": [p for p in pools if p["visibility"] == "public"],
            "pools": pools,
            "blockchainNodes": blockchain_nodes,
            "infrastructure": infrastructure,
            "counts": {
                "privatePools": len([p for p in pools if p["visibility"] == "private"]),
                "publicPools": len([p for p in pools if p["visibility"] == "public"]),
                "pools": len(pools),
                "blockchainNodes": len(blockchain_nodes),
                "hosts": len(infrastructure)
            }
        }
    }


def scan():
    return scan_network()
