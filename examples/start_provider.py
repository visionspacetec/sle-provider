import os
from sleprovider.sleProvider import SleProvider

DATA_PORT = int(os.getenv('SLE_PROVIDER_DATA_PORT', 55555))
USER_PORT = int(os.getenv('SLE_PROVIDER_USER_PORT', 55529))
RESPONDER_ID = os.getenv('SLE_PROVIDER_RESPONDER_ID', 'SLE_PROVIDER')
RESPONDER_PASS = os.getenv('SLE_PROVIDER_RESPONDER_PASS', '')

provider = SleProvider()

provider.local_id = RESPONDER_ID
provider.local_password = RESPONDER_PASS

provider.initialize_server('sle_provider', 'sle_protocol', USER_PORT, print_frames=False)
provider.initialize_server('data_endpoint', 'json_data_protocol', DATA_PORT, print_frames=False)

provider.start_reactor()

