# Changelog

## 034 — Infrastructure Explorer Platform Integration

- Replaced compatibility fetch interception with an explicit Platform client.
- Switched graph topology reads to `/api/platform/topology`.
- Switched worker telemetry reads to `/api/platform/workers`.
- Added request timeout and clearer Platform source/error states.
- Retained current worker telemetry during transient refresh failures.
- Preserved all existing Explorer visuals and Digital Twin behavior.
