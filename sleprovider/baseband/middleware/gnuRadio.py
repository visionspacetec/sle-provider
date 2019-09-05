from twisted.internet import reactor, protocol
import json
import datetime as dt


class JsonClient(protocol.Protocol):

    def connectionMade(self):
        try:
            print("Connection to the SLE provider successful")
            self._rem = ''
            self.factory.container.users.append(self)
        except Exception as e:
            print("Not able to connect to the SLE provider: {}".format(e))
            self.disconnect()

    def connectionLost(self, reason):
        pass

    def dataReceived(self, data):
        try:
            data = (self._rem + data.decode()).encode()
            self._rem = ''
            pdu = json.loads(data)
            print("The SLE server said: {}".format(pdu))
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

    def send_message(self, data, frame_quality):
        msg = {'earthReceiveTime': str(dt.datetime.utcnow()),
               'antennaId': self.factory.container.antenna_id,
               'deliveredFrameQuality': frame_quality,
               'data': data.hex()}
        self.transport.write(json.dumps(msg).encode())

    def disconnect(self):
        print("SLE server disconnecting!")
        self.transport.loseConnection()


class JsonClientFactory(protocol.ClientFactory):

    def clientConnectionFailed(self, connector, reason):
        print("SLE server connection failed - goodbye!")
        reactor.stop()

    def clientConnectionLost(self, connector, reason):
        print("Connection to the SLE server lost!")

    def buildProtocol(self, addr):
        p = JsonClient()
        p.factory = self
        return p


class UdpProtocol(protocol.DatagramProtocol):

    def __init__(self, container, frame_quality):
        self.container = container
        self.frame_quality = frame_quality

    def datagramReceived(self, datagram, addr):
        if self.container.print_frames:
            print(datagram.hex())
        self.container.users[0].send_message(datagram, self.frame_quality)


class GnuRadioMiddleware:

    def __init__(self, port_good_frames, port_erred_frames, host_sle, port_sle, antenna_id, print_frames):
        f = JsonClientFactory()
        f.container = self
        self.antenna_id = antenna_id
        self.print_frames = print_frames
        self.connectors = {}
        self.users = []
        self.connectors.update({'jsonClient': reactor.connectTCP(host_sle,
                                                                 port_sle,
                                                                 f)})
        if port_good_frames is not None:
            self.connectors.update({'udpGoodFrames': reactor.listenUDP(port_good_frames, UdpProtocol(self, 'good'))})
        if port_erred_frames is not None:
            self.connectors.update({'udpErredFrames': reactor.listenUDP(port_erred_frames, UdpProtocol(self, 'erred'))})

    def start_reactor(self):
        print("GNU Radio middleware is now running!")
        if self.print_frames:
            print("Print of UDP frames enabled")
        reactor.run()


def main(port_good_frames, port_erred_frames, host_sle, port_sle, antenna_id, print_frames=False):
    client = GnuRadioMiddleware(port_good_frames, port_erred_frames, host_sle, port_sle, antenna_id, print_frames)
    client.start_reactor()
