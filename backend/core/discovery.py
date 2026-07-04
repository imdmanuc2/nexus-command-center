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

    return {
        "targets": ips,
        "found": found,
        "count": len(found)
    }


def scan_network():
    return scan_targets(["192.168.1.154", "192.168.1.156"])
