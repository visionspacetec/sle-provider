import os
from sleprovider.baseband.middleware.SatNOGS import main

HOST_SLE = os.getenv('SLE_PROVIDER_HOSTNAME', '127.0.0.1')
PORT_SLE = int(os.getenv('SLE_PROVIDER_DATA_PORT', 55555))

main(HOST_SLE, PORT_SLE, print_frames=False)
