# Package 008 — Infrastructure Explorer Platform Cutover

Moves Infrastructure Explorer live graph and worker telemetry reads to the
PostgreSQL-backed Platform APIs while preserving the current renderer.

```bash
chmod +x scripts/*.sh
./scripts/doctor.sh
./scripts/install.sh
sudo systemctl restart nexus-api.service
until curl -fsS http://127.0.0.1:8080/api >/dev/null; do sleep 1; done
./scripts/verify.sh
```

Open `/graph.html` and verify canvas, filters, inspector, layout, topology lines,
and mining animation.

Rollback:

```bash
./scripts/rollback.sh
sudo systemctl restart nexus-api.service
```

Commit:

```bash
git add frontend/graph.html frontend/js/nexus-platform-explorer.js
git commit -m "Move Infrastructure Explorer to Platform topology"
git push origin feature/discovery-engine-v2
```
