# CR-1: tray-install

_Requesting agent/task: CEO, task `tray`. Date: 2026-11-19._
_Status: APPROVED_

## Frozen surface affected
- `install.sh`
- `uninstall.sh`
- `packaging/vpnconnect.desktop`

## Why (cite the requirement)
FR-TRAY-07, FR-TRAY-08 in `company/specs/spec-tray.md` (owner asked for a permanent top-bar icon).

## Exact proposed change
- `install.sh`: add `gir1.2-ayatanaappindicator3-0.1` to the apt list, and
  `libayatana-appindicator-gtk3 gnome-shell-extension-appindicator` to the dnf list; install
  `packaging/vpnconnect-tray.desktop` to `/etc/xdg/autostart/vpnconnect-tray.desktop` (0644).
  The `/opt/vpnconnect`, `/usr/local/bin/vpnconnect` and `/etc/vpnconnect` layout is unchanged.
- `uninstall.sh`: also remove `/etc/xdg/autostart/vpnconnect-tray.desktop`.
- `packaging/vpnconnect.desktop`: `Exec=vpnconnect gui` -> `Exec=vpnconnect tray --open`.

## Blast radius
Installer only; existing machines get the icon after IT re-runs `sudo ./install.sh` (idempotent).
The config file and settings schema are untouched. The gates re-run lint (shellcheck) and tests.

## Owner sign-off needed?
No: there is no money, prod schema or invariant change. The owner asked for exactly this.

## Workaround if rejected
Users start `vpnconnect tray` by hand; there is no autostart and no menu integration.

---
_CEO decision and remarks:_ APPROVED 2026-11-19. Directly requested by the owner; additive; the layout is preserved.

## Amendment 1 (2026-11-19, from the tray audit, finding 10)
- `install.sh`: install the indicator packages in a separate, non-fatal step, so a distro without them still gets the app.
- `install.sh`: the wrapper uses `python3 -I` instead of `-P`, because `-P` needs Python 3.11 and broke Ubuntu 22.04 and Debian 11. `-I` also keeps the current directory off `sys.path`.

_CEO decision:_ APPROVED. Same blast radius as above.
