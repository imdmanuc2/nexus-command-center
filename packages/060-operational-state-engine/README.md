# Package 060 — Operational State Engine

Consolidates live worker, pool, blockchain, and CMDB state into one canonical operational model.

Key corrections:
- Live worker upserts immediately own the current-session slot.
- Both Seymour ASIC sessions remain current simultaneously because they map to distinct assets.
- Worker activity derivation no longer references `recent_share` before assignment.
- CMDB assets receive observed operational state, health, and connectivity from live facts.
- Topology and Canvas continue to consume canonical PostgreSQL state.
