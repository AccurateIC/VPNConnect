#!/usr/bin/env bash
# Remove VPNConnect. Users' imported VPN connections are left in NetworkManager
# (each user can remove theirs with: vpnconnect remove).
set -euo pipefail
if [[ $EUID -ne 0 ]]; then echo "Please run with sudo." >&2; exit 1; fi
rm -rf /opt/vpnconnect /usr/local/bin/vpnconnect /usr/share/applications/vpnconnect.desktop
echo "Removed. Configuration in /etc/vpnconnect was kept; delete it manually if no longer needed."
