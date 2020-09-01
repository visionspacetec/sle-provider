import logging; logging.basicConfig(level=logging.DEBUG); logger = logging.getLogger(__name__)
import struct
import datetime as dt
from slecommon.datatypes.raf_pdu import FrameOrNotification as RafFrameOrNotification
from .baseband.dataProviderProtocolFactory import DataProviderProtocolFactory
from .service.commonProviderProtocolFactory import CommonProviderProtocolFactory
from .service.commonStatelessProviderProtocolFactory import CommonStatelessProviderProtocolFactory
from .management.restfulManager import RestfulManager
from .management.security.realm import Realm
from .management.security.hash import check_hashed_password
from twisted.web import guard
from twisted.cred.checkers import FilePasswordDB
from twisted.cred.portal import Portal
from twisted.web.server import Site
from twisted.internet import reactor, ssl

configurable_sle_parameters = ['authentication-delay',
                               'transmit-queue-size',
                               'startup-timer',
                               'allow-non-use-heartbeat',
                               'min-heartbeat',
                               'max-heartbeat',
                               'min-deadfactor',
                               'max-deadfactor',
                               'max-trace-length',
                               'min-reporting-cycle',
                               'max-reporting-cycle',
                               'server-types',
                               'local-id',
                               'local-password',
                               'remote-peers']
commands = ['start-telemetry',
            'stop-telemetry']


