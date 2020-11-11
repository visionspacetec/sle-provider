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

In any case, after start-up of the SLE provider, create the python-sle-user Return All Frames example:

In *python-sle-user/examples/raf.py*:

```python
import time
import sle

raf_service = sle.RafUser(
    service_instance_identifier="sagr=1.spack=VST-PASS0001.rsl-fg=1.raf=onlt1",
    responder_host="localhost",
    responder_port=55529,
    auth_level=None,
    local_identifier="SLE_USER",
    peer_identifier="SLE_PROVIDER",
    local_password="",
    peer_password="")

def print_data(data):
    print(data.prettyPrint())

raf_service.frame_handler = print_data

raf_service.bind()
time.sleep(1)

input("Enter to start")
raf_service.start()
time.sleep(1)

input("Enter to stop \n")
raf_service.stop()
time.sleep(1)

input("Enter to unbind")
raf_service.unbind()
time.sleep(1)

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

Create the file *python-sle-user/examples/cltu.py*:
```python
import time
import sle

cltu_service = sle.CltuUser(
    service_instance_identifier="sagr=1.spack=VST-PASS0001.fsl-fg=1.cltu=cltu1",
    responder_ip="localhost",
    responder_port=55529,
    auth_level=None,
    local_identifier="SLE_USER",
    peer_identifier="SLE_PROVIDER",
    local_password="",
    peer_password="")

def print_data(data):
    print(data.prettyPrint())

cltu_service.status_report = print_data

cltu_service.bind()
time.sleep(1)

cltu_service.schedule_status_report(report_type='periodically', cycle=10)

input("Enter to start \n")
cltu_service.start()
time.sleep(1)

cltu = b"\xab\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a"  # dummy example
cltu_service.transfer_data(cltu)

input("Enter to stop")
cltu_service.stop()
time.sleep(1)

input("Enter to unbind")
cltu_service.unbind()
time.sleep(1)

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

The CLTU user will send one telecommand to the provider which is sent back using a UDP loopback client. On the RAF user the frame is received again.
Open a new terminal session for the second user:
```bash
source ~/python-sle-user/venv/bin/activate
python ~/python-sle-user/examples/cltu.py
```

## Questions or need help?

In case this guide is not working for you, please check if you followed all steps correctly and in case of missing instructions or other problems please do not hesitate to contact us or open an **[issue](https://github.com/visionspacetec/sle-provider/issues/new/choose)** for bug reporting, enhancement or feature requests.
