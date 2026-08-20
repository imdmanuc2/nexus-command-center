# Package 079 — CMDB Canonical Platform Projection Repair

## Objective

Repair the Nexus platform inventory contract so `/api/platform/inventory`
includes canonical PostgreSQL CMDB assets.

The CMDB frontend already treats platform inventory as authoritative when
assets are present. Before this package, the inventory service returned pools,
workers, workloads, and relationships but omitted assets. That caused the CMDB
UI to incorrectly display discovery data as its fallback source even though
canonical CMDB assets existed in PostgreSQL.

## Changes

- Import `list_assets` into `platform_inventory_service.py`.
- Add canonical assets to `inventory()`.
- Add `assets` to the inventory counts.
- Preserve the existing pools, workers, workloads, and relationships contract.
- Leave discovery available only as a frontend fallback.
- Do not derive CMDB inventory from topology.

## Expected result

`GET /api/platform/inventory` returns:

- `assets`
- `pools`
- `workers`
- `workloads`
- `relationships`

The CMDB page should report:

`PostgreSQL CMDB · authoritative`

## Version 1.0 scope

This package repairs the existing CMDB authority contract only.

Blockchain navigation and Blockchain Manager UI integration are deferred to
the next package.
