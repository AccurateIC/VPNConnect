# SPEC: Remember my password (opt-in)

_Type: feature. Author: CEO. Date: 2026-11-19._
_Status: SPEC-READY._

## Part 1 - Product requirements

### Problem
See owner's idea, verbatim: "add feature to opt to save username and password so u dont have to do
it everytime".

The username is already remembered (stored in the NetworkManager connection). This spec adds an
opt-in saved password. **It changes a stated invariant** ("the password is never saved"). The
owner asked for it explicitly; the new invariant is BR-SAVE-01.

### Goal and success metrics
An employee who opted in connects with one click (window or top-bar icon) and never types the
password again until it changes.

### User stories and acceptance criteria
US-SAVE-1: As an employee, I can choose to remember my password.
  - AC: Sign in shows an unticked "Remember my password on this computer" box (when allowed and a
    keyring is available). Tick it and connect successfully, and the password is in the keyring. Connect unsuccessfully, and nothing is saved.
US-SAVE-2: Next time I just press Connect.
  - AC: with a saved password, Sign in shows "Signed in as <user>" and "Password: saved on this
    computer", focus is on Connect (or on the code field when OTP is on), and Enter connects.
US-SAVE-3: I can connect from the top-bar icon.
  - AC: with a saved password and OTP off, the icon menu has "Connect", which connects without opening the window.
US-SAVE-4: A saved password that stopped working cleans itself up.
  - AC: an auth failure while using the saved password deletes it and shows "Your saved password
    didn't work, so it was removed. Type your current password." with the password field back.
US-SAVE-5: I can forget it.
  - AC: "Forget" next to the saved line, "More > Forget saved password", and "Remove VPN file"
    all delete it.

### Functional requirements
- FR-SAVE-01: New module `vpnconnect/keyring_store.py`: `available()`, `lookup(conn, user)`,
  `store(conn, user, password)`, `forget(conn)`; libsecret (Secret Service / GNOME Keyring),
  schema `com.accurateic.vpnconnect.Password`, attributes `connection`, `username`.
- FR-SAVE-02: Checkbox on Sign in (US-SAVE-1), default off, hidden when not allowed or no keyring.
- FR-SAVE-03: Saved-password Sign in layout (US-SAVE-2), with "Change user" (forgets and shows the fields again).
- FR-SAVE-04: Store only after a successful connect; with OTP on, store only the password part.
- FR-SAVE-05: Auth failure while using the saved password -> forget + message (US-SAVE-4). Other
  failures keep it.
- FR-SAVE-06: Forget paths (US-SAVE-5).
- FR-SAVE-07: Tray "Connect" item (US-SAVE-3), visible only when not connected, a password is
  saved, OTP is off and saving is allowed. Failure -> open the window, which shows the error.
- FR-SAVE-08: IT setting `allow_save_password` (default `true`). When `false`: no checkbox, saved
  passwords are not used and are deleted at the next start.
- FR-SAVE-09: CLI `vpnconnect connect` uses the saved password when present (`--ask` forces the
  prompt); `vpnconnect forget-password`.
- FR-SAVE-10: Auth detection also reads nmcli's own failure text ("login failed", "authentication
  failed"), not just the journal (helps WORRIES #7).

### Business rules
- BR-SAVE-01 (new invariant, replaces "never saved"): a password is stored **only** in the user's
  keyring through libsecret, and only after the user opted in. Never in a file, argv, log, the Details panel, or a
  widget. The saved password is never inserted into the password Entry; it is fetched inside the
  worker thread that calls `nm.connect`. It still reaches NetworkManager only via stdin.
- BR-SAVE-02: Keyring calls run off the Tk/GTK main loop. A keyring error is never fatal; it means
  "no saved password".
- BR-SAVE-03: Everything stays per user: another account on the same machine cannot read it (the
  keyring is per user and unlocked by that user's login).

### Scope
**In:** keyring_store.py, gui.py, tray.py, cli.py, ui_model.py (FR-SAVE-10), nm.py untouched,
settings.py + conf example (via CR-2), README, CLAUDE.md invariant text, tests.
**Out:** saving OTP codes, sharing one saved password between users, a password manager UI,
NetworkManager-owned secrets (password-flags stay 2), KDE KWallet-specific code (libsecret covers it
where a Secret Service exists).

## Part 2 - Build readiness
- **Owned paths:** as in Scope. Execution: self.
- **Invariants in play:** password storage (BR-SAVE-01 replaces the old rule, owner-requested), threading.
- **Frozen surfaces touched:** `vpnconnect/settings.py`, `packaging/vpnconnect.conf.example` -> CR-2.
- **Data / contracts:** additive setting `allow_save_password`; new CLI flag and command; keyring schema.
- **Open questions and chosen fallbacks:**
  - OQ-SAVE-01: Default for `allow_save_password`. FALLBACK: `true` (the owner asked for the
    feature); IT can turn it off. `// OQ-SAVE-01 assumption`
- **Verification plan:** unit tests with a fake keyring (store only on success, OTP split, auth
  failure forgets, policy off deletes, never in the Details log or widgets, tray Connect visibility and
  call), CLI tests, a real libsecret store/lookup/forget round trip against this session's keyring
  under a test connection name, gates, auditor.

## Spec-ready checklist
- [x] Every FR has a stable ID and at least one acceptance criterion
- [x] Out-of-scope is explicit
- [x] Every open question has a single decided fallback
- [x] Owned directories are named and disjoint from other in-flight work
- [x] Frozen-surface needs are identified and CRs filed (CR-2)
- [x] Data/contract impact stated
- [x] Verification plan covers every FR

## Part 3 - Handoff
Brief: `company/briefs/brief-save-password.md`.
