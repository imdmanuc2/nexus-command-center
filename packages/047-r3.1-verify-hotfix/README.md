# Package 047 R3.1 Verification Hotfix

This hotfix updates only the Package 047 R3 verification script so its
temporary `nexus.change_requests` row matches the current database schema.

It does not rerun the migration or reinstall the services.

Run:

```bash
cd ~/Projects/Seymour/nexus-command-center/packages
unzip 047-r3.1-verify-hotfix.zip
cd 047-r3.1-verify-hotfix
./scripts/install.sh

cd ../047-change-rollback-orchestration-recovery-r3
./scripts/verify.sh
```
