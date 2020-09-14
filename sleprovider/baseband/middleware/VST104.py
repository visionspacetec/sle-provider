import logging; logging.basicConfig(level=logging.DEBUG); logger = logging.getLogger(__name__)
import os
import json
import datetime as dt
from twisted.internet import reactor, protocol


class JsonClient(protocol.Protocol):

    def connectionMade(self):
        try:
            logger.debug("Connection to the SLE provider successful")
            self._rem = ''
            self.factory.container.users.append(self)
        except Exception as e:
            logger.debug("Not able to connect to the SLE provider: {}".format(e))
            self.disconnect()

    def connectionLost(self, reason):
        pass

    def dataReceived(self, data):
        try:
            data = (self._rem + data.decode()).encode()
            self._rem = ''
            pdu = json.loads(data)
            self._pdu_handler(pdu)
        except json.JSONDecodeError:
            buffer = data.decode()
            buffer_split = buffer.split('}{')
            for sub in buffer_split:
                if len(sub) < 2:
                    continue
                if sub[:1] != '{':
                    sub = '{' + sub
                if sub[-1:] != '}':
                    sub = sub + '}'
                sub = sub.encode()
                try:
                    pdu = json.loads(sub)
                except json.JSONDecodeError:
                    self._rem = sub[:-1].decode()
                    return
                self._pdu_handler(pdu)

    def _pdu_handler(self, pdu):
        if 'command' in pdu:
            if pdu['command'] == 'send-telecommand':
                try:
                    telecommand = pdu['args'][0].encode()
                    logger.debug("send-telecommand: {}".format(telecommand))
                    self.factory.container.data_endpoints[0].send_message(telecommand)
                except Exception as e:
                    logger.debug("Not able to send telecommand {}".format(e))
                    return
            else:
                logger.debug("Unknown command from SLE server received")
                return
        else:
            logger.debug("Received invalid request from SLE server")
            return

    def send_message(self, data, frame_quality):
        msg = {'earthReceiveTime': str(dt.datetime.utcnow()),
               'antennaId': self.factory.container.antenna_id,
               'deliveredFrameQuality': frame_quality,
               'data': data.hex()}
        logger.debug("Send message to SLE provider: {}".format(msg))
        self.transport.write(json.dumps(msg).encode())

    def disconnect(self):
        logger.debug("SLE server disconnecting!")
        self.transport.loseConnection()


class JsonClientFactory(protocol.ClientFactory):

    def clientConnectionFailed(self, connector, reason):
        logger.debug("SLE server connection failed - goodbye!")
        reactor.stop()

    def clientConnectionLost(self, connector, reason):
        logger.debug("Connection to the SLE server lost!")

    def buildProtocol(self, addr):
        p = JsonClient()
        p.factory = self
        return p


class UdpProtocol(protocol.DatagramProtocol):

    def __init__(self, container):
        self.container = container
        self.container.data_endpoints.append(self)

    def datagramReceived(self, datagram, address):
        if self.container.print_frames:
            logger.debug("Datagram received: {}".format(datagram.hex()))
        logger.debug("Address: {}".format(address))
        self.container.users[0].send_message(datagram, 'good')

    def stopProtocol(self):
        self.container.data_endpoints.remove(self)

    def send_message(self, tc_frame):
        self.transport.write(tc_frame, (os.getenv('SLE_MIDDLEWARE_TC_HOSTNAME', '127.0.0.1'),
                                        int(os.getenv('SLE_MIDDLEWARE_GOOD_FRAMES', 16887))))


class VST104Middleware:

    def __init__(self, port_good_frames, host_sle, port_sle, antenna_id, print_frames):
        f = JsonClientFactory()
        f.container = self
        self.antenna_id = antenna_id
        self.print_frames = print_frames
        self.connectors = {}
        self.users = []
        self.data_endpoints = []
        self.connectors.update({'jsonClient': reactor.connectTCP(host_sle,
                                                                 port_sle,
                                                                 f)})
        if port_good_frames is not None:
            self.connectors.update({'udpFrames': reactor.listenUDP(16888, UdpProtocol(self))})
        else:
            raise ValueError

    def start_reactor(self):
        logger.debug("VST104 middleware is now running!")
        if self.print_frames:
            logger.debug("Print of telecommand frames enabled")
        reactor.run()


def main(port_good_frames, host_sle, port_sle, antenna_id, print_frames=False):
    client = VST104Middleware(port_good_frames, host_sle, port_sle, antenna_id, print_frames)
    client.start_reactor()
