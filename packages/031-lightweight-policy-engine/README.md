# Package 031 — Lightweight Policy Engine

Final Nexus Operations Engine package for Seymour Platform Version 1.

Provides:

- Allow, deny, and confirmation-required policy decisions
- Explicit confirmation for destructive operations
- Denial of arbitrary command execution
- Immutable PostgreSQL decision history
- Policy evaluation API and read-only policies page
- Policy gate integration with the Package 030 playbook engine

## Install

```bash
cd ~/Projects/Seymour/nexus-command-center/packages
unzip 031-lightweight-policy-engine.zip
cd 031-lightweight-policy-engine
chmod +x scripts/*.sh
./scripts/doctor.sh
./scripts/install.sh
./scripts/verify.sh
```
