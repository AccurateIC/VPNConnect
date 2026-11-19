# SPEC: Easy GUI for every employee

_Type: feature. Author: CEO. Date: 2026-11-19._
_Status: SHIPPED (pending owner commit). AC wording below reconciled with the build on 2026-11-19, see DECISIONS.md._

## Part 1 - Product requirements

### Problem
See owner's idea, verbatim: "make gui better and make it like an internal tool
for all employees make it as easy as possible".

Audit facts that make it hard today (`vpnconnect/gui.py`, `vpnconnect/cli.py`):
- Launched from the app menu (`Terminal=false`) with a missing requirement, the
  app prints to stderr and exits: the employee sees **nothing happen**.
- One dense form for every state: fields, Import, Get profile, Connect,
  Disconnect and a raw log are all visible at once, even before a profile exists.
- Errors arrive as raw nmcli/OpenVPN text in a log box.
- Username is not pre-filled from the saved profile; no way to see the typed
  password; no Caps Lock hint.
- Closing the window disconnects on the Tk main thread (can freeze up to 30 s).

### Goal and success metrics
A non-technical employee goes from "app opened" to "connected" without reading
docs, and always knows the current state at a glance.
- Every screen shows exactly one primary action.
- No raw nmcli/OpenVPN text is shown unless the user opens "Details".
- Launching from the menu with a missing requirement shows a window that says what to do.

### Users and personas
- **Employee** (non-admin, often non-technical, Ubuntu/Debian/Fedora desktop). Uses the GUI only.
- **IT** sets `/etc/vpnconnect/vpnconnect.conf` and may pre-install a shared profile; reads "Details" when helping.

### User stories and acceptance criteria
US-GUI-1: As an employee with no profile, I am guided to set one up in one click.
  - AC: given no profile, when the app opens, then the Setup screen shows a single
    primary button "Choose VPN file...", plus "Download from VPN portal" only if `portal_url` is set.
  - AC: given `.ovpn` files in `~/Downloads`, then the newest one is offered as a one-click
    "Use <filename>" option, which then becomes the primary button and "Choose VPN file..."
    becomes the secondary "Choose a different file...".
US-GUI-2: As an employee with a profile, I sign in with username pre-filled and the cursor in the right field.
  - AC: given a profile with a saved username, when the Sign-in screen opens, then the username is
    pre-filled and focus is in the password field; Enter connects.
US-GUI-3: As an employee, I always know whether I am connected.
  - AC: a coloured status banner shows grey Not connected / Not set up yet, amber Connecting...,
    green Connected, red Not connected or Can't check the VPN (with the message below). The Connected
    screen shows the connected time and, with a session limit, the time left.
US-GUI-4: As an employee, when something fails I get a plain-language message and a next step.
  - AC: given auth failure, then the message reads "Wrong username, password or code" and the
    password field is cleared and focused; raw text is available under "Details". With `otp` off the
    headline is "Wrong username or password.".
US-GUI-5: As an employee launching from the menu without the OpenVPN plugin, I see what to do.
  - AC: given `check_requirements()` returns problems and a display is available, when the GUI is
    requested, then a window lists the problems and says "Ask IT to run install.sh".

### Functional requirements
- FR-GUI-01: Three screens chosen from status: **Setup** (no profile), **Sign in** (profile,
  not connected / connecting), **Connected**. Exactly one primary button per screen.
- FR-GUI-02: Setup screen: "Choose VPN file..." (file picker, `.ovpn` filter), quick-pick of the newest
  `.ovpn` in `~/Downloads` (if any, by mtime), and "Download from VPN portal" when `portal_url` is set.
  Automatic import of `/etc/vpnconnect/profile.ovpn` still happens first (existing behaviour).
- FR-GUI-03: Sign-in screen: username (pre-filled from the profile), password with a Show toggle,
  OTP field only when `otp` is on, Caps Lock warning, Connect primary button, Enter submits.
  While connecting, inputs are disabled and the button reads "Connecting...".
- FR-GUI-04: Connected screen: large green status, user, connected-for timer (updated each second),
  "Disconnects in N min" when `session_limit_minutes` > 0, Disconnect primary button.
