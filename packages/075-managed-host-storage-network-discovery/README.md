# Package 075 — Managed Host, Storage & Network Discovery

## Purpose

Extend Nexus managed-host execution with safe read-only discovery
capabilities required by the blockchain setup workflow.

## Capabilities

- host.storage-inventory
- host.mounts
- host.network-interfaces
- host.listening-ports

Existing host.identity and host.disk-usage contracts remain unchanged.

## CMDB rule

The CMDB remains the canonical source of truth.

Package 075 does not create or overwrite CMDB assets directly. Capability
results are normalized into discovery evidence suitable for the existing
Nexus observation -> identity -> reconciliation -> CMDB pipeline.

## Safety

All new capabilities are read-only and allow-listed.

No arbitrary shell command execution is introduced.

This package does not:

- install blockchain software
- create directories
- mount storage
- modify filesystems
- change network configuration
- open or close firewall ports
- restart services
- create CMDB assets automatically

Future Package 075 work will connect the normalized evidence to the
existing reconciliation pipeline and establish canonical managed-host
and storage relationships.

## Reconciliation behavior

Managed-host discovery evidence now enters the existing Nexus reconciliation
engine through `reconcile_managed_host_discovery()`.

The behavior intentionally follows the existing CMDB lifecycle:

- confident identity match -> update canonical existing CMDB asset
- conflicting identity -> review required
- possible identity match -> review required
- new host -> pending candidate by default
- new CMDB asset creation -> only when `approve_new=True` is explicitly supplied

A discovered host is therefore never silently promoted into the canonical
CMDB.

The supplied managed-host asset identifier is discovery context. Stable CMDB
identity remains governed by the Nexus identity/reconciliation engine.

## Managed-host discovery orchestration

`discover_managed_host()` collects the required read-only capabilities for
one already-enrolled managed host and forwards the normalized evidence into
the existing reconciliation path.

The orchestrator:

- executes only allow-listed host discovery capabilities
- does not accept arbitrary commands
- does not modify the target host
- does not promote a new CMDB asset unless `approve_new=True`
- fails closed if any required discovery capability fails

The execution callable is injected by the caller so the existing Nexus
managed-host executor/transport remains authoritative for remote execution.
