# Package 007 — Home v2 Platform API Cutover

This package keeps the current Home v2 renderer intact while moving its fleet,
pool, and worker reads to PostgreSQL-backed Platform APIs.

```bash
chmod +x scripts/*.sh
./scripts/doctor.sh
./scripts/install.sh
sudo systemctl restart nexus-api.service
./scripts/verify.sh
```

Open `/home-v2.html` and confirm the dashboard renders normally.

Rollback:

```bash
./scripts/rollback.sh
sudo systemctl restart nexus-api.service
```

Commit:

```bash
git add frontend/home-v2.html frontend/js/nexus-platform-home.js
git commit -m "Move Home v2 fleet data to Platform APIs"
git push origin feature/discovery-engine-v2
```
