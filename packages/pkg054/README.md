# Package 054 — CKPool Live Worker Telemetry

This package has two installation stages.

1. `bitcoin-node/` adds read-only CKPool telemetry endpoints to the existing Node dashboard on port 3000.
2. `nexus/` updates Generic Stratum synchronization to consume that endpoint and promote only genuinely active CKPool workers.

The endpoint uses a 180-second freshness window and never treats historical cumulative shares as proof of current activity.

Install the Bitcoin Node stage first, verify it, then install the Nexus stage.
