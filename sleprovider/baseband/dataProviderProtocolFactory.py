import logging; logging.basicConfig(level=logging.DEBUG); logger = logging.getLogger(__name__)
from twisted.internet import protocol
from .dataProtocol import DataProtocol


class DataProviderProtocolFactory(protocol.Factory):

    def __init__(self, container, print_frames):
        self.container = container
        self.name = 'DataProviderProtocolFactory'
        if print_frames:
            logger.debug("Print of incoming data frames enabled")
        self.print_frames = print_frames

    def buildProtocol(self, addr):
        p = DataProtocol()
        p.factory = self
        p.print_frames = self.print_frames
        return p
