#!/bin/bash
set -e

# Start the SLE Provider
python3 /usr/local/sle-provider/examples/start_provider.py &
# Wait until it is running
sleep 2
# Start the middleware for GNU Radio
python3 /usr/local/sle-provider/examples/start_VST104_middleware.py &

# To disable the virtual frame sink comment out the '&' in line 9 and the following lines 12 and 14
sleep 1
# Start virtual frame sink
python3 /usr/local/sle-provider/examples/udp_VST104_endpoint.py
