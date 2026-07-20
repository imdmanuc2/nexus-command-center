# Package 030 — Enterprise Playbook Engine

Adds declarative, capability-based operational playbooks to Nexus Command Center.

## Install
```bash
bash packages/030-enterprise-playbook-engine/scripts/doctor.sh
bash packages/030-enterprise-playbook-engine/scripts/install.sh
bash packages/030-enterprise-playbook-engine/scripts/verify.sh
```

Playbooks call allow-listed capabilities only. Embedded shell commands, argv, scripts, Bash, and Python are rejected. The package adds catalog, validation, variables, conditions, execution history, API endpoints, PostgreSQL persistence, six seed playbooks, and a Playbooks UI at `/playbooks.html`.
