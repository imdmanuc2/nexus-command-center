#!/usr/bin/env bash
set -e

sudo systemctl restart nexus-api

echo "Waiting for Nexus API..."
for i in {1..10}; do
  if curl -fss http://127.0.0.1:8080/api/system/status >/dev/null; then
    echo "Nexus API is online."
    exit 0
  fi
  sleep 1
done

echo "Nexus API did not come online."
sudo systemctl status nexus-api --no-pager
exit 1
