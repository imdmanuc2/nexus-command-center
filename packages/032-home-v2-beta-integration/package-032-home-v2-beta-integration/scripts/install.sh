#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"
TARGET="frontend/js/home-v2.js"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="${TARGET}.before-package-032-${STAMP}"
cp "$TARGET" "$BACKUP"

python3 - "$TARGET" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()

old = '''async function loadOperationsEvents() {
  try {
    const response = await fetch(
      "/api/events/operations",
      {
        cache: "no-store",
        headers: {
          Accept: "application/json",
        },
      }
    );

    if (!response.ok) {
      throw new Error(
        `Operations events returned HTTP ${response.status}`
      );
    }

    const payload = await response.json();

    renderOperationsEvents(payload);
  } catch (error) {
    console.error(
      "Unable to load operations events:",
      error
    );
  }
}
'''

new = '''function normalizeOperationsTimeline(payload) {
  const entries = Array.isArray(payload?.entries)
    ? payload.entries
    : [];

  return {
    status: payload?.status || "ok",
    source:
      payload?.source
      || "nexus-postgresql-operations-timeline",
    generatedAt:
      entries[0]?.occurredAt
      || new Date().toISOString(),
    events: entries.map((entry) => ({
      id:
        entry.timelineId
        || entry.sourceId
        || `${entry.sourceType || "timeline"}-${entry.occurredAt || "event"}`,
      timestamp:
        entry.occurredAt
        || entry.timestamp
        || null,
      type:
        entry.eventType
        || entry.sourceType
        || "operation",
      severity:
        entry.severity
        || "info",
      title:
        entry.title
        || "Operations event",
      message:
        entry.message
        || "No additional event details.",
      source:
        entry.sourceType
        || payload?.source
        || "Nexus",
      objectType:
        entry.entityType
        || entry.eventType
        || "system",
      objectId:
        entry.entityId
        || entry.sourceId
        || null,
      metadata:
        entry.data
        || {},
    })),
  };
}


async function loadOperationsEvents() {
  try {
    const response = await fetch(
      "/api/platform/timeline/latest",
      {
        cache: "no-store",
        headers: {
          Accept: "application/json",
        },
      }
    );

    if (!response.ok) {
      throw new Error(
        `Platform timeline returned HTTP ${response.status}`
      );
    }

    const payload = await response.json();

    renderOperationsEvents(
      normalizeOperationsTimeline(payload)
    );
  } catch (error) {
    console.error(
      "Unable to load platform operations timeline:",
      error
    );
  }
}
'''

if new in text:
    print("Package 032 changes already installed.")
elif old not in text:
    raise SystemExit(
        "Could not locate the expected loadOperationsEvents block. "
        "Restore the current repository version or update the package patch."
    )
else:
    path.write_text(text.replace(old, new, 1))
    print("Updated Home V2 operations activity to use Platform Timeline.")
PY

echo "Backup: $BACKUP"
echo "Package 032 installed."
