import logging; logging.basicConfig(level=logging.DEBUG); logger = logging.getLogger(__name__)
import os
import json
import datetime as dt
import requests
import zmq
import time
import binascii

from twisted.internet import reactor, protocol
from twisted.internet.task import LoopingCall
from slecommon.frames import SpacePacket, TelemetryTransferFrame, ax25_csp_to_spp
from bitstring import BitArray
from collections import OrderedDict

ZEROMQ_SUB_URI = str(os.getenv('ZEROMQ_SUB_URI', "tcp://127.0.0.1:5560"))
ZEROMQ_SOCKET_RCVTIMEO = int(os.getenv('ZEROMQ_SOCKET_RCVTIMEO', "10"))

class JsonClient(protocol.Protocol):

    def connectionMade(self):
        try:
            logger.info("Connection to the SLE provider successful")
            self._rem = ''
            self.factory.container.users.append(self)
        except Exception as e:
            logger.info("Not able to connect to the SLE provider: {}".format(e))
            self.disconnect()

    def connectionLost(self, reason):
        pass

    def dataReceived(self, data):
        try:
            data = (self._rem + data.decode()).encode()
            self._rem = ''
            pdu = json.loads(data)
            logger.info("The SLE server said: {}".format(pdu))
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
            if pdu['command'] == 'start-telemetry':
                observation_id = pdu['args'][0].split('=')[1]
                self.factory.container.observation_id = observation_id
                self.factory.container.stopped = False

                if pdu['args'].__len__() > 1:
                    self.wrapper = dict()
                    self.wrapper.update({'name': pdu['args'][1].split('=')[1]})

                    if self.wrapper['name'] == 'CCSDS-TM-SPP':
                        args = dict()
                        for arg in pdu['args'][2:]:
                            args.update({arg.split('=')[0]: arg.split('=')[1]})
                        self.wrapper.update({'args': args})
                    elif self.wrapper['name'] == 'OPS-SAT':
                        args = dict()
                        for arg in pdu['args'][2:]:
                            args.update({arg.split('=')[0]: arg.split('=')[1]})
                        self.wrapper.update({'args': args})
                    elif self.wrapper['name'] == 'None':
                        self.wrapper = None
                    else:
                        raise NotImplementedError
                else:
                    self.wrapper = None
                logger.info("Wrapper used: {}".format(self.wrapper))

                self.factory.container.start_timer = \
                    reactor.callInThread(self.factory.container.subscribe)
            elif pdu['command'] == 'stop-telemetry':
                self.factory.container.stopped = True

    def send_message(self, data, frame_quality, earth_receive_time):
        if self.wrapper is None:
            msg = {'earthReceiveTime': earth_receive_time,
                   'antennaId': self.factory.container.antenna_id,
                   'deliveredFrameQuality': frame_quality,
                   'data': data.hex()}
        elif self.wrapper['name'] == 'CCSDS-TM-SPP':
            space_packet = SpacePacket()
            space_packet['version'] = int(self.wrapper['args']['spp-version'])
            space_packet['type'] = int(self.wrapper['args']['spp-type'])
            space_packet['sec_header_flag'] = self.wrapper['args']['spp-secondary-header-flag'] == 'True'
            space_packet['apid'] = int(self.wrapper['args']['spp-apid'])
            space_packet['sequence_flags'] = int(self.wrapper['args']['spp-sequence-flags'])
            space_packet['seq_ctr_or_pkt_name'] = int(self.wrapper['args']['spp-sequence-count-or-packet-name'])
            space_packet['data'] = BitArray(data)
            tm_frame = TelemetryTransferFrame()
            tm_frame.length = int(self.wrapper['args']['tm-length'])
            tm_frame.has_fecf = self.wrapper['args']['tm-has-fecf'] == 'True'
            tm_frame.is_idle = self.wrapper['args']['tm-is-idle'] == 'True'
            tm_frame['version'] = int(self.wrapper['args']['tm-version'])
            tm_frame['spacecraft_id'] = int(self.wrapper['args']['tm-spacecraft-id'])
            tm_frame['virtual_channel_id'] = int(self.wrapper['args']['tm-virtual-channel-id'])
            tm_frame['ocf_flag'] = self.wrapper['args']['tm-ocf-flag'] == 'True'
            tm_frame['master_chan_frame_count'] = int(self.wrapper['args']['tm-master-channel-frame-count'])
            tm_frame['virtual_chan_frame_count'] = int(self.wrapper['args']['tm-virtual-channel-frame-count'])
            tm_frame['sec_header_flag'] = self.wrapper['args']['tm-secondary-header-flag'] == 'True'
            tm_frame['sync_flag'] = self.wrapper['args']['tm-sync-flag'] == 'True'
            tm_frame['pkt_order_flag'] = self.wrapper['args']['tm-packet-order-flag'] == 'True'
            tm_frame['seg_len_id'] = int(self.wrapper['args']['tm-segment-length-id'])
            tm_frame['first_hdr_ptr'] = int(self.wrapper['args']['tm-first-header-pointer'], 2)
            tm_frame['ocf'] = BitArray(self.wrapper['args']['tm-ocf'])
            tm_frame.space_packet = space_packet
            # ToDo: Packet counters
            msg = {'earthReceiveTime': earth_receive_time,
                   'antennaId': self.factory.container.antenna_id,
                   'deliveredFrameQuality': frame_quality,
                   'data': tm_frame.encode()}
        elif self.wrapper['name'] == 'OPS-SAT':
            frame = OrderedDict(
                [
                    ("timestamp", dt.datetime.strptime(earth_receive_time, "%Y-%m-%d %H:%M:%S.%f")),
                    ("data", data)
                ]
            )
            space_packet_data = ax25_csp_to_spp(frame)
            if not space_packet_data:
                logger.info("No SPP, skipping packet")
                return
            space_packet = SpacePacket(data=BitArray(space_packet_data))
            tm_frame = TelemetryTransferFrame()
            tm_frame.length = int(self.wrapper['args']['tm-length'])
            tm_frame.has_fecf = self.wrapper['args']['tm-has-fecf'] == 'True'
            tm_frame.is_idle = self.wrapper['args']['tm-is-idle'] == 'True'
            tm_frame['version'] = int(self.wrapper['args']['tm-version'])
            tm_frame['spacecraft_id'] = int(self.wrapper['args']['tm-spacecraft-id'])
            tm_frame['virtual_channel_id'] = int(self.wrapper['args']['tm-virtual-channel-id'])
            tm_frame['ocf_flag'] = self.wrapper['args']['tm-ocf-flag'] == 'True'
            master_chan_frame_count = int(self.wrapper['args']['tm-master-channel-frame-count']) % 256
            virtual_chan_frame_count = int(self.wrapper['args']['tm-virtual-channel-frame-count']) % 256
            tm_frame['master_chan_frame_count'] = master_chan_frame_count
            tm_frame['virtual_chan_frame_count'] = virtual_chan_frame_count
            self.wrapper['args']['tm-master-channel-frame-count'] = str((master_chan_frame_count + 1) % 256)
            self.wrapper['args']['tm-virtual-channel-frame-count'] = str((virtual_chan_frame_count + 1) % 256)
            tm_frame['sec_header_flag'] = self.wrapper['args']['tm-secondary-header-flag'] == 'True'
            tm_frame['sync_flag'] = self.wrapper['args']['tm-sync-flag'] == 'True'
            tm_frame['pkt_order_flag'] = self.wrapper['args']['tm-packet-order-flag'] == 'True'
            tm_frame['seg_len_id'] = int(self.wrapper['args']['tm-segment-length-id'])
            tm_frame['first_hdr_ptr'] = int(self.wrapper['args']['tm-first-header-pointer'], 2)
            tm_frame['ocf'] = BitArray(self.wrapper['args']['tm-ocf'])
            tm_frame.space_packet = space_packet
            # ToDo: Packet counters
            msg = {'earthReceiveTime': earth_receive_time,
                   'antennaId': self.factory.container.antenna_id,
                   'deliveredFrameQuality': frame_quality,
                   'data': tm_frame.encode()}
        else:
            raise NotImplementedError
        self.transport.write(json.dumps(msg).encode())

    def disconnect(self):
        logger.info("SLE server disconnecting!")
        self.transport.loseConnection()


