# VPNConnect

Internal VPN client for employees on Linux (Ubuntu / Debian / Fedora).
A small app (GUI + command line) for connecting to the company Sophos / OpenVPN gateway.

- **No admin rights needed** to connect. The app uses NetworkManager instead of running `openvpn` with `sudo`.
- **Passwords are never saved to disk.** You type your password each time, and it goes straight to NetworkManager.
- **Each profile belongs to one user.** On a shared machine, other people can't see or use your VPN profile.
- **Company DNS and routes work**, because NetworkManager applies them. The VPN also shows up in the normal GNOME network menu.
- **Optional OTP field and auto-disconnect timer**, both set by IT.

---

## For employees

### 1. Get your VPN profile

Download your personal `.ovpn` file from the company VPN portal. Ask IT for the address, or use the
**Get profile** button in the app if IT has set it up.

### 2. Connect

Open **VPNConnect** from the applications menu:

1. Click **Import .ovpn …** and choose the file you downloaded (you only do this once).
2. Enter your username and password, plus your OTP code if asked.
3. Click **Connect**.

Closing the window disconnects the VPN.

### Command line

```bash
vpnconnect import ~/Downloads/myname.ovpn   # once
vpnconnect connect                          # asks for password
vpnconnect status                           # exit code 0 when connected
vpnconnect disconnect
vpnconnect remove                           # delete your profile
```

### Troubleshooting

| Problem | Fix |
|---|---|
| "Authentication failed" | Check your username and password. If OTP is enabled, use a fresh code. |
| "OpenVPN plugin is missing" | Ask IT to run `install.sh` on your machine. |
| Connected, but internal sites don't open | Run `vpnconnect disconnect`, then `connect` again. If that doesn't help, send IT the output of `journalctl -t nm-openvpn -n 50`. |
| Got a new profile from the portal | Import it again. It replaces the old one. |

---

## For IT: installing on a machine

```bash
git clone https://github.com/AccurateIC/VPNConnect.git
cd VPNConnect
sudo ./install.sh
```

This installs the dependencies (`network-manager-openvpn-gnome`, `python3-tk`, `python3-gi`, `gir1.2-nm-1.0`),
copies the app to `/opt/vpnconnect`, adds the `vpnconnect` command and a menu entry, and creates
`/etc/vpnconnect/vpnconnect.conf`.

If everyone shares the same profile, IT can pre-install it. Each user gets it imported automatically the first time they run the app:

```bash
sudo ./install.sh --profile /path/to/company.ovpn   # stored as /etc/vpnconnect/profile.ovpn
```

To uninstall, run `sudo ./uninstall.sh`.

### Settings: `/etc/vpnconnect/vpnconnect.conf`

```ini
[vpnconnect]
connection_name = Company VPN     # name in the app and the network menu
portal_url =                      # VPN portal link, shown as the "Get profile" button
session_limit_minutes = 0         # auto-disconnect after N minutes (0 = never)
otp = false                       # show an OTP field; the code is added after the password
disconnect_on_exit = true
```

Users can override any of these in `~/.config/vpnconnect/vpnconnect.conf`.

> Keep the real portal URL, gateway address and `.ovpn` files **out of this repository**.
> `.gitignore` already blocks `*.ovpn`, keys and credential files.

---

## Development

```bash
python3 -m vpnconnect --help         # run from the checkout, no install needed
python3 -m unittest tests.test_vpnconnect
```

Layout:

```
vpnconnect/
  nm.py        NetworkManager integration (libnm import, nmcli connect/disconnect/status)
  gui.py       Tkinter UI (network calls run in worker threads)
  cli.py       command line entry point
  settings.py  /etc + ~/.config settings
packaging/     .desktop launcher, example config
install.sh     system-wide installer
```
