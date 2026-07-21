# Package 038 — CMDB Relationships & Dependency Mapping

Adds CMDB-authoritative dependency mapping, relationship taxonomy, provenance/confidence fields, immutable relationship history, blast-radius API, and a generic compute/workload model supporting ASIC, GPU, CPU, FPGA, AI workloads, and rentable compute.

## APIs
- `GET /api/cmdb/relationships/catalog`
- `GET /api/cmdb/relationships/asset?assetId=...`
- `GET /api/cmdb/dependency-map?assetId=...&depth=3`
- `POST /api/cmdb/relationships/upsert`
