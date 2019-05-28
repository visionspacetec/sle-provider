import logging; logging.basicConfig(level=logging.DEBUG); logger = logging.getLogger(__name__)
import json
from twisted.internet import defer


def sle_config_app(app):
    @app.route('/', methods=['GET'])
    @defer.inlineCallbacks
    def get_sle_config_list(self, request):
        request.setHeader('Content-Type'.encode('utf-8'), 'application/json')
        try:
            request.setResponseCode(200)  # Ok
            rtn = yield json.dumps(self.sle_config)
            return rtn
        except Exception as e:
            logger.debug(e)
            request.setResponseCode(500)  # Internal Server Error
            return

    @app.route('/<string:param>', methods=['GET'])
    @defer.inlineCallbacks
    def get_sle_config(self, request, param):
        request.setHeader('Content-Type'.encode('utf-8'), 'application/json')
        if param in self.sle_config:
            try:
                value = yield getattr(self.container, param.replace('-', '_'))
                request.setResponseCode(200)  # Ok
                rtn = yield json.dumps(value)
                return rtn
            except Exception as e:
                logger.debug(e)
                request.setResponseCode(500)  # Internal Server Error
                return
        else:
            request.setResponseCode(404)  # Not Found
            return

    @app.route('/<string:param>', methods=['PATCH'])
    @defer.inlineCallbacks
    def patch_sle_config(self, request, param):
        request.setHeader('Content-Type'.encode('utf-8'), 'application/json')
        if param in self.sle_config:
            try:
                req = yield json.loads(request.content.read())
                setattr(self.container, param.replace('-', '_'), req)
                request.setResponseCode(202)  # Accepted
                return
            except Exception as e:
                logger.debug(e)
                request.setResponseCode(500)  # Internal Server Error
                return
        else:
            request.setResponseCode(404)  # Not Found
            return
