# VPNConnect

The company VPN for Linux, made simple. After one install command you get a **VPN icon in the
top bar**, next to wifi, sound and battery. Click it, enter your password, and you are on the
company network.

Works on Ubuntu, Debian and Fedora (GNOME desktop).

- **No admin rights needed to connect.** Only the one-time install needs `sudo`.
- **Your password is never saved.** You type it each time; it goes straight to the system's network manager.
- **Your VPN setup is yours alone.** On a shared computer, other people can't see or use it.
- **Company sites and DNS just work**, and the VPN also shows up in the normal system network menu.

---

## 1. Install (once per computer)

Open a terminal (`Ctrl` + `Alt` + `T`), paste this line, press Enter and type your computer password:

```bash
curl -fsSL https://raw.githubusercontent.com/AccurateIC/VPNConnect/main/get.sh | sudo bash
```

That's it. Then open **VPNConnect** from your applications menu (or log out and back in) and the
VPN icon appears in the top bar. From now on it starts by itself every time you log in.

> No `curl`? Run `sudo apt install curl` first (Fedora: `sudo dnf install curl`).

<details>
<summary>Install from a downloaded copy instead</summary>

```bash
git clone https://github.com/AccurateIC/VPNConnect.git
cd VPNConnect
sudo ./install.sh
```
</details>

## 2. Get your VPN file (once)

You need a personal VPN file. Its name ends in **`.ovpn`** (for example `jsmith.ovpn`).

1. Open the **company VPN portal** in your browser. IT gives you the address, and if IT has set it
   up, the **Download it from the VPN portal** button in VPNConnect opens it for you.
2. Sign in with your normal company username and password.
3. Go to the **VPN** section and download the configuration for **other operating systems / Linux**
   (the `.ovpn` file).
   Do not pick the Windows installer or the Android/iOS file.
4. Leave it in your **Downloads** folder. VPNConnect finds it there by itself.

Can't find the portal or the file? Ask IT. Your `.ovpn` file is personal: don't share it or email it around.

## 3. Connect

1. Click the **VPN icon** in the top bar, then **Open VPNConnect**.
   (Middle-click on the icon opens it directly. You can also use the applications menu.)
2. **First time only:** click **Use jsmith.ovpn** (the file it found in Downloads), or
   **Choose VPN file...** if you saved it somewhere else.
3. Type your password (your username is remembered), plus the code from your authenticator app
   if you are asked for one.
4. Press **Enter** or click **Connect**.

The coloured bar at the top of the window tells you where you are:

| Colour | Means |
|---|---|
| Grey | Not connected |
| Amber | Connecting (can take up to a minute) |
| Green | Connected, with how long you have been on |
| Red | Something needs your attention; the message below says what to do |

The top-bar icon shows the same thing: a VPN box with a line through it means off, a plain VPN box means connected.

## 4. Disconnect

- Click the VPN icon in the top bar and choose **Disconnect**, or
- click **Disconnect** in the window.

You can close the window while connected: the VPN stays on and the icon keeps showing it.
**Quit VPNConnect** in the icon's menu closes everything (and disconnects, if IT set it up that way).
If IT set a time limit, you are disconnected automatically after that time.

## Troubleshooting

| Problem | What to do |
|---|---|
| "Wrong username or password" | Check them and try again. If you use a code, wait for a new one. |
| "Something went wrong" | Try again. Still failing? In the window click **Show details**, then **Copy for IT**, and paste it into a message to IT. |
| No VPN icon in the top bar | Open **VPNConnect** from the applications menu (this starts the icon). On Fedora or Debian, IT may need to turn on top-bar icons, see below. |
| "VPNConnect can't start" window | Something is missing on this computer. Run the install command again, or ask IT. |
| Connected, but internal sites don't open | Disconnect and connect again. If that doesn't help, use **Copy for IT**. |
| Got a new VPN file from the portal | Window: **More** > **Change VPN file...** and pick the new file. It replaces the old one. |
| Want to remove your VPN setup | Window: **More** > **Remove VPN file from this computer...** |

## Command line (optional)

Everything also works from a terminal:

```bash
vpnconnect import ~/Downloads/jsmith.ovpn   # once
vpnconnect connect                           # asks for your password
vpnconnect status                            # exit code 0 when connected, 3 when not
vpnconnect disconnect
vpnconnect remove                            # delete your VPN setup
vpnconnect tray                              # the top-bar icon (starts by itself at login)
```

---

## For IT

### Install, update, uninstall

