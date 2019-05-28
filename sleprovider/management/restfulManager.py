import logging; logging.basicConfig(level=logging.DEBUG); logger = logging.getLogger(__name__)
from klein import Klein
from .routes.service_instances_app import service_instances_app
from .routes.sle_config_app import sle_config_app

try:
    from .routes.cortex_config_app import cortex_config_app
    from .routes.cortex_command_app import cortex_command_app
    use_cortex = True
except ImportError:
    use_cortex = False

routes = "Welcome to our REST API server!\n" \
         "GET, DELETE /api/service-instances\n" \
         "GET, DELETE, POST, PATCH /api/service-instances/<string:si>\n" \
         "GET /api/sle-config\n" \
         "GET, PATCH /api/sle-config/<string:param>\n"
if use_cortex:
    routes += "GET /api/cortex-config\n" \
              "GET /api/cortex-config/<string:table>\n" \
              "GET, POST /api/cortex-command\n"


class RestfulManager(object):

    def __int__(self):
        self.container = None
        self.sle_config = None
        if use_cortex:
            self.commands = None
            logger.debug('Added Cortex support to the REST API')

    app = Klein()

    @app.route('/api/')
    def root(self, request):
        request.setHeader('Content-Type'.encode('utf-8'), 'application/json')
        return routes

    with app.subroute('/api/service-instances/'):
        service_instances_app(app)

    with app.subroute('/api/sle-config/'):
        sle_config_app(app)

    if use_cortex:
        with app.subroute('/api/cortex-config/'):
            cortex_config_app(app)

        with app.subroute('/api/cortex-command/'):
            cortex_command_app(app)
