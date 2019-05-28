from twisted.internet import reactor, protocol
from twisted.internet import defer
from twisted.internet.task import LoopingCall
try:
    from cortex.clients import Telemetry
    from cortex.clients import Monitor
    from cortex.clients import Control
    from cortex.clients.transport import receive_message
    from cortex.clients.transport import parse_tm_message
except ImportError:
    pass
import json
import datetime as dt
from bitstring import BitArray
from slecommon import frames


class CortexClient(protocol.Protocol):

    def connectionMade(self):
        try:
            self.mon = Monitor(self.factory.host_cortex)
            self.ctrl = Control(self.factory.host_cortex)
            self.tm = Telemetry(self.factory.host_cortex)
            print("Cortex connection made")
            self._rem = ''
        except Exception as e:
            print("Not able to connect to the Cortex: {}".format(e))
            self.disconnect()
            # self.init_frame()
            # self._rem = ''
            # print("Starting Packet Generation")
            # reactor.callLater(0.5, self.send_message)

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

    def disconnect(self):
        print("SLE server disconnecting!")
        self.transport.loseConnection()

    def init_frame(self):
        self.tm_frame = frames.TelemetryTransferFrame()
        self.tm_frame.length = 1115
        self.tm_frame.has_fecf = True
        self.tm_frame.is_idle = True
        self.tm_frame['version'] = 0
        self.tm_frame['spacecraft_id'] = 3
        self.tm_frame['virtual_channel_id'] = 7
        self.tm_frame['ocf_flag'] = True
        self.tm_frame['master_chan_frame_count'] = 0
        self.tm_frame['virtual_chan_frame_count'] = 0
        self.tm_frame['sec_header_flag'] = False
        self.tm_frame['sync_flag'] = False
        self.tm_frame['pkt_order_flag'] = False
        self.tm_frame['seg_len_id'] = 3
        self.tm_frame['first_hdr_ptr'] = int('11111111110', 2)
        self.tm_frame['ocf'] = BitArray('0x01000000')

    def send_message(self, data=None):
        msg = {'earthReceiveTime': str(dt.datetime.utcnow()),
               'antennaId': 'NNO',
               'deliveredFrameQuality': 'good',
               'data': None}
        if data is not None:
            msg['data'] = data
            self.transport.write(json.dumps(msg).encode())
            print('data sent')
        else:
            msg['data'] = self.tm_frame.encode()
            self.transport.write(json.dumps(msg).encode())
            self.tm_frame['master_chan_frame_count'] = (self.tm_frame['master_chan_frame_count'] + 1) % 256
            self.tm_frame['virtual_chan_frame_count'] = (self.tm_frame['virtual_chan_frame_count'] + 1) % 256
            reactor.callLater(10, self.send_message)

    def _pdu_handler(self, pdu):
        if 'command' in pdu:
            if pdu['command'] == 'start-telemetry':
                try:
                    if pdu['args'][0] == 'TMUA':
                        channel = 0
                    elif pdu['args'][0] == 'TMUB':
                        channel = 1
                    self.tm.start_telemetry(channel)
                    LoopingCall(self._read_frame_buffer_parse_message).start(0)
                except Exception as e:
                    print("Not able to start telemetry {}".format(e))
                    return
            elif pdu['command'] == 'stop-telemetry':
                try:
                    if pdu['args'][0] == 'TMUA':
                        channel = 0
                    elif pdu['args'][0] == 'TMUB':
                        channel = 1
                    self.tm.channel = channel
                    self.tm.stop_telemetry()
                except Exception as e:
                    print("Not able to stop telemetry {}".format(e))
                    return
            else:
                print("Unknown command from SLE server received")
                return
        else:
            print("Received invalid request from SLE server")
            return

    def _read_buffer_from_socket(self):
        return receive_message(self.tm._sock)

    @defer.inlineCallbacks
    def _read_frame_buffer_parse_message(self):
        frame = yield parse_tm_message(self._read_buffer_from_socket())
        print(frame)
        try:
            data = BitArray(frame['frame_data']).hex
            data = data[int(frame['sync_word_length'] / 4):]
            self.send_message(data)
        except Exception as e:
            print(e)


class CortexFactory(protocol.ClientFactory):

    def clientConnectionFailed(self, connector, reason):
        print("SLE server connection failed - goodbye!")
        reactor.stop()

    def clientConnectionLost(self, connector, reason):
        print("Connection to the SLE server lost!")

    def buildProtocol(self, addr):
        p = CortexClient()
        p.factory = self
        p.frame_length = self.frame_length
        return p


def main(host_cortex, host_sle, port_sle, frame_length):
    f = CortexFactory()
    f.frame_length = frame_length
    f.host_cortex = host_cortex
    reactor.connectTCP(host_sle, port_sle, f)
    reactor.run()
