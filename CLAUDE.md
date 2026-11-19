<!-- claude-company:begin -->
## claude-company

This project runs **claude-company**, a hierarchical SDLC system for Claude Code.

- Main sessions act as CEO: drive the project through `/company` and `COMPANY.md`.
- Subagents obey their brief plus `company/METHOD.md` - the brief is the contract.
- Gates are the definition of done and are hook-enforced. Red stays red until proven green.
- Run gates with `company/run-gates.sh`; configure them in `company/gates.config`.
- Frozen surfaces (`company/frozen-surfaces.json`) change only via a change request in `company/change-requests/`.
- Project state lives in `company/state/` (STATUS, RESUME, WORRIES, DECISIONS).

New to this project, or adopting an existing codebase? Run `/company-init`. Then `/company`.
<!-- claude-company:end -->

## Project conventions (from the /company-init audit, 2026-11-19)

- **Stack:** Python 3 stdlib only (tkinter, configparser, subprocess) plus system `python3-gi`/libnm. No pip deps, no pyproject. Do not add third-party packages; target distro Python on Ubuntu/Debian/Fedora.
- **Gates:** `tests` = `python3 -m unittest tests.test_vpnconnect`; `lint` = `compileall` + `shellcheck install.sh uninstall.sh`. No CI exists; gates are the only check.
- **Security invariants (non-negotiable, test-pinned in `tests/test_vpnconnect.py`, `tests/test_gui.py`, `tests/test_save_password.py`; the live keyring test runs with `VPNCONNECT_KEYRING_TEST=1`):**
  - The password never touches a file or argv: profiles are saved with `password-flags=2`, and the secret goes to `nmcli ... passwd-file /dev/stdin` via stdin.
  - Saving a password is opt-in and goes **only** to the user's keyring through `vpnconnect/keyring_store.py` (libsecret), only after a successful connect, never with the OTP code, and never into a widget, log or the Details panel; UI decisions use `has_saved()`, which never loads the secret; a code-bearing auth failure never deletes it (BR-SAVE-01; the owner changed this rule on 2026-11-19, and it was previously "never saved"). IT can disable it with `allow_save_password = false`.
  - Imported connections carry a `user:<login>` permission and `autoconnect=false`.
  - No sudo / running `openvpn` directly: everything goes through NetworkManager.
  - Never commit `.ovpn`, keys, portal URLs or gateway addresses.
- **Layering:** `nm.py` is the only module that shells out to `nmcli`/libnm and raises `VPNError`; `cli.py` and `gui.py` only call `nm` and `settings`. GUI: NetworkManager calls run in worker threads; widgets are touched only on the Tk main loop (results go through `App.events`).
- **CLI contract:** `vpnconnect status` exits 0 connected / 3 not connected / 1 no profile or error / 2 missing requirements / 130 on Ctrl-C. Scripts depend on this.
- **Tests mock `nm._run`** (and `nm.status`/`check_requirements` at CLI level); they must never hit a real NetworkManager.
- **Frozen:** settings schema, config example, install/uninstall layout, `.desktop`, `.gitignore`. See `company/frozen-surfaces.json`.
