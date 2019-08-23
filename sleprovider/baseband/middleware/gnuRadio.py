from twisted.internet import reactor, protocol
import json
import datetime as dt


class GnuRadioClientJson(protocol.Protocol):

    def connectionMade(self):
        try:
            print("GNU Radio connection made")
            self._rem = ''
            self.factory.container.users.append(self)
        except Exception as e:
            print("Not able to connect to GNU Radio: {}".format(e))
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

    def send_message(self, data):
        msg = {'earthReceiveTime': str(dt.datetime.utcnow()),
               'antennaId': 'VST',
               'deliveredFrameQuality': 'good',
               'data': data.hex()}
        self.transport.write(json.dumps(msg).encode())

    def disconnect(self):
        print("SLE server disconnecting!")
        self.transport.loseConnection()


class GnuRadioFactory(protocol.ClientFactory):

    def clientConnectionFailed(self, connector, reason):
        print("SLE server connection failed - goodbye!")
        reactor.stop()

    def clientConnectionLost(self, connector, reason):
        print("Connection to the SLE server lost!")

    def buildProtocol(self, addr):
        p = GnuRadioClientJson()
        p.factory = self
        return p


class GnuRadioClientUdp(protocol.DatagramProtocol):

    def __init__(self, container):
        self.container = container

    def datagramReceived(self, datagram, addr):
        # host, port = addr
        # print("Received from {} on port {}: {}".format(host, port, datagram))
        self.container.users[0].send_message(datagram)


class GnuRadioClient:

    def __init__(self, port_gnu_radio, host_sle, port_sle):
        f = GnuRadioFactory()
        f.container = self
        self.connectors = {}
        self.users = []
        self.connectors.update({'json': reactor.connectTCP(host_sle, port_sle, f)})
        self.connectors.update({'udp': reactor.listenUDP(port_gnu_radio, GnuRadioClientUdp(self))})

    def start_reactor(self):
        print('GNU Radio client is now running!')
        reactor.run()


def main(port_gnu_radio, host_sle, port_sle):
    client = GnuRadioClient(port_gnu_radio, host_sle, port_sle)
    client.start_reactor()
