# SBP-028 — Live Runtime State Verification & Nexus Current-Metric Acceptance

Targets the Nexus Command Center repository.

Purpose:
- verify that live Seymour registration refreshes update the BCH node asset in Nexus;
- prove `observed_state` is normalized (`starting`, `syncing`, `healthy`, `degraded`, etc.);
- prove SBP-027 runtime metrics land in `nexus.current_metrics`;
- verify duplicate/idempotent refreshes continue reconciling live state;
- avoid changing runtime behavior: this is an acceptance/verification package.

This package does not restart the Nexus API automatically.
