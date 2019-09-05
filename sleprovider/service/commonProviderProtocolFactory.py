import logging; logging.basicConfig(level=logging.DEBUG); logger = logging.getLogger(__name__)
from twisted.internet import protocol
from .commonProtocol import CommonProtocol


class CommonProviderProtocolFactory(protocol.Factory):

    def __init__(self, container, print_frames):
        self.container = container
        self.name = 'CommonProviderProtocolFactory'
        if print_frames:
            logger.debug("Print of outgoing SLE frames enabled")
        self.print_frames = print_frames

    def buildProtocol(self, addr):
        p = CommonProtocol()
        p.factory = self
        p.print_frames = self.print_frames
        return p
