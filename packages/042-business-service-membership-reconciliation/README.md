# Package 042 — Business Service Membership Reconciliation

Connects CMDB assets and active workload assignments to the business-service topology introduced by Package 040 and the Operations Center introduced by Package 041.

## Delivers

- Rule-driven automatic business-service membership
- Idempotent reconciliation with run history
- Safe retirement of stale automatically-managed memberships
- Preservation of manually-managed memberships
- `not-configured` health for empty service templates
- No false incidents for unconfigured services
- Membership rules and reconciliation APIs
- Operations Center reconciliation control and member preview

## Install

```bash
cd ~/Projects/Seymour/nexus-command-center/packages/042-business-service-membership-reconciliation
./scripts/doctor.sh
./scripts/install.sh
./scripts/verify.sh
```
