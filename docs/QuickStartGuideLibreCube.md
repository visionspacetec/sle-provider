<a href="http://www.visionspace.com">
   <img src="https://www.visionspace.com/img/VISIONSPACE_HZ_BLACK_HR.png" alt="visionspace logo" title="visionspace_cicd" align="right" height="25px" />
</a>

# Setup the LibreCube SLE User

The LibreCube **[python-sle-user](https://gitlab.com/librecube/lib/python-sle-user)** client can be used in combination with the VisionSpace sle-provider.

This guide shows you how to set it up and run an example.

## Installation

Before installing the user, make sure you successfully installed the **[sle-provider](https://github.com/visionspacetec/sle-provider#installation--usage)**, then run:

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

* Start the python-sle Return All Frames example:

**Currently you have to comment out the lines 48-52 in raf.py:**

```python
# if raf.state != 'active':
# print("Failed to start data transfer. Aborting...")
# raf.unbind(reason='other')
# time.sleep(2)
# return
```

In python-sle-user/examples/raf.py change the authentication option in line 11 from bind to none:

```bash
auth_level='none'
```

The configuration file *config.py* in the examples folder from the python-sle-user package has to be filled with:

```python
config = {
"RAF":{
"RAF_INST_ID": "sagr=1.spack=VST-PASS0001.rsl-fg=1.raf=onlt1",
"SLE_PROVIDER_HOSTNAME": "localhost",
"SLE_PROVIDER_TM_PORT": "55529",
"INITIATOR_ID": "SLE_USER",
"RESPONDER_ID": "SLE_PROVIDER",
"PASSWORD": "",
"PEER_PASSWORD": ""}}
```

```bash
# Activate the virtual environment
source ~/python-sle/venv/bin/activate
python ~/python-sle/examples/raf.py
```

After the successful **Bind** and **Start** operation, you can already see the **[ISP1](https://public.ccsds.org/Pubs/913x1b2.pdf)** heartbeat transmission.

* Now generate some frames at the provider and send them to the user:

```bash
python3 ~/sle-provider/examples/data_endpoint.py
```

Frames are generated, send to the SLE provider and forwarded to connected clients!

## Questions or need help?

Please open an **[issue](https://github.com/visionspacetec/sle-provider/issues/new/choose)** for bug reporting, enhancement or feature requests.
