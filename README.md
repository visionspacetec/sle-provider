> **⚠️ Deprecation Notice**
>
> This repository is no longer maintained.
> The SLE Provider project has moved to a new home on GitLab:
> 👉 [https://gitlab.com/visionspace/oss/sle/sle-provider](https://gitlab.com/visionspace/oss/sle/sle-provider)
>
> Please refer to the new repository for the latest updates, development, and issues.

# sle-provider

The **sle-provider** implements the **Space Link Extension** (SLE) protocol, for communication with satellite ground stations.
It includes an interface for the Space Link Extension protocol, a management server and a connection to ground station equipment.

## Framework
### Overview

- **[sle-common](https://github.com/visionspacetec/sle-common)**: Library for user and provider side Space Link Extension application development
- **[sle-provider](https://github.com/visionspacetec/sle-provider)**: Provider (ground station side) Space Link Extension application
- **[sle-management-client](https://github.com/visionspacetec/sle-management-client)**: OpenAPI based client for sle-provider management

### Features

- Return All Frames (RAF) service
- (in progress) Forward  Communications Link Transmission Units (FCLTU) Service
    - Incomplete implementation: ASYNC NOTIFY, GET PARAMETER and THROW EVENT missing
- Online Timely frame delivery
- OpenAPI management server and client
- Integration with the SatNOGS Network API
- Docker Swarm based service
- (in progress) Support for professional ground station equipment
    - CORTEX supported, required library available on request
- (planned) Return Channel Frames (RCF) service
- (planned) Online Complete frame delivery
- (planned) Offline frame delivery

## Installation & Usage

If you want to configure the SLE Provider at runtime install our **[sle-management-client](https://github.com/visionspacetec/sle-management-client)**.

### Docker
The SLE Provider is started together with the GNU Radio telemetry middleware by running:
```bash
# Build and start the container
docker-compose up --build -d
# Check the state of the running container
docker ps --all
# Check the console output of the container
docker logs sleprovider
# Terminate the container
docker-compose down
```
Which scripts are executed on startup can be configured in *./docker/frame_generation/docker-entrypoint.py* of by changing the Docker entrypoint in *./docker-compose.yml*.

If you have troubles restarting the Docker container try out the following to update all dependencies:
```bash
docker-compose build --force-rm --pull --no-cache
docker-compose up --build -d
```

### Setuptools

Install the **[sle-common](https://github.com/visionspacetec/sle-common)** package first, before installing the sle-provider!

```bash
python3 setup.py install --user
```

### Virtual environment

```bash
cd sle-provider
virtualenv -p python3 venv
source venv/bin/activate
pip install -e .
```
### Raspberry Pi

When installing on a Raspberry Pi, install these packages before the next steps:

```bash
sudo apt-get install libffi-dev libssl-dev
```

## Getting started

Follow the [installation procedure](#installation--usage), then install a Space Link Extension Client, one of the following will work:
- **[LibreCube python-sle](https://gitlab.com/librecube/prototypes/python-sle)**: 
Try our [quick start guide](https://github.com/visionspacetec/sle-provider/blob/master/docs/QuickStartGuideLibreCube.md) for the python-sle!
- **[NASA AIT-DSN](https://github.com/NASA-AMMOS/AIT-DSN)**

### Stateless SLE telemetry server for SatNOGS
This example comes with a REST DB to simulate the SatNOGS Network DB locally, a configured Traefik instance and a scaleable, stateless SLE provider.

Features supported:
* Scaleable Docker Swarm service
  * One user per running container
* Reverse proxy
  * Round-robin loadbalancer
  * Limits maximum connection count to number of running SLE providers
* SLE user database
  * Local database to manage SLE users
  * Users to satellites mapping
* All SLE SHA-1 authentication modes supported
  * No authentication
  * Bind authentication
  * Full encryption
* Return All Frames Service
  * Timely Online service
  * Offline service via Timely Online service

To build open terminal, go into the sle-provider folder, checkout the develop-satnogs branch and build the Docker image:
```bash
docker build -f ./docker/satnogs/Dockerfile . --tag sleprovider-stateless --force-rm
```

Add local DNS entry
```bash
sudo nano /etc/hosts
```

Add these lines to route requests to sle.network.satnogs.org to your local machine.
```bash
127.0.0.1 sle.network.satnogs.org
```
Save with CRTL+S and exit with CTRL+X.

Initialize the Docker swarm
```bash
docker swarm init
```

Deploy the test stack
```bash
docker stack deploy -c sle-stateless-traefik.yml sle
```

Check the status of the SLE service
```bash
docker service logs sle_provider
```

Check the virtual IP of the json-server, the second IP is used.
```bash
 docker service inspect sle_json-server -f "{{ .Endpoint.VirtualIPs }}"
{wuuq5q3jnkr2avqqthatcx8sq 10.11.0.31/16} {dt9om1lifuan221uqcq56dkgp 10.0.75.7/24}
```

Copy this IP to the sle-stateless-traefik.yml file into the user db url field. This is necessary since we are running a local server to simulate the planned behaviour of the SatNOGS Network API. Afterwads restart the SLE provider service to use the changed IP.
```bash
"SATNOGS_NETWORK_API_INTERNAL=http://10.0.75.7:80"
```

Make sure that the local volume mapping for the database file is correct.

Open your browser and navigate to localhost:8080 to view the Traefik dashboard. You can view the DB using the obtained IP on port 9090, from your local browser.

The SLE service can be scaled, they are round-robin loadbalanced.
```bash
docker service scale sle_provider=5
```

Metrics for the services can be measured using (hit tab to complete xxxx):
```bash
docker stats sle_provider.1.xxxx sle_provider.2.xxxx 
```

When updating the SLE provider image
```bash
docker service rm sle_provider
docker stack deploy -c sle-stateless-traefik.yml sle
```

## Security

Usage of HTTPS and Basic Authentication on the management API is optional for development but highly recommended for production!

### HTTPS for Management API

If you want to try the sle-management-client with HTTPS locally, you have to generate a HTTPS certificate first:

```bash
cd examples/
openssl genrsa -aes256 -passout pass:HereGoesYourPass -out server.key 2048
openssl req -new -key server.key -passin pass:HereGoesYourPass -out server.csr
# Fill the form, using localhost in "Common Name"
openssl x509 -req -passin pass:HereGoesYourPass -days 1024 -in server.csr -signkey server.key -out server.crt
cat server.crt server.key > server.pem
```

Now trust your own certificate:

```bash
sudo cp server.crt /usr/local/share/ca-certificates/
sudo update-ca-certificates
```

Or, if you are working in a virtual environment:

```bash
cp -f server.pem /pathTo/venv/lib/python3.6/site-packages/certifi<your-version>/certifi/cacert.pem
```

### HTTP Basic Authentication

To setup the local password database, for the HTTP Basic authentication schema, 
open authentication_db.py, enter a username-password combination in the empty fields and run the script.
This is only needed when using the REST management API.
```python
from sleprovider.management.security.authManager import AuthManager
user = ''  # Enter username here
password = ''  # Enter password here
AuthManager.create_user(user, password)
```

Use the 'http_rest_protocol' or 'https_rest_protocol',  when initializing the management server.

## Start the SLE Provider:

Run the example script

```bash
python3 start_provider.py
```

or configure the server for your own needs:

```python
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
        },
    'sagr=1.spack=VST-PASS0001.fsl-fg=1.cltu=cltu1':
        {
            'start_time': None,
            'stop_time': None,
            'initiator_id': 'SLE_USER',
            'responder_id': 'SLE_PROVIDER',
            'return_timeout_period': 15,
            'maximum_cltu_length': 306,
            'minimum_cltu_delay': 0,
            'maximum_cltu_delay': 6000000,
            'bit_lock_required': False,
            'rf_availiable_required': False,
            'report_cycle': None,
            'protocol_abort_clear_enabled': True,
            'state': 'unbound'
        }
}

provider.initialize_server('rest_manager', 'http_no_auth_rest_protocol', MANAGER_PORT)
provider.initialize_server('sle_provider', 'sle_protocol', USER_PORT, print_frames=False)
provider.initialize_server('data_endpoint', 'json_data_protocol', DATA_PORT, print_frames=False)
provider.start_reactor()
``` 

Connect with a client of our choice and start the generation of telemetry:

```bash
python3 dataEndpoint.py
```

## Find out more

This work was created following the standards defined by the **Consultative Committee for Space Data Systems** (CCSDS): https://public.ccsds.org

## Contributing

If you would like help implementing a new feature or fix a bug, check out our **[Contributing](https://github.com/visionspacetec/sle-provider/blob/master/.github/contributing.md)** page and the **[Code of Conduct](https://github.com/visionspacetec/sle-provider/blob/master/.github/code_of_conduct.md)**!

## Questions or need help?

Please open an **[issue](https://github.com/visionspacetec/sle-provider/issues/new/choose)** for bug reporting, enhancement or feature requests.

## Acknowledgement

Support for this work was provided by the European Space Agency through the OPS Innovation Cup. The content of this repository is solely the responsibility of the authors and does not necessarily represent the official views of the European Space Agency.