- FR-GUI-05: Status banner colour + text on every screen (grey/amber/green/red).
- FR-GUI-06: Friendly error mapping (auth failed, plugin missing, timeout, NetworkManager missing,
  file unreadable, generic). Raw detail goes to a collapsible "Details" log with "Copy for IT".
- FR-GUI-07: Secondary actions live in a small "More" menu: Change VPN file, Remove profile
  (with confirmation), Open VPN portal (if set), About (version).
- FR-GUI-08: When the GUI is requested and requirements are missing, show a GUI error window
  instead of only printing to stderr (cli.py). CLI behaviour (exit code 2, stderr text) unchanged.
- FR-GUI-09: Closing the window while connected (with `disconnect_on_exit`) disconnects off the
  main thread, shows "Disconnecting...", then closes; closes anyway after a 15 s cap.
- FR-GUI-10: When the session limit disconnects the user, the Sign-in screen says so.

### Business rules and validations
- BR-GUI-01: The password is never logged, written to disk, put in the Details log, or kept after
  a connect attempt (field cleared on every attempt). The Show toggle only changes the mask.
- BR-GUI-02: All NetworkManager calls run in worker threads; widgets are touched only on the Tk
  main loop (results through `App.events`).
- BR-GUI-03: The pure logic (screen choice, error mapping, Downloads scan, duration format) lives in
  a Tk-free module so it is unit-tested without a display.

### Scope
**In:** `vpnconnect/gui.py` rewrite, new Tk-free `vpnconnect/ui_model.py`, the GUI-requirements
path in `vpnconnect/cli.py`, tests, README "For employees" section refresh.
**Out:** system tray / indicator, desktop notifications, autostart, saving passwords or a keyring,
multiple profiles, changing the config schema or `settings.py`, the `.desktop` file, the installer,
GTK/Qt port (stay on Tkinter: zero new dependencies), translations.

### UX notes
Language: `company/design/DESIGN-LANGUAGE.md` (tokens, components, focus rules).
Names in CAPS below are its tokens; component names are its section 5. No sketch:
the ASCII layouts below are the design.

**Frame for every main-window screen**
- Window title: `<connection_name> - VPNConnect`. Width 440, height fits content,
  `minsize(380, requested height)`. Content padding 24. clam theme, palette fixed.
- Top to bottom: Header row, Status banner, (Message box if any), screen body,
  Details panel. Only the body and the banner change between screens; the window
  never rebuilds from scratch (no flicker, the Details log survives).
- Narrow width (380): every button and entry is full content width already, so
  nothing reflows except wrapped text; labels re-wrap via `<Configure>`.
- Startup (loading): grey banner "Checking...", body is one muted line "One moment...".
  No buttons. Replaced by Setup or Sign in when the first status arrives.

**Status banner text (FR-GUI-05, US-GUI-3).** The banner shows the real VPN state.

| State | Colour | Line 1 | Line 2 |
|---|---|---|---|
| starting | STATUS_GREY | Checking... | - |
| no profile / disconnected | STATUS_GREY | Not connected | - |
| importing a file | STATUS_AMBER | Setting up... | - |
| connecting | STATUS_AMBER | Connecting... | This can take up to a minute. |
| connected | STATUS_GREEN | Connected (FONT_BANNER_BIG) | For 0:12:05 (H:MM:SS, every second); with a limit: For 0:12:05 - disconnects in 47 min |
| last attempt failed, not connected | STATUS_RED | Problem | - |
| disconnecting | STATUS_AMBER | Disconnecting... | - |

Time left: minutes rounded up; under one minute: "disconnects in less than 1 min".
If a Disconnect fails while still connected, the banner stays green and the error
goes in the Message box.

