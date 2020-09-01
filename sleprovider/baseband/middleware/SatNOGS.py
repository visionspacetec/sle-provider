import logging; logging.basicConfig(level=logging.DEBUG); logger = logging.getLogger(__name__)
import os
import json
import datetime as dt
import requests
from twisted.internet import reactor, protocol
from twisted.internet.task import LoopingCall
from .frames import SpacePacket, TelemetryTransferFrame, ax25_csp_to_spp
from bitstring import BitArray
from collections import OrderedDict

SLE_PROVIDER_STARTUP_DELAY = int(os.getenv('SLE_PROVIDER_STARTUP_DELAY', 10))
SLE_PROVIDER_POLLING_DELAY = int(os.getenv('SLE_PROVIDER_POLLING_DELAY', 10))


class SatNOGSNetwork(object):
    def __init__(self, config):
        self.url = config['default']['NETWORK_API_URL']
        self.key = config['default']['NETWORK_API_KEY']
        self.params = config['default']['NETWORK_PARAMS']
        self.header = self._get_header()

    def _get_header(self):
        token = self.key
        return {'Authorization': 'Token ' + token}

    def get_observations(self):
        return requests.get(self.url, headers=self.header, params=self.params)

    def get_observation(self, observation_id):
        return requests.get(self.url, params={"id": observation_id})


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

    def _pdu_handler(self, pdu):
        if 'command' in pdu:
            if pdu['command'] == 'start-telemetry':
                observation_id = pdu['args'][0].split('=')[1]
                self.factory.container.cfg['default']['NETWORK_PARAMS']['satellite__norad_cat_id'] = observation_id
                self.factory.container.observation_data = \
                    self.factory.container.satnogs.get_observation(observation_id).json()
                self.factory.container.observation_count = \
                    len(self.factory.container.observation_data[0]['demoddata'])
                self.factory.container.antenna_id = self.factory.container.observation_data[0]['ground_station']

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

                if dt.datetime.fromisoformat(self.factory.container.observation_data[0]['end'][:-1]) < dt.datetime.utcnow():
                    self.factory.container.past_observation = 'TRUE'
                    self.factory.container.start_timer = \
                        reactor.callLater(SLE_PROVIDER_STARTUP_DELAY, self.factory.container.send_message)
                else:
                    self.factory.container.past_observation = 'FALSE'
                    self.factory.container.start_timer = \
                        reactor.callLater(SLE_PROVIDER_STARTUP_DELAY, self.factory.container.looping_call)
            elif pdu['command'] == 'stop-telemetry':
                if self.factory.container.past_observation == 'FALSE':
                    self.factory.container.looping_send_message_call.stop()

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


class SatNOGSMiddleware:

    def __init__(self, host_sle, port_sle, print_frames):
        f = JsonClientFactory()
        f.container = self
        self.antenna_id = ''
        self.past_observation = 'FALSE'
        self.observation_data = []
        self.observation_count = 0
        self.print_frames = print_frames
        self.cfg = \
            {
                "default":
                    {
                    "NETWORK_API_URL": str(os.getenv('SATNOGS_NETWORK_API_EXTERNAL')) + '/observations/',
                    "NETWORK_API_KEY": "",
                    "NETWORK_PARAMS": {"satellite__norad_cat_id": 0},
                    "DB_API_URL": "https://db.satnogs.org/api/telemetry",
                    "DB_API_KEY": ""
                    }
            }
        self.satnogs = SatNOGSNetwork(self.cfg)
        self.users = []
        self.connectors = {}
        self.connectors.update({'jsonClient': reactor.connectTCP(host_sle,
                                                                 port_sle,
                                                                 f)})

    def send_message(self):
        if self.past_observation == 'TRUE':
            for data in self.observation_data[0]['demoddata']:
                time = data['payload_demod'].split('_')
                if len(time) == 5:
                    time_rem = time[4]
                else:
                    time_rem = '0'
                time = ''.join(reversed(''.join(reversed(time[3])).replace('-', ':', 2)))
                time = str(dt.datetime.fromisoformat(time))
                time = time + '.' + time_rem
                self.users[0].send_message(requests.get(data['payload_demod']).content, 'good', time)
        else:
            self.observation_data = \
                self.satnogs.get_observation(self.cfg['default']['NETWORK_PARAMS']['satellite__norad_cat_id']).json()
            if self.observation_count < len(self.observation_data[0]['demoddata']):
                for data in self.observation_data[0]['demoddata'][self.observation_count:]:
                    time = data['payload_demod'].split('_')
                    if len(time) == 5:
                        time_rem = time[4]
                    else:
                        time_rem = '0'
                    time = ''.join(reversed(''.join(reversed(time[3])).replace('-', ':', 2)))
                    time = str(dt.datetime.fromisoformat(time))
                    time = time + '.' + time_rem
                    self.users[0].send_message(requests.get(data['payload_demod']).content, 'good', time)
                self.observation_count = len(self.observation_data[0]['demoddata'])

    def looping_call(self):
        if self.past_observation == 'FALSE':
            self.looping_send_message_call = LoopingCall(self.send_message)
            self.looping_send_message_call.start(SLE_PROVIDER_POLLING_DELAY)
        else:
            self.send_message()

    def start_reactor(self):
        print("SatNOGS middleware is now running!")
        if self.print_frames:
            print("Print of frames enabled")
        reactor.run()


def main(host_sle, port_sle, print_frames=False):
    client = SatNOGSMiddleware(host_sle, port_sle, print_frames)
    client.start_reactor()
