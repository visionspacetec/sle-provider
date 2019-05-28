import logging; logging.basicConfig(level=logging.DEBUG); logger = logging.getLogger(__name__)
import json
from twisted.internet import defer
from cortex.clients.structures import TABLES


def cortex_config_app(app):
    # Returns a list of all available Cortex configuration tables
    @app.route('/', methods=['GET'])
    @defer.inlineCallbacks
    def get_cortex_config_table_list(self, request):
        request.setHeader('Content-Type'.encode('utf-8'), 'application/json')
        try:
            request.setResponseCode(200)  # Ok
            rtn = []
            for key, value in TABLES.items():
                rtn.append(str(key).split('.')[1].lower().replace('_', '-'))
            rtn = yield json.dumps(rtn)
            return rtn
        except Exception as e:
            logger.debug(e)
            request.setResponseCode(500)  # Internal Server Error
            return

    # Returns a list of all available parameters in the requested Cortex configuration table
    @app.route('/<string:param>', methods=['GET'])
    @defer.inlineCallbacks
    def get_cortex_config_table(self, request, param):
        request.setHeader('Content-Type'.encode('utf-8'), 'application/json')
        try:
            request.setResponseCode(200)  # Ok
            rtn = []
            for key, value in TABLES.items():
                if param.replace('-', '_') == str(key).split('.')[1].lower():
                    for field, field_type in TABLES[key].__dict__['_fields_']:
                        if field != 'unused':
                            rtn.append(field)
                    break
            if rtn is []:
                request.setResponseCode(404)  # Not Found
                return
            rtn = yield json.dumps(rtn)
            return rtn
        except Exception as e:
            logger.debug(e)
            request.setResponseCode(500)  # Internal Server Error
            return