**Screen 1: Setup (no VPN file; FR-GUI-02, US-GUI-1)**
Purpose: get a VPN file into the app. Primary: Choose VPN file...
```
+--------------------------------------------+
| Company VPN                         More v |  header
| [o Not connected                         ] |  grey banner
|                                            |
| Set up the VPN                             |  FONT_TITLE
| You need the VPN file (.ovpn) from IT.     |  TEXT
| You only do this once.                     |  TEXT_MUTED
|                                            |
| [          Choose VPN file...            ] |  primary
|                                            |
| Found in your Downloads folder:            |  TEXT_MUTED   } only if a
| [        Use vpn-jdoe.ovpn               ] |  secondary    } .ovpn exists
|                                            |
| [      Download from VPN portal          ] |  secondary, only if portal_url
|                                            |
| Show details                               |  link button
+--------------------------------------------+
```
- Choose VPN file... opens `filedialog.askopenfilename` titled "Choose your VPN file",
  filters `VPN file (*.ovpn)` then `All files (*)`, starting in the Downloads folder.
- Quick pick label is `Use <filename>` (file name only, no path; truncate the middle
  with "..." past 40 characters).
- Download from VPN portal opens the browser and shows an info Message box:
  headline "Your browser opened the VPN portal." next step "Download the VPN file,
  then come back here." When the window gets focus again, rescan Downloads so the
  quick pick appears.
- Importing: banner "Setting up...", all buttons disabled, primary reads "Setting up...".
  Success -> Sign in screen with info Message box: "VPN file added." / "Sign in to connect."
  Failure -> stay on Setup, red banner, Message box with the "file unreadable" copy.
- Focus: the primary button. Enter: activates the focused button (primary by default).
- Empty Downloads: the "Found in..." label and quick pick are not shown at all.

**Screen 2: Sign in (profile, not connected; FR-GUI-03, US-GUI-2)**
Purpose: connect. Primary: Connect.
```
+--------------------------------------------+
| Company VPN                         More v |
| [o Not connected                         ] |
| +----------------------------------------+ |  Message box, only when
| | headline                               | |  there is a note or error
| | next step                              | |
| +----------------------------------------+ |
| Sign in                                    |  FONT_TITLE
| Username                                   |
| [jdoe                                    ] |
| Password                                   |
| [**********                              ] |
| [ ] Show password                          |
| Caps Lock is on.                           |  WARN_TEXT, only when on
| One-time code                              |  } only if otp = on
| [                                        ] |  }
| From your authenticator app.               |  } TEXT_MUTED
|                                            |
| [               Connect                  ] |  primary
|                                            |
| Show details                               |
+--------------------------------------------+
```
- Password masked with the bullet character (U+2022). "Show password" toggles `show`
  between bullet and "" only (BR-GUI-01).
- Caps Lock: check `event.state & 0x2` on KeyPress/KeyRelease and FocusIn of the
  password and code fields; show "Caps Lock is on." under Show password; hide it otherwise.
- Focus on open: password if the username is pre-filled, else username.
- Enter in any field = Connect. Escape: collapses Details only.
- Validation on Connect, inline under the field in ERROR_TEXT, focus moves to the
  first empty field, no request is sent:
  - username empty: "Type your username."
  - password empty: "Type your password."
  - code empty (otp on): "Type the code from your app."
  Messages clear when the user types in that field.
- Notes shown in the info Message box (NOTE_BG):
  - after the session limit (FR-GUI-10): "You were disconnected after <N> min." /
    "This is the company time limit. Sign in again to reconnect."
  - connection dropped without the user asking: "The VPN connection dropped." /
    "Sign in again to reconnect."
  - after a user Disconnect: no note.

**State 2b: Connecting (FR-GUI-03)**
Same layout as Sign in. Banner amber "Connecting..." + "This can take up to a minute."
Username, password, code, Show password, primary and the More menu's Change/Remove
items are disabled. Primary reads "Connecting...". Password and code fields are
cleared the moment Connect is accepted (BR-GUI-01). Focus stays on the window;
Enter does nothing.

**State 2c: Problem (FR-GUI-06, US-GUI-4)**
Same layout as Sign in (or Setup, for file errors). Red banner "Problem". Error
Message box (ERROR_BG) right under the banner: headline in FONT_BODY_BOLD ERROR_TEXT,
next step in TEXT. Raw text goes only to the Details log; Details does not auto-open.
Auth failure: password (and code) cleared, focus in password. Other errors: focus on
Connect. The box stays until the next Connect click or a screen change.

