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
        self.add_handler('CltuTransferDataInvocation', self._transfer_data_invocation_handler)
        self.add_handler('CltuScheduleStatusReportInvocation', self._schedule_status_report_invocation_handler)
        self._cltu_last_processed = None
        self._cltu_last_ok = None
        self._cltu_production_status = 'operational'
        self._uplink_status = 'nominal'
        self._cltu_buffer_availiable = 4096  # ToDo: Read from service instance
        self._number_of_cltus_received = 0
        self._number_of_cltus_processed = 0
        self._number_of_cltus_radiated = 0
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

    def _transfer_data_invocation_handler(self, pdu):
        logger.debug('Transfer Data Invocation received!')
        if self.factory.container.si_config[self._inst_id]['state'] is not 'active':
            logger.error('Invalid state transition')
            self.peer_abort()
        else:
            pdu = pdu['cltuTransferDataInvocation']
            pdu_return = CltuProviderToUserPdu()['cltuTransferDataReturn']
            if 'used' in pdu['invokerCredentials']:
                self._invoker_credentials = pdu['invokerCredentials']['used']
                if check_invoke_credentials(
                        self._invoker_credentials,
                        self._initiator_id,
                        str(self.factory.container.remote_peers[
                                str(self._initiator_id)]['password'])):
                    pdu_return['performerCredentials']['used'] = make_credentials(
                        self.factory.container.local_id,
                        str(self.factory.container.remote_peers[str(self._initiator_id)]['password']))
            else:
                pdu_return['performerCredentials']['unused'] = None
                self._invoker_credentials = None
            self._invoke_id = int(pdu['invokeId'])
            pdu_return['invokeId'] = self._invoke_id

            self.cltu_identification = int(pdu['cltuIdentification'])
            # ToDo: Minimum time in milliseconds between radiation of this and next CLTU
            self.delay_time = int(pdu['delayTime'])

            if 'undefined' in pdu['earliestTransmissionTime']:
                self.earliest_transmission_time = None
            elif 'known' in pdu['earliestTransmissionTime']:
                # ToDo: Implement
                raise NotImplementedError
                # self.earliest_transmission_time = pdu['earliestTransmissionTime']['known']
            if 'undefined' in pdu['latestTransmissionTime']:
                self.latest_transmission_time = None
            elif 'known' in pdu['latestTransmissionTime']:
                # ToDo: Implement
                raise NotImplementedError
                # self.latest_transmission_time = pdu['latestTransmissionTime']['known']

            if str(pdu['slduRadiationNotification']) == 'doNotProduceNotification':
                pass
            else:
                # ToDo: Implement produceNotification mechanism
                raise NotImplementedError
            self._number_of_cltus_received += 1
            self.last_radiation_start_time = str(dt.datetime.utcnow())  # ToDo: How to find out when actually started?
            str_time = dt.datetime.strptime(self.last_radiation_start_time, '%Y-%m-%d %H:%M:%S.%f')
            time_days = (str_time - dt.datetime(1958, 1, 1)).days
            time_ms = (str_time - dt.datetime(str_time.year, str_time.month, str_time.day)).seconds \
                      * 1000 + ((str_time - dt.datetime(str_time.year, str_time.month,
                                                        str_time.day)).microseconds // 1000)
            time_micro = ((str_time -
                           dt.datetime(str_time.year, str_time.month, str_time.day)).microseconds
                          % 1000)
            self.last_radiation_start_time = struct.pack('!HIH', time_days, time_ms, time_micro)
            self._cltu_last_processed = self.cltu_identification  # ToDo: Get feedback from data_endpoint if actually radiated

            self.factory.container.data_endpoints[0].send_command('send-telecommand', [bytes(pdu['cltuData']).decode()])

            self._number_of_cltus_processed += 1
            self._number_of_cltus_radiated += 1  # ToDo: Get feedback from data_endpoint if actually radiated
            self.last_radiation_stop_time = str(dt.datetime.utcnow())  # ToDo: How to find out when radiated?
            str_time = dt.datetime.strptime(self.last_radiation_stop_time, '%Y-%m-%d %H:%M:%S.%f')
            time_days = (str_time - dt.datetime(1958, 1, 1)).days
            time_ms = (str_time - dt.datetime(str_time.year, str_time.month, str_time.day)).seconds \
                      * 1000 + ((str_time - dt.datetime(str_time.year, str_time.month,
                                                        str_time.day)).microseconds // 1000)
            time_micro = ((str_time -
                           dt.datetime(str_time.year, str_time.month, str_time.day)).microseconds
                          % 1000)
            self.last_radiation_stop_time = struct.pack('!HIH', time_days, time_ms, time_micro)
            self._cltu_last_ok = self.cltu_identification  # ToDo: Get feedback from data_endpoint if actually radiated

            # ToDo: implement logic and different counting for return cltu identification if rejected
            pdu_return['cltuIdentification'] = self.cltu_identification + 1
            pdu_return['cltuBufferAvailable'] = self._cltu_buffer_availiable
            # ToDo: Negative result
            pdu_return['result']['positiveResult'] = None
            self._send_pdu(pdu_return)

    def _schedule_status_report_invocation_handler(self, pdu):
        logger.debug('Schedule Status Report Invocation received!')
        pdu = pdu['cltuScheduleStatusReportInvocation']
        pdu_return = CltuProviderToUserPdu()['cltuScheduleStatusReportReturn']
        if 'used' in pdu['invokerCredentials']:
            self._invoker_credentials = pdu['invokerCredentials']['used']
            pdu_return['performerCredentials']['used'] = make_credentials(self.factory.container.local_id,
                                                                          self.factory.container.local_password)
        else:
            self._invoker_credentials = None
            pdu_return['performerCredentials']['unused'] = None
        # ToDo: pdu_return['result']['negativeResult']['common'] = 'duplicateInvokeId'
        pdu_return['invokeId'] = int(pdu['invokeId'])
        if self.factory.container.si_config[self._inst_id]['state'] not in {'ready', 'active'}:
            pdu_return['result']['negativeResult']['common'] = 'otherReason'
        elif self.factory.container.remote_peers[self._initiator_id]['authentication_mode'] == \
                'ALL' and not check_invoke_credentials(self._invoker_credentials,
                                                       self._initiator_id,
                                                       str(self.factory.container.remote_peers[
                                                               str(self._initiator_id)]['password'])):
            pdu_return['result']['negativeResult']['common'] = 'otherReason'
        elif 'periodically' in pdu['reportRequestType']:
            if not (self.factory.container.min_reporting_cycle
                    <= int(pdu['reportRequestType']['periodically'])
                    <= self.factory.container.max_reporting_cycle):
                pdu_return['result']['negativeResult']['specific'] = 'invalidReportingCycle'
            else:
                if self._report_timer is None:
                    self._report_timer = reactor.callLater(int(pdu['reportRequestType']['periodically']),
                                                           self._send_status_report)
                    self.factory.container.si_config[self._inst_id]['report_cycle'] = \
                        int(pdu['reportRequestType']['periodically'])
                else:
                    self.factory.container.si_config[self._inst_id]['report_cycle'] = \
                        int(pdu['reportRequestType']['periodically'])
                    self._report_timer.reset(int(pdu['reportRequestType']['periodically']))
                pdu_return['result']['positiveResult'] = None
        elif 'stop' in pdu['reportRequestType']:
            if self._report_timer is None:
                pdu_return['result']['negativeResult']['specific'] = 'alreadyStopped'
            else:
                if (self._report_timer.called == 1) or (self._report_timer.cancelled == 1):
                    self._report_timer = None
                    pdu_return['result']['negativeResult']['specific'] = 'alreadyStopped'
                else:
                    self._report_timer.cancel()
                    self._report_timer = None
                    pdu_return['result']['positiveResult'] = None
        elif 'immediately' in pdu['reportRequestType']:
            self._send_status_report()
            if self._report_timer is not None:
                if (self._report_timer.called == 1) or (self._report_timer.cancelled == 1):
                    self._report_timer = None
                else:
                    self._report_timer.cancel()
                    self._report_timer = None
            pdu_return['result']['positiveResult'] = None
        else:
            raise Exception()
        self._send_pdu(pdu_return)

    def _send_status_report(self):
        if self.factory.container.si_config[self._inst_id]['state'] not in {'ready', 'active'}:
            logger.error('Can not send status report in state: {}'
                         .format(self.factory.container.si_config[self._inst_id]['state']))
            return
        pdu_invoc = CltuProviderToUserPdu()['cltuStatusReportInvocation']
        if self.factory.container.remote_peers[self.factory.container.si_config[self._inst_id]['initiator_id']][
                'authentication_mode'] == 'ALL':
            pdu_invoc['invokerCredentials']['used'] = make_credentials(self.factory.container.local_id,
                                                                       self.factory.container.local_password)
        else:
            pdu_invoc['invokerCredentials']['unused'] = None
        if self._cltu_last_processed is None:
            pdu_invoc['cltuLastProcessed']['noCltuProcessed'] = None
        else:
            pdu_invoc['cltuLastProcessed']['cltuProcessed']['cltuIdentification'] = self.cltu_identification
            pdu_invoc['cltuLastProcessed']['cltuProcessed']['radiationStartTime']['known']['ccsdsFormat'] = \
                self.last_radiation_start_time
            pdu_invoc['cltuLastProcessed']['cltuProcessed']['cltuStatus'] = 'radiated'  # ToDo: Relate to something
        if self._cltu_last_ok is None:
            pdu_invoc['cltuLastOk']['noCltuOk'] = None
        else:
            pdu_invoc['cltuLastOk']['cltuOk']['cltuIdentification'] = self.cltu_identification
            pdu_invoc['cltuLastOk']['cltuOk']['radiationStopTime']['ccsdsFormat'] = \
                self.last_radiation_stop_time
        pdu_invoc['cltuProductionStatus'] = self._cltu_production_status
        pdu_invoc['uplinkStatus'] = self._uplink_status
        pdu_invoc['numberOfCltusReceived'] = self._number_of_cltus_received
        pdu_invoc['numberOfCltusProcessed'] = self._number_of_cltus_processed
        pdu_invoc['numberOfCltusRadiated'] = self._number_of_cltus_radiated
        pdu_invoc['cltuBufferAvailable'] = self._cltu_buffer_availiable
        self._send_pdu(pdu_invoc)
        if self._report_timer is not None:
            if self._report_timer.called == 1:
                self._report_timer = reactor.callLater(self.factory.container.si_config[self._inst_id]['report_cycle'],
                                                       self._send_status_report)

    # def _get_parameter_invocation_handler(self, pdu):
    #     pass
