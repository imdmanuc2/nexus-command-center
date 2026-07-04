from backend.connectors.miningcore import MiningCoreConnector
from backend.connectors.bchnode import BCHNodeConnector
from backend.connectors.asic import ASICConnector


class ConnectorManager:

    def __init__(self):
        self.connectors = {
            "miningcore": MiningCoreConnector(),
            "bchnode": BCHNodeConnector(),
            "asic": ASICConnector(),
        }

    def status(self):
        return {
            name: connector.status()
            for name, connector in self.connectors.items()
        }
