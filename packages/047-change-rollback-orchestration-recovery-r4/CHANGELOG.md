# Changelog

## R4

- Use `nexus-local` for authorized local transport verification.
- Supply `assetId` explicitly so rollback execution resolves the reserved local target.
- Poll the specific rollback plan for asynchronous worker completion.
- Report recorded database errors for failed/manual-intervention outcomes.
- Validate attempts and lifecycle events against the current schema.
- Clean verification data after a successful test.