| Category | Headline | Next step |
|---|---|---|
| auth failed | Wrong username, password or code | Check them and try again. Passwords are case-sensitive. |
| plugin missing | The VPN add-on is missing | Ask IT to run install.sh on this computer. |
| timeout | The VPN server did not answer | Check that you are online, then try again. |
| NetworkManager missing | Network Manager is missing | Ask IT to run install.sh on this computer. |
| file unreadable | This VPN file can't be used | Choose the VPN file IT sent you, or download it again. |
| generic | Something went wrong | Try again. If it happens again, click Show details, then Copy for IT. |

Suggested matching for `ui_model` (first match wins, case-insensitive, on the
VPNError text): "AUTH_FAILED" or "Authentication failed" -> auth; "OpenVPN plugin" or
"libnm Python bindings" -> plugin; "nmcli) is not installed" or "NetworkManager is not
installed" -> NetworkManager; "Timed out" or "timeout" -> timeout; "File not found" or
"Could not read" or "refused the profile" -> file; else generic.

**Screen 3: Connected (FR-GUI-04)**
Purpose: show it is working; let the user stop it. Primary: Disconnect.
```
+--------------------------------------------+
| Company VPN                         More v |
| +----------------------------------------+ |
| | (o) Connected                          | |  green banner, FONT_BANNER_BIG,
| |     For 0:12:05 - disconnects in 47 min| |  padding 16 x 16
| +----------------------------------------+ |
|                                            |
| Signed in as jdoe                          |  TEXT
| You can now use company websites and apps. |  TEXT_MUTED
| Closing this window also disconnects.      |  TEXT_MUTED, only if disconnect_on_exit
|                                            |
| [              Disconnect                ] |  primary
|                                            |
| Show details                               |
+--------------------------------------------+
```
- Focus moves to Disconnect. Do NOT bind Enter on this screen (an extra Enter after
  Connect must not disconnect); Space on the focused button works.
- Disconnecting: banner amber "Disconnecting...", primary disabled and reads
  "Disconnecting...". Then Sign in, no note, focus in password.

**Closing the window (FR-GUI-09)**
- Not connected, or `disconnect_on_exit` off: close at once.
- Connected and `disconnect_on_exit` on: banner amber "Disconnecting...", body
  replaced by one line "Closing VPNConnect. This takes a few seconds.", all buttons
  and the More menu disabled. Disconnect runs in a worker; the window closes on
  success, on error, or after 15 s, whichever is first. A second close click during
  this is ignored.

**More menu (FR-GUI-07)** - ttk.Menubutton "More" in the header, tk.Menu items in order:
1. Change VPN file... (disabled on Setup and while busy). Same file picker as Setup.
   If connected, it disconnects first.
2. Open VPN portal (only if portal_url).
3. separator
4. Remove VPN file... (disabled on Setup and while busy). Confirm dialog: title
   "Remove VPN file?", message "You will need the VPN file again to sign in.",
   OK / Cancel, Cancel is default. On OK: disconnect if connected, delete, go to Setup.
5. separator
6. About VPNConnect. `messagebox.showinfo` title "About VPNConnect", message
   "VPNConnect <version>\nConnection: <connection_name>\nFor help, contact IT."

**Details panel (FR-GUI-06)**
- Collapsed by default on every launch, never auto-opens. Link button text
  "Show details" / "Hide details". Opening grows the window by the panel height.
- Open: read-only tk.Text, FONT_MONO, BG_SUBTLE, 8 lines, wrap word, scrollbar,
  newest line kept in view; lines are "HH:MM:SS  message"; keep the last 200 lines.
  Under it a secondary button "Copy for IT", right-aligned, auto width.
- Copy for IT puts on the clipboard: "VPNConnect <version>", "Connection: <name>",
  "State: <state>", "Time: <local ISO time>", a blank line, then the log. The button
  reads "Copied" for 2 s. The password never enters the log (BR-GUI-01).
- Tab order: Show details -> log -> Copy for IT. Escape collapses it and returns
  focus to the Show details link.

