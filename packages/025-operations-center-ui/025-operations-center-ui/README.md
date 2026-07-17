
# Package 025 — Operations Center UI

Adds the live Operations Center page backed by Package 024's unified
PostgreSQL Platform API.

## Install

```bash
chmod +x scripts/*.sh
./scripts/doctor.sh
./scripts/install.sh
./scripts/verify.sh
```

## Page

```text
/operations-center.html
```

The page refreshes every 15 seconds and displays Platform health,
infrastructure, mining output, alerts, recommendations, automation runs,
timeline activity, and safe action previews.
