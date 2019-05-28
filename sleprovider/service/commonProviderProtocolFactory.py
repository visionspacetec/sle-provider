import logging; logging.basicConfig(level=logging.DEBUG); logger = logging.getLogger(__name__)
from twisted.internet import protocol
from .commonProtocol import CommonProtocol


class CommonProviderProtocolFactory(protocol.Factory):

    def __init__(self, container):
        self.container = container
        self.name = 'CommonProviderProtocolFactory'

    def buildProtocol(self, addr):
        p = CommonProtocol()
        p.factory = self
        return p
