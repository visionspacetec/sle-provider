import logging; logging.basicConfig(level=logging.DEBUG); logger = logging.getLogger(__name__)
from .commonStatelessProtocol import CommonStatelessProtocol
from slecommon.datatypes.raf_pdu import RafProvidertoUserPdu
from slecommon.datatypes.raf_structure import RafParameterName
from slecommon.datatypes.raf_structure import PermittedFrameQualitySet
from slecommon.proxy.authentication import make_credentials
from slecommon.proxy.authentication import check_invoke_credentials
from twisted.internet import reactor


class RafStatelessProtocol(CommonStatelessProtocol):

    def __init__(self):
        pass

    def _initialise(self):
        self.add_handler('RafPeerAbortInvocation', self._peer_abort_invocation_handler)
        self.add_handler('RafStartInvocation', self._start_invocation_handler)
        self.add_handler('RafStopInvocation', self._stop_invocation_handler)
        self.add_handler('RafGetParameterInvocation', self._get_parameter_invocation_handler)
        self.add_handler('RafScheduleStatusReportInvocation', self._schedule_status_report_invocation_handler)
        self._data_continuity = -1
        self._number_of_error_free_frames_delivered = 0
        self._number_of_frames_delivered = 0
        self._frame_sync_lock_status = 'inLock'
        self._symbol_sync_lock_status = 'inLock'
        self._carrier_lock_status = 'inLock'
        self._subcarrier_lock_status = 'inLock'
        # ToDo Production status update when receiving message from data endpoint
        self._production_status = 'running'  # 'halted'
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
        # ToDo discard transfer buffer
        # ToDo generate info for status report

    def _start_invocation_handler(self, pdu):
        logger.debug('Start Invocation received!')
        if self.factory.container.si_config[self._inst_id]['state'] is not 'ready':
            logger.error('Invalid state transition')
            self.peer_abort()
        else:
            pdu = pdu['rafStartInvocation']
            if 'used' in pdu['invokerCredentials']:
                self._invoker_credentials = pdu['invokerCredentials']['used']
            else:
                self._invoker_credentials = None
            self._invoke_id = int(pdu['invokeId'])
            if 'undefined' in pdu['startTime']:
                self.start_time = None
            elif 'known' in pdu['startTime']:
                self.start_time = pdu['startTime']['known']
            if 'undefined' in pdu['stopTime']:
                self.stop_time = None
            elif 'known' in pdu['stopTime']:
                self.stop_time = pdu['stopTime']['known']
            # else:
            # ToDo raise error

            pdu_return = RafProvidertoUserPdu()['rafStartReturn']
            if self.factory.container.remote_peers[self._initiator_id]['authentication_mode'] == 'ALL':
                pdu_return['performerCredentials']['used'] = make_credentials(self.factory.container.local_id,
                                                                              self.factory.container.local_password)
            else:
                pdu_return['performerCredentials']['unused'] = None
            pdu_return['invokeId'] = self._invoke_id
            '''
            if self._invoke_id in self._invoked_ids:
                pdu_return['result']['negativeResult']['common'] = 'duplicateInvokeId'
            '''
            # ToDo: pdu_return['result']['negative']['specific'] = 'unableToComply'
            # ToDo: pdu_return['result']['negative']['specific'] = 'invalidStartTime'
            # ToDo: pdu_return['result']['negative']['specific'] = 'invalidStopTime'
            # ToDo: pdu_return['result']['negative']['common'] = 'otherReason'
            if self.factory.container.si_config[self._inst_id]['state'] is 'halted':
                pdu_return['result']['negativeResult']['specific'] = 'outOfService'
            elif self.factory.container.si_config[self._inst_id]['delivery_mode'] == 'OFFLINE':  # ToDo: case sensitive?
                if 'undefined' in pdu['startTime'] or 'undefined' in pdu['stopTime']:
                    pdu_return['result']['negativeResult']['specific'] = 'missingTimeValue'
            elif str(pdu['requestedFrameQuality']) \
                    not in self.factory.container.si_config[self._inst_id]['permitted_frame_quality']:
                pdu_return['result']['negativeResult']['common'] = 'otherReason'
            elif self.factory.container.remote_peers[self._initiator_id]['authentication_mode'] == \
                    'ALL' and not check_invoke_credentials(self._invoker_credentials, self._initiator_id,
                                          str(self.factory.container.remote_peers[str(self._initiator_id)]['password'])):
                pdu_return['result']['negativeResult']['common'] = 'otherReason'
            else:
                pdu_return['result']['positiveResult'] = None
            self._send_pdu(pdu_return)
            if 'negativeResult' not in pdu_return['result']:
                self.factory.container.si_config[self._inst_id]['requested_frame_quality'] = \
                    str(pdu['requestedFrameQuality'])
                self.factory.container.si_config[self._inst_id]['state'] = 'active'

                if self._wrapper is not None:
                    if self._wrapper['name'] == 'CCSDS-TM-SPP':
                        self.factory.container.data_endpoints[0].send_command(
                            'start-telemetry',
                            ['OBSERVATION_ID={}'.format(self._requested_observation),
                             'WRAPPER={}'.format(self._wrapper['name']),
                             'tm-length={}'.format(self._wrapper['args']['tm-length']),
                             'tm-has-fecf={}'.format(self._wrapper['args']['tm-has-fecf']),
                             'tm-is-idle={}'.format(self._wrapper['args']['tm-is-idle']),
                             'tm-version={}'.format(self._wrapper['args']['tm-version']),
                             'tm-spacecraft-id={}'.format(self._wrapper['args']['tm-spacecraft-id']),
                             'tm-virtual-channel-id={}'.format(self._wrapper['args']['tm-virtual-channel-id']),
                             'tm-ocf-flag={}'.format(self._wrapper['args']['tm-ocf-flag']),
                             'tm-master-channel-frame-count={}'.format(self._wrapper['args']['tm-master-channel-frame-count']),
                             'tm-virtual-channel-frame-count={}'.format(self._wrapper['args']['tm-virtual-channel-frame-count']),
                             'tm-secondary-header-flag={}'.format(self._wrapper['args']['tm-secondary-header-flag']),
                             'tm-sync-flag={}'.format(self._wrapper['args']['tm-sync-flag']),
                             'tm-packet-order-flag={}'.format(self._wrapper['args']['tm-packet-order-flag']),
                             'tm-segment-length-id={}'.format(self._wrapper['args']['tm-segment-length-id']),
                             'tm-first-header-pointer={}'.format(self._wrapper['args']['tm-first-header-pointer']),
                             'tm-ocf={}'.format(self._wrapper['args']['tm-ocf']),
                             'spp-version={}'.format(self._wrapper['args']['spp-version']),
                             'spp-type={}'.format(self._wrapper['args']['spp-type']),
                             'spp-secondary-header-flag={}'.format(self._wrapper['args']['spp-secondary-header-flag']),
                             'spp-apid={}'.format(self._wrapper['args']['spp-apid']),
                             'spp-sequence-flags={}'.format(self._wrapper['args']['spp-sequence-flags']),
                             'spp-sequence-count-or-packet-name={}'.format(self._wrapper['args']['spp-sequence-count-or-packet-name'])
                             ])
                    elif  self._wrapper['name'] == 'OPS-SAT':
                        self.factory.container.data_endpoints[0].send_command(
                            'start-telemetry',
                            ['OBSERVATION_ID={}'.format(self._requested_observation),
                             'WRAPPER={}'.format(self._wrapper['name']),
                             'tm-length={}'.format(self._wrapper['args']['tm-length']),
                             'tm-has-fecf={}'.format(self._wrapper['args']['tm-has-fecf']),
                             'tm-is-idle={}'.format(self._wrapper['args']['tm-is-idle']),
                             'tm-version={}'.format(self._wrapper['args']['tm-version']),
                             'tm-spacecraft-id={}'.format(self._wrapper['args']['tm-spacecraft-id']),
                             'tm-virtual-channel-id={}'.format(self._wrapper['args']['tm-virtual-channel-id']),
                             'tm-ocf-flag={}'.format(self._wrapper['args']['tm-ocf-flag']),
                             'tm-master-channel-frame-count={}'.format(
                                 self._wrapper['args']['tm-master-channel-frame-count']),
                             'tm-virtual-channel-frame-count={}'.format(
                                 self._wrapper['args']['tm-virtual-channel-frame-count']),
                             'tm-secondary-header-flag={}'.format(self._wrapper['args']['tm-secondary-header-flag']),
                             'tm-sync-flag={}'.format(self._wrapper['args']['tm-sync-flag']),
                             'tm-packet-order-flag={}'.format(self._wrapper['args']['tm-packet-order-flag']),
                             'tm-segment-length-id={}'.format(self._wrapper['args']['tm-segment-length-id']),
                             'tm-first-header-pointer={}'.format(self._wrapper['args']['tm-first-header-pointer']),
                             'tm-ocf={}'.format(self._wrapper['args']['tm-ocf'])
                             ])
                    else:
                        self.factory.container.data_endpoints[0].send_command(
                            'start-telemetry',
                            ['OBSERVATION_ID={}'.format(self._requested_observation),
                             'WRAPPER=None'])
                else:
                    self.factory.container.data_endpoints[0].send_command(
                        'start-telemetry',
                        ['OBSERVATION_ID={}'.format(self._requested_observation),
                         'WRAPPER=None'])

    def _stop_invocation_handler(self, pdu):
        logger.debug('Stop Invocation received!')
        if self.factory.container.si_config[self._inst_id]['state'] is not 'active':
            logger.error('Invalid state transition')
            self.peer_abort()
        else:
            pdu = pdu['rafStopInvocation']
            pdu_return = RafProvidertoUserPdu()['rafStopReturn']
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
            # ToDo: pdu_return['result']['negative'] = 'duplicate Invoke-ID'
            # ToDo: pdu_return['result']['negative'] = 'other reason'
            pdu_return['result']['positiveResult'] = None
            self._send_pdu(pdu_return)
            if 'positiveResult' in pdu_return['result']:
                self.factory.container.si_config[self._inst_id]['state'] = 'ready'
                self.factory.container.si_config[self._inst_id]['requested_frame_quality'] = \
                    self.factory.container.si_config[self._inst_id]['permitted_frame_quality'][0]
                self._data_continuity = -1
                self.factory.container.data_endpoints[0].send_command(
                    'stop-telemetry',
                    [])
                if self._release_timer is not None:
                    if (self._release_timer.called == 1) or (self._release_timer.cancelled == 1):
                        self._release_timer = None
                    else:
                        self._release_timer.cancel()
                        self._release_timer = None

    def _get_parameter_invocation_handler(self, pdu):
        logger.debug('Get Parameter Invocation received!')
        pdu = pdu['rafGetParameterInvocation']
        pdu_return = RafProvidertoUserPdu()['rafGetParameterReturn']

        if 'used' in pdu['invokerCredentials']:
            self._invoker_credentials = pdu['invokerCredentials']['used']
        else:
            self._invoker_credentials = None
            pdu_return['performerCredentials']['unused'] = None
        self._invoke_id = int(pdu['invokeId'])
        pdu_return['invokeId'] = self._invoke_id
        if self.factory.container.si_config[self._inst_id]['state'] not in {'ready', 'active'}:
            pdu_return['result']['negativeResult']['common'] = 'otherReason'
        # ToDo: pdu_return['result']['negative'] = 'duplicate Invoke-ID'
        elif str(pdu['rafParameter']) not in [n for n in RafParameterName().namedValues]:
            pdu_return['result']['negativeResult'] = 'unknownParameter'
        elif self.factory.container.remote_peers[self._initiator_id]['authentication_mode'] == \
                'ALL' and not check_invoke_credentials(self._invoker_credentials, self._initiator_id,
                                            str(self.factory.container.remote_peers[str(self._initiator_id)][
                                                    'password'])):
            pdu_return['result']['negativeResult']['common'] = 'otherReason'
        else:
            if self.factory.container.remote_peers[self._initiator_id]['authentication_mode'] == 'ALL':
                if check_invoke_credentials(self._invoker_credentials, self._initiator_id,
                                                str(self.factory.container.remote_peers[str(self._initiator_id)][
                                                        'password'])):
                    pdu_return['performerCredentials']['used'] = make_credentials(self._initiator_id,
                                                                                str(self.factory.container.remote_peers[
                                                                                str(self._initiator_id)]['password']))
            raf_parameter = str(pdu['rafParameter'])
            if raf_parameter == 'bufferSize':
                pdu_return['result']['positiveResult']['parBufferSize']['parameterName'] = \
                    'bufferSize'
                pdu_return['result']['positiveResult']['parBufferSize']['parameterValue'] = \
                    self.factory.container.si_config[self._inst_id]['transfer_buffer_size']
            elif raf_parameter == 'deliveryMode':
                pdu_return['result']['positiveResult']['parDeliveryMode']['parameterName'] = \
                    'deliveryMode'
                if self.factory.container.si_config[self._inst_id]['delivery_mode'] == 'TIMELY_ONLINE':
                    pdu_return['result']['positiveResult']['parDeliveryMode']['parameterValue'] = \
                        'rtnTimelyOnline'
                elif self.factory.container.si_config[self._inst_id]['delivery_mode'] == 'COMPLETE_ONLINE':
                    pdu_return['result']['positiveResult']['parDeliveryMode']['parameterValue'] = \
                        'rtnCompleteOnline'
                elif self.factory.container.si_config[self._inst_id]['delivery_mode'] == 'OFFLINE':
                    pdu_return['result']['positiveResult']['parDeliveryMode']['parameterValue'] = \
                        'rtnOffline'
            elif raf_parameter == 'latencyLimit':
                pdu_return['result']['positiveResult']['parLatencyLimit']['parameterName'] = \
                    'latencyLimit'
                if self.factory.container.si_config[self._inst_id]['delivery_mode'] == 'OFFLINE':
                    pdu_return['result']['positiveResult']['parLatencyLimit']['parameterValue']['offline'] = \
                        None
                else:
                    pdu_return['result']['positiveResult']['parLatencyLimit']['parameterValue']['online'] = \
                        self.factory.container.si_config[self._inst_id]['latency_limit']
            elif raf_parameter == 'minReportingCycle':
                pdu_return['result']['positiveResult']['parMinReportingCycle']['parameterName'] = \
                    'minReportingCycle'
                pdu_return['result']['positiveResult']['parMinReportingCycle']['parameterValue'] = \
                    self.factory.container.min_reporting_cycle
            elif raf_parameter == 'permittedFrameQuality':
                pdu_return['result']['positiveResult']['parPermittedFrameQuality']['parameterName'] = \
                    'permittedFrameQuality'
                quality_set = PermittedFrameQualitySet()
                for pos, quality in enumerate(self.factory.container.si_config[self._inst_id]['permitted_frame_quality']):
                    quality_set.setComponentByPosition(pos, quality)
                pdu_return['result']['positiveResult']['parPermittedFrameQuality']['parameterValue'] = \
                    quality_set
            elif raf_parameter == 'reportingCycle':
                pdu_return['result']['positiveResult']['parReportingCycle']['parameterName'] = \
                    'reportingCycle'
                if self.factory.container.si_config[self._inst_id]['report_cycle'] is None:
                    pdu_return['result']['positiveResult']['parReportingCycle']['parameterValue']['periodicReportingOff'] = \
                        None
                else:
                    pdu_return['result']['positiveResult']['parReportingCycle']['parameterValue']['periodicReportingOn'] = \
                        self.factory.container.si_config[self._inst_id]['report_cycle']
            elif raf_parameter == 'requestedFrameQuality':
                pdu_return['result']['positiveResult']['parReqFrameQuality']['parameterName'] = \
                    'requestedFrameQuality'
                if self.factory.container.si_config[self._inst_id]['state'] == 'ready':
                    pdu_return['result']['positiveResult']['parReqFrameQuality']['parameterValue'] = \
                        self.factory.container.si_config[self._inst_id]['permitted_frame_quality'][0]
                else:
                    pdu_return['result']['positiveResult']['parReqFrameQuality']['parameterValue'] = \
                        self.factory.container.si_config[self._inst_id]['requested_frame_quality']
            elif raf_parameter == 'returnTimeoutPeriod':
                pdu_return['result']['positiveResult']['parReturnTimeout']['parameterName'] = \
                    'returnTimeoutPeriod'
                pdu_return['result']['positiveResult']['parReturnTimeout']['parameterValue'] = \
                    self.factory.container.si_config[self._inst_id]['return_timeout_period']
        self._send_pdu(pdu_return)

    def _schedule_status_report_invocation_handler(self, pdu):
        logger.debug('Get Schedule Status Report Invocation received!')
        pdu = pdu['rafScheduleStatusReportInvocation']
        pdu_return = RafProvidertoUserPdu()['rafScheduleStatusReportReturn']
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
        elif self.factory.container.si_config[self._inst_id]['delivery_mode'] == 'OFFLINE':
            pdu_return['result']['negativeResult']['specific'] = 'notSupportedInThisDeliveryMode'
        elif self.factory.container.remote_peers[self._initiator_id]['authentication_mode'] == \
                'ALL' and not check_invoke_credentials(self._invoker_credentials, self._initiator_id,
                                            str(self.factory.container.remote_peers[str(self._initiator_id)][
                                                    'password'])):
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
        pdu_invoc = RafProvidertoUserPdu()['rafStatusReportInvocation']
        if self.factory.container.remote_peers[self.factory.container.si_config[self._inst_id]['initiator_id']][
            'authentication_mode'] == 'ALL':
            pdu_invoc['invokerCredentials']['used'] = make_credentials(self.factory.container.local_id,
                                                                              self.factory.container.local_password)
        else:
            pdu_invoc['invokerCredentials']['unused'] = None
        pdu_invoc['errorFreeFrameNumber'] = self._number_of_error_free_frames_delivered
        pdu_invoc['deliveredFrameNumber'] = self._number_of_frames_delivered
        pdu_invoc['frameSyncLockStatus'] = self._frame_sync_lock_status
        pdu_invoc['symbolSyncLockStatus'] = self._symbol_sync_lock_status
        pdu_invoc['subcarrierLockStatus'] = self._subcarrier_lock_status
        pdu_invoc['carrierLockStatus'] = self._carrier_lock_status
        pdu_invoc['productionStatus'] = self._production_status
        self._send_pdu(pdu_invoc)
        if self._report_timer is not None:
            if self._report_timer.called == 1:
                self._report_timer = reactor.callLater(self.factory.container.si_config[self._inst_id]['report_cycle'],
                                                       self._send_status_report)

    def append_to_transfer_buffer(self, frame_or_notification):
        if self._transfer_buffer is None:
            self._transfer_buffer = RafProvidertoUserPdu()['rafTransferBuffer']
            self._release_timer = reactor.callLater(self.factory.container.si_config[self._inst_id]['latency_limit'],
                              self._send_transfer_buffer)
        if 'data' in frame_or_notification:
            if self.factory.container.remote_peers[self.factory.container.si_config[self._inst_id]['initiator_id']
            ]['authentication_mode'] == 'ALL':
                frame_or_notification['invokerCredentials']['used'] = make_credentials(self.factory.container.local_id,
                                                                              self.factory.container.local_password)
            else:
                frame_or_notification['invokerCredentials']['unused'] = None
            frame_or_notification['dataLinkContinuity'] = self._data_continuity
            frame_or_notification['privateAnnotation']['null'] = None
            self._number_of_frames_delivered += 1
            if str(frame_or_notification['deliveredFrameQuality']) == 'good':
                self._number_of_error_free_frames_delivered += 1
            self._data_continuity = 0
            # ToDo Data link continuity
        elif 'notification' in frame_or_notification:
            if self.factory.container.remote_peers[self.factory.container.si_config[self._inst_id]['initiator_id']
            ]['authentication_mode'] == 'ALL':
                frame_or_notification['invokerCredentials']['used'] = make_credentials(self.factory.container.local_id,
                                                                                       self.factory.container.local_password)
            else:
                frame_or_notification['invokerCredentials']['unused'] = None
        else:
            raise Exception('Bad Frame')
        if self.print_frames is True:
            logger.debug(frame_or_notification)
        if len(self._transfer_buffer) < (self.factory.container.si_config[self._inst_id]['transfer_buffer_size']):
            self._transfer_buffer.setComponentByPosition(len(self._transfer_buffer),
                                                         frame_or_notification,
                                                         matchTags=False)
        else:
            pass
            # ToDo generate dropped notification
        if len(self._transfer_buffer) == self.factory.container.si_config[self._inst_id]['transfer_buffer_size']:
            self._send_transfer_buffer()

    def _send_transfer_buffer(self):
        self._send_pdu(self._transfer_buffer)
        self._transfer_buffer = None
        if (self._release_timer.called == 1) or (self._release_timer.cancelled == 1):
            self._release_timer = None
        else:
            self._release_timer.cancel()
            self._release_timer = None
