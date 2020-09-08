import logging; logging.basicConfig(level=logging.DEBUG); logger = logging.getLogger(__name__)
import os
from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor


class UdpVST104Endpoint(DatagramProtocol):

    def startProtocol(self):
        logger.debug('UdpVST104Endpoint running...')

    def datagramReceived(self, datagram, address):
        logger.debug("Telecommand received: {}".format(datagram))

    def send_message(self):
        pass

reactor.listenUDP(int(os.getenv('SLE_MIDDLEWARE_GOOD_FRAMES', 16887)), UdpVST104Endpoint())
reactor.run()
