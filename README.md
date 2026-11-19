# VPNConnect

The company VPN for Linux, made simple. After one install command you get a **VPN icon in the
top bar**, next to wifi, sound and battery. Click it, enter your password, and you are on the
company network.

Works on Ubuntu, Debian and Fedora (GNOME desktop).

- **No admin rights needed to connect.** Only the one-time install needs `sudo`.
- **Remember your password if you want to.** Tick **Remember my password on this computer** once and
  next time it's one click. It is kept only in your own encrypted keyring (the same place your wifi
  passwords live), never in a file. Don't tick it and you type it each time.
- **Your VPN setup is yours alone.** On a shared computer, other people can't see or use it.
- **Company sites and DNS just work**, and the VPN also shows up in the normal system network menu.

---

## 1. Install (once per computer)

Open a terminal (`Ctrl` + `Alt` + `T`), paste this line, press Enter and type your computer password:

```bash
curl -fsSL https://github.com/AccurateIC/VPNConnect/archive/main.tar.gz | tar -xz -C /tmp && sudo /tmp/VPNConnect-main/install.sh
```

That's it. Then open **VPNConnect** from your applications menu (or log out and back in) and the
VPN icon appears in the top bar. From now on it starts by itself every time you log in.

> No `curl`? Run `sudo apt install curl` first (Fedora: `sudo dnf install curl`).

<details>
<summary>Other ways to install</summary>

Shorter command (needs `raw.githubusercontent.com`, which some office networks block; if you see
`Connection reset by peer`, use the command above):

```bash
curl -fsSL https://raw.githubusercontent.com/AccurateIC/VPNConnect/main/get.sh | sudo bash
```

From a downloaded copy:

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
4. Optional: tick **Remember my password on this computer**, so next time you just click **Connect**
   (or choose **Connect** straight from the top-bar icon). The password is saved only after it worked.
5. Press **Enter** or click **Connect**.

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
| Install says `Connection reset by peer` | Your network blocks `raw.githubusercontent.com`. Use the install command at the top of this page; it only needs `github.com`. |
| "VPNConnect can't start" window | Something is missing on this computer. Run the install command again, or ask IT. |
| Connected, but internal sites don't open | Disconnect and connect again. If that doesn't help, use **Copy for IT**. |
| Got a new VPN file from the portal | Window: **More** > **Change VPN file...** and pick the new file. It replaces the old one. |
| Changed your password | Just connect: the old saved password is removed automatically when it stops working. Then type the new one (and tick **Remember** again if you like). |
| Want to stop saving your password | Window: **Forget** next to "Password: saved", or **More** > **Forget saved password**. |
| Want to remove your VPN setup | Window: **More** > **Remove VPN file from this computer...** (also forgets a saved password) |

## Command line (optional)

Everything also works from a terminal:

```bash
vpnconnect import ~/Downloads/jsmith.ovpn   # once
vpnconnect connect                           # asks for your password
vpnconnect status                            # exit code 0 when connected, 3 when not
vpnconnect disconnect
vpnconnect connect --ask                     # type the password even if one is saved
vpnconnect forget-password                   # delete your saved password
vpnconnect remove                            # delete your VPN setup (and saved password)
vpnconnect tray                              # the top-bar icon (starts by itself at login)
```

---

## For IT

### Install, update, uninstall

| Task | Command |
|---|---|
First download the app (works on networks that block `raw.githubusercontent.com`):

```bash
curl -fsSL https://github.com/AccurateIC/VPNConnect/archive/main.tar.gz | tar -xz -C /tmp
```

| Task | Command |
|---|---|
| Install or update | `sudo /tmp/VPNConnect-main/install.sh` |
| Install with a shared VPN file for everyone | `sudo /tmp/VPNConnect-main/install.sh --profile /path/to/company.ovpn` |
| Uninstall | `sudo /tmp/VPNConnect-main/uninstall.sh` |
| Install a specific branch or tag | download `archive/<ref>.tar.gz` instead; the folder is `/tmp/VPNConnect-<ref>` |

If your network allows `raw.githubusercontent.com`, the `get.sh` one-liner does the download for you:
`curl -fsSL https://raw.githubusercontent.com/AccurateIC/VPNConnect/main/get.sh | sudo bash`
(add `-s -- --profile <file>` or `-s -- --uninstall` after `bash`).

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
allow_save_password = true        # allow "Remember my password" (false = forbid; saved ones are deleted)
```

Users can override any of these in `~/.config/vpnconnect/vpnconnect.conf`, except that they cannot
turn `allow_save_password` back on once IT has set it to `false`.

> This repository is **public**. Keep the real portal address, gateway address and any `.ovpn`
> files **out of it**. `.gitignore` already blocks `*.ovpn`, keys and credential files. Set the
> portal address only in `/etc/vpnconnect/vpnconnect.conf` on the machines.

### How it works

- VPNConnect uses **NetworkManager** and its OpenVPN plugin. It never runs `openvpn` with `sudo`,
  so employees don't need admin rights, and DNS from the VPN is applied correctly.
- The `.ovpn` file is imported as a NetworkManager connection that belongs only to that user,
  set to **always ask** for the password. The password is passed to NetworkManager directly and
  is never written to a file or shown in logs.
- **Remember my password** is opt-in per user. The password is stored only in that user's keyring
  (Secret Service / GNOME Keyring, encrypted and unlocked by their login), only after a successful
  connection, and never together with an authenticator code. Other users on the same computer cannot
  read it. IT can forbid it with `allow_save_password = false`.
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
