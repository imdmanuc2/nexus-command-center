# Design Notes

Home V2 remains a thin presentation layer over canonical PostgreSQL-backed Platform APIs.

This package intentionally does not rearrange cards or introduce new backend capabilities. It improves operator trust during partial failures by distinguishing current telemetry, stale telemetry, unavailable telemetry, and browser connectivity loss.
