import os
from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor
from twisted.internet.task import LoopingCall
from slecommon import frames
from bitstring import BitArray


class UdpEndpoint(DatagramProtocol):

    def startProtocol(self):
        self.transport.connect(os.getenv('SLE_MIDDLEWARE_HOSTNAME', '127.0.0.1'),
                               int(os.getenv('SLE_MIDDLEWARE_GOOD_FRAMES', 16887)))
        looping_call = LoopingCall(self.send_message)
        looping_call.start(1)

    def send_message(self):
        tm_frame = frames.TelemetryTransferFrame()
        tm_frame.length = 1115
        tm_frame.has_fecf = True
        tm_frame.is_idle = True
        tm_frame['version'] = 0
        tm_frame['spacecraft_id'] = 3
        tm_frame['virtual_channel_id'] = 7
        tm_frame['ocf_flag'] = True
        tm_frame['master_chan_frame_count'] = 0
        tm_frame['virtual_chan_frame_count'] = 0
        tm_frame['sec_header_flag'] = False
        tm_frame['sync_flag'] = False
        tm_frame['pkt_order_flag'] = False
        tm_frame['seg_len_id'] = 3
        tm_frame['first_hdr_ptr'] = int('11111111110', 2)
        tm_frame['ocf'] = BitArray('0x01000000')
        self.transport.write(bytes.fromhex(tm_frame.encode()))

reactor.listenUDP(0, UdpEndpoint())
reactor.run()
