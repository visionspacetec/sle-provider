import logging; logging.basicConfig(level=logging.DEBUG); logger = logging.getLogger(__name__)
import struct
import datetime as dt
from .commonProtocol import CommonProtocol
from slecommon.datatypes.cltu_pdu import CltuProviderToUserPdu
# from slecommon.datatypes.cltu_structure import CltuParameterName
from slecommon.proxy.authentication import make_credentials
from slecommon.proxy.authentication import check_invoke_credentials
from twisted.internet import reactor


class CltuProtocol(CommonProtocol):

    def __init__(self):
        pass

    def _initialise(self):
        self.add_handler('CltuPeerAbortInvocation', self._peer_abort_invocation_handler)
        self.add_handler('CltuStartInvocation', self._start_invocation_handler)
        self.add_handler('CltuStopInvocation', self._stop_invocation_handler)
        # self.add_handler('RafGetParameterInvocation', self._get_parameter_invocation_handler)
        # self.add_handler('RafScheduleStatusReportInvocation', self._schedule_status_report_invocation_handler)
        self._production_status = 'operational'
        self._transfer_buffer = None
        self._release_timer = None
        self._report_timer = None
        self.factory.container.si_config[self._inst_id]['report_cycle'] = None

    def _peer_abort_invocation_handler(self, pdu):
        logger.debug('Peer Abort Invocation received!')
        if self.factory.container.si_config[self._inst_id]['state'] not in {'ready', 'active'}:
            logger.error('Invalid state transition')
            self.peer_abort()
            return
        logging.debug('Peer Abort with reason: {} received'.format(pdu['rafPeerAbortInvocation']))
        self.factory.container.si_config[self._inst_id]['state'] = 'unbound'
        self.disconnect()

    def _start_invocation_handler(self, pdu):
        logger.debug('Start Invocation received!')
        if self.factory.container.si_config[self._inst_id]['state'] is not 'ready':
            logger.error('Invalid state transition')
            self.peer_abort()
        else:
            pdu = pdu['cltuStartInvocation']
            if 'used' in pdu['invokerCredentials']:
                self._invoker_credentials = pdu['invokerCredentials']['used']
            else:
                self._invoker_credentials = None
            self._invoke_id = int(pdu['invokeId'])
            self.first_cltu_identification = pdu['firstCltuIdentification']
            pdu_return = CltuProviderToUserPdu()['cltuStartReturn']
            if self.factory.container.remote_peers[self._initiator_id]['authentication_mode'] == 'ALL':
                pdu_return['performerCredentials']['used'] = make_credentials(self.factory.container.local_id,
                                                                              self.factory.container.local_password)
            else:
                pdu_return['performerCredentials']['unused'] = None
            pdu_return['invokeId'] = self._invoke_id

            if self.factory.container.remote_peers[self._initiator_id]['authentication_mode'] == \
                'ALL' and not check_invoke_credentials(self._invoker_credentials, self._initiator_id,
                                                       str(self.factory.container.remote_peers[
                                                               str(self._initiator_id)]['password'])):
                pdu_return['result']['negativeResult']['common'] = 'otherReason'
            else:
                start_radiation_time = str(dt.datetime.utcnow())
                str_time = dt.datetime.strptime(start_radiation_time, '%Y-%m-%d %H:%M:%S.%f')
                time_days = (str_time - dt.datetime(1958, 1, 1)).days
                time_ms = (str_time - dt.datetime(str_time.year, str_time.month, str_time.day)).seconds \
                          * 1000 + ((str_time - dt.datetime(str_time.year, str_time.month,
                                                            str_time.day)).microseconds // 1000)
                time_micro = ((str_time -
                               dt.datetime(str_time.year, str_time.month, str_time.day)).microseconds
                              % 1000)
                start_radiation_time = struct.pack('!HIH', time_days, time_ms, time_micro)
                pdu_return['result']['positiveResult']['startRadiationTime']['ccsdsFormat'] = start_radiation_time
                pdu_return['result']['positiveResult']['stopRadiationTime']['undefined'] = None
            self._send_pdu(pdu_return)
            if 'negativeResult' not in pdu_return['result']:
                self.factory.container.si_config[self._inst_id]['state'] = 'active'

    def _stop_invocation_handler(self, pdu):
        logger.debug('Stop Invocation received!')
        if self.factory.container.si_config[self._inst_id]['state'] is not 'active':
            logger.error('Invalid state transition')
            self.peer_abort()
        else:
            pdu = pdu['cltuStopInvocation']
            pdu_return = CltuProviderToUserPdu()['cltuStopReturn']
            if 'used' in pdu['invokerCredentials']:
                self._invoker_credentials = pdu['invokerCredentials']['used']
                if check_invoke_credentials(self._invoker_credentials, self._initiator_id,
                                            str(self.factory.container.remote_peers[
                                                    str(self._initiator_id)]['password'])):
                    pdu_return['credentials']['used'] = make_credentials(self.factory.container.local_id,
                                                                         str(self.factory.container.remote_peers[
                                                                                 str(self._initiator_id)]['password']))
            else:
                pdu_return['credentials']['unused'] = None
                self._invoker_credentials = None
            self._invoke_id = int(pdu['invokeId'])
            pdu_return['invokeId'] = self._invoke_id
            pdu_return['result']['positiveResult'] = None
            self._send_pdu(pdu_return)
            if 'positiveResult' in pdu_return['result']:
                self.factory.container.si_config[self._inst_id]['state'] = 'ready'
                if self._release_timer is not None:
                    if (self._release_timer.called == 1) or (self._release_timer.cancelled == 1):
                        self._release_timer = None
                    else:
                        self._release_timer.cancel()
                        self._release_timer = None

    # def _get_parameter_invocation_handler(self, pdu):
    #    pass

    # def _schedule_status_report_invocation_handler(self, pdu):
    #    pass

    # def _send_status_report(self):
    #    pass

    def append_to_transfer_buffer(self, frame_or_notification):
        pass

    def _send_transfer_buffer(self):
        pass
