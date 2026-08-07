# Package 058.1 — Live Session Precedence Fix

Corrects CMDB identity and topology precedence after Seymour Pool Engine integration.

## Fixes
- Matches Seymour `.001` and `.002` workers to existing CMDB assets using stable worker suffix identity.
- Uses miner IP only as supporting/fallback identity.
- Retires stale MiningCore and CKPool sessions once Seymour owns the current physical asset session.
- Prevents historical Generic Stratum shares from keeping a disconnected CPU worker active.
- Enforces exact pool-instance matching in the Canvas so Seymour hashrate cannot appear on CKPool.
- Keeps historical relationships in PostgreSQL while excluding them from the live topology.
