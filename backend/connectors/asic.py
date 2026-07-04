from backend.core.connector import Connector


class ASICConnector(Connector):

    def status(self):
        return {
            "name": "ASIC Discovery",
            "connected": False,
            "message": "Discovery not started"
        }

    def info(self):
        return {}

    def metrics(self):
        return {
            "miners": []
        }
