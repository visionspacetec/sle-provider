import os
from sleprovider.sleProvider import SleProvider

DATA_PORT = int(os.getenv('SLE_PROVIDER_DATA_PORT', 55555))
USER_PORT = int(os.getenv('SLE_PROVIDER_USER_PORT', 55529))
MANAGER_PORT = int(os.getenv('SLE_PROVIDER_MANAGER_PORT', 2048))

provider = SleProvider()

provider.local_id = 'SLE_PROVIDER'
provider.remote_peers = {
    'SLE_USER':
        {
            'authentication_mode': 'NONE',
            'password': ''
        }
}
provider.si_config = {
    'sagr=1.spack=VST-PASS0001.rsl-fg=1.raf=onlt1':
        {
            'start_time': None,
            'stop_time': None,
            'initiator_id': 'SLE_USER',
            'responder_id': 'SLE_PROVIDER',
            'return_timeout_period': 15,
            'delivery_mode': 'TIMELY_ONLINE',
            'initiator': 'USER',
            'permitted_frame_quality':
                ['allFrames', 'erredFramesOnly', 'goodFramesOnly'],
            'latency_limit': 9,
            'transfer_buffer_size': 1,
            'report_cycle': None,
            'requested_frame_quality': 'allFrames',
            'state': 'unbound'
        }
}

provider.initialize_server('rest_manager', 'http_no_auth_rest_protocol', MANAGER_PORT)
provider.initialize_server('sle_provider', 'sle_protocol', USER_PORT, print_frames=False)
provider.initialize_server('data_endpoint', 'json_data_protocol', DATA_PORT, print_frames=False)
provider.start_reactor()
