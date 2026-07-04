import socket
from concurrent.futures import ThreadPoolExecutor, as_completed


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

    return {
        "ip": ip,
        "primaryRole": primary_role,
        "openPorts": open_ports,
        "roles": roles,
        "serviceCount": len(services),
    }


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

    systems = [
        classify_host(ip, services)
        for ip, services in sorted(grouped.items())
    ]

    return {
        "targets": ips,
        "summary": summarize_results(found),
        "systems": systems,
        "found": found,
        "count": len(found)
    }


def scan_network():
    return scan_targets(["192.168.1.154", "192.168.1.156"])
