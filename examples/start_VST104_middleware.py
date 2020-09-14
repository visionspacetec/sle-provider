import os
from sleprovider.baseband.middleware.VST104 import main

PORT_GOOD_FRAMES = int(os.getenv('SLE_MIDDLEWARE_GOOD_FRAMES', 16887))
HOST_SLE = os.getenv('SLE_PROVIDER_HOSTNAME', '127.0.0.1')
PORT_SLE = int(os.getenv('SLE_PROVIDER_DATA_PORT', 55555))
ANTENNA_ID = os.getenv('SLE_MIDDLEWARE_ANTENNA_ID', 'VST')

main(PORT_GOOD_FRAMES, HOST_SLE, PORT_SLE, ANTENNA_ID, print_frames=True)
