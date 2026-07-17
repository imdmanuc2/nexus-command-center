"""API-facing platform inventory functions."""

from backend.services.platform_inventory_service import inventory, topology


def summary():
    return inventory()


def graph():
    return topology()
