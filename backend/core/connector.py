from abc import ABC, abstractmethod


class Connector(ABC):
    """
    Base class for all Nexus connectors.
    Every connector should implement this interface.
    """

    @abstractmethod
    def status(self):
        pass

    @abstractmethod
    def info(self):
        pass

    @abstractmethod
    def metrics(self):
        pass
