<a href="http://www.visionspace.com">
   <img src="https://www.visionspace.com/img/VISIONSPACE_HZ_BLACK_HR.png" alt="visionspace logo" title="visionspace_cicd" align="right" height="25px" />
</a>

# Setup the LibreCube SLE User

The LibreCube **[python-sle](https://gitlab.com/librecube/prototypes/python-sle)** client can be used in combination with the VisionSpace sle-provider.

This guide shows you how to set it up and run an example.

## Installation

Before installing the user, make sure you successfully installed the **[sle-provider](https://github.com/visionspacetec/sle-provider#installation--usage)**.

```bash
git clone https://gitlab.com/librecube/prototypes/python-sle.git
cd python-sle
virtualenv -p python3 venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Run the example

### Start the SLE Provider

*Be aware that the sle-provider is not installed in the same environment as the python-sle package!*

* Start the sle-provider example configuration:

```bash
python3 ~/sle-provider/examples/start_provider.py
```

* Start the python-sle Return All Frames example:

**Currently you have to comment out the following lines in raf_user.py:**
```python
raf.schedule_status_report()
# and
raf.get_parameter('requestedFrameQuality')
```

```bash
# Activate the virtual environment
source ~/python-sle/venv/bin/activate

export RAF_INST_ID="sagr=1.spack=VST-PASS0001.rsl-fg=1.raf=onlt1"
export SLE_PROVIDER_HOSTNAME="localhost"
export SLE_PROVIDER_TM_PORT=55529
export INITIATOR_ID="SLE_USER"
export RESPONDER_ID="SLE_PROVIDER"
export PASSWORD=""
export PEER_PASSWORD=""

python ~/python-sle/examples/raf_user.py
```

After the successful **Bind** and **Start** operation, you can already see the **[ISP1](https://public.ccsds.org/Pubs/913x1b2.pdf)** heartbeat transmission.

* Now generate some frames at the provider and send them to the user:

```bash
python3 ~/sle-provider/examples/data_endpoint.py
```

Frames are generated, send to the SLE provider and forwarded to connected clients!

## Questions or need help?

Please open an **[issue](https://github.com/visionspacetec/sle-provider/issues/new/choose)** for bug reporting, enhancement or feature requests.