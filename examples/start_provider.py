import os
from sleprovider.sleProvider import SleProvider

DATA_PORT = int(os.getenv('SLE_PROVIDER_DATA_PORT', 55555))
USER_PORT = int(os.getenv('SLE_PROVIDER_USER_PORT', 55529))
MANAGER_PORT = int(os.getenv('SLE_PROVIDER_MANAGER_PORT', 2048))

provider = SleProvider()
provider.initialize_server('rest_manager', 'http_no_auth_rest_protocol', MANAGER_PORT)
provider.initialize_server('sle_provider', 'sle_protocol', USER_PORT, print_frames=False)
provider.initialize_server('data_endpoint', 'json_data_protocol', DATA_PORT, print_frames=False)
provider.start_reactor()
