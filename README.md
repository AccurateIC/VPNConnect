
# VPN Starter Script

This Bash script automates the process of connecting to a VPN using the first `.ovpn` configuration file found in a specified directory.

## 📜 Description

- Checks if **OpenVPN** is installed.
- Searches for the first `.ovpn` file in the `./vpn` directory.
- Starts the VPN connection using `sudo openvpn`.

## 📁 Directory Structure

Your project should have the following structure:

```
.
├── start-vpn.sh        # This script
└── vpn/
    └── your-config.ovpn
```

## 🛠️ Prerequisites

- Linux-based system
- `openvpn` installed

Install OpenVPN if not already installed:

```bash
sudo apt update
sudo apt install openvpn
```
## 🌐 Download VPN Configuration

You can download the required `.ovpn` configuration file from the following link:

🔗 [Download .ovpn file](https://49.248.149.138)

Place the downloaded file inside the `vpn/` directory.

## 🖼️ Screenshot
![alt text](<Untitled design.png>)
## 🚀 Usage

1. Make sure the script is executable:

```bash
chmod +x start-vpn.sh
```

2. Run the script:

```bash
./start-vpn.sh
```

The script will:
- Notify you if OpenVPN is missing.
- Look for `.ovpn` files in the `vpn` directory.
- Start the VPN using the first `.ovpn` file found.

## ⚠️ Notes

- You may be prompted for `sudo` password to start the VPN.
- If no `.ovpn` file is found, the script exits with an error message.
- Only the **first** `.ovpn` file found will be used.

## ✅ Example Output

```
🔐 Starting VPN using config: ./vpn/myvpn.ovpn
```

If OpenVPN is not installed:

```
❌ OpenVPN is not installed. Run 'sudo apt install openvpn'
```

If no `.ovpn` file is found:

```
❌ No .ovpn file found in ./vpn
```

## ▶️ Running the Script

To run the script:

1. Give it executable permissions (if not already):

```bash
chmod +x start-vpn.sh
```

2. Execute the script:

```bash
./start-vpn.sh
```

Make sure you have at least one `.ovpn` file in the `vpn/` directory before running.