**Requirements-missing window (FR-GUI-08, US-GUI-5)** - its own small Tk window
(same theme), no header, More menu or Details panel.
```
+--------------------------------------------+
| [! Problem                               ] |  red banner
|                                            |
| VPNConnect can't start                     |  FONT_TITLE
| This computer is missing something the     |
| VPN needs:                                 |
|  - <problem line 1 from check_requirements>|  TEXT_MUTED, one per line
|  - <problem line 2>                        |
|                                            |
| Ask IT to run install.sh.                  |  FONT_BODY_BOLD
|                                            |
| [ Copy for IT ]            [    Close    ] |  secondary left, primary right
+--------------------------------------------+
```
- Window title "VPNConnect can't start". Width 440, not resizable below 380.
- Focus on Close. Enter and Escape both close. Exit code stays 2 and the stderr
  text is still printed (FR-GUI-08).
- Copy for IT copies the version, the problem lines and
  "Ask IT to run install.sh, or: sudo apt install network-manager-openvpn-gnome".

**Proposed FR changes**
- Add to FR-GUI-02: while the Setup screen is shown, rescan Downloads when the
  window regains focus. AC: a new `.ovpn` saved to Downloads while the app is open
  appears as "Use <filename>" after the window is focused again.
- Add to FR-GUI-03: inline validation, no messagebox. AC: Connect with an empty
  password shows "Type your password." under the field, sends no request, and
  focuses the password field.
- Add to FR-GUI-01: on the Connected screen Enter does not disconnect. AC: pressing
  Return on the Connected screen leaves the connection up.
- Add to FR-GUI-10: an unexpected drop shows "The VPN connection dropped." on Sign in.
  AC: status changes connected -> disconnected without a user Disconnect, and the
  note is shown.
- Add a styling FR: every text/background pair in the palette is >= 4.5:1 and focus
  is visible on every focusable widget. AC: a unit test computes contrast for the
  token pairs in `ui_model`/gui constants; a screenshot shows focus on each widget type.
- Candidate (CEO call, not designed here): a "Cancel" on Connecting. Today the user
  waits up to about 70 s with no way out.
- Copy note: the auth AC says "or code" even when otp is off. Proposed: drop
  ", or code" -> "Wrong username or password" when otp is off.

## Part 2 - Build readiness

- **Owned paths:** `vpnconnect/gui.py`, `vpnconnect/ui_model.py` (new), `vpnconnect/cli.py`
  (FR-GUI-08 only), `tests/`, `README.md`. Execution: self (single lane).
- **Invariants in play:** password never on disk or argv, and never logged (BR-GUI-01); GUI threading rule (BR-GUI-02).
- **Frozen surfaces touched:** none. `settings.py`, the conf example, `.desktop` and the installer are untouched.
- **Data model impact:** none.
- **Contracts impact:** none. The CLI commands and exit codes are unchanged; `nm.py` API unchanged.
- **Open questions and chosen fallbacks:**
  - OQ-GUI-01: Keep "closing the window disconnects"? FALLBACK: yes (existing `disconnect_on_exit`
    default), and the Connected screen states it. `// OQ-GUI-01 assumption`
  - OQ-GUI-02: Where to look for downloaded profiles? FALLBACK: `~/Downloads` (XDG download dir
    if `xdg-user-dir DOWNLOAD` resolves), non-recursive, newest by mtime. `// OQ-GUI-02 assumption`
- **Verification plan:** unit tests for `ui_model` (screen choice FR-GUI-01, error mapping
  FR-GUI-06, Downloads scan FR-GUI-02, duration/countdown FR-GUI-04) and the cli GUI-requirements
  path (FR-GUI-08); test that the Details log never receives the password (BR-GUI-01); screenshots of the
  Setup / Sign-in / Connecting / Connected / error states rendered on the live display with `nm`
  stubbed; gates green; auditor pass.

## Spec-ready checklist

- [x] Every FR has a stable ID and at least one acceptance criterion
- [x] Out-of-scope is explicit
- [x] Every open question has a single decided fallback
- [x] Owned directories are named and disjoint from other in-flight work
- [x] Frozen-surface needs are identified and CRs filed (none needed)
- [x] Data/contract impact stated (none)
- [x] Verification plan covers every FR

## Part 3 - Handoff
Brief: `company/briefs/brief-easy-gui.md`.
