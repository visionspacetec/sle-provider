import logging; logging.basicConfig(level=logging.DEBUG); logger = logging.getLogger(__name__)
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

    def _peer_abort_invocation_handler(self, pdu):
        pass

    def _start_invocation_handler(self, pdu):
        pass

    def _stop_invocation_handler(self, pdu):
        pass

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
