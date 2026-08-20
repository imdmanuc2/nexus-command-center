from __future__ import annotations

import json
import re
from typing import Any


NETWORK_FILESYSTEMS = {
    "nfs",
    "nfs4",
    "cifs",
    "smb3",
    "sshfs",
    "fuse.sshfs",
}

PORT_RE = re.compile(r":(\d+)$")


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def normalize_storage_inventory(raw: str) -> list[dict[str, Any]]:
    payload = json.loads(raw or "{}")
    devices = payload.get("blockdevices") or []

    result: list[dict[str, Any]] = []

    def visit(
        item: dict[str, Any],
        parent: str | None = None,
    ) -> None:
        mountpoints = [
            _text(value)
            for value in (item.get("mountpoints") or [])
            if _text(value)
        ]

        result.append({
            "name": _text(item.get("name")),
            "kernelName": _text(item.get("kname")),
            "path": _text(item.get("path")),
            "type": _text(item.get("type")),
            "filesystem": _text(item.get("fstype")),
            "sizeBytes": int(item.get("size") or 0),
            "mountpoints": mountpoints,
            "model": _text(item.get("model")),
            "serial": _text(item.get("serial")),
            "transport": _text(item.get("tran")),
            "uuid": _text(item.get("uuid")),
            "parentKernelName": (
                _text(item.get("pkname"))
                or parent
                or ""
            ),
            "readOnly": bool(item.get("ro")),
            "removable": bool(item.get("rm")),
        })

        for child in item.get("children") or []:
            if isinstance(child, dict):
                visit(
                    child,
                    _text(item.get("kname"))
                    or parent,
                )

    for item in devices:
        if isinstance(item, dict):
            visit(item)

    return result


def normalize_mounts(raw: str) -> list[dict[str, Any]]:
    payload = json.loads(raw or "{}")
    filesystems = payload.get("filesystems") or []

    result = []

    def visit(item: dict[str, Any]) -> None:
        filesystem = _text(item.get("fstype"))

        result.append({
            "source": _text(item.get("source")),
            "target": _text(item.get("target")),
            "filesystem": filesystem,
            "options": _text(item.get("options")),
            "networkStorage": (
                filesystem.lower()
                in NETWORK_FILESYSTEMS
            ),
        })

        for child in item.get("children") or []:
            if isinstance(child, dict):
                visit(child)

    for item in filesystems:
        if isinstance(item, dict):
            visit(item)

    return result


def normalize_network_interfaces(
    raw: str,
) -> list[dict[str, Any]]:
    payload = json.loads(raw or "[]")

    result = []

    for item in payload:
        if not isinstance(item, dict):
            continue

        addresses = []

        for info in item.get("addr_info") or []:
            if not isinstance(info, dict):
                continue

            local = _text(info.get("local"))

            if not local:
                continue

            addresses.append({
                "family": _text(info.get("family")),
                "address": local,
                "prefixLength": int(
                    info.get("prefixlen") or 0
                ),
                "scope": _text(info.get("scope")),
            })

        result.append({
            "interface": _text(item.get("ifname")),
            "state": _text(item.get("operstate")),
            "mtu": int(item.get("mtu") or 0),
            "macAddress": _text(item.get("address")),
            "addresses": addresses,
        })

    return result


