# SPEC: Top-bar VPN icon, installed for good

_Type: feature. Author: CEO. Date: 2026-11-19._
_Status: SPEC-READY._

## Part 1 - Product requirements

### Problem
See owner's idea, verbatim: "can i make it as a purmanet install in linux where it is a option next
to the wifi and sound battery where i can directly install and there is a icon that id there when
clicke this screen pops up".

### Goal and success metrics
After `sudo ./install.sh`, every employee who logs in has a VPN icon in the top bar. The icon shows
the VPN state at a glance, and from the icon the VPNConnect window opens.

Platform fact (sets expectations, not negotiable in Tk/GTK): GNOME shows app icons in the top bar
through the AppIndicator extension. Ubuntu enables it by default. Clicking such an icon opens a
small menu, whose first item is "Open VPNConnect". A direct click-to-window is not available
there; middle-click opens the window directly.

### Users and personas
- **Employee:** sees the icon after login, never configures anything.
- **IT:** runs the installer once per machine.

### User stories and acceptance criteria
US-TRAY-1: As an employee, after logging in I see a VPN icon in the top bar.
  - AC: given install.sh ran, when a user logs in, then `vpnconnect tray` starts (XDG autostart)
    and an indicator icon appears.
US-TRAY-2: As an employee, I can tell from the icon whether I am connected.
  - AC: connected -> `network-vpn-symbolic`; connecting -> `network-vpn-acquiring-symbolic`;
    otherwise -> `network-vpn-disconnected-symbolic`. Updated within 3 s of a change.
US-TRAY-3: As an employee, clicking the icon then "Open VPNConnect" shows the VPNConnect window.
  - AC: if the window is already open it is raised, not opened twice.
US-TRAY-4: As an employee, closing the window does not kill my VPN; the icon keeps it.
  - AC: window opened from the tray, connected, close it -> still connected, icon still shows connected.

### Functional requirements
- FR-TRAY-01: `vpnconnect tray` runs a status-notifier icon via `AyatanaAppIndicator3` (fallback
  `AppIndicator3`), GTK 3 menu. One instance per user session (lock in `$XDG_RUNTIME_DIR`).
- FR-TRAY-02: Icon per US-TRAY-2. Status is polled every 3 s in a worker thread; results are
  applied on the GLib main loop.
- FR-TRAY-03: Menu: status line (not clickable: "Connected as <user>" / "Connecting..." /
  "Not connected" / "Not set up yet"), "Open VPNConnect", "Disconnect" (only while connected or
  connecting), separator, "Quit VPNConnect". Middle-click = Open.
- FR-TRAY-04: Open: start the window as a child process (`gui --from-tray`); if the child is alive,
  signal it (SIGUSR1) to raise itself instead.
- FR-TRAY-05: Window started `--from-tray`: closing it never disconnects; the Connected screen says
  "You can close this window. The VPN stays on until you disconnect from the top-bar icon."
- FR-TRAY-06: Quit: if `disconnect_on_exit` and connected/connecting -> disconnect first; close the
  window child; exit.
- FR-TRAY-07: `vpnconnect tray --open` (the app-menu launcher): if a tray is running, tell it to
  open the window (SIGUSR1 to the tray pid); else start the tray and open the window. If no
  indicator library is available, fall back to the plain window (today's behaviour).
- FR-TRAY-08: Installer installs the indicator bindings (apt: `gir1.2-ayatanaappindicator3-0.1`;
  dnf: `libayatana-appindicator-gtk3`, `gnome-shell-extension-appindicator`), installs
  `/etc/xdg/autostart/vpnconnect-tray.desktop`, and switches the menu launcher to `vpnconnect tray --open`.
  Uninstall removes the autostart file.
- FR-TRAY-09: `vpnconnect tray` without the indicator library exits with code 2 and a one-line
  stderr reason (autostart stays silent to the user).

### Business rules and validations
- BR-TRAY-01: The tray never asks for or handles a password; Connect happens only in the window.
- BR-TRAY-02: No NetworkManager call on the GTK main loop (threads + `GLib.idle_add`).
- BR-TRAY-03: Pure logic (icon/menu text from status, lock/pid helpers) is Gtk-free and unit-tested.
- BR-TRAY-04: `disconnect_on_exit` now means "quitting VPNConnect" (tray Quit, or closing a window
  that was not started from the tray). Recorded in DECISIONS for owner veto.

### Scope
**In:** `vpnconnect/tray.py` (new), `vpnconnect/gui.py` (`--from-tray` close behaviour, SIGUSR1 raise),
`vpnconnect/cli.py` (`tray` command, `gui --from-tray`), tests, README, `packaging/vpnconnect-tray.desktop`
(new), and via CR-1: `install.sh`, `uninstall.sh`, `packaging/vpnconnect.desktop`.
**Out:** a GNOME Shell extension of our own, putting the window inside the system menu, desktop
notifications, enabling the AppIndicator extension on non-Ubuntu GNOME (documented for IT),
connect-from-menu without the window, changes to the settings schema.

### UX notes
Follows `company/design/DESIGN-LANGUAGE.md`; copy says "VPN", never "profile". Icons are the
standard symbolic theme icons so they match wifi/sound/battery in light and dark top bars.

## Part 2 - Build readiness
- **Owned paths:** `vpnconnect/tray.py`, `vpnconnect/gui.py`, `vpnconnect/cli.py`, `tests/`,
  `README.md`, `packaging/vpnconnect-tray.desktop`; via CR-1 `install.sh`, `uninstall.sh`,
  `packaging/vpnconnect.desktop`. Execution: self (single lane).
- **Invariants in play:** password handling (BR-TRAY-01), threading (BR-TRAY-02).
- **Frozen surfaces touched:** `install.sh`, `uninstall.sh`, `packaging/vpnconnect.desktop` -> CR-1.
- **Data model / contracts impact:** none. New CLI command `tray`; existing commands and exit codes unchanged.
- **Open questions and chosen fallbacks:**
  - OQ-TRAY-01: Close-window semantics with a tray. FALLBACK: BR-TRAY-04. `// OQ-TRAY-01 assumption`
  - OQ-TRAY-02: Non-Ubuntu GNOME without the extension enabled. FALLBACK: installer installs the
    package; README tells IT how to enable it; app still works from the menu. `// OQ-TRAY-02 assumption`
- **Verification plan:** unit tests for view/menu model, lock + pid helpers, `tray --open` fallback,
  `--from-tray` close (no disconnect), SIGUSR1 raise flag; shellcheck on installer; live run of
  `vpnconnect tray` on this Ubuntu 24.04 GNOME session once the indicator bindings are installed,
  with screenshots of the icon and its menu.

## Spec-ready checklist
- [x] Every FR has a stable ID and at least one acceptance criterion
- [x] Out-of-scope is explicit
- [x] Every open question has a single decided fallback
- [x] Owned directories are named and disjoint from other in-flight work
- [x] Frozen-surface needs are identified and CRs filed (CR-1)
- [x] Data/contract impact stated
- [x] Verification plan covers every FR

## Part 3 - Handoff
Brief: `company/briefs/brief-tray.md`.
