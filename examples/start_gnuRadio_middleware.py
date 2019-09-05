from sleprovider.baseband.middleware.gnuRadio import main

PORT_GOOD_FRAMES = 16887
PORT_ERRED_FRAMES = 16888
HOST_SLE = 'localhost'
PORT_SLE = 55555
ANTENNA_ID = 'VST'

main(PORT_GOOD_FRAMES, PORT_ERRED_FRAMES, HOST_SLE, PORT_SLE, ANTENNA_ID, print_frames=False)
