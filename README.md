# VPNConnect



## Project Structure
```├── README.md
├── requirements.txt
├── start_vpn.sh
├── vpn
│ └── cred.txt
└── VPNConnect.py
```





- `VPNConnect.py` — Main Python application.
- `requirements.txt` — Python dependencies.
- `start_vpn.sh` — Optional shell script to start VPN.
- `vpn/cred.txt` — VPN credentials file.

---

## Prerequisites

- Python 3.10 or higher
- `pip` package manager
- `pyinstaller` for packaging the app

---

## Setup

### Install dependencies

``` pip install -r requirements.txt ```

Note: Currently only pyinstaller is required since other modules are from the standard library.

### Building the Executable
Run the following command to create a standalone Linux binary:


``` pyinstaller --onefile --noconsole --add-binary /usr/lib/x86_64-linux-gnu/libpython3.10.so.1.0:. VPNConnect.py ```

***The output binary will be located at dist/VPNConnect.***

### Running the App
Execute the binary:

```./dist/VPNConnect```


### Troubleshooting
If you encounter missing libraries, install them via:


```sudo apt install libpython3.10 python3-tk```

Consider building inside a Python virtual environment if issues persist:

```
python3 -m venv venv
source venv/bin/activate
pip install pyinstaller
pyinstaller --onefile --noconsole --add-binary /usr/lib/x86_64-linux-gnu/libpython3.10.so.1.0:. VPNConnect.py
```
