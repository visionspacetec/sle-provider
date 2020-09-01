import logging; logging.basicConfig(level=logging.DEBUG); logger = logging.getLogger(__name__)
from twisted.internet import protocol
from .commonStatelessProtocol import CommonStatelessProtocol


class CommonStatelessProviderProtocolFactory(protocol.Factory):

    def __init__(self, container, print_frames):
        self.container = container
        self.name = 'CommonStatelessProviderProtocolFactory'
        if print_frames:
            logger.debug("Print of outgoing SLE frames enabled")
        self.print_frames = print_frames

    def buildProtocol(self, addr):
        p = CommonStatelessProtocol()
        p.factory = self
        p.print_frames = self.print_frames
        return p
