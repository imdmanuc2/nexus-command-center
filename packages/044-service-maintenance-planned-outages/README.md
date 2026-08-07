# Package 044 — Service Maintenance & Planned Outages

Package 044 extends the existing Nexus maintenance-window foundation with business-service targets, planned-outage impact previews, lifecycle history, and Operations Center controls.

## Capabilities

- Schedule maintenance against a business service.
- Preview affected assets and expected service capacity before scheduling.
- List active, upcoming, completed, and cancelled maintenance.
- Start, complete, or cancel a window from Operations Center.
- Resolve service-targeted maintenance down to member assets for alert suppression.
- Persist immutable maintenance lifecycle history.
- Use strict verification that fails on API or JSON errors.

This package intentionally extends the existing `nexus.maintenance_windows` and `nexus.maintenance_targets` tables instead of creating a competing maintenance subsystem.
