# CR-2: allow-save-password

_Requesting agent/task: CEO, task `save-password`. Date: 2026-11-19._
_Status: APPROVED_

## Frozen surface affected
- `vpnconnect/settings.py`
- `packaging/vpnconnect.conf.example`

## Why (cite the requirement)
FR-SAVE-08 in `company/specs/spec-save-password.md`.

## Exact proposed change
- `settings.py`: add `allow_save_password: bool = True` to `Settings`; in `_apply`, parse
  `allow_save_password` with `_str2bool` like `otp`. No other key or precedence changes.
- `vpnconnect.conf.example`: add a commented `allow_save_password = true` entry with one line of explanation.

## Blast radius
Additive: existing config files without the key keep working (the default applies). Readers are gui.py, tray.py and cli.py.
The gates re-run tests.

## Owner sign-off needed?
Yes: it touches a security invariant. The owner requested the feature directly (2026-11-19).

## Workaround if rejected
The feature ships without an IT off switch.

---
_CEO decision and remarks:_ APPROVED 2026-11-19. Additive, and gives IT control over an owner-requested invariant change.

## Amendment 1 (2026-11-19, from the save-password audit, finding 5)
`allow_save_password` is the one key a later file can only lower: `true` in
`~/.config` cannot override `false` in `/etc`. Otherwise IT's "forbid" could be undone by any
employee. The precedence of all other keys is unchanged.

_CEO decision:_ APPROVED.
