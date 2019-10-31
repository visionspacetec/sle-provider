import os
from sleprovider.baseband.middleware.gnuRadio import main

PORT_GOOD_FRAMES = int(os.getenv('SLE_MIDDLEWARE_GOOD_FRAMES', 16887))
PORT_ERRED_FRAMES = int(os.getenv('SLE_MIDDLEWARE_BAD_FRAMES', 16888))
HOST_SLE = os.getenv('SLE_PROVIDER_HOSTNAME', '127.0.0.1')
PORT_SLE = int(os.getenv('SLE_PROVIDER_DATA_PORT', 55555))
ANTENNA_ID = os.getenv('SLE_MIDDLEWARE_ANTENNA_ID', 'VST')

main(PORT_GOOD_FRAMES, PORT_ERRED_FRAMES, HOST_SLE, PORT_SLE, ANTENNA_ID, print_frames=False)
