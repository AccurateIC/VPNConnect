# RESUME - maintained by the company. Where we are and what happens next.

## 2026-11-19 - adopted via /company-init (branch `rebuild-internal-tool`)

- Codebase: VPNConnect, ~700 LOC Python (nm.py, cli.py, gui.py, settings.py) + install.sh. Rebuilt as an internal tool in 7c1d35f.
- Gates (`company/gates.config`, hand-wired; `gates_detect.py` finds no stack because there is no pyproject): `tests` (9 unittest cases) and `lint` (compileall + shellcheck). Both GREEN on a fresh run, 2026-11-19.
- Frozen surfaces registered: settings.py, conf example, install.sh, uninstall.sh, .desktop, .gitignore.
- Conventions recorded in CLAUDE.md.
- No CI, no remote checks. Nothing in flight.

## 2026-11-19 - easy-gui delivered (uncommitted, awaiting owner)
- Rewrote the GUI as Setup / Sign in / Connected screens with a status banner, friendly errors, a Details panel with "Copy for IT", and a More menu. Added the Tk-free `ui_model.py` and a requirements window for menu launches (cli.py).
- Gates green: 31 tests (incl. 8 live-Tk GUI tests). The auditor said SHIP-WITH-FIXES; findings 1-5, 7, 8 and 9 are fixed and test-pinned, and 6 is reconciled in the spec (DECISIONS).
- Screenshots: scratchpad only (not durable).

## 2026-11-19 - tray + one-line install (branch `vpn-icon-easy-install`)
- Top-bar icon (`vpnconnect tray`, AppIndicator): autostarts at login, the menu opens the window, and closing the window keeps the VPN up (BR-TRAY-04). The installer, uninstaller and menu launcher changed under CR-1 (APPROVED).
- `get.sh` is the one-line installer (curl | sudo bash) and downloads `main` by default. Until this branch merges, use `VPNCONNECT_REF=vpn-icon-easy-install`.
- README fully rewritten for employees + IT.
- Verified live on the owner's Ubuntu 24.04: the icon is registered and visible (company/evidence/tray). Gates green, 46 tests.
- The tray audit returned HALT (two startup signal races, a stale-status Quit, a queue put inside a signal handler, logout policy, no icon host, installer). All fixed in a follow-up commit, with regression tests (53 tests). The auditor's own race scripts now pass: 3/3 tray runs survive, and a double Open leaves one window. Live menu evidence: the owner clicked through the icon menu on 2026-11-19 ("it works").

- 2026-11-19: the owner ran the github.com-archive install of the branch on their Ubuntu 24.04 machine. It installed, and the icon works (live end-to-end). The office/home network blocks raw.githubusercontent.com, so the README leads with the archive command.
- Open: PR #2 (includes #1). After the merge, close #1 and re-test the `main` archive command on a second machine.

## 2026-11-19 - save-password (opt-in "Remember my password", keyring only)
- Owner-requested invariant change (BR-SAVE-01). CR-2 adds the setting `allow_save_password`, and amendment 1 stops users re-enabling it.
- Audit: SHIP-WITH-FIXES. All findings are fixed with tests: a wrong OTP no longer deletes the saved password; the poll uses has_saved (no secret load, no unlock prompts); the journal is scoped to the current attempt; a failed tray connect opens the window with the reason; the IT off switch is enforceable; Quit during a one-click connect disconnects; another user's item is cleaned up.
- 89 tests; the live keyring round trip passes with VPNCONNECT_KEYRING_TEST=1 (not part of the gate, because it touches the user keyring).

## Next
- `/company` is open. Candidate work, cheapest first: add tests for import_profile and `_ensure_profile` (WORRIES #2), and add a CI workflow that runs the two gates.

## Spawn facts
- Test: `python3 -m unittest tests.test_vpnconnect` · Lint: `python3 -m compileall -q vpnconnect tests && shellcheck install.sh uninstall.sh`
- Run from the checkout: `python3 -m vpnconnect --help`. The real VPN needs NetworkManager-openvpn and a `.ovpn` file, and neither is in the repo.
