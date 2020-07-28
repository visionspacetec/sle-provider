import logging; logging.basicConfig(level=logging.DEBUG); logger = logging.getLogger(__name__)
from collections import defaultdict
from twisted.internet import protocol
from twisted.internet import reactor
import struct
import os
import requests

from slecommon.proxy.authentication import make_credentials
from slecommon.proxy.authentication import check_invoke_credentials
from slecommon.proxy.coding import SleCoding
from slecommon.datatypes.raf_pdu import RafUsertoProviderPdu
from slecommon.datatypes.raf_pdu import RafProvidertoUserPdu

TML_CONTEXT_MSG_FORMAT = '!IIbbbbIHH'
TML_CONTEXT_MSG_TYPE = 0x02000000
TML_CONTEXT_HB_FORMAT = '!ii'
TML_CONTEXT_HEARTBEAT_TYPE = 0x03000000

sii_dict = {'1.3.112.4.3.1.2.40': 'rsp',
            '1.3.112.4.3.1.2.7': 'cltu',
            '1.3.112.4.3.1.2.53': 'spack',
            '1.3.112.4.3.1.2.46': 'rcf',
            '1.3.112.4.3.1.2.16': 'tcva',
            '1.3.112.4.3.1.2.38': 'rsl-fg',
            '1.3.112.4.3.1.2.22': 'raf',
            '1.3.112.4.3.1.2.14': 'fsl-fg',
            '1.3.112.4.3.1.2.10': 'fsp',
            '1.3.112.4.3.1.2.52': 'sagr',
            '1.3.112.4.3.1.2.49': 'rocf',
            '1.3.112.4.3.1.2.12': 'tcf',
            '1.3.112.4.3.1.2.44': 'rcfsh'}


