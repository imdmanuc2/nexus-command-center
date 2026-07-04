from backend.core.connector import Connector


class MiningCoreConnector(Connector):

    def status(self):
        return {
            "name": "MiningCore",
            "connected": False,
            "message": "Not configured"
        }

    def info(self):
        return {
            "version": None,
            "endpoint": None
        }

    def metrics(self):
        return {
            "poolHashrate": 0,
            "workers": 0,
            "blocks": 0
        }
