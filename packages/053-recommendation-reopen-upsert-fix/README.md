# Package 053 — Recommendation Reopen Upsert Fix

Fixes deterministic recommendation IDs colliding with previously completed or dismissed recommendations.

The repository now uses an atomic PostgreSQL upsert. When a recommendation condition returns, the existing row is reopened, completion/acceptance/dismissal timestamps are cleared, generation history is retained, and the primary-key collision is avoided.