| Task | Command |
|---|---|
| Install or update | `curl -fsSL https://raw.githubusercontent.com/AccurateIC/VPNConnect/main/get.sh \| sudo bash` |
| Install with a shared VPN file for everyone | `curl -fsSL https://raw.githubusercontent.com/AccurateIC/VPNConnect/main/get.sh \| sudo bash -s -- --profile /path/to/company.ovpn` |
| Uninstall | `curl -fsSL https://raw.githubusercontent.com/AccurateIC/VPNConnect/main/get.sh \| sudo bash -s -- --uninstall` |
| Install a specific branch or tag | `curl -fsSL https://raw.githubusercontent.com/AccurateIC/VPNConnect/<ref>/get.sh \| sudo VPNCONNECT_REF=<ref> bash` |

Running the install again updates the app and keeps your settings. From a clone, `sudo ./install.sh`
and `sudo ./uninstall.sh` do the same.

The installer:
- installs the dependencies: `network-manager-openvpn-gnome`, `python3-tk`, `python3-gi`,
  `gir1.2-nm-1.0`, `gir1.2-ayatanaappindicator3-0.1` (Fedora: the matching `dnf` packages plus
  `gnome-shell-extension-appindicator`);
- copies the app to `/opt/vpnconnect` and adds the `vpnconnect` command;
- adds **VPNConnect** to the applications menu;
- starts the top-bar icon for every user at login (`/etc/xdg/autostart/vpnconnect-tray.desktop`);
- creates `/etc/vpnconnect/vpnconnect.conf` (an existing one is kept).

With `--profile`, the shared file is stored as `/etc/vpnconnect/profile.ovpn` and each user gets it
imported automatically the first time they open VPNConnect.

Uninstalling leaves `/etc/vpnconnect` and users' VPN connections in place; users can remove theirs
with `vpnconnect remove`.

### Top-bar icon on Fedora / Debian

GNOME shows app icons in the top bar through the AppIndicator extension. **Ubuntu has it on by
default.** On Fedora or Debian GNOME the installer adds the extension; each user turns it on once with:

```bash
gnome-extensions enable appindicatorsupport@rgcjonas.gmail.com
```

Without it, VPNConnect still works from the applications menu.

### Settings: `/etc/vpnconnect/vpnconnect.conf`

```ini
[vpnconnect]
connection_name = Company VPN     # name in the app and the system network menu
portal_url =                      # VPN portal address: shows the "Download it from the VPN portal" button
session_limit_minutes = 0         # disconnect automatically after N minutes (0 = never)
otp = false                       # ask for an authenticator code; it is added after the password
disconnect_on_exit = true         # quitting VPNConnect disconnects the VPN
```

Users can override any of these in `~/.config/vpnconnect/vpnconnect.conf`.

> This repository is **public**. Keep the real portal address, gateway address and any `.ovpn`
> files **out of it**. `.gitignore` already blocks `*.ovpn`, keys and credential files. Set the
> portal address only in `/etc/vpnconnect/vpnconnect.conf` on the machines.

### How it works

- VPNConnect uses **NetworkManager** and its OpenVPN plugin. It never runs `openvpn` with `sudo`,
  so employees don't need admin rights, and DNS from the VPN is applied correctly.
- The `.ovpn` file is imported as a NetworkManager connection that belongs only to that user,
  set to **always ask** for the password. The password is passed to NetworkManager directly and
  is never written to disk or shown in logs.
- The top-bar icon (`vpnconnect tray`) watches the connection state every few seconds and opens
  the window on request.

---

## Development

```bash
python3 -m vpnconnect --help              # run from the checkout, no install needed
python3 -m vpnconnect tray --open         # icon + window from the checkout
python3 -m unittest discover -s tests     # tests (GUI tests need a display, else they skip)
```

Layout:

```
vpnconnect/
  nm.py        NetworkManager integration (libnm import, nmcli connect/disconnect/status)
  gui.py       window: Setup / Sign in / Connected screens (network calls run in worker threads)
  ui_model.py  window logic without Tk: screen choice, friendly errors, Downloads scan
  tray.py      top-bar icon (AppIndicator + GTK 3); runs the window as a child process
  cli.py       command line entry point
  settings.py  /etc + ~/.config settings
packaging/     app menu entry, login autostart for the icon, example config
get.sh         one-line installer (downloads from GitHub, runs install.sh)
install.sh     system-wide installer
uninstall.sh   remover
tests/         unit tests
```