class JsonClientFactory(protocol.ClientFactory):

    def clientConnectionFailed(self, connector, reason):
        logger.info("SLE server connection failed - goodbye!")
        reactor.stop()

    def clientConnectionLost(self, connector, reason):
        logger.info(reason)
        logger.info("Connection to the SLE server lost!")
        logger.info("Trying to reconnect...")
        connector.connect()

    def buildProtocol(self, addr):
        p = JsonClient()
        p.factory = self
        return p


class SatNOGSMiddleware:

    def __init__(self, host_sle, port_sle, print_frames):
        f = JsonClientFactory()
        f.container = self
        self.antenna_id = ''
        self.stopped = True
        self.context = zmq.Context()
        self.print_frames = print_frames
        self.users = []
        self.connectors = {}
        self.frame_counter = 0
        self.connectors.update({'jsonClient': reactor.connectTCP(host_sle,
                                                                 port_sle,
                                                                 f)})

    def subscribe(self):
        self.subscriber = self.context.socket(zmq.SUB)
        self.subscriber.setsockopt(zmq.RCVTIMEO, ZEROMQ_SOCKET_RCVTIMEO)
        logger.info('Subscriber connects to %s' % (ZEROMQ_SUB_URI))
        self.subscriber.connect(ZEROMQ_SUB_URI)
        logger.info('Subscriber subscribes to data publisher')
        self.subscriber.setsockopt(zmq.SUBSCRIBE, b'')
        while True:
            try:
                [norad_id, timestamp, frame, station, obs_id, station_id] = self.subscriber.recv_multipart()
                if self.observation_id == obs_id.decode("utf-8"):
                    frame_time = timestamp.decode("utf-8")[:23].replace('T',' ')
                    frame = binascii.unhexlify(frame)
                    self.antenna_id = station_id.decode("utf-8")
                    self.users[0].send_message(frame, 'good', frame_time)
                    self.frame_counter += 1
                    logger.info('Frames sent: ' + str(self.frame_counter))
            except zmq.ZMQError as error:
                pass
            if self.stopped:
                logger.info('Subscriber unsubscribes from data publisher')
                logger.info('Subscriber close connection to %s' % (ZEROMQ_SUB_URI))
                self.subscriber.close()
                break

    def start_reactor(self):
        logger.info("SatNOGS middleware is now running!")
        if self.print_frames:
            logger.info("Print of frames enabled")
        reactor.run()


def main(host_sle, port_sle, print_frames=False):
    client = SatNOGSMiddleware(host_sle, port_sle, print_frames)
    client.start_reactor()
