# Package 077 — Managed Host & Storage CMDB Enrollment

Package 077 establishes approval-safe enrollment of discovered managed-host
storage into the Nexus CMDB.

## Architecture

The Nexus CMDB remains the canonical source of truth.

Managed-host discovery is evidence. Discovery does not independently create
authoritative infrastructure inventory.

The enrollment flow is:

1. Package 075 gathers read-only host, network, mount, and storage evidence.
2. The reconciliation engine promotes an explicitly approved host into CMDB.
3. Package 077 derives storage candidates from that canonical host's evidence.
4. Storage candidates remain non-authoritative until explicitly approved.
5. Approved storage is persisted through the existing CMDB asset manager.
6. An explicit `mounts` relationship connects the canonical host to storage.
7. Package 076 can subsequently consume those canonical objects when
   reconciling blockchain runtime topology.

## Safety

Package 077 does not:

- install blockchain software;
- modify mounts;
- format disks;
- create filesystems;
- alter network configuration;
- infer laboratory-specific hosts or paths;
- automatically approve newly discovered storage;
- treat Docker, tmpfs, procfs, sysfs, boot, or similar mounts as blockchain
  storage.

Custom and advanced storage paths belong to the later blockchain deployment
wizard and must still be validated against managed-host evidence before
execution.

## Host enrollment

Package 077 also exposes `enroll_managed_host_discovery()`.

New managed hosts are not promoted automatically. An explicit approval is
required before the discovery evidence is sent through the existing Nexus
reconciliation engine with `approve_new=True`.

The reconciliation engine remains the authoritative promotion path. Package
077 does not bypass identity matching or write newly discovered hosts directly
to the asset repository.

Storage enrollment requires the canonical host asset to exist first.

## Stable host identity

Canonical managed-host identity must not depend on hostname or IP address.

Vendor appliances may share the same hostname and DHCP may change addresses.
Package 077 therefore selects the strongest available stable identity using:

1. board/hardware serial
2. system UUID
3. machine-id
4. SSH host-key fingerprint
5. physical MAC address

Hostname and IP remain descriptive current-state attributes.

This permits multiple Umbrel systems, servers, VMs, or appliances with
identical hostnames to coexist as independent CMDB assets.

## Canonical managed-host identity migration

Managed hosts use stable hardware or machine identity rather than mutable
network naming as their canonical CMDB identity.

Identity precedence established by Package 077:

1. hardware / board serial when available;
2. machine identity for hosts without hardware serials;
3. other strong stable identity evidence as supported by enrollment.

Hostname and IP address remain discovery evidence and must not determine the
canonical asset ID.

Package 077 also provides a transactional canonical asset-ID migration path.
The migration operates from an explicit reference allow-list, validates column
types before treating values as asset IDs, moves dependent references before
removing the legacy asset, and rolls back if the migration cannot complete.

The first real managed-host canonicalization was verified against the Umbrel
Pi discovered at 192.168.1.154. Its temporary CMDB identity was replaced
one-for-one by its stable canonical host identity while preserving its
identities, network-address evidence, and audit history.
