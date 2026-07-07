from backend.core.discovery import scan as core_scan
from backend.core.discovery import discovery_v2_from_scan


def scan():
    return core_scan()


def topology():
    return discovery_v2_from_scan()
