import logging; logging.basicConfig(level=logging.DEBUG); logger = logging.getLogger(__name__)
from twisted.internet import protocol
from .dataProtocol import DataProtocol


class DataProviderProtocolFactory(protocol.Factory):

    def __init__(self, container):
        self.container = container
        self.name = 'DataProviderProtocolFactory'

    def buildProtocol(self, addr):
        p = DataProtocol()
        p.factory = self
        return p
