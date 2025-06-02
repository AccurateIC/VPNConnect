
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

## 🚀 Usage

1. Place your `.ovpn` file inside the `vpn/` folder.
2. Run the script:

```bash
chmod +x start-vpn.sh
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