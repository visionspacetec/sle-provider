<a href="http://www.visionspace.com">
   <img src="https://www.visionspace.com/img/VISIONSPACE_HZ_BLACK_HR.png" alt="visionspace logo" title="visionspace_cicd" align="right" height="25px" />
</a>

# Setup the LibreCube SLE User

The LibreCube **[python-sle-user](https://gitlab.com/librecube/lib/python-sle-user)** client can be used in combination with the VisionSpace sle-provider.

This guide shows you how to set up the VisionSpace SLE provider for Return All Frames frame generation and how to run an example.

## Installation

Before installing the user, make sure you successfully installed the **[sle-provider](https://github.com/visionspacetec/sle-provider#installation--usage)**, afterwards run:

```bash
git clone https://gitlab.com/librecube/lib/python-sle-user.git
cd python-sle-user
virtualenv -p python3 venv
source venv/bin/activate
pip install -e .
```

## Run the example

### Start the SLE Provider

*Be aware that the sle-provider might not be installed in the same environment as the python-sle-user package!*

* Start the sle-provider example configuration:

```bash
python3 ~/sle-provider/examples/start_provider.py
```

* Alternatively use docker-compose to start the SLE provider. Make sure that in *docker-compose.yml* the docker file is set to **dockerfile: ./docker/frame_generation/Dockerfile**. Start up the container:

```bash
docker-compose up --build -d
```

In any case, after start-up of the SLE provider, start the python-sle-user Return All Frames example:

In *python-sle-user/examples/raf.py*:

```python
import logging; logging.basicConfig(level=logging.DEBUG)
import time
import sle
from config import config

raf = sle.RafUser(
    service_instance_identifier=config['RAF']['RAF_INST_ID'],
    responder_ip=config['RAF']['SLE_PROVIDER_HOSTNAME'],
    responder_port=int(config['RAF']['SLE_PROVIDER_TM_PORT']),
    auth_level='none',
    local_identifier=config['RAF']['INITIATOR_ID'],
    peer_identifier=config['RAF']['RESPONDER_ID'],
    local_password=config['RAF']['PASSWORD'],
    peer_password=config['RAF']['PEER_PASSWORD'],
    heartbeat=25,
    deadfactor=5,
    buffer_size=4096,
    version_number=2)

def return_data_handler(data):
    print(data.prettyPrint())

raf.frame_handler = return_data_handler
raf.status_report_handler = return_data_handler
raf.parameter_handler = return_data_handler

def main():
    raf.bind()
    time.sleep(2)

    if raf.state != 'ready':
        print("Failed to bind to provider. Aborting...")
        return

    raf.start()
    time.sleep(2)

    try:
        while True:
            time.sleep(0)

    except KeyboardInterrupt:
        pass

    finally:
        if raf.state == 'active':
            raf.stop()
            time.sleep(2)
        raf.schedule_status_report()
        time.sleep(2)
        raf.unbind(reason='other')
        time.sleep(2)

main()
```

Fill the configuration parameters in *python-sle-user/examples/config.py*:

```python
config = {
    "RAF": {
        "RAF_INST_ID": "sagr=1.spack=VST-PASS0001.rsl-fg=1.raf=onlt1",
        "SLE_PROVIDER_HOSTNAME": "localhost",
        "SLE_PROVIDER_TM_PORT": "55529",
        "INITIATOR_ID": "SLE_USER",
        "RESPONDER_ID": "SLE_PROVIDER",
        "PASSWORD": "",
        "PEER_PASSWORD": "",
    },
    "CLTU": {
        "CLTU_INST_ID": "sagr=1.spack=VST-PASS0001.fsl-fg=1.cltu=cltu1",
        "SLE_PROVIDER_HOSTNAME": "localhost",
        "SLE_PROVIDER_TC_PORT": "55529",
        "INITIATOR_ID": "SLE_USER",
        "RESPONDER_ID": "SLE_PROVIDER",
        "PASSWORD": "",
        "PEER_PASSWORD": "",
    }
}
```

If you used the virtual environment installation procedure activate it and start the Return All Frames user:
```bash
source ~/python-sle-user/venv/bin/activate
python ~/python-sle-user/examples/raf.py
```

After the successful **Bind** and **Start** operation, you can already see the **[ISP1](https://public.ccsds.org/Pubs/913x1b2.pdf)** heartbeat transmission.

* Now generate some frames at the provider side and send them to the user:
```bash
python3 ~/sle-provider/examples/data_endpoint.py
```
If you used the docker-compose start-up procedure, you can choose in */frame_generation/docker-entrypoint.sh* if frames are generated:

Frames are generated, send to the SLE provider and forwarded to connected clients! 

## Next steps

After you finished this first example you can try out disabling frame generation and sending frames from your preferred source to the SLE provider (e.g. GNUradio) or start up the FCLTU example.

### FCLTU example
Change the docker entrypoint in the *docker-compose.yml* to **dockerfile: ./docker/frame_sending/Dockerfile**.


In *python-sle-user/examples/cltu.py*:
```python
import logging; logging.basicConfig(level=logging.DEBUG)
import time
import sle
from config import config


cltu = sle.CltuUser(
    service_instance_identifier=config['CLTU']['CLTU_INST_ID'],
    responder_ip=config['CLTU']['SLE_PROVIDER_HOSTNAME'],
    responder_port=int(config['CLTU']['SLE_PROVIDER_TC_PORT']),
    auth_level='none',
    local_identifier=config['CLTU']['INITIATOR_ID'],
    peer_identifier=config['CLTU']['RESPONDER_ID'],
    local_password=config['CLTU']['PASSWORD'],
    peer_password=config['CLTU']['PEER_PASSWORD'],
    heartbeat=25,
    deadfactor=5,
    buffer_size=256000,
    version_number=2)


def return_data_handler(data):
    print(data.prettyPrint())


cltu.status_report_handler = return_data_handler
cltu.parameter_handler = return_data_handler


cltu.bind()
time.sleep(2)

if cltu.state == 'ready':
    cltu.start()
    time.sleep(2)

    try:
        cltu.transfer_data(b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a")
        time.sleep(2)
        cltu.transfer_data(b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a")
        time.sleep(2)

    except KeyboardInterrupt:
        pass

    finally:
        cltu.stop()
        time.sleep(2)
        cltu.unbind(reason='other')  # avoid instance to be unloaded
        time.sleep(2)

else:
    print("Failed binding to Provider. Aborting...")
```

Restart the SLE provider:
```bash
docker-compose up --build -d
```

Connect at first with the RAF user and then with the CLTU user to the provider. 
```bash
source ~/python-sle-user/venv/bin/activate
python ~/python-sle-user/examples/raf.py
```

The CLTU user will send two telecommands to the provider which are sent bach using a UDP loopback client. On the RAF user these frames are received again.
. Open a new terminal session for the second user:
```bash
source ~/python-sle-user/venv/bin/activate
python ~/python-sle-user/examples/cltu.py
```

## Questions or need help?

In case this guide is not working for you, please check if you followed all steps correctly and in case of missing instructions or other problems please do not hesitate to contact us or open an **[issue](https://github.com/visionspacetec/sle-provider/issues/new/choose)** for bug reporting, enhancement or feature requests.
