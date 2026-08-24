# SBP-076.5 — Canonical Blockchain Runtime Health Model

Provides independent provider-neutral blockchain health dimensions:

- Runtime state
- Connectivity state
- Synchronization state
- RPC state
- Mining readiness
- Overall state
- State reason

The model does not infer synchronization merely because a runtime is
running. Missing authoritative sync telemetry remains unknown.

SBP-076.5.1 integrates the model into the existing
`/api/blockchain/operations` contract without removing legacy fields.
