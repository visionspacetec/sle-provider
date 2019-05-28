from sleprovider.baseband.middleware.cortex import main

host_cortex = ''
host_sle = 'localhost'
port_sle = 55555
frame_length = 1115

main(host_cortex, host_sle, port_sle, frame_length)
