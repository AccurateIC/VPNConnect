#!/usr/bin/env bash
# Install VPNConnect system-wide. Run once per machine (needs sudo):
#
#   sudo ./install.sh                         # install the app
#   sudo ./install.sh --profile company.ovpn  # also pre-load a shared profile for every user
#
set -euo pipefail

PREFIX=/opt/vpnconnect
ETC=/etc/vpnconnect
PROFILE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --profile) PROFILE="$2"; shift 2 ;;
        -h|--help) sed -n '2,6p' "$0"; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

if [[ $EUID -ne 0 ]]; then
    echo "Please run with sudo: sudo $0 $*" >&2
    exit 1
fi

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Installing dependencies"
if command -v apt-get >/dev/null; then
    apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        network-manager network-manager-openvpn network-manager-openvpn-gnome \
        python3 python3-tk python3-gi gir1.2-nm-1.0
elif command -v dnf >/dev/null; then
    dnf install -y NetworkManager NetworkManager-openvpn NetworkManager-openvpn-gnome \
        python3 python3-tkinter python3-gobject NetworkManager-libnm
else
    echo "Unsupported distro: install NetworkManager-openvpn, python3-tk and python3-gi manually." >&2
fi
# The OpenVPN plugin is only picked up after NetworkManager restarts.
systemctl try-reload-or-restart NetworkManager 2>/dev/null || true

echo "==> Copying files to $PREFIX"
rm -rf "$PREFIX"
install -d "$PREFIX"
cp -r "$SRC/vpnconnect" "$PREFIX/"
find "$PREFIX" -name '__pycache__' -prune -exec rm -rf {} +

cat > /usr/local/bin/vpnconnect <<EOF
#!/bin/sh
exec /usr/bin/python3 -P -c 'import sys; sys.path.insert(0, "$PREFIX"); from vpnconnect.cli import main; sys.exit(main())' "\$@"
EOF
chmod 755 /usr/local/bin/vpnconnect

install -Dm644 "$SRC/packaging/vpnconnect.desktop" /usr/share/applications/vpnconnect.desktop

install -d "$ETC"
if [[ ! -f "$ETC/vpnconnect.conf" ]]; then
    install -m644 "$SRC/packaging/vpnconnect.conf.example" "$ETC/vpnconnect.conf"
    echo "    wrote $ETC/vpnconnect.conf (edit to set the portal URL, session limit, OTP)"
else
    echo "    kept existing $ETC/vpnconnect.conf"
fi
if [[ -n "$PROFILE" ]]; then
    install -m644 "$PROFILE" "$ETC/profile.ovpn"
    echo "    installed shared profile $ETC/profile.ovpn"
fi

echo "==> Done. Employees can open 'VPNConnect' from the app menu or run: vpnconnect"
