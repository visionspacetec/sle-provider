import logging; logging.basicConfig(level=logging.DEBUG); logger = logging.getLogger(__name__)

from twisted.internet import protocol
import json


class DataProtocol(protocol.Protocol):

    def __init__(self):
        pass

    def connectionMade(self):
        logger.info('Connection with data endpoint established')
        self.factory.container.data_endpoints.append(self)
        self.transport.setTcpNoDelay(True)
        self._rem = ''

    def connectionLost(self, reason):
        logger.info('Connection with data endpoint lost')
        self.factory.container.data_endpoints.remove(self)

    def disconnect(self):
        logger.debug('Disconnecting')
        self.transport.loseConnection()

    def dataReceived(self, data):
        try:
            data = (self._rem + data.decode()).encode()
            self._rem = ''
            pdu = json.loads(data)
            if 'data' not in pdu and 'notification' not in pdu:
                self._rem = data[:-1].decode()
                return
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
                    if 'data' not in pdu and 'notification' not in pdu:
                        # print(buffer_split)
                        # print(sub)
                        # if sub is buffer_split[-1]:
                        # self._rem = sub[:-1].decode()
                        return
                except json.JSONDecodeError:
                    self._rem = sub[:-1].decode()
                    return
                self._pdu_handler(pdu, True)
        except UnicodeDecodeError:
            logger.error('Unsupported Protocol tried to connect!')
            self.disconnect()

    def _pdu_handler(self, pdu, opt=False):
        if self.print_frames is True:
            logger.debug(pdu)
        if 'data' in pdu:
            self._data_handler(pdu)
        elif 'notification' in pdu:
            self._notification_handler(pdu)
        else:
            logger.error("Neither data nor notification in pdu: {}{}".format(pdu, opt))
            self._rem = ''

    def _data_handler(self, pdu):
        self.factory.container._annotated_frame_handler(pdu['earthReceiveTime'],
                                                        pdu['antennaId'],
                                                        pdu['deliveredFrameQuality'],
                                                        pdu['data'])

    def _notification_handler(self, pdu):
        if 'endOfData' in pdu['notification']:
            self.factory.container._notification_handler(notification_type='endOfData')
        elif 'excessiveDataBacklog' in pdu['notification']:
            self.factory.container._notification_handler(notification_type='excessiveDataBacklog')
        elif 'productionStatusChange' in pdu['notification']:
            self.factory.container._notification_handler(notification_type='productionStatusChange',
                                                         production_status=pdu['notification'][
                                                             'productionStatusChange'])
        elif 'lossFrameSync' in pdu['notification']:
            # TODO Session id
            self.factory.container._notification_handler(notification_type='lossFrameSync',
                                                         time=pdu['notification']['lossFrameSync']['time'],
                                                         carrier_lock_status=pdu['notification']['lossFrameSync'][
                                                             'carrierLockStatus'],
                                                         subcarrier_lock_status=pdu['notification']['lossFrameSync'][
                                                             'subcarrierLockStatus'],
                                                         symbol_sync_lock_status=pdu['notification']['lossFrameSync'][
                                                             'symbolSyncLockStatus'])

    def send_command(self, command, arg_list):
        if not isinstance(command, str):
            logger.error('Command must be a string but is {}'.format(type(command)))
            return
        if not isinstance(arg_list, list):
            logger.error('Argument must be a list but is {}'.format(type(arg_list)))
            return
        if command == 'start-telemetry':
            self.transport.write(json.dumps({'command': command, 'args': arg_list}).encode())
        elif command == 'stop-telemetry':
            self.transport.write(json.dumps({'command': command, 'args': arg_list}).encode())
        elif command == 'send-telecommand':
            self.transport.write(json.dumps({'command': command, 'args': arg_list}).encode())
        else:
            logger.error('Command {} is not supported!'.format(command))
