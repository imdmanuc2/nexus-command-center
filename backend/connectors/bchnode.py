from backend.core.connector import Connector


class BCHNodeConnector(Connector):

    def status(self):
        return {
            "name": "Bitcoin Cash Node",
            "connected": False,
            "message": "Not configured"
        }

    def info(self):
        return {}

    def metrics(self):
        return {}
