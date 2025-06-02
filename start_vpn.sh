#!/bin/bash

# Define directory where .ovpn files are stored
VPN_DIR="./vpn"

# Color formatting
GREEN="\033[0;32m"
RED="\033[0;31m"
RESET="\033[0m"

# Check if openvpn is installed
if ! command -v openvpn &> /dev/null; then
    echo -e "${RED}❌ OpenVPN is not installed. Run 'sudo apt install openvpn'${RESET}"
    exit 1
fi

# Find the first .ovpn file in the vpn folder
CONFIG_FILE=$(find "$VPN_DIR" -maxdepth 1 -type f -name "*.ovpn" | head -n 1)

if [[ -z "$CONFIG_FILE" ]]; then
    echo -e "${RED}❌ No .ovpn file found in $VPN_DIR${RESET}"
    exit 1
fi

# Start OpenVPN
echo -e "${GREEN}🔐 Starting VPN using config: $CONFIG_FILE${RESET}"
sudo openvpn --config "$CONFIG_FILE"
