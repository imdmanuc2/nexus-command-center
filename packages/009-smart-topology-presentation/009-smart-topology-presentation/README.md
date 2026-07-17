# Package 009 — Smart Topology Presentation

This package makes Auto use the clean Overview and keeps Engineering as the
full asset/worker/workload X-ray view.

Overview:
- one node per managed asset
- matched worker and workload nodes hidden
- offline managed assets remain visible
- asset-to-pool edges remain visible
- ASIC clustering only above 50 ASIC assets

Install:

```bash
chmod +x scripts/*.sh scripts/patch_graph.py
./scripts/doctor.sh
./scripts/install.sh
sudo systemctl restart nexus-api.service
sleep 2
./scripts/verify.sh
```

Hard-refresh `/graph.html`.

Rollback:

```bash
./scripts/rollback.sh
sudo systemctl restart nexus-api.service
```

Commit:

```bash
git add frontend/js/graph.js
git commit -m "Add asset-centric Explorer overview"
git push origin feature/discovery-engine-v2
```
