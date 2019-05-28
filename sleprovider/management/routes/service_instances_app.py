import logging; logging.basicConfig(level=logging.DEBUG); logger = logging.getLogger(__name__)
import json
from twisted.internet import defer


def service_instances_app(app):
    @app.route('/', methods=['GET'])
    @defer.inlineCallbacks
    def get_si_list(self, request):
        request.setHeader('Content-Type'.encode('utf-8'), 'application/json')
        request.setResponseCode(200)  # Ok
        rtn = yield json.dumps(list(self.container.si_config.keys()))
        return rtn

    @app.route('/', methods=['DELETE'])
    def delete_si_list(self, request):
        request.setHeader('Content-Type'.encode('utf-8'), 'application/json')
        self.container.si_config.clear()
        # ToDo Unload the clients
        request.setResponseCode(202)  # Accepted
        return

    @app.route('/<string:si>', methods=['GET'])
    @defer.inlineCallbacks
    def get_si(self, request, si):
        request.setHeader('Content-Type'.encode('utf-8'), 'application/json')
        if si in self.container.si_config.keys():
            request.setResponseCode(200)  # Ok
            rtn = yield json.dumps(self.container.si_config[si])
            return rtn
        else:
            request.setResponseCode(404)  # Not Found
            return

    @app.route('/<string:si>', methods=['POST'])
    @defer.inlineCallbacks
    def post_si(self, request, si):
        request.setHeader('Content-Type'.encode('utf-8'), 'application/json')
        if si in self.container.si_config:
            request.setResponseCode(409)  # Conflict
            return
        else:
            try:
                req = yield json.loads(request.content.read())
                self.container.si_config.update({si: req})
                logger.debug("Created service instance: {}".format(si))
            except Exception as e:
                logger.debug(e)
                request.setResponseCode(400)  # Bad Request
                return
            request.setResponseCode(201)  # Created
            return

    @app.route('/<string:si>', methods=['DELETE'])
    def delete_si(self, request, si):
        request.setHeader('Content-Type'.encode('utf-8'), 'application/json')
        if si not in self.container.si_config:
            request.setResponseCode(404)  # Not Found
            return
        self.container.si_config.pop(si)
        # ToDo Unload the client?
        request.setResponseCode(202)  # Accepted
        return

    @app.route('/<string:si>', methods=['PATCH'])
    @defer.inlineCallbacks
    def patch_si(self, request, si):
        request.setHeader('Content-Type'.encode('utf-8'), 'application/json')
        if si not in self.container.si_config:
            request.setResponseCode(404)  # Not Found
            return
        try:
            req = yield json.loads(request.content.read())
            for key in req.keys():
                if key not in self.container.si_config[si]:
                    request.setResponseCode(404)  # Not Found
                    return
                else:
                    self.container.si_config[si][key] = req[key]
        except Exception as e:
            logger.debug(e)
            request.setResponseCode(400)  # Bad Request
            return
        request.setResponseCode(202)  # Accepted
        return
