
from backend.services.operations_center_service import (
    build_operations_center,
    latest_snapshot,
    operations_queue,
    operations_status,
)


def dashboard():
    return build_operations_center(
        persist=False,
    )


def status():
    return operations_status()


def queue():
    return operations_queue()


def snapshot():
    return latest_snapshot()
