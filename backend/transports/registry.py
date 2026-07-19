from __future__ import annotations

from backend.transports.local_transport import LocalTransport
from backend.transports.ssh_transport import SshTransport


class TransportRegistry:
    def __init__(self) -> None:
        self._items = {"local": LocalTransport(), "ssh": SshTransport()}

    def resolve(self, name: str):
        transport = self._items.get(name)
        if transport is None:
            raise ValueError(f"Unsupported managed transport: {name}")
        return transport

    def describe(self):
        return sorted(self._items)


_registry = TransportRegistry()


def get_transport_registry() -> TransportRegistry:
    return _registry