class CommonProtocol(protocol.Protocol):

    def __init__(self):
        pass

    def connectionMade(self):
        logger.info('Connection with client established')
        self.factory.container.users.append(self)
        self._state = 'TML starting'
        self._invoked_ids = {}
        self._handlers = defaultdict(list)
        self.add_handler('RafBindInvocation', self._bind_invocation_handler)
        self.add_handler('RafUnbindInvocation', self._unbind_invocation_handler)
        self._hostname = None
        self._port = None
        self._heartbeat = None
        self._deadfactor = None
        self._buffer_size = 256000
        self._initiator_id = None
        self._responder_id = None
        self._password = None
        self._peer_password = None
        self._responder_port = None
        self._inst_id = None
        self._requested_observation = None
        self._auth_level = 'none'
        self._coding = SleCoding(decode_spec=RafUsertoProviderPdu())
        self._service_type = 'rtnAllFrames'
        self._version = 5
        self._tms_timer = reactor.callLater(self.factory.container.startup_timer, self._timer, 'TML start-up')
        self._hbt_timer = None
        self._hbr_timer = None
        self._cpa_timer = None
        self._buffer = bytearray()
        self._wrapper = None

    def connectionLost(self, reason):
        logger.info('Connection with client lost')
        self.factory.container.users.remove(self)
        if self._state == 'Peer Aborting':
            if self._cpa_timer is not None:
                if self._cpa_timer.called is 0:
                    if self._cpa_timer.cancelled is 0:
                        self._cpa_timer.cancel()
        if self._hbt_timer is not None:
            if self._hbt_timer.called is 0:
                if self._hbt_timer.cancelled is 0:
                    self._hbt_timer.cancel()
        if self._hbr_timer is not None:
            if self._hbr_timer.called is 0:
                if self._hbr_timer.cancelled is 0:
                    self._hbr_timer.cancel()
        if self.__class__ is not CommonProtocol:
            self.factory.container.si_config[self._inst_id]['state'] = 'unbound'
            self.factory.container.si_config[self._inst_id]['report_cycle'] = None
            self.factory.container.si_config[self._inst_id]['requested_frame_quality'] = \
                self.factory.container.si_config[self._inst_id]['permitted_frame_quality'][0]
            if (self._release_timer is not None) \
                    and (self._release_timer.called != 1) \
                    and (self._release_timer.cancelled != 1):
                self._release_timer.cancel()
                self._release_timer = None
            if (self._report_timer is not None) \
                    and (self._report_timer.called != 1) \
                    and (self._report_timer.cancelled != 1):
                self._report_timer.cancel()
                self._report_timer = None
        self.factory.container.si_config.pop(self._inst_id, None)

    def disconnect(self):
        logger.debug('Disconnecting')
        self.transport.loseConnection()

    def _timer(self, name):
        logger.error('{} Timer expired, aborting!'.format(name))
        self.disconnect()

    def _reset_hbr_timer(self):
        if self._heartbeat != 0:
            self._hbr_timer.reset(self._heartbeat*self._deadfactor)
        else:
            pass

    def _send_heartbeat(self):
        hb = struct.pack(
            TML_CONTEXT_HB_FORMAT,
            TML_CONTEXT_HEARTBEAT_TYPE,
            0)
        self.transport.write(hb)
        self._hbt_timer = reactor.callLater(self._heartbeat, self._send_heartbeat)

    def _send_pdu(self, pdu):
        self.transport.write(self._coding.encode(pdu))
        if self._hbt_timer is not None:
            if (self._hbt_timer.cancelled != 1) and (self._hbt_timer.called != 1):
                self._hbt_timer.reset(self._heartbeat)

    def dataReceived(self, data):
        """ Handler for processing data received from the Provider into PDUs"""
        msg = self._buffer + bytearray(data)
        self._buffer = bytearray()
        hdr, rem = msg[:8], msg[8:]
        # Context Message Received
        if hdr[:4].hex() == '02000000':
            logger.debug('Context Message received')
            if self._state != 'TML starting':
                logger.debug('Context Message received while running')
                self.disconnect()
            body_len = int.from_bytes(hdr[4:], byteorder='big')
            body = rem[:body_len]
            rem = rem[body_len:]
            if body[:8].hex() != '4953503100000001':
                self._tms_timer.cancel()
                logger.debug('Invalid Context Message received')
                self.disconnect()
            req_heartbeat = int(bytes(body[8:10].hex(), 'utf-8'), 16)
            req_deadfactor = int(bytes(body[10:12].hex(), 'utf-8'), 16)
            if req_heartbeat == 0:
                if self.factory.container.allow_non_use_heartbeat:
                    logger.debug('Accepted non use Heartbeat')
                    self._heartbeat = 0
                    self._state = 'data transfer'
                    if len(rem) != 12:
                        rem = msg[20:]
                        self.dataReceived(bytes(rem))
                    return
                else:
                    self._tms_timer.cancel()
                    logger.debug('Request to not use Heartbeats rejected')
                    self.disconnect()
            elif self.factory.container.min_heartbeat \
                    <= req_heartbeat \
                    <= self.factory.container.max_heartbeat:
                self._heartbeat = req_heartbeat
            else:
                logger.debug('Requested Heartbeat rate rejected')
                self._tms_timer.cancel()
                self.disconnect()
            if self.factory.container.min_deadfactor \
                    <= req_deadfactor \
                    <= self.factory.container.max_deadfactor:
                self._deadfactor = req_deadfactor
            else:
                logger.debug('Requested Deadfactor rejected')
                self._tms_timer.cancel()
                self.disconnect()
            self._state = 'data transfer'
            self._hbr_timer = reactor.callLater(self._heartbeat*self._deadfactor, self._timer, 'Heartbeat Receive')
            self._hbt_timer = reactor.callLater(self._heartbeat, self._send_heartbeat)
            if len(rem) != 12:
                rem = msg[20:]
                self.dataReceived(bytes(rem))
        else:
            if self._state == 'TML starting':
                self._tms_timer.cancel()
                logger.debug('First message was not Context Message')
                self.disconnect()
            elif self._state == 'Peer Aborting':
                logger.debug('Waiting for the connection to be released by the client')
                return
            # PDU Received
            if hdr[:4].hex() == '01000000':
                if self._state == 'data transfer' and self._tms_timer is not None:
                    self._tms_timer.cancel()
                    self._tms_timer = None
                self._reset_hbr_timer()
                body_len = int.from_bytes(hdr[4:], byteorder='big')
                if len(rem) < body_len:
                    self._buffer = msg
                    return
                else:
                    body = rem[:body_len]
                    rem = rem[body_len:]
                    decoded_pdu = self._coding.decode(bytes(hdr + body))
                    if decoded_pdu:
                        self._handle_pdu(decoded_pdu)
                    else:
                        msg = msg[len(hdr) + len(body):]
                    if rem.hex() != '':
                        self.dataReceived(bytes(rem))

            # Heartbeat Received
            elif hdr[:8].hex() == '0300000000000000':
                self._reset_hbr_timer()
                logger.debug('Heartbeat received')
                if rem.hex() != '':
                    self.dataReceived(bytes(rem))
            else:
                pass

    def add_handler(self, event, handler):
        self._handlers[event].append(handler)

    def _handle_pdu(self, pdu):
        pdu_key = pdu.getName()
        pdu_key = pdu_key[:1].upper() + pdu_key[1:]
        if pdu_key in self._handlers:
            pdu_handlers = self._handlers[pdu_key]
            for h in pdu_handlers:
                h(pdu)
        else:
            err = (
                'PDU of type {} has no associated handlers. '
                'Unable to process further and skipping ...'
            )
            logger.error(err.format(pdu_key))

    def _bind_invocation_handler(self, pdu):
        logger.debug('Bind Invocation received!')
        if 'used' in pdu['rafBindInvocation']['invokerCredentials']:
            self._invoker_credentials = pdu['rafBindInvocation']['invokerCredentials']['used']
        else:
            self._invoker_credentials = None
        self._responder_port = str(pdu['rafBindInvocation']['responderPortIdentifier'])
        if str(pdu['rafBindInvocation']['serviceType']) == 'rtnAllFrames':
            self._service_type = str(pdu['rafBindInvocation']['serviceType'])
            self._coding = SleCoding(decode_spec=RafUsertoProviderPdu())
            self._version = int(pdu['rafBindInvocation']['versionNumber'])
            pdu_return = RafProvidertoUserPdu()['rafBindReturn']
        else:
            raise Exception('Not Implemented')
            # ToDo implement more service types

        pdu_return['responderIdentifier'] = self.factory.container.local_id
        self._initiator_id = pdu['rafBindInvocation']['initiatorIdentifier']
        ###
        # Query the API to get the registered Users
        peer_request = requests.get(str(os.getenv('SATNOGS_NETWORK_API_INTERNAL')) + '/sle-users')
        peers = peer_request.json()
        for peer in peers:
            remote_peer = {str(peer['INITIATOR_ID']):
                               {
                                    'authentication_mode': str(peer['INITIATOR_AUTH']),
                                    'password': str(peer['INITIATOR_PASS']),
                                    'satellites': peer['SATELLITES']
                               }
                           }
            self.factory.container.remote_peers.update(remote_peer)
        ###
        if self._initiator_id not in self.factory.container.remote_peers:
            pdu_return['result']['negative'] = 'accessDenied'
        elif self._service_type not in self.factory.container.server_types:
            pdu_return['result']['negative'] = 'serviceTypeNotSupported'
        elif self._version not in self.factory.container.server_types[self._service_type]:
            pdu_return['result']['negative'] = 'versionNotSupported'

        if 'negative' not in pdu_return['result']:
            self._inst_id = ''
            ctr = 0
            for i in pdu['rafBindInvocation']['serviceInstanceIdentifier']:
                self._inst_id += sii_dict[str(i[0]['identifier'])] + '=' + str(i[0]['siAttributeValue'])
                if ctr == 1:
                    self._requested_observation = str(i[0]['siAttributeValue']).split('-')[-1]
                if i != pdu['rafBindInvocation']['serviceInstanceIdentifier'][-1]:
                    self._inst_id += '.'
                ctr += 1
            ###
            # Query the API for the requested observation and check if it exists
            observation_request = requests.get(
                str(os.getenv('SATNOGS_NETWORK_API_EXTERNAL')) + '/observations',
                params={"id": self._requested_observation})
            observations = observation_request.json()
            if observations != []:
                observation = observations[0]
                # ToDo: Start and stop time conversation
                service_instance = {
                    'sagr=1.spack=ID-{}-PASS-{}.rsl-fg=1.raf=onlt1'.format(self._initiator_id,
                                                                           observation['id']):
                        {
                            'start_time': None,
                            'stop_time': None,
                            'initiator_id': str(self._initiator_id),
                            'responder_id': self.factory.container.local_id,
                            'return_timeout_period': int(os.getenv('SLE_PROVIDER_RETURN_TIMEOUT_PERIOD', 15)),
                            'delivery_mode': 'TIMELY_ONLINE',
                            'initiator': 'USER',
                            'permitted_frame_quality':
                                ['allFrames', 'erredFramesOnly', 'goodFramesOnly'],
                            'latency_limit': int(os.getenv('SLE_PROVIDER_LATENCY_LIMIT', 9)),
                            'transfer_buffer_size': int(os.getenv('SLE_PROVIDER_TRANSFER_BUFFER_SIZE', 20)),
                            'report_cycle': None,
                            'requested_frame_quality': 'allFrames',
                            'state': 'unbound'}
                        }
                self.factory.container.si_config.update(service_instance)

            satellite_accessible = False
            for sat in self.factory.container.remote_peers[self._initiator_id]['satellites']:
                if sat['id'] == observation['norad_cat_id']:
                    satellite_accessible = True
                    self._wrapper = sat['wrapper']
                    break

            if self._inst_id not in self.factory.container.si_config:
                pdu_return['result']['negative'] = 'noSuchServiceInstance'
            elif self.factory.container.si_config[self._inst_id]['state'] != 'unbound':
                pdu_return['result']['negative'] = 'alreadyBound'
            elif self.factory.container.si_config[self._inst_id]['state'] == 'halted':
                pdu_return['result']['negative'] = 'outOfService'
            elif not satellite_accessible:
                pdu_return['result']['negative'] = 'siNotAccessibleToThisInitiator'
            # ToDo out of provisioning period
            else:
                # ToDo move upwards otherwise unreachable
                if self._service_type is 'rtnAllFrames':
                    if '.raf=' not in self._inst_id:
                        pdu_return['result']['negative'] = 'inconsistentServiceType'
        if self._initiator_id in self.factory.container.remote_peers:
            if self.factory.container.remote_peers[self._initiator_id]['authentication_mode'] == 'NONE':
                if 'used' in pdu['rafBindInvocation']['invokerCredentials']:
                    logger.info("Disconnecting, authentication modes do not match")
                    self.disconnect()
                pdu_return['performerCredentials']['unused'] = None
            elif (('used' in pdu['rafBindInvocation']['invokerCredentials'])
                    and (self.factory.container.remote_peers[self._initiator_id]['authentication_mode'] == 'NONE')) \
                    or ('used' not in pdu['rafBindInvocation']['invokerCredentials']
                        and ((self.factory.container.remote_peers[self._initiator_id]['authentication_mode'] == 'BIND')
                        or (self.factory.container.remote_peers[self._initiator_id]['authentication_mode'] == 'ALL'))):
                logger.info("Disconnecting, authentication modes do not match")
                self.disconnect()
                return
            else:
                pdu_return['performerCredentials']['used'] = make_credentials(self.factory.container.local_id,
                                                                              self.factory.container.local_password)
        else:
            pdu_return['performerCredentials']['unused'] = None

        if 'negative' not in pdu_return['result']:
            if self.factory.container.remote_peers[self._initiator_id]['authentication_mode'] != 'NONE':
                if check_invoke_credentials(self._invoker_credentials, self._initiator_id,
                                            str(self.factory.container.remote_peers[str(self._initiator_id)]['password'])):
                    pdu_return['result']['positive'] = self._version
                    self.factory.container.si_config[self._inst_id]['state'] = 'ready'
                else:
                    pdu_return['result']['negative'] = 'accessDenied'
                    self._inst_id = None
                    logger.error('Bind error {}'.format(str(pdu_return['result']['negative'])))
            else:
                pdu_return['result']['positive'] = self._version
                self.factory.container.si_config[self._inst_id]['state'] = 'ready'
        else:
            self._inst_id = None
            logger.error('Bind error {}'.format(str(pdu_return['result']['negative'])))
        self._send_pdu(pdu_return)

        if 'negative' not in pdu_return['result']:
            if self._service_type == 'rtnAllFrames':
                from .rafProtocol import RafProtocol
                self.__class__ = RafProtocol
                self._initialise()

    def _unbind_invocation_handler(self, pdu):
        logger.debug('Unbind Invocation received!')
        if self.factory.container.si_config[self._inst_id]['state'] != 'ready':
            logger.error('Invalid state transition')
            self.peer_abort()
        else:
            if self._service_type is 'rtnAllFrames':
                pdu = pdu['rafUnbindInvocation']
                pdu_return = RafProvidertoUserPdu()['rafUnbindReturn']
            # else:
            # ToDo implement more service types
            if self.factory.container.remote_peers[self._initiator_id]['authentication_mode'] != 'ALL':
                pdu_return['responderCredentials']['unused'] = None
            else:
                pdu_return['responderCredentials']['used'] = make_credentials(self.factory.container.local_id,
                                                                              self.factory.container.local_password)
            pdu_return['result']['positive'] = None
            self._send_pdu(pdu_return)
            if ('positive' in pdu_return['result']) and (self.__class__ is not CommonProtocol):
                self.factory.container.si_config[self._inst_id]['state'] = 'unbound'
                self.factory.container.si_config[self._inst_id]['report_cycle'] = None
                if (self._release_timer is not None) \
                        and (self._release_timer.called != 1) \
                        and (self._release_timer.cancelled != 1):
                    self._release_timer.cancel()
                    self._release_timer = None
                if (self._report_timer is not None) \
                        and (self._report_timer.called != 1) \
                        and (self._report_timer.cancelled != 1):
                    self._report_timer.cancel()
                    self._report_timer = None
            logger.debug('Unbind reason: {}'.format(str(pdu['unbindReason'])))

    def peer_abort(self, reason=127):
        """Send a peer abort notification"""
        logger.info('Sending Peer Abort')
        if self.factory.container.si_config[self._inst_id]['state'] is not ('ready' or 'active'):
            logger.error('Invalid state transition requested! Must be ready or running!')
            return
        if self._service_type == 'rtnAllFrames':
            pdu = RafProvidertoUserPdu()['rafPeerAbortInvocation']
        # else:
        # ToDo implement more service types
        pdu = reason
        self._cpa_timer = reactor.callLater(10, self._timer, 'Peer Abort')
        self._send_pdu(pdu)
        self._hbr_timer.cancel()
        self._hbt_timer.cancel()
        self._state = 'Peer Aborting'
        if self.__class__ is not CommonProtocol:
            self.factory.container.si_config[self._inst_id]['state'] = 'unbound'
            self.factory.container.si_config[self._inst_id]['report_cycle'] = None
            self.factory.container.si_config[self._inst_id]['requested_frame_quality'] = \
                self.factory.container.si_config[self._inst_id]['permitted_frame_quality'][0]
            if (self._release_timer is not None) \
                    and (self._release_timer.called != 1) \
                    and (self._release_timer.cancelled != 1):
                self._release_timer.cancel()
                self._release_timer = None
            if (self._report_timer is not None) \
                    and (self._report_timer.called != 1) \
                    and (self._report_timer.cancelled != 1):
                self._report_timer.cancel()
                self._report_timer = None
        # ToDo save info for status report
