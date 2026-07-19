# Package 028 — Managed Host Transport

Package 028 establishes a typed capability execution layer. It does **not** expose arbitrary SSH commands.

## Contract

Callers request a capability such as `service.restart`, a target asset, and validated parameters. The capability registry owns the exact executable and arguments. SSH and local execution are internal adapters.

## Security guarantees

- Strict host-key verification with a dedicated known-hosts file
- Key-only, non-interactive SSH
- No public command, shell, or argv fields
- Per-capability parameter validation and timeouts
- Structured stdout/stderr/exit-code results
- Secret redaction
- Approval enforcement for mutating capabilities
- Correlation identifiers
- Post-action verification for service restart
- Existing Package 026 immutable lifecycle auditing

## Managed host setup

Copy `backend/data/private/managed_hosts.example.json` to `managed_hosts.json`, then create one profile per CMDB asset. Preload host keys deliberately, for example after verifying the fingerprint out-of-band:

```bash
ssh-keyscan -H 192.0.2.10 >> backend/data/private/known_hosts
chmod 600 backend/data/private/known_hosts
```

The remote account should have narrowly scoped sudoers rules, not unrestricted sudo.

## Install

```bash
chmod +x scripts/*.sh
./scripts/doctor.sh
./scripts/install.sh
./scripts/verify.sh
```
