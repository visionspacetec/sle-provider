import logging; logging.basicConfig(level=logging.DEBUG); logger = logging.getLogger(__name__)
import json
from twisted.internet import defer


def cortex_command_app(app):
    # Returns a list of all available Cortex commands
    @app.route('/', methods=['GET'])
    @defer.inlineCallbacks
    def get_cortex_command_list(self, request):
        request.setHeader('Content-Type'.encode('utf-8'), 'application/json')
        try:
            request.setResponseCode(200)  # Ok
            rtn = self.commands
            rtn = yield json.dumps(rtn)
            return rtn
        except Exception as e:
            logger.debug(e)
            request.setResponseCode(500)  # Internal Server Error
            return

    # Starts the execution of a Cortex command
    @app.route('/', methods=['POST'])
    @defer.inlineCallbacks
    def post_cortex_command(self, request):
        request.setHeader('Content-Type'.encode('utf-8'), 'application/json')
        if self.container.data_endpoints == []:
            request.setResponseCode(500)  # Internal Server Error
            return
        request.setResponseCode(202)  # Accepted
        try:
            req = yield json.loads(request.content.read())
            # ToDo support more than one data endpoint
            # ToDo check if command is valid
            self.container.data_endpoints[0].send_command(req['command'], req['args'])
            logger.debug("Accepted command {} with arguments {}".format(req['command'], req['args']))
            return
        except Exception as e:
            logger.debug(e)
            request.setResponseCode(400)  # Bad Request
            return
