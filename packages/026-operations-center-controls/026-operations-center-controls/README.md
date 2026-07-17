# Package 026 — Operations Center Controls

Turns Operations Center action previews into controlled Platform automation workflows.

Safety model:
- Dry-run is selected by default.
- Dry runs queue without approval.
- Live high-risk actions enter pending approval.
- Only queued actions execute.
- Actions without an enabled managed remote executor return a safe audited no-op.
- Every lifecycle transition is written to PostgreSQL.

Install:
```bash
chmod +x scripts/*.sh
./scripts/doctor.sh
./scripts/install.sh
./scripts/verify.sh
```
