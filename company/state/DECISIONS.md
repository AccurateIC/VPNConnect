# DECISIONS - maintained by the company. Durable choices and their rationale.

## 2026-11-19 - easy-gui (CEO, owner can veto)
- Stayed on Tkinter (no new dependencies). Spec `company/specs/spec-easy-gui.md`, design `company/design/DESIGN-LANGUAGE.md` (proposed).
- Built from the CEO's spec while the designer was still working (the owner said not to wait). Copy follows the designer's main rules: "VPN file", never "profile"; errors in the window, not pop-ups; no Enter on Connected. Palette/fonts are close to the designer's but not identical (primary `#0969da` vs proposed `#0B5CAD`, both pass 4.5:1).
- Spec ACs were reconciled with the build where the build is clearer (quick-pick becomes primary; banner wording). The auditor's literal-AC list (finding 6) is accepted as reconciled, not as defects.
- Closing the window while connected **or still connecting** disconnects (OQ-GUI-01 kept; extended so a half-started connection is not left running).
- Taken from the designer's proposals: rescan Downloads on focus, inline validation, a "connection dropped" note, and the no-OTP auth copy. Deferred: a Cancel button while connecting, and a contrast unit test.
- The tests gate now runs `python3 -m unittest discover -s tests`. `tests/test_gui.py` needs a display and skips without one.

## 2026-11-19 - tray (CEO, owner can veto)
- BR-TRAY-04: `disconnect_on_exit` means "quitting VPNConnect". That is the icon's **Quit**, **logging out** (the session sends SIGTERM to the icon), or closing a window that was *not* opened from the icon. Closing a window opened from the icon keeps the VPN up; the icon owns the connection. Logout was added after the audit (finding 4), so that a shared machine is not left connected.
- With the icon libraries present but no top-bar host (AppIndicator extension off), the menu launcher falls back to the plain window, where closing disconnects. Autostart waits up to 20 s for the host, then exits quietly.
- The installer treats top-bar icon packages as optional, and the wrapper runs `python3 -I` so Python 3.10 works (CR-1 amendment 1).

## 2026-11-19 - save-password (owner-requested invariant change)
- The owner asked for an opt-in saved password. The invariant "the password is never saved" is replaced by BR-SAVE-01: opt-in, keyring only (libsecret), saved only after a successful connect, never with the OTP code, never in a widget or log.
- OQ-SAVE-01: `allow_save_password` defaults to **true**; IT can set it to false (saved passwords are then deleted). Owner can veto the default.
- The tray gets one-click Connect when a password is saved and OTP is off (this changes BR-TRAY-01: the tray still never *asks* for a password).
