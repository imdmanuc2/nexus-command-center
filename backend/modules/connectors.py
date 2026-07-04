from datetime import datetime, timezone
from backend.core.connectors import ConnectorManager

connector_manager = ConnectorManager()


def status():
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "connectors": connector_manager.status()
    }