def normalize_listening_ports(
    raw: str,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    for line in (raw or "").splitlines():
        line = line.strip()

        if not line:
            continue

        columns = line.split()

        if len(columns) < 5:
            continue

        protocol = columns[0].lower()
        local = columns[4]

        match = PORT_RE.search(local)

        if not match:
            continue

        result.append({
            "protocol": protocol,
            "localAddress": local,
            "port": int(match.group(1)),
        })

    dedup = {
        (
            item["protocol"],
            item["localAddress"],
            item["port"],
        ): item
        for item in result
    }

    return sorted(
        dedup.values(),
        key=lambda item: (
            item["port"],
            item["protocol"],
            item["localAddress"],
        ),
    )


def _host_identity_fields(
    raw: str,
) -> dict[str, str]:
    value = _text(raw)

    # Existing host.identity uses `uname -a`.
    # Preserve that contract and extract only conservative fields.
    parts = value.split()

    hostname = ""
    architecture = ""

    if len(parts) >= 2:
        hostname = parts[1]

    architecture_aliases = {
        "x86_64": "x86_64",
        "amd64": "amd64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }

    # `uname -a` normally ends with GNU/Linux, not the machine
    # architecture. Search the token stream for a known architecture
    # instead of assuming the final token is the architecture.
    for candidate in reversed(parts):
        normalized = candidate.lower()

        if normalized in architecture_aliases:
            architecture = architecture_aliases[normalized]
            break

    return {
        "hostname": hostname,
        "architecture": architecture,
        "raw": value,
    }


def observation_payload(
    *,
    asset_id: str,
    identity_stdout: str,
    storage_stdout: str,
    mounts_stdout: str,
    interfaces_stdout: str,
    ports_stdout: str,
    serial_number: str = "",
    machine_uuid: str = "",
    ssh_host_key: str = "",
) -> dict[str, Any]:
    interfaces = normalize_network_interfaces(
        interfaces_stdout
    )

    storage_devices = normalize_storage_inventory(
        storage_stdout
    )

    mounts = normalize_mounts(
        mounts_stdout
    )

    listening_ports = normalize_listening_ports(
        ports_stdout
    )

    addresses = [
        address["address"]
        for interface in interfaces
        for address in interface["addresses"]
        if (
            address["scope"] != "host"
            and not address["address"].startswith("127.")
            and address["address"] != "::1"
        )
    ]

    mac_addresses = [
        interface["macAddress"]
        for interface in interfaces
        if (
            interface["macAddress"]
            and interface["macAddress"]
            != "00:00:00:00:00:00"
        )
    ]

    identity_fields = _host_identity_fields(
        identity_stdout
    )

    primary_ip = (
        addresses[0]
        if addresses
        else ""
    )

    primary_mac = (
        mac_addresses[0]
        if mac_addresses
        else ""
    )

    open_ports = sorted({
        item["port"]
        for item in listening_ports
    })

    # IMPORTANT:
    # normalize_observation() consumes identity/classification/network
    # values from these TOP-LEVEL fields. Keep the richer nested sections
    # as discovery evidence as well.
    payload = {
        "source": "managed-host-discovery",
        "assetId": asset_id,
        "id": asset_id,
        "name": (
            identity_fields["hostname"]
            or asset_id
        ),
        "friendlyName": (
            identity_fields["hostname"]
            or asset_id
        ),
        "displayName": (
            identity_fields["hostname"]
            or asset_id
        ),
        "hostname": identity_fields["hostname"],
        "ip": primary_ip,
        "macAddress": primary_mac,
        "serialNumber": _text(serial_number),
        "machineUuid": _text(machine_uuid),
        "sshHostKey": _text(ssh_host_key),
        "assetType": "server",
        "canonicalType": "server",
        "primaryRole": "Managed Host",
        "purpose": "Infrastructure Host",
        "operatingSystem": "Linux",
        "architecture": identity_fields["architecture"],
        "managed": True,
        "managementModel": "nexus-managed",
        "openPorts": open_ports,
        "services": [],
        "capabilities": [
            "managed-host",
            "blockchain-runtime-host",
            "storage-discovery",
            "network-discovery",
        ],
        "identity": {
            "hostname": identity_fields["hostname"],
            "ip": primary_ip,
            "macAddress": primary_mac,
            "serialNumber": _text(serial_number),
            "machineUuid": _text(machine_uuid),
            "sshHostKey": _text(ssh_host_key),
        },
        "classification": {
            "assetType": "server",
            "primaryRole": "Managed Host",
            "purpose": "Infrastructure Host",
        },
        "network": {
            "ip": primary_ip,
            "addresses": addresses,
            "openPorts": open_ports,
            "interfaces": interfaces,
            "listeningPorts": listening_ports,
        },
        "storage": {
            "devices": storage_devices,
            "mounts": mounts,
        },
        "observedState": {
            "managedHostDiscovery": {
                "identity": identity_fields,
                "network": {
                    "addresses": addresses,
                    "interfaces": interfaces,
                    "listeningPorts": listening_ports,
                },
                "storage": {
                    "devices": storage_devices,
                    "mounts": mounts,
                },
            }
        },
        "metadata": {
            "discoverySource": "managed-host-discovery",
            "managedHostAssetId": asset_id,
        },
        "raw": {
            "managedHostAssetId": asset_id,
            "hostIdentity": identity_fields["raw"],
            "interfaces": interfaces,
            "openPorts": open_ports,
            "listeningPorts": listening_ports,
            "storageDevices": storage_devices,
            "mounts": mounts,
        },
    }

    return payload


def reconcile_managed_host_discovery(
    *,
    asset_id: str,
    identity_stdout: str,
    storage_stdout: str,
    mounts_stdout: str,
    interfaces_stdout: str,
    ports_stdout: str,
    serial_number: str = "",
    machine_uuid: str = "",
    ssh_host_key: str = "",
    approve_new: bool = False,
    actor_id: str = "nexus",
) -> dict[str, Any]:
    # Local import avoids introducing reconciliation dependencies when
    # callers only need the pure normalization helpers.
    from backend.core.reconciliation_engine import (
        reconcile_observation,
    )

    payload = observation_payload(
        asset_id=asset_id,
        identity_stdout=identity_stdout,
        storage_stdout=storage_stdout,
        mounts_stdout=mounts_stdout,
        interfaces_stdout=interfaces_stdout,
        ports_stdout=ports_stdout,
        serial_number=serial_number,
        machine_uuid=machine_uuid,
        ssh_host_key=ssh_host_key,
    )

    result = reconcile_observation(
        payload,
        source="managed-host-discovery",
        observer_id="nexus-managed-host",
        approve_new=approve_new,
        actor_id=actor_id,
    )

    return {
        **result,
        "discovery": {
            "assetId": asset_id,
            "approveNew": approve_new,
            "network": payload["network"],
            "storage": payload["storage"],
        },
    }



def discover_managed_host(
    *,
    target: dict[str, Any],
    execute_capability,
    approve_new: bool = False,
    actor_id: str = "nexus",
) -> dict[str, Any]:
    if not isinstance(target, dict):
        raise ValueError("target must be an object.")

    asset_id = _text(
        target.get("assetId")
        or target.get("id")
        or target.get("targetId")
    )

    if not asset_id:
        raise ValueError(
            "Managed host target requires assetId/id/targetId."
        )

    capability_ids = (
        "host.identity",
        "host.storage-inventory",
        "host.mounts",
        "host.network-interfaces",
        "host.listening-ports",
    )

    results: dict[str, dict[str, Any]] = {}

    for capability_id in capability_ids:
        result = execute_capability(
            capability_id,
            target,
            {},
        )

        if not isinstance(result, dict):
            raise RuntimeError(
                f"{capability_id} returned invalid result."
            )

        results[capability_id] = result

        if result.get("success") is False:
            raise RuntimeError(
                f"{capability_id} failed: "
                f"{result.get('stderr') or result.get('error') or 'unknown error'}"
            )

    def stdout(capability_id: str) -> str:
        return _text(
            results[capability_id].get("stdout")
        )

    reconciled = reconcile_managed_host_discovery(
        asset_id=asset_id,
        identity_stdout=stdout("host.identity"),
        storage_stdout=stdout(
            "host.storage-inventory"
        ),
        mounts_stdout=stdout("host.mounts"),
        interfaces_stdout=stdout(
            "host.network-interfaces"
        ),
        ports_stdout=stdout(
            "host.listening-ports"
        ),
        approve_new=approve_new,
        actor_id=actor_id,
    )

    return {
        "status": "ok",
        "assetId": asset_id,
        "approveNew": approve_new,
        "capabilities": {
            capability_id: {
                "success": results[
                    capability_id
                ].get("success", True),
                "exitCode": results[
                    capability_id
                ].get("exitCode"),
                "durationMs": results[
                    capability_id
                ].get("durationMs"),
            }
            for capability_id in capability_ids
        },
        "reconciliation": reconciled,
    }
