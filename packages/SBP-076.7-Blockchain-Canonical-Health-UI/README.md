# SBP-076.7 — Blockchain Canonical Health UI

Updates the Nexus Blockchain page to consume and present the canonical
blockchain runtime health model.

Changes:

- restores shared Nexus navigation
- uses overallState as the primary visible runtime state
- presents Runtime, Connectivity, Sync, RPC, and Mining readiness
- renders synchronization progress for canonical syncing runtimes
- changes summary semantics to Runtimes / Ready / Syncing / Attention
- preserves the provider-driven Available Blockchains catalog
