<a href="http://www.visionspace.com">
   <img src="https://www.visionspace.com/img/VISIONSPACE_HZ_BLACK_HR.png" alt="visionspace logo" title="visionspace_cicd" align="right" height="25px" />
</a>

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
- Online Timely frame delivery
- OpenAPI management server and client
- (in progress) Support for professional ground station equipment
- (planned) Return Channel Frames (RCF) service
- (planned) Forward  Communications Link Transmission Units (CLTU) Service
- (planned) Online Complete frame delivery
- (planned) Offline frame delivery

## Installation & Usage

When installing on a Raspberry Pi, install these packages before the next steps:

```bash
sudo apt-get install libffi-dev libssl-dev
```

If you want to configure the SLE Provider at runtime install our **[sle-management-client](https://github.com/visionspacetec/sle-management-client)**.

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

## Getting started

Follow the [installation procedure](#installation--usage), then install a Space Link Extension Client, one of the following will work:
- **[LibreCube python-sle](https://gitlab.com/librecube/prototypes/python-sle)**: 
Try our [quick start guide](https://github.com/visionspacetec/sle-provider/blob/master/docs/QuickStartGuideLibreCube.md) for the python-sle!
- **[NASA AIT-DSN](https://github.com/NASA-AMMOS/AIT-DSN)**

## Security

Usage of HTTPS and Basic Authentication is optional for development but highly recommended for production!

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
```python
from sleprovider.management.security.authManager import AuthManager
user = ''  # Enter username here
password = ''  # Enter password here
AuthManager.create_user(user, password)
```

Use the 'http_rest_protocol' or 'https_rest_protocol',  when initializing the management server.

### Start the SLE Provider:

Run the example script

```bash
python3 start_provider.py
```

or configure the server for your own needs:

```python
from sleprovider.sleProvider import SleProvider

DATA_PORT = 55555
USER_PORT = 55529
MANAGER_PORT = 2048

provider = SleProvider()
provider.initialize_server('rest_manager', 'https_rest_protocol', MANAGER_PORT)
provider.initialize_server('sle_provider', 'sle_protocol', USER_PORT)
provider.initialize_server('data_endpoint', 'json_data_protocol', DATA_PORT)
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
