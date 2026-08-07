# Package 071 — Platform Consolidation & Canonical Dashboard Framework

Introduces one canonical dashboard aggregation boundary for operator-facing dashboards.

## Changes
- Adds `/api/platform/dashboard-summary`.
- Preserves the existing Home V2 payload contract.
- Annotates every dashboard domain with its canonical service and verified authority.
- Updates Home V2 to consume the canonical endpoint.
- Explicitly reports whether any legacy fallback was used.
- Keeps `/api/platform/home` temporarily for compatibility; new dashboards must use the canonical route.
