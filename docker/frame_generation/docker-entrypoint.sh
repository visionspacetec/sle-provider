#!/bin/bash
set -e

# Start the SLE Provider
python3 /usr/local/sle-provider/examples/start_provider.py &
# Wait until it is running
sleep 2
# Start the middleware for GNU Radio
python3 /usr/local/sle-provider/examples/start_gnuRadio_middleware.py &

# To disable frame generation comment out the '&' in line 9 and the following lines 12 and 14
sleep 10
# Start frame generation
python3 /usr/local/sle-provider/examples/udp_data_endpoint.py
