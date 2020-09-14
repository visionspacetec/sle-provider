import logging; logging.basicConfig(level=logging.DEBUG); logger = logging.getLogger(__name__)
import os
from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor


class UdpVST104Endpoint(DatagramProtocol):

    def startProtocol(self):
        logger.debug('UdpVST104Endpoint running...')

    def datagramReceived(self, datagram, address):
        logger.debug("Address: {}".format(address))
        logger.debug("Telecommand received: {}".format(datagram))
        if ('127.0.0.1', 16889) != address:
            self.send_message(datagram)

    def send_message(self, tm_frame):
        self.transport.write(tm_frame, (os.getenv('SLE_MIDDLEWARE_TC_HOSTNAME', '127.0.0.1'),
                                        16888))
        #self.transport.write(tm_frame, (os.getenv('SLE_MIDDLEWARE_TC_HOSTNAME', '127.0.0.1'),
        #                                int(os.getenv('SLE_MIDDLEWARE_GOOD_FRAMES', 16887))))


reactor.listenUDP(int(os.getenv('SLE_MIDDLEWARE_GOOD_FRAMES', 16887)), UdpVST104Endpoint())
reactor.run()