class SleProvider(object):

    def __init__(self):
        # Servers
        self.servers = {}
        self.connectors = {}
        self.ports = {}
        self.data_endpoints = []
        self.users = []
        # SLE Configuration
        self.authentication_delay = 60
        self.transmit_queue_size = 20
        self.startup_timer = 180
        self.allow_non_use_heartbeat = True
        self.min_heartbeat = 25
        self.max_heartbeat = 60
        self.min_deadfactor = 2
        self.max_deadfactor = 10
        self.max_trace_length = 200
        self.min_reporting_cycle = 8
        self.max_reporting_cycle = 60
        # ToDo For Version 1 SI OID Mapping is missing
        self.server_types = {
            'rtnAllFrames': {2, 3, 4, 5},
            'fwdCltu': {2, 3, 4, 5}
        }
        # Credentials
        # ToDo Move in-memory passwords to file
        self.local_id = ''
        self.local_password = ''
        self.remote_peers = {}
        # Service Instances
        self.si_config = {}

    def initialize_server(self, name, server_type, port, print_frames=False):
        if name not in self.servers:
            if server_type == 'sle_protocol':
                self.servers[name] = CommonProviderProtocolFactory(self, print_frames)
            elif server_type == 'sle_stateless_protocol':
                self.servers[name] = CommonStatelessProviderProtocolFactory(self, print_frames)
            elif server_type == 'json_data_protocol':
                self.servers[name] = DataProviderProtocolFactory(self, print_frames)
            elif server_type in ['https_rest_protocol', 'http_rest_protocol']:
                checkers = [FilePasswordDB('http.password', delim=b'=', hash=check_hashed_password)]
                realm = Realm()
                realm.initialize(self, configurable_sle_parameters, commands)
                portal = Portal(realm, checkers)
                resource = guard.HTTPAuthSessionWrapper(portal, [guard.BasicCredentialFactory('auth')])
                self.servers[name] = Site(resource)
            elif server_type in ['https_no_auth_rest_protocol', 'http_no_auth_rest_protocol']:
                root = RestfulManager()
                root.container = self
                root.sle_config = configurable_sle_parameters
                root.commands = commands
                self.servers[name] = Site(root.app.resource())
            else:
                logger.error("Server type {} does not exist!".format(server_type))
                return False
            if port not in self.ports.values():
                if server_type in ['https_rest_protocol', 'https_no_auth_rest_protocol']:
                    with open('server.pem') as f:
                        cert_data = f.read()
                    self.certificate = ssl.PrivateCertificate.loadPEM(cert_data)
                    self.connectors.update({name: reactor.listenSSL(port,
                                                                    self.servers[name],
                                                                    self.certificate.options())})
                else:
                    self.connectors.update({name: reactor.listenTCP(port,
                                                                    self.servers[name])})
                self.ports.update({name: port})
                logger.info("{} with {} is now running on port: {}".format(name, server_type, port))
                return True
            else:
                logger.error("Port {} already used!".format(port))
                return False
        else:
            logger.error("Server with name {} already exists!".format(name))
            return False

    def remove_server(self, name):
        if name not in self.servers:
            logger.error("Server {} does not exist!".format(name))
            return False
        else:
            self.connectors[name].stopListening()
            logger.info("Successfully stopped server {} on port {}".format(name, self.ports[name]))
            self.connectors.pop(name)
            self.servers.pop(name)
            self.ports.pop(name)
            return True

    def start_reactor(self):
        logger.info('SLE Provider is now running!')
        reactor.run()

    def stop_reactor(self):
        logger.info('Stopping the SLE Provider!')
        reactor.stop()

    def _annotated_frame_handler(self,
                                 earth_receive_time,
                                 antenna_id,
                                 delivered_frame_quality,
                                 data):
        for si in self.si_config:
            if '.raf=' in si:
                frame = RafFrameOrNotification()['annotatedFrame']
            else:
                raise NotImplementedError()
            if self.si_config[si]['delivery_mode'] == 'TIMELY_ONLINE':
                if self.si_config[si]['state'] == 'active':
                    for user in self.users:
                        if user._inst_id == si:
                            if (self.si_config[si]['requested_frame_quality'] == delivered_frame_quality) or \
                                    (self.si_config[si]['requested_frame_quality'] == 'allFrames'):
                                str_time = dt.datetime.strptime(earth_receive_time, '%Y-%m-%d %H:%M:%S.%f')
                                time_days = (str_time - dt.datetime(1958, 1, 1)).days
                                time_ms = (str_time -
                                           dt.datetime(str_time.year, str_time.month, str_time.day)).seconds \
                                           * 1000 + ((str_time - dt.datetime(str_time.year, str_time.month,
                                                                             str_time.day)).microseconds // 1000)
                                time_micro = ((str_time -
                                               dt.datetime(str_time.year, str_time.month, str_time.day)).microseconds
                                              % 1000)
                                receive_time = struct.pack('!HIH', time_days, time_ms, time_micro)
                                # ToDo Format time correctly SLE V1&V2 Microsec V3 Picosec
                                frame['earthReceiveTime']['ccsdsFormat'] = receive_time
                                frame['antennaId']['localForm'] = str(antenna_id).encode('utf-8')
                                frame['deliveredFrameQuality'] = delivered_frame_quality
                                frame['data'] = bytes.fromhex(data)
                                user.append_to_transfer_buffer(frame)
            elif self.si_config[si]['delivery_mode'] == 'COMPLETE_ONLINE':
                raise NotImplementedError()
                # ToDo Implement online buffer
            elif self.si_config[si]['delivery_mode'] == 'OFFLINE':
                raise NotImplementedError()
                # ToDo Implement offline buffer

    def _notification_handler(self,
                              notification_type,
                              production_status=None,
                              time=None,
                              carrier_lock_status=None,
                              subcarrier_lock_status=None,
                              symbol_sync_lock_status=None):
        for si in self.si_config:
            if '.raf=' in si:
                frame = RafFrameOrNotification()['syncNotification']
            else:
                raise NotImplementedError()
            if (self.si_config[si]['delivery_mode'] == 'TIMELY_ONLINE') \
                    and (self.si_config[si]['state'] == 'active'):
                for user in self.users:
                    if user._inst_id == si:
                        if notification_type == 'endOfData':
                            frame['notification']['endOfData'] = None
                            user.append_to_transfer_buffer(frame)
                        elif notification_type == 'excessiveDataBacklog':
                            frame['notification']['excessiveDataBacklog'] = None
                            user.append_to_transfer_buffer(frame)
                        elif notification_type == 'productionStatusChange':
                            frame['notification']['productionStatusChange'] = production_status
                            user._production_status = production_status
                            user.append_to_transfer_buffer(frame)
                        elif notification_type == 'lossFrameSync':
                            time = struct.pack('!HIH',
                                                   (dt.datetime.strptime(time,
                                                    '%Y-%m-%d %H:%M:%S.%f') -
                                                    dt.datetime(1958, 1, 1)).days, 0, 0)
                            frame['notification']['lossFrameSync']['time']['ccsdsFormat'] = time
                            frame['notification']['lossFrameSync']['carrierLockStatus'] = carrier_lock_status
                            frame['notification']['lossFrameSync']['subcarrierLockStatus'] = subcarrier_lock_status
                            frame['notification']['lossFrameSync']['symbolSyncLockStatus'] = symbol_sync_lock_status
                            user._carrier_lock_status = carrier_lock_status
                            user._subcarrier_lock_status = subcarrier_lock_status
                            user._symbol_sync_lock_status = symbol_sync_lock_status
                            user.append_to_transfer_buffer(frame)
                        else:
                            raise Exception()
