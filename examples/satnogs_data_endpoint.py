import json
import os
import requests
from twisted.internet.protocol import DatagramProtocol
from twisted.internet import reactor
from twisted.internet.task import LoopingCall

from satnogs_data import SatNOGSNetwork

OBSERVATION_ID = int(os.getenv('SLE_PROVIDER_OBSERVATION_ID', '1'))
PAST_OBSERVATION = os.getenv('SLE_PROVIDER_PAST_OBSERVATION', 'FALSE')


class SatNOGSEndpoint(DatagramProtocol):

    def __init__(self):
        super().__init__()
        self.cfg = json.load(open('/usr/local/sle-provider/examples/satnogs_config.json'))
        self.satnogs = SatNOGSNetwork(self.cfg)
        self.observation_data = self.satnogs.get_observation(OBSERVATION_ID).json()
        self.observation_count = len(self.observation_data[0]['demoddata'])

    def startProtocol(self):
        self.transport.connect(os.getenv('SLE_MIDDLEWARE_TM_HOSTNAME', '127.0.0.1'),
                               int(os.getenv('SLE_MIDDLEWARE_GOOD_FRAMES', 16887)))
        self.observation_data = self.satnogs.get_observation(OBSERVATION_ID).json()
        self.observation_count = len(self.observation_data[0]['demoddata'])

    def send_message(self):
        print('Send message...')
        if PAST_OBSERVATION == 'TRUE':
            for data in self.observation_data[0]['demoddata']:
                self.transport.write(requests.get(data['payload_demod']).content)
        else:
            self.observation_data = self.satnogs.get_observation(OBSERVATION_ID).json()
            if self.observation_count < len(self.observation_data[0]['demoddata']):
                for data in self.observation_data[0]['demoddata'][self.observation_count:]:
                    self.transport.write(requests.get(data['payload_demod']).content)
                self.observation_count = len(self.observation_data[0]['demoddata'])

    def looping_call(self):
        if PAST_OBSERVATION == 'FALSE':
            looping_call = LoopingCall(self.send_message)
            looping_call.start(int(os.getenv('SLE_PROVIDER_POLLING_DELAY', '10')))
        else:
            self.send_message()


endpoint = SatNOGSEndpoint()
reactor.callLater(int(os.getenv('SLE_PROVIDER_STARTUP_DELAY', '0')), endpoint.looping_call)
reactor.listenUDP(0, endpoint)
reactor.run()
