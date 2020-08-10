#!/bin/bash
set -e

# Start the SLE Provider
python3 /usr/local/sle-provider/examples/start_provider_stateless.py &
# Wait until it is running
sleep 2
# Start the middleware for SatNOGS
python3 /usr/local/sle-provider/examples/start_SatNOGS_middleware.py
