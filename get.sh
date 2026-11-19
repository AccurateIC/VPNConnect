#!/usr/bin/env bash
# One-line installer for VPNConnect. Downloads the app from GitHub and runs install.sh.
#
#   curl -fsSL https://raw.githubusercontent.com/AccurateIC/VPNConnect/main/get.sh | sudo bash
#
# Options go after "bash -s --":
#   ... | sudo bash -s -- --profile /path/to/company.ovpn   # also pre-load a shared VPN file
#   ... | sudo bash -s -- --uninstall                       # remove VPNConnect
#
# Install a different branch or tag: ... | sudo VPNCONNECT_REF=<branch> bash
set -euo pipefail

REPO="AccurateIC/VPNConnect"
REF="${VPNCONNECT_REF:-main}"

if [[ $EUID -ne 0 ]]; then
    echo "Please run with sudo:" >&2
    echo "  curl -fsSL https://raw.githubusercontent.com/$REPO/main/get.sh | sudo bash" >&2
    exit 1
fi

ACTION=install
ARGS=()
for arg in "$@"; do
    if [[ "$arg" == "--uninstall" ]]; then ACTION=uninstall; else ARGS+=("$arg"); fi
done

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

URL="https://github.com/$REPO/archive/$REF.tar.gz"
echo "==> Downloading VPNConnect ($REF)"
if command -v curl >/dev/null; then
    curl -fsSL "$URL" -o "$TMP/vpnconnect.tar.gz"
elif command -v wget >/dev/null; then
    wget -qO "$TMP/vpnconnect.tar.gz" "$URL"
else
    echo "Need curl or wget to download VPNConnect." >&2
    exit 1
fi
tar -xzf "$TMP/vpnconnect.tar.gz" -C "$TMP" --strip-components=1

if [[ "$ACTION" == "uninstall" ]]; then
    bash "$TMP/uninstall.sh"
else
    bash "$TMP/install.sh" "${ARGS[@]+"${ARGS[@]}"}"
fi